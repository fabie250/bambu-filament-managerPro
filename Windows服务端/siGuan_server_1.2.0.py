import os
import sys
import datetime
import secrets
import logging
import hashlib
import socket
import urllib.request
import json
import requests
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, Depends, HTTPException, status, Header, Request, UploadFile, File, Form
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
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

Base.metadata.create_all(bind=engine)
for sql in [
    "ALTER TABLE filaments ADD COLUMN purchase_url TEXT DEFAULT NULL;",
    "ALTER TABLE filaments ADD COLUMN pending_weight_g FLOAT DEFAULT NULL;"
]:
    try:
        with engine.connect() as conn:
            conn.execute(text(sql))
            conn.commit()
    except Exception:
        pass

# ----------------- 3. FastAPI 初始化与静态资源托管 -----------------
app = FastAPI(title="拓竹耗材与打印机管理系统 - Windows 服务端", version="3.1.0")

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
    possible_paths = [os.path.join(BASE_DIR, "frontend"), os.path.join(os.path.dirname(BASE_DIR), "frontend"), "./frontend"]
    for p in possible_paths:
        if os.path.exists(p) and os.path.isdir(p): return p
    return None

FRONTEND_DIR = get_frontend_dir()
if FRONTEND_DIR:
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

@app.get("/", include_in_schema=False)
def read_index():
    if FRONTEND_DIR:
        idx_path = os.path.join(FRONTEND_DIR, "index.html")
        if os.path.exists(idx_path): return FileResponse(idx_path)
    return {"status": "success", "message": "拓竹耗材管理服务端运行正常"}

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

# ----------------- 4. Pydantic 数据结构 -----------------
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
    id: int
    key_name: str
    api_key: str
    created_at: datetime.datetime
    class Config: from_attributes = True

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

class FilamentUrlUpdate(BaseModel): purchase_url: str
class FilamentApplySameUrl(BaseModel): brand: str; material: str; purchase_url: str
class ManualAdjustWeightData(BaseModel): adjust_weight_g: float; reason: Optional[str] = "手动调整"

class FilamentOut(BaseModel):
    id: int; brand: str; material: str; color_name: str; color_hex: str
    nfc_uid: Optional[str]; initial_weight_g: float; current_weight_g: float
    price: float; purchase_url: Optional[str] = None; created_at: datetime.datetime
    class Config: from_attributes = True

class UsageRecordOut(BaseModel):
    id: int; task_name: Optional[str]; used_weight_g: float
    remaining_weight_g: Optional[float]; created_at: datetime.datetime
    class Config: from_attributes = True

class ScriptReportData(BaseModel):
    filament_id: int; used_weight_g: float; printer_id: Optional[int] = None; task_name: Optional[str] = None

# ----------------- 5. 安全鉴权逻辑 -----------------
def get_password_hash(password: str) -> str:
    salt = os.urandom(16).hex()
    pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000).hex()
    return f"{salt}${pwd_hash}"

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        salt, pwd_hash = hashed_password.split('$')
        check_hash = hashlib.pbkdf2_hmac('sha256', plain_password.encode('utf-8'), salt.encode('utf-8'), 100000).hex()
        return check_hash == pwd_hash
    except Exception: return False

def create_token(data: dict, expires_delta: datetime.timedelta) -> str:
    to_encode = data.copy()
    to_encode.update({"exp": datetime.datetime.utcnow() + expires_delta})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if not username: raise HTTPException(status_code=401)
    except JWTError: raise HTTPException(status_code=401)
    user = db.query(User).filter(User.username == username).first()
    if not user or not user.is_active: raise HTTPException(status_code=401)
    return user

def verify_script_api_key(x_api_key: Optional[str] = Header(None, alias="X-API-Key"), db: Session = Depends(get_db)) -> User:
    if not x_api_key: raise HTTPException(status_code=401, detail="缺少 API Key")
    db_key = db.query(APIKey).filter(APIKey.api_key == x_api_key, APIKey.is_active == True).first()
    if not db_key: raise HTTPException(status_code=401, detail="API Key 无效")
    return db_key.owner

# ----------------- 6. 核心业务与称重/OTA 路由 -----------------
@app.post("/api/auth/register")
def register(user_data: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == user_data.username).first(): raise HTTPException(status_code=400, detail="用户已存在")
    user = User(username=user_data.username, hashed_password=get_password_hash(user_data.password))
    db.add(user); db.commit()
    return {"status": "success"}

@app.post("/api/auth/login", response_model=TokenResponse)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password): raise HTTPException(status_code=400, detail="密码错误")
    return {"access_token": create_token({"sub": user.username}, datetime.timedelta(minutes=120)), "refresh_token": create_token({"sub": user.username}, datetime.timedelta(days=7)), "token_type": "bearer"}

@app.post("/api/auth/quick-api-key")
def quick_get_api_key(user_data: UserCreate, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == user_data.username).first()
    if not user or not verify_password(user_data.password, user.hashed_password): raise HTTPException(status_code=400)
    existing = db.query(APIKey).filter(APIKey.user_id == user.id, APIKey.is_active == True).first()
    if existing: return {"status": "success", "api_key": existing.api_key}
    raw_key = f"sk_{secrets.token_hex(16)}"
    new_key = APIKey(key_name="Auto", api_key=raw_key, user_id=user.id)
    db.add(new_key); db.commit()
    return {"status": "success", "api_key": raw_key}

@app.get("/api/ingest/script-user-info")
def get_script_user_info(user: User = Depends(verify_script_api_key)):
    return {"status": "success", "username": user.username, "user_id": user.id}

@app.get("/api/filaments", response_model=List[FilamentOut])
def list_filaments(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(Filament).filter(Filament.user_id == user.id).all()

@app.post("/api/filaments", response_model=FilamentOut)
def create_filament(f: FilamentCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    filament = Filament(**f.model_dump(), user_id=user.id)
    db.add(filament); db.commit(); db.refresh(filament)
    return filament

@app.delete("/api/filaments/{filament_id}")
def delete_filament(filament_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    f = db.query(Filament).filter(Filament.id == filament_id, Filament.user_id == user.id).first()
    if not f: raise HTTPException(status_code=404)
    db.query(UsageRecord).filter(UsageRecord.filament_id == filament_id).delete()
    db.delete(f); db.commit()
    return {"status": "success"}

# ================== 10. 智能称重与云端双轨 OTA 核心节点 ==================
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

Base.metadata.create_all(bind=engine)

class ScaleReportData(BaseModel):
    device_id: str; nfc_uid: str; weight_g: Optional[float] = None; gross_weight: Optional[float] = None; ip: Optional[str] = None
class ScaleOTACheckData(BaseModel): device_id: str; version: str

SCALE_TOLERANCE_G = 5.0
FIRMWARE_DIR = os.path.join(BASE_DIR, "firmware")
os.makedirs(FIRMWARE_DIR, exist_ok=True)
FIRMWARE_INFO_PATH = os.path.join(FIRMWARE_DIR, "version.json")

LAST_ESP_IP = ""
LAST_ESP_HEARTBEAT = None

def get_firmware_info():
    if os.path.exists(FIRMWARE_INFO_PATH):
        try:
            with open(FIRMWARE_INFO_PATH, "r", encoding="utf-8") as f: return json.load(f)
        except Exception: pass
    return {"version": "1.0.0", "filename": "firmware.bin"}

@app.post("/api/scale/report", tags=["智能称重节点"])
def scale_report(data: ScaleReportData, user: User = Depends(verify_script_api_key), db: Session = Depends(get_db)):
    global LAST_ESP_IP, LAST_ESP_HEARTBEAT
    if data.ip: LAST_ESP_IP = data.ip
    LAST_ESP_HEARTBEAT = datetime.datetime.utcnow()
    
    filament = db.query(Filament).filter(Filament.nfc_uid == data.nfc_uid, Filament.user_id == user.id).first()
    net_weight = round(data.gross_weight - filament.spool_weight_g, 2) if (data.gross_weight is not None and filament) else round(data.gross_weight if data.gross_weight is not None else (data.weight_g or 0.0), 2)

    if not filament:
        pending = ScalePending(device_id=data.device_id, nfc_uid=data.nfc_uid, measured_weight_g=net_weight, status="pending", user_id=user.id)
        db.add(pending); db.commit()
        return {"action": "pending", "message": "NFC未绑定耗材", "pending_id": pending.id, "net_weight": net_weight}

    expected = filament.current_weight_g
    diff = round(net_weight - expected, 2)
    if abs(diff) <= SCALE_TOLERANCE_G:
        filament.current_weight_g = net_weight; db.commit()
        return {"action": "success", "message": "已同步", "filament_id": filament.id, "net_weight": net_weight}
    else:
        pending = ScalePending(device_id=data.device_id, nfc_uid=data.nfc_uid, measured_weight_g=net_weight, expected_weight_g=expected, difference_g=diff, filament_id=filament.id, status="pending", user_id=user.id)
        db.add(pending); db.commit()
        return {"action": "pending", "message": f"误差{diff}g", "pending_id": pending.id, "difference_g": diff, "net_weight": net_weight}

GITHUB_FIRMWARE_API = "https://api.github.com/repos/fabie250/-bambu-filament-manager/releases/latest"

@app.get("/api/scale/ota_check", tags=["智能称重节点"])
def scale_ota_check(user: User = Depends(verify_script_api_key)):
    try:
        resp = requests.get(GITHUB_FIRMWARE_API, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            latest_version = data.get("tag_name", "1.0.0").replace("v", "")
            download_url = next((a.get("browser_download_url") for a in data.get("assets", []) if a.get("name", "").endswith(".bin")), "")
            return {"status": "success", "latest_version": latest_version, "download_url": download_url}
    except Exception: pass
    return {"status": "error", "message": "获取固件失败"}

class OtaPushBody(BaseModel): download_url: str

@app.post("/api/scale/ota/push", tags=["智能称重节点"])
def push_ota_to_device(data: OtaPushBody, user: User = Depends(verify_script_api_key), db: Session = Depends(get_db)):
    cmd = DeviceCommand(device_id="scale_001", command="ota", params_json=json.dumps({"url": data.download_url}), user_id=user.id)
    db.add(cmd); db.commit()
    return {"status": "success", "message": "OTA 更新指令已下发"}

@app.get("/api/scale/status", tags=["智能称重节点"])
def scale_status(user: User = Depends(verify_script_api_key), db: Session = Depends(get_db)):
    pending_list = db.query(ScalePending).filter(ScalePending.user_id == user.id, ScalePending.status == "pending").all()
    result = []
    for p in pending_list:
        filament = db.query(Filament).filter(Filament.id == p.filament_id).first() if p.filament_id else None
        result.append({
            "pending_id": p.id, "device_id": p.device_id, "nfc_uid": p.nfc_uid,
            "measured_weight_g": p.measured_weight_g, "expected_weight_g": p.expected_weight_g, "difference_g": p.difference_g,
            "filament_id": p.filament_id, "filament_name": f"{filament.brand} {filament.material} {filament.color_name}" if filament else "未绑定耗材",
            "color_hex": filament.color_hex if filament else "#888888"
        })
    return {"count": len(result), "items": result}

@app.post("/api/scale/bind", tags=["智能称重节点"])
def scale_bind(data: ScaleBindData := None, user: User = Depends(verify_script_api_key), db: Session = Depends(get_db)):
    # 兼容绑定逻辑
    pass

@app.post("/api/scale/device/command", tags=["智能称重节点"])
def send_device_command(data: dict, user: User = Depends(verify_script_api_key), db: Session = Depends(get_db)):
    cmd = DeviceCommand(device_id=data.get("device_id", "scale_001"), command=data.get("command"), params_json=json.dumps(data.get("params", {})), user_id=user.id)
    db.add(cmd); db.commit()
    return {"status": "queued"}

@app.get("/api/scale/device/pending_command", tags=["智能称重节点"])
def get_pending_command(device_id: str = "scale_001", user: User = Depends(verify_script_api_key), db: Session = Depends(get_db)):
    cmd = db.query(DeviceCommand).filter(DeviceCommand.device_id == device_id, DeviceCommand.status == "pending", DeviceCommand.user_id == user.id).first()
    if not cmd: return {"has_command": False}
    cmd.status = "executed"; cmd.executed_at = datetime.datetime.utcnow(); db.commit()
    return {"has_command": True, "command": cmd.command, "params": json.loads(cmd.params_json)}

@app.post("/api/scale/heartbeat", tags=["智能称重节点"])
def scale_heartbeat(data: dict, user: User = Depends(verify_script_api_key), db: Session = Depends(get_db)):
    return {"status": "ok"}

@app.get("/api/scale/device/status", tags=["智能称重节点"])
def get_device_status(device_id: str = "scale_001", user: User = Depends(verify_script_api_key), db: Session = Depends(get_db)):
    online = LAST_ESP_HEARTBEAT and (datetime.datetime.utcnow() - LAST_ESP_HEARTBEAT).total_seconds() < 120
    return {"online": online, "current_weight": 0.0, "wifi_bars": 4, "current_page": "weighing"}

# ----------------- 11. 服务启动入口 -----------------
if __name__ == "__main__":
    print("=" * 60)
    print(" 拓竹耗材资产管理系统 - Windows 本地服务端 v3.1.0 (已集成校准与OTA)")
    print("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=8000)