import os
import sys
import datetime
import secrets
import logging
import hashlib
import socket
import urllib.request
import json
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, Depends, HTTPException, status, Header, Request, UploadFile, File, Form
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text, event, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session, relationship
from jose import JWTError, jwt
import uvicorn

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("filament_server")

# ----------------- 0. 路径定位与运行时环境 -----------------
BASE_DIR = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, 'frozen', False) else __file__))
DB_FILE_PATH = os.path.join(BASE_DIR, "filament_db.db")

# ----------------- 1. 数据库配置 (本地 SQLite) -----------------
DB_SECRET_KEY = os.getenv("DB_SECRET_KEY", "") 
DATABASE_URL = f"sqlite:///{DB_FILE_PATH}"

engine = create_engine(
    DATABASE_URL, 
    connect_args={"check_same_thread": False},
    pool_pre_ping=True
)

if DB_SECRET_KEY:
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute(f"PRAGMA key = '{DB_SECRET_KEY}'")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

SECRET_KEY = os.getenv("JWT_SECRET", "bambu-filament-local-jwt-secret-key-3.1.0")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 120
REFRESH_TOKEN_EXPIRE_DAYS = 7

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# ----------------- 2. ORM 模型定义 -----------------
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    api_keys = relationship("APIKey", back_populates="owner")
    filaments = relationship("Filament", back_populates="owner")
    records = relationship("UsageRecord", back_populates="owner")
    printers = relationship("Printer", back_populates="owner")

class APIKey(Base):
    __tablename__ = "api_keys"
    id = Column(Integer, primary_key=True, index=True)
    key_name = Column(String(50), nullable=False)
    api_key = Column(String(64), unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    owner = relationship("User", back_populates="api_keys")

class Printer(Base):
    __tablename__ = "printers"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False)
    model = Column(String(50), default="Bambu P1S")
    ip_address = Column(String(50), nullable=True)
    ams_slots_json = Column(Text, default="{}")
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    owner = relationship("User", back_populates="printers")

class Filament(Base):
    __tablename__ = "filaments"
    id = Column(Integer, primary_key=True, index=True)
    brand = Column(String(50), default="Bambu Lab")
    material = Column(String(50), nullable=False)
    color_name = Column(String(50), nullable=False)
    color_hex = Column(String(10), default="#000000")
    nfc_uid = Column(String(64), index=True, nullable=True)
    initial_weight_g = Column(Float, default=1000.0)
    current_weight_g = Column(Float, default=1000.0)
    spool_weight_g = Column(Float, default=250.0)
    pending_weight_g = Column(Float, nullable=True)
    price = Column(Float, default=0.0)
    purchase_url = Column(Text, nullable=True)
    remarks = Column(Text, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    owner = relationship("User", back_populates="filaments")

class UsageRecord(Base):
    __tablename__ = "usage_records"
    id = Column(Integer, primary_key=True, index=True)
    filament_id = Column(Integer, ForeignKey("filaments.id"), nullable=False)
    printer_id = Column(Integer, nullable=True)
    used_weight_g = Column(Float, nullable=False)
    remaining_weight_g = Column(Float, nullable=True)
    source = Column(String(50), default="script")
    task_name = Column(String(255), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    owner = relationship("User", back_populates="records")

class CorrectionLog(Base):
    __tablename__ = "correction_logs"
    id = Column(Integer, primary_key=True, index=True)
    nfc_uid = Column(String(64), index=True, nullable=True)
    filament_id = Column(Integer, ForeignKey("filaments.id"), nullable=True)
    action_type = Column(String(30), nullable=False)
    theory_weight_g = Column(Float, nullable=True)
    actual_weight_g = Column(Float, nullable=False)
    variance_g = Column(Float, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class DeviceStatus(Base):
    __tablename__ = "device_status"
    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String(64), index=True, nullable=False)
    current_weight = Column(Float, default=0.0)
    wifi_rssi = Column(Integer, default=0)
    wifi_bars = Column(Integer, default=0)
    current_page = Column(String(30), default="weighing")
    battery = Column(Integer, nullable=True)
    ip_address = Column(String(50), nullable=True)
    firmware_version = Column(String(20), nullable=True)
    last_heartbeat = Column(DateTime, default=datetime.datetime.utcnow)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

class DeviceCommand(Base):
    __tablename__ = "device_commands"
    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String(64), index=True, nullable=False)
    command = Column(String(30), nullable=False)
    params_json = Column(Text, default="{}")
    status = Column(String(20), default="pending")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    executed_at = Column(DateTime, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

class ScalePending(Base):
    __tablename__ = "scale_pending"
    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String(64), index=True, nullable=False)
    nfc_uid = Column(String(64), index=True, nullable=False)
    measured_weight_g = Column(Float, nullable=False)
    expected_weight_g = Column(Float, nullable=True)
    difference_g = Column(Float, nullable=True)
    filament_id = Column(Integer, ForeignKey("filaments.id"), nullable=True)
    status = Column(String(20), default="pending")
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)

# 自动建立表结构与迁移
Base.metadata.create_all(bind=engine)
for sql in [
    "ALTER TABLE filaments ADD COLUMN purchase_url TEXT DEFAULT NULL;",
    "ALTER TABLE filaments ADD COLUMN pending_weight_g FLOAT DEFAULT NULL;",
    "ALTER TABLE usage_records ADD COLUMN remaining_weight_g FLOAT DEFAULT NULL;",
    "ALTER TABLE usage_records ADD COLUMN printer_id INT DEFAULT NULL;",
    "ALTER TABLE printers ADD COLUMN ams_slots_json TEXT DEFAULT NULL;",
    "ALTER TABLE printers ADD COLUMN model VARCHAR(50) DEFAULT 'Bambu P1S';",
    "ALTER TABLE printers ADD COLUMN ip_address VARCHAR(50) DEFAULT NULL;"
]:
    try:
        with engine.connect() as conn:
            conn.execute(text(sql))
            conn.commit()
    except Exception:
        pass

# ----------------- 3. FastAPI 初始化与静态资源托管 -----------------
app = FastAPI(
    title="拓竹耗材与打印机管理系统 - Windows 服务端", 
    version="3.1.0",
    docs_url="/api/docs",
    redoc_url=None
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_frontend_dir():
    if hasattr(sys, '_MEIPASS'):
        p = os.path.join(sys._MEIPASS, "frontend")
        if os.path.exists(p): return p
    possible_paths = [
        os.path.join(BASE_DIR, "frontend"),
        os.path.join(os.path.dirname(BASE_DIR), "frontend"),
        "./frontend"
    ]
    for p in possible_paths:
        if os.path.exists(p) and os.path.isdir(p):
            return p
    return None

FRONTEND_DIR = get_frontend_dir()
if FRONTEND_DIR:
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

@app.get("/", include_in_schema=False)
def read_index():
    if FRONTEND_DIR:
        idx_path = os.path.join(FRONTEND_DIR, "index.html")
        if os.path.exists(idx_path):
            return FileResponse(idx_path)
    return {"status": "success", "message": "拓竹耗材管理服务端 (Windows SQLite v3.1.0) 运行正常"}

@app.get("/robots.txt", include_in_schema=False)
def robots():
    return PlainTextResponse("User-agent: *\nDisallow: /")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ----------------- 4. Pydantic 数据结构 (全面兼容 Pydantic V2) -----------------
class UserCreate(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class APIKeyCreate(BaseModel):
    key_name: str

class APIKeyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    key_name: str
    api_key: str
    created_at: datetime.datetime

class PrinterCreate(BaseModel):
    name: str
    model: Optional[str] = "Bambu P1S"
    ip_address: Optional[str] = None

class PrinterAmsUpdate(BaseModel):
    ams_slots: Dict[str, Any]

class FilamentCreate(BaseModel):
    brand: str = "Bambu Lab"
    material: str
    color_name: str
    color_hex: str = "#000000"
    nfc_uid: Optional[str] = None
    initial_weight_g: float = 1000.0
    current_weight_g: float = 1000.0
    spool_weight_g: float = 250.0
    price: float = 0.0
    purchase_url: Optional[str] = None
    remarks: Optional[str] = None

class FilamentUrlUpdate(BaseModel):
    purchase_url: str

class FilamentApplySameUrl(BaseModel):
    brand: str
    material: str
    purchase_url: str

class ManualAdjustWeightData(BaseModel):
    adjust_weight_g: float
    reason: Optional[str] = "手动调整"

class FilamentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    brand: str
    material: str
    color_name: str
    color_hex: str
    nfc_uid: Optional[str]
    initial_weight_g: float
    current_weight_g: float
    price: float
    purchase_url: Optional[str] = None
    created_at: datetime.datetime

class UsageRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    task_name: Optional[str]
    used_weight_g: float
    remaining_weight_g: Optional[float]
    created_at: datetime.datetime

class ScriptReportData(BaseModel):
    filament_id: int
    used_weight_g: float
    printer_id: Optional[int] = None
    task_name: Optional[str] = None

class ScaleReportData(BaseModel):
    device_id: str
    nfc_uid: str
    weight_g: Optional[float] = None
    gross_weight: Optional[float] = None
    ip: Optional[str] = None

class ScaleOTACheckData(BaseModel):
    device_id: str
    version: str

class ScaleBindData(BaseModel):
    nfc_uid: str
    filament_id: Optional[int] = None
    brand: Optional[str] = "Bambu Lab"
    material: Optional[str] = "PLA"
    color_name: Optional[str] = "自定义"
    color_hex: Optional[str] = "#888888"
    initial_weight_g: Optional[float] = 1000.0
    mode: str = "spool"
    spool_weight_g: Optional[float] = 250.0
    total_weight_g: Optional[float] = None

class ScaleConfirmData(BaseModel):
    action_type: str = "normal_sync"

class ScaleCorrectData(BaseModel):
    uid: str
    action_type: str
    confirmed_weight: float

class OtaPushBody(BaseModel):
    download_url: str

class CommandData(BaseModel):
    device_id: str = "scale_001"
    command: str
    params: Optional[Dict[str, Any]] = None

class HeartbeatData(BaseModel):
    device_id: str
    current_weight: float = 0.0
    wifi_rssi: int = 0
    wifi_bars: int = 0
    current_page: str = "weighing"
    battery: Optional[int] = None
    ip_address: Optional[str] = None
    firmware_version: Optional[str] = None

# ----------------- 5. 安全加盐哈希鉴权 -----------------
def get_password_hash(password: str) -> str:
    salt = os.urandom(16).hex()
    pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000).hex()
    return f"{salt}${pwd_hash}"

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        salt, pwd_hash = hashed_password.split('$')
        check_hash = hashlib.pbkdf2_hmac('sha256', plain_password.encode('utf-8'), salt.encode('utf-8'), 100000).hex()
        return check_hash == pwd_hash
    except Exception:
        return False

def create_token(data: dict, expires_delta: datetime.timedelta) -> str:
    to_encode = data.copy()
    expire = datetime.datetime.utcnow() + expires_delta
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token 无效或已过期，请重新登录",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = db.query(User).filter(User.username == username).first()
    if user is None or not user.is_active:
        raise credentials_exception
    return user

def verify_script_api_key(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    db: Session = Depends(get_db)
) -> User:
    if not x_api_key:
        raise HTTPException(status_code=401, detail="缺少 API Key 鉴权标头")
    db_key = db.query(APIKey).filter(APIKey.api_key == x_api_key, APIKey.is_active == True).first()
    if not db_key:
        raise HTTPException(status_code=401, detail="API Key 无效或已禁用")
    return db_key.owner

# ----------------- 6. API 业务接口 (用户 & 打印机 & 耗材) -----------------
@app.post("/api/auth/register", tags=["账号管理"])
def register(user_data: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == user_data.username).first():
        raise HTTPException(status_code=400, detail="用户名已被注册")
    new_user = User(username=user_data.username, hashed_password=get_password_hash(user_data.password))
    db.add(new_user); db.commit()
    return {"status": "success", "message": "注册成功"}

@app.post("/api/auth/login", response_model=TokenResponse, tags=["账号管理"])
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="账号或密码错误")
    return {
        "access_token": create_token({"sub": user.username}, datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)),
        "refresh_token": create_token({"sub": user.username}, datetime.timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)),
        "token_type": "bearer"
    }

@app.post("/api/auth/quick-api-key", tags=["账号管理"])
def quick_get_api_key(user_data: UserCreate, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == user_data.username).first()
    if not user or not verify_password(user_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="账号或密码错误")
    existing_key = db.query(APIKey).filter(APIKey.user_id == user.id, APIKey.is_active == True).first()
    if existing_key:
        return {"status": "success", "username": user.username, "api_key": existing_key.api_key}
    raw_key = f"sk_{secrets.token_hex(16)}"
    new_key = APIKey(key_name="ClientAutoGenerated", api_key=raw_key, user_id=user.id)
    db.add(new_key); db.commit(); db.refresh(new_key)
    return {"status": "success", "username": user.username, "api_key": new_key.api_key}

@app.get("/api/ingest/script-user-info", tags=["自动采集接入"])
def get_script_user_info(user: User = Depends(verify_script_api_key)):
    return {"status": "success", "username": user.username, "user_id": user.id}

@app.get("/api/ingest/script-printers", tags=["打印机管理"])
def list_printers(user: User = Depends(verify_script_api_key), db: Session = Depends(get_db)):
    printers = db.query(Printer).filter(Printer.user_id == user.id).all()
    res = []
    for p in printers:
        try: slots = json.loads(p.ams_slots_json) if p.ams_slots_json else {}
        except Exception: slots = {}
        res.append({"id": p.id, "name": p.name, "model": p.model, "ip_address": p.ip_address, "ams_slots": slots})
    return res

@app.post("/api/ingest/script-printers", tags=["打印机管理"])
def create_printer(p: PrinterCreate, user: User = Depends(verify_script_api_key), db: Session = Depends(get_db)):
    printer = Printer(name=p.name, model=p.model, ip_address=p.ip_address, user_id=user.id)
    db.add(printer); db.commit(); db.refresh(printer)
    return {"status": "success", "id": printer.id, "name": printer.name}

@app.post("/api/ingest/script-printers/{printer_id}/ams", tags=["打印机管理"])
def update_printer_ams(printer_id: int, data: PrinterAmsUpdate, user: User = Depends(verify_script_api_key), db: Session = Depends(get_db)):
    printer = db.query(Printer).filter(Printer.id == printer_id, Printer.user_id == user.id).first()
    if not printer: raise HTTPException(status_code=404, detail="打印机不存在")
    printer.ams_slots_json = json.dumps(data.ams_slots)
    db.commit()
    return {"status": "success", "message": "AMS 槽位更新成功"}

@app.delete("/api/ingest/script-printers/{printer_id}", tags=["打印机管理"])
def delete_printer(printer_id: int, user: User = Depends(verify_script_api_key), db: Session = Depends(get_db)):
    printer = db.query(Printer).filter(Printer.id == printer_id, Printer.user_id == user.id).first()
    if not printer: raise HTTPException(status_code=404, detail="打印机不存在")
    db.delete(printer); db.commit()
    return {"status": "success", "message": "打印机已删除"}

@app.get("/api/ingest/script-analytics", tags=["数据洞察"])
def get_analytics_data(user: User = Depends(verify_script_api_key), db: Session = Depends(get_db)):
    records = db.query(UsageRecord).filter(UsageRecord.user_id == user.id, UsageRecord.used_weight_g > 0).all()
    filaments = db.query(Filament).filter(Filament.user_id == user.id).all()
    printers = db.query(Printer).filter(Printer.user_id == user.id).all()

    f_map = {f.id: f for f in filaments}
    p_map = {p.id: p.name for p in printers}

    total_consumed_g = sum(r.used_weight_g for r in records)
    total_cost = 0.0
    material_usage = {}
    printer_usage = {}

    for r in records:
        f = f_map.get(r.filament_id)
        if f:
            unit_price = f.price / (f.initial_weight_g if f.initial_weight_g > 0 else 1000.0)
            cost = r.used_weight_g * unit_price
            total_cost += cost
            material_usage[f.material] = material_usage.get(f.material, 0.0) + r.used_weight_g
        p_name = p_map.get(r.printer_id, "默认/未指定机位")
        if p_name not in printer_usage:
            printer_usage[p_name] = {"consumed_g": 0.0, "cost": 0.0}
        printer_usage[p_name]["consumed_g"] += r.used_weight_g
        if f:
            printer_usage[p_name]["cost"] += r.used_weight_g * (f.price / (f.initial_weight_g or 1000.0))

    printers_stat = [{"name": k, "consumed_g": v["consumed_g"], "cost": v["cost"]} for k, v in printer_usage.items()]
    materials_stat = [{"material": k, "consumed_g": v} for k, v in sorted(material_usage.items(), key=lambda x: x[1], reverse=True)]

    return {
        "status": "success",
        "total_consumed_g": total_consumed_g,
        "total_consumed_cost": total_cost,
        "task_count": len(records),
        "printers_stat": printers_stat,
        "materials_stat": materials_stat
    }

@app.post("/api/auth/api-keys", response_model=APIKeyResponse, tags=["账号管理"])
def create_script_api_key(key_data: APIKeyCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    raw_key = f"sk_{secrets.token_hex(16)}"
    new_api_key = APIKey(key_name=key_data.key_name, api_key=raw_key, user_id=current_user.id)
    db.add(new_api_key); db.commit(); db.refresh(new_api_key)
    return new_api_key

@app.post("/api/filaments", response_model=FilamentOut, tags=["耗材台账"])
def create_filament(f: FilamentCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    filament = Filament(**f.model_dump(), user_id=user.id)
    db.add(filament); db.commit(); db.refresh(filament)
    return filament

@app.get("/api/filaments", response_model=List[FilamentOut], tags=["耗材台账"])
def list_filaments(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(Filament).filter(Filament.user_id == user.id).all()

@app.get("/api/ingest/script-filaments", tags=["自动采集接入"])
def get_filaments_for_script(user: User = Depends(verify_script_api_key), db: Session = Depends(get_db)):
    filaments = db.query(Filament).filter(Filament.user_id == user.id).all()
    return [
        {
            "id": f.id, "brand": f.brand, "material": f.material, "color_name": f.color_name,
            "color_hex": f.color_hex, "initial_weight_g": f.initial_weight_g, "current_weight_g": f.current_weight_g,
            "price": f.price, "purchase_url": f.purchase_url
        }
        for f in filaments
    ]

@app.post("/api/ingest/script-report-create", response_model=FilamentOut, tags=["自动采集接入"])
def create_filament_for_script(f: FilamentCreate, user: User = Depends(verify_script_api_key), db: Session = Depends(get_db)):
    filament = Filament(**f.model_dump(), user_id=user.id)
    db.add(filament); db.commit(); db.refresh(filament)
    return filament

@app.post("/api/ingest/script-filaments-batch", tags=["自动采集接入"])
def create_filaments_batch(items: List[FilamentCreate], user: User = Depends(verify_script_api_key), db: Session = Depends(get_db)):
    created = []
    for item in items:
        f = Filament(**item.model_dump(), user_id=user.id)
        db.add(f); created.append(f)
    db.commit()
    return {"status": "success", "count": len(created)}

@app.post("/api/ingest/script-filaments/{filament_id}/url", tags=["自动采集接入"])
def update_filament_url(filament_id: int, data: FilamentUrlUpdate, user: User = Depends(verify_script_api_key), db: Session = Depends(get_db)):
    f = db.query(Filament).filter(Filament.id == filament_id, Filament.user_id == user.id).first()
    if not f: raise HTTPException(status_code=404, detail="耗材不存在")
    f.purchase_url = data.purchase_url; db.commit()
    return {"status": "success", "message": "购买链接已更新"}

@app.post("/api/ingest/script-filaments/apply-url", tags=["自动采集接入"])
def apply_url_to_same_type(data: FilamentApplySameUrl, user: User = Depends(verify_script_api_key), db: Session = Depends(get_db)):
    filaments = db.query(Filament).filter(
        Filament.user_id == user.id, Filament.brand == data.brand, Filament.material == data.material
    ).all()
    for f in filaments: f.purchase_url = data.purchase_url
    db.commit()
    return {"status": "success", "count": len(filaments)}

@app.post("/api/ingest/script-filaments/import-urls", tags=["自动采集接入"])
def import_urls_json(items: List[Dict[str, Any]], user: User = Depends(verify_script_api_key), db: Session = Depends(get_db)):
    for item in items:
        fid = item.get("id"); p_url = item.get("purchase_url")
        if fid and p_url:
            f = db.query(Filament).filter(Filament.id == fid, Filament.user_id == user.id).first()
            if f: f.purchase_url = p_url
    db.commit()
    return {"status": "success", "message": "JSON 链接批量导入成功"}

@app.delete("/api/ingest/script-report-delete/{filament_id}", tags=["自动采集接入"])
def delete_filament_for_script(filament_id: int, user: User = Depends(verify_script_api_key), db: Session = Depends(get_db)):
    filament = db.query(Filament).filter(Filament.id == filament_id, Filament.user_id == user.id).first()
    if not filament: raise HTTPException(status_code=404, detail="耗材不存在")
    db.query(UsageRecord).filter(UsageRecord.filament_id == filament_id).delete()
    db.delete(filament); db.commit()
    return {"status": "success", "message": "删除成功"}

@app.get("/api/ingest/script-filament-logs/{filament_id}", tags=["自动采集接入"])
def get_filament_logs_for_script(filament_id: int, user: User = Depends(verify_script_api_key), db: Session = Depends(get_db)):
    records = db.query(UsageRecord).filter(
        UsageRecord.filament_id == filament_id, UsageRecord.user_id == user.id
    ).order_by(UsageRecord.id.desc()).all()
    res = []
    for r in records:
        created_time = r.created_at + datetime.timedelta(hours=8) if r.created_at else None
        res.append({
            "id": r.id, "task_name": r.task_name, "used_weight_g": r.used_weight_g,
            "remaining_weight_g": r.remaining_weight_g,
            "created_at": created_time.strftime("%Y-%m-%d %H:%M:%S") if created_time else ""
        })
    return res

@app.delete("/api/ingest/script-undo-record/{record_id}", tags=["自动采集接入"])
def delete_record_for_script(record_id: int, user: User = Depends(verify_script_api_key), db: Session = Depends(get_db)):
    record = db.query(UsageRecord).filter(UsageRecord.id == record_id, UsageRecord.user_id == user.id).first()
    if not record: raise HTTPException(status_code=404, detail="记录不存在")
    filament = db.query(Filament).filter(Filament.id == record.filament_id, Filament.user_id == user.id).first()
    if filament:
        prev_record = db.query(UsageRecord).filter(
            UsageRecord.filament_id == filament.id, UsageRecord.user_id == user.id, UsageRecord.id < record.id
        ).order_by(UsageRecord.id.desc()).first()
        if prev_record and prev_record.remaining_weight_g is not None:
            filament.current_weight_g = max(0.0, round(prev_record.remaining_weight_g, 2))
        else:
            filament.current_weight_g = round(filament.initial_weight_g, 2)
    db.delete(record); db.commit()
    return {"status": "success", "message": "记录已撤销并恢复历史快照"}

@app.post("/api/filaments/{filament_id}/adjust-weight", tags=["耗材台账"])
def adjust_filament_weight(filament_id: int, data: ManualAdjustWeightData, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    filament = db.query(Filament).filter(Filament.id == filament_id, Filament.user_id == user.id).first()
    if not filament: raise HTTPException(status_code=404, detail="耗材不存在")
    filament.current_weight_g = max(0.0, round(filament.current_weight_g - data.adjust_weight_g, 2))
    action_str = "手动增加" if data.adjust_weight_g < 0 else "手动减少"
    task_desc = f"{action_str} ({data.reason})" if data.reason else action_str
    record = UsageRecord(filament_id=filament_id, used_weight_g=data.adjust_weight_g, remaining_weight_g=filament.current_weight_g, source="manual", task_name=task_desc, user_id=user.id)
    db.add(record); db.commit()
    return {"status": "success", "message": "调整成功", "current_weight_g": filament.current_weight_g}

@app.get("/api/filaments/{filament_id}/logs", response_model=List[UsageRecordOut], tags=["耗材台账"])
def get_filament_usage_logs(filament_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    records = db.query(UsageRecord).filter(UsageRecord.filament_id == filament_id, UsageRecord.user_id == user.id).order_by(UsageRecord.id.desc()).all()
    for r in records:
        if r.created_at: r.created_at = r.created_at + datetime.timedelta(hours=8)
    return records

@app.delete("/api/usage-records/{record_id}", tags=["耗材台账"])
def delete_usage_record(record_id: int, refund_weight_g: Optional[float] = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    record = db.query(UsageRecord).filter(UsageRecord.id == record_id, UsageRecord.user_id == user.id).first()
    if not record: raise HTTPException(status_code=404, detail="记录不存在")
    filament = db.query(Filament).filter(Filament.id == record.filament_id, Filament.user_id == user.id).first()
    if filament:
        if refund_weight_g is not None:
            filament.current_weight_g = max(0.0, round(filament.current_weight_g + refund_weight_g, 2))
        else:
            prev_record = db.query(UsageRecord).filter(
                UsageRecord.filament_id == filament.id, UsageRecord.user_id == user.id, UsageRecord.id < record.id
            ).order_by(UsageRecord.id.desc()).first()
            if prev_record and prev_record.remaining_weight_g is not None:
                filament.current_weight_g = max(0.0, round(prev_record.remaining_weight_g, 2))
            else:
                filament.current_weight_g = round(filament.initial_weight_g, 2)
    db.delete(record); db.commit()
    return {"status": "success", "message": "记录已删除"}

@app.post("/api/ingest/script-report", tags=["自动采集接入"])
def report_usage_from_script(data: ScriptReportData, user: User = Depends(verify_script_api_key), db: Session = Depends(get_db)):
    filament = db.query(Filament).filter(Filament.id == data.filament_id, Filament.user_id == user.id).first()
    if not filament: raise HTTPException(status_code=404, detail=f"找不到 ID={data.filament_id} 的耗材")
    filament.current_weight_g = max(0.0, round(filament.current_weight_g - data.used_weight_g, 2))
    record = UsageRecord(filament_id=data.filament_id, printer_id=data.printer_id, used_weight_g=data.used_weight_g, remaining_weight_g=filament.current_weight_g, source="script", task_name=data.task_name, user_id=user.id)
    db.add(record); db.commit()
    return {"status": "success", "message": "消耗上报成功", "filament_id": filament.id, "remaining_weight_g": filament.current_weight_g}

# ================== 7. 智能称重节点与 OTA 全功能支持 ==================
SCALE_TOLERANCE_G = 5.0
GITHUB_FIRMWARE_API = "https://api.github.com/repos/fabie250/-bambu-filament-manager/releases/latest"

@app.post("/api/scale/report", tags=["智能称重节点"])
def scale_report(data: ScaleReportData, user: User = Depends(verify_script_api_key), db: Session = Depends(get_db)):
    filament = db.query(Filament).filter(Filament.nfc_uid == data.nfc_uid, Filament.user_id == user.id).first()
    if data.gross_weight is not None:
        net_weight = round(data.gross_weight - filament.spool_weight_g, 2) if filament else round(data.gross_weight, 2)
    else:
        net_weight = round(data.weight_g if data.weight_g is not None else 0.0, 2)

    if not filament:
        pending = ScalePending(
            device_id=data.device_id, nfc_uid=data.nfc_uid, measured_weight_g=net_weight,
            expected_weight_g=None, difference_g=None, filament_id=None, status="pending", user_id=user.id
        )
        db.add(pending); db.commit()
        return {"action": "pending", "message": "NFC未绑定耗材，请在客户端确认", "pending_id": pending.id, "net_weight": net_weight}

    expected = filament.current_weight_g
    diff = round(net_weight - expected, 2)
    if abs(diff) <= SCALE_TOLERANCE_G:
        filament.current_weight_g = net_weight
        filament.pending_weight_g = None
        db.commit()
        return {"action": "success", "message": "数据已同步", "filament_id": filament.id, "current_weight_g": filament.current_weight_g, "net_weight": net_weight}
    else:
        filament.pending_weight_g = net_weight
        pending = ScalePending(
            device_id=data.device_id, nfc_uid=data.nfc_uid, measured_weight_g=net_weight,
            expected_weight_g=expected, difference_g=diff, filament_id=filament.id, status="pending", user_id=user.id
        )
        db.add(pending); db.commit()
        return {"action": "pending", "message": f"检测到误差{diff}g，请在客户端确认", "pending_id": pending.id, "difference_g": diff, "net_weight": net_weight, "expected_weight_g": expected}

@app.get("/api/scale/ota_check", tags=["智能称重节点"])
def scale_ota_check_get(user: User = Depends(verify_script_api_key)):
    try:
        req = urllib.request.Request(GITHUB_FIRMWARE_API, headers={"User-Agent": "BambuManager/3.1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode())
                latest_ver = data.get("tag_name", "1.0.0").replace("v", "")
                download_url = next((a.get("browser_download_url") for a in data.get("assets", []) if a.get("name", "").endswith(".bin")), "")
                return {"status": "success", "latest_version": latest_ver, "download_url": download_url}
    except Exception:
        pass
    return {"status": "error", "message": "无法获取 GitHub 最新固件"}

@app.post("/api/scale/ota_check", tags=["智能称重节点"])
def scale_ota_check_post(data: ScaleOTACheckData, user: User = Depends(verify_script_api_key)):
    return scale_ota_check_get(user=user)

@app.post("/api/scale/ota/push", tags=["智能称重节点"])
def push_ota_to_device(data: OtaPushBody, user: User = Depends(verify_script_api_key), db: Session = Depends(get_db)):
    if not data.download_url: raise HTTPException(status_code=400, detail="缺少固件下载地址")
    cmd = DeviceCommand(device_id="scale_001", command="ota", params_json=json.dumps({"url": data.download_url}), user_id=user.id)
    db.add(cmd); db.commit()
    return {"status": "success", "message": "OTA 更新指令已下发"}

@app.get("/api/scale/status", tags=["智能称重节点"])
def scale_status(user: User = Depends(verify_script_api_key), db: Session = Depends(get_db)):
    pending_list = db.query(ScalePending).filter(ScalePending.user_id == user.id, ScalePending.status == "pending").order_by(ScalePending.id.desc()).all()
    result = []
    for p in pending_list:
        filament = db.query(Filament).filter(Filament.id == p.filament_id).first() if p.filament_id else None
        result.append({
            "pending_id": p.id, "device_id": p.device_id, "nfc_uid": p.nfc_uid,
            "measured_weight_g": p.measured_weight_g, "expected_weight_g": p.expected_weight_g,
            "difference_g": p.difference_g, "filament_id": p.filament_id,
            "filament_name": f"{filament.brand} {filament.material} {filament.color_name}" if filament else "未绑定耗材",
            "color_hex": filament.color_hex if filament else "#888888",
            "spool_weight_g": filament.spool_weight_g if filament else 250.0,
            "created_at": (p.created_at + datetime.timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S") if p.created_at else ""
        })
    return {"count": len(result), "items": result}

@app.get("/api/scale/pending", tags=["智能称重节点"])
def list_scale_pending(user: User = Depends(verify_script_api_key), db: Session = Depends(get_db)):
    pending_list = db.query(ScalePending).filter(ScalePending.user_id == user.id, ScalePending.status == "pending").order_by(ScalePending.id.desc()).all()
    return [
        {
            "id": p.id, "device_id": p.device_id, "nfc_uid": p.nfc_uid, "measured_weight_g": p.measured_weight_g,
            "expected_weight_g": p.expected_weight_g, "difference_g": p.difference_g, "filament_id": p.filament_id,
            "status": p.status, "created_at": (p.created_at + datetime.timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S") if p.created_at else ""
        }
        for p in pending_list
    ]

@app.post("/api/scale/bind", tags=["智能称重节点"])
def scale_bind(data: ScaleBindData = None, user: User = Depends(verify_script_api_key), db: Session = Depends(get_db)):
    if not data or not data.nfc_uid.strip(): raise HTTPException(status_code=400, detail="NFC UID 不能为空")
    nfc_uid = data.nfc_uid.strip()
    spool_weight = round(data.total_weight_g - (data.initial_weight_g or 1000.0), 2) if (data.mode == "calibrate" and data.total_weight_g is not None) else (data.spool_weight_g or 250.0)
    current_weight = data.initial_weight_g or 1000.0

    if data.filament_id:
        filament = db.query(Filament).filter(Filament.id == data.filament_id, Filament.user_id == user.id).first()
        if not filament: raise HTTPException(status_code=404, detail="耗材不存在")
        filament.nfc_uid = nfc_uid; filament.spool_weight_g = spool_weight; action = "updated"
    else:
        filament = Filament(brand=data.brand or "Bambu Lab", material=data.material or "PLA", color_name=data.color_name or "自定义", color_hex=data.color_hex or "#888888", nfc_uid=nfc_uid, initial_weight_g=data.initial_weight_g or 1000.0, current_weight_g=current_weight, spool_weight_g=spool_weight, user_id=user.id)
        db.add(filament); action = "created"

    db.commit(); db.refresh(filament)
    return {"status": "success", "action": action, "message": f"NFC UID {nfc_uid} 已绑定到耗材", "filament": {"id": filament.id, "brand": filament.brand, "material": filament.material, "color_name": filament.color_name, "color_hex": filament.color_hex, "nfc_uid": filament.nfc_uid, "initial_weight_g": filament.initial_weight_g, "current_weight_g": filament.current_weight_g, "spool_weight_g": filament.spool_weight_g}}

@app.post("/api/scale/pending/{pending_id}/confirm", tags=["智能称重节点"])
def confirm_scale_pending(pending_id: int, data: Optional[ScaleConfirmData] = None, user: User = Depends(verify_script_api_key), db: Session = Depends(get_db)):
    pending = db.query(ScalePending).filter(ScalePending.id == pending_id, ScalePending.user_id == user.id).first()
    if not pending or pending.status != "pending": raise HTTPException(status_code=404, detail="记录不存在或已处理")
    actual_weight = pending.measured_weight_g
    theory_weight = pending.expected_weight_g
    if pending.filament_id:
        filament = db.query(Filament).filter(Filament.id == pending.filament_id).first()
        if filament:
            filament.current_weight_g = round(actual_weight, 2)
            filament.pending_weight_g = None
    log = CorrectionLog(nfc_uid=pending.nfc_uid, filament_id=pending.filament_id, action_type=data.action_type if data else "normal_sync", theory_weight_g=theory_weight, actual_weight_g=actual_weight, variance_g=round(actual_weight - theory_weight, 2) if theory_weight is not None else None, user_id=user.id)
    db.add(log); pending.status = "confirmed"; pending.resolved_at = datetime.datetime.utcnow(); db.commit()
    return {"status": "success", "message": "已确认，重量已更新"}

@app.post("/api/scale/pending/{pending_id}/reject", tags=["智能称重节点"])
def reject_scale_pending(pending_id: int, user: User = Depends(verify_script_api_key), db: Session = Depends(get_db)):
    pending = db.query(ScalePending).filter(ScalePending.id == pending_id, ScalePending.user_id == user.id).first()
    if not pending or pending.status != "pending": raise HTTPException(status_code=404, detail="记录不存在或已处理")
    pending.status = "rejected"; pending.resolved_at = datetime.datetime.utcnow(); db.commit()
    return {"status": "success", "message": "已拒绝"}

@app.post("/api/scale/correct", tags=["智能称重节点"])
def scale_correct(data: ScaleCorrectData, user: User = Depends(verify_script_api_key), db: Session = Depends(get_db)):
    filament = db.query(Filament).filter(Filament.nfc_uid == data.uid, Filament.user_id == user.id).first()
    if not filament: raise HTTPException(status_code=404, detail="找不到该NFC对应的耗材")
    actual_weight = round(data.confirmed_weight, 2)
    theory_weight = filament.current_weight_g
    filament.current_weight_g = actual_weight
    filament.pending_weight_g = None
    log = CorrectionLog(nfc_uid=data.uid, filament_id=filament.id, action_type=data.action_type, theory_weight_g=theory_weight, actual_weight_g=actual_weight, variance_g=round(actual_weight - theory_weight, 2), user_id=user.id)
    db.add(log); db.commit()
    return {"status": "success", "message": "纠正成功", "current_weight_g": actual_weight}

@app.post("/api/scale/device/command", tags=["智能称重节点"])
def send_device_command(data: CommandData, user: User = Depends(verify_script_api_key), db: Session = Depends(get_db)):
    cmd = DeviceCommand(device_id=data.device_id, command=data.command, params_json=json.dumps(data.params or {}), user_id=user.id)
    db.add(cmd); db.commit()
    return {"status": "queued", "command_id": cmd.id, "message": f"指令 {data.command} 已下发"}

@app.get("/api/scale/device/pending_command", tags=["智能称重节点"])
def get_pending_command(device_id: str = "scale_001", user: User = Depends(verify_script_api_key), db: Session = Depends(get_db)):
    cmd = db.query(DeviceCommand).filter(DeviceCommand.device_id == device_id, DeviceCommand.status == "pending", DeviceCommand.user_id == user.id).order_by(DeviceCommand.id.asc()).first()
    if not cmd: return {"has_command": False}
    cmd.status = "executed"; cmd.executed_at = datetime.datetime.utcnow(); db.commit()
    return {"has_command": True, "command_id": cmd.id, "command": cmd.command, "params": json.loads(cmd.params_json) if cmd.params_json else {}}

@app.post("/api/scale/heartbeat", tags=["智能称重节点"])
def scale_heartbeat(data: HeartbeatData, user: User = Depends(verify_script_api_key), db: Session = Depends(get_db)):
    status_row = db.query(DeviceStatus).filter(DeviceStatus.device_id == data.device_id, DeviceStatus.user_id == user.id).first()
    if not status_row:
        status_row = DeviceStatus(device_id=data.device_id, user_id=user.id)
        db.add(status_row)
    status_row.current_weight = data.current_weight
    status_row.wifi_rssi = data.wifi_rssi
    status_row.wifi_bars = data.wifi_bars
    status_row.current_page = data.current_page
    status_row.ip_address = data.ip_address
    status_row.firmware_version = data.firmware_version
    status_row.last_heartbeat = datetime.datetime.utcnow()
    db.commit()
    return {"status": "ok", "server_time": datetime.datetime.utcnow().isoformat()}

@app.get("/api/scale/device/status", tags=["智能称重节点"])
def get_device_status(device_id: str = "scale_001", user: User = Depends(verify_script_api_key), db: Session = Depends(get_db)):
    status_row = db.query(DeviceStatus).filter(DeviceStatus.device_id == device_id, DeviceStatus.user_id == user.id).first()
    if not status_row: return {"online": False, "device_id": device_id, "message": "未检测到设备心跳"}
    online = (datetime.datetime.utcnow() - status_row.last_heartbeat).total_seconds() < 120
    return {
        "online": online, "device_id": status_row.device_id, "current_weight": status_row.current_weight,
        "wifi_rssi": status_row.wifi_rssi, "wifi_bars": status_row.wifi_bars, "current_page": status_row.current_page,
        "ip_address": status_row.ip_address, "firmware_version": status_row.firmware_version,
        "last_heartbeat": (status_row.last_heartbeat + datetime.timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S") if status_row.last_heartbeat else ""
    }

# ----------------- 8. 环境探测与交互式启动引导 -----------------
def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def get_public_ip():
    try:
        req = urllib.request.Request("https://api.ipify.org", headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            return resp.read().decode('utf-8').strip()
    except Exception:
        return None

if __name__ == "__main__":
    local_ip = get_local_ip()
    pub_ip = get_public_ip()

    print("=" * 72)
    print("      拓竹 3D 打印耗材资产管理系统 - Windows 独立服务端 v3.1.0")
    print("=" * 72)
    print(f"📁 本地数据库: {DB_FILE_PATH}")
    print(f"🏠 本机内网IP: {local_ip}")
    if pub_ip:
        print(f"🌐 检测到公网: {pub_ip}")
    print("-" * 72)
    print("请选择运行模式：")
    print("  [1] 全网卡监听模式 (0.0.0.0 - 推荐，支持局域网设备/ESP32直连 [默认回车])")
    print("  [2] 本地独占模式   (127.0.0.1 - 仅当前电脑自身可访问)")
    print("  [3] 自定义端口模式 (支持手动指定 80, 8080, 18000 等任意可用端口)")
    print("-" * 72)

    choice = input("请输入选项 (1/2/3，直接回车使用 1): ").strip()
    if not choice: choice = "1"

    port = 8000
    host_ip = "0.0.0.0"
    mode_str = "全网卡监听 (0.0.0.0)"

    if choice == "2":
        host_ip = "127.0.0.1"
        mode_str = "本地独占 (Localhost)"
    elif choice == "3":
        host_ip = "0.0.0.0"
        p_str = input("请输入希望监听的端口号 (默认 8000): ").strip()
        if p_str.isdigit() and int(p_str) > 0:
            port = int(p_str)
        mode_str = f"自定义端口模式 ({port})"

    print(f"\n🚀 服务端启动中... [{mode_str}]")
    print(f"📌 本机浏览器访问 : http://127.0.0.1:{port}")
    print(f"📌 局域网/ESP32地址: http://{local_ip}:{port}")
    if pub_ip:
        print(f"📌 公网远程访问   : http://{pub_ip}:{port} (请确保防火墙已放行)")
    print("=" * 72 + "\n")

    uvicorn.run(app, host=host_ip, port=port, proxy_headers=True, forwarded_allow_ips="*")