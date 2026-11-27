# 丝衡 SiGuan · 3D 打印耗材管理

> 耗材台账、称重校准、AMS 多仓、ESP32 节点与 OTA，一套系统管理 3D 打印耗材。
>
> Windows 客户端 + Windows / Linux 服务端，支持网页端与手机浏览器访问。

![License](https://img.shields.io/badge/license-GPLv3-blue.svg)
![Client](https://img.shields.io/badge/client-v1.5.4-green.svg)
![Server](https://img.shields.io/badge/server-v1.2.4-orange.svg)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux-lightgrey.svg)

**最新发布**：[v1.5.4](https://github.com/fabie250/bambu-filament-managerPro/releases/tag/v1.5.4) · **更新公告**：[`更新公告_v1.5.4.md`](更新公告_v1.5.4.md)

---

## 下载

| 组件 | 版本 | 说明 | 获取方式 |
|---|---|---|---|
| Windows 客户端（在线版） | v1.5.4 | 连接服务端使用 | [SiGuan_1.5.4.exe](https://github.com/fabie250/bambu-filament-managerPro/releases/download/v1.5.4/SiGuan_1.5.4.exe) |
| Windows 客户端（离线版） | v1.5.4 | 本机离线使用 | [SiGuan_Offline_1.5.4.exe](https://github.com/fabie250/bambu-filament-managerPro/releases/download/v1.5.4/SiGuan_Offline_1.5.4.exe) |
| Windows 服务端 | v1.2.4 | SQLite，免安装 EXE | [siGuan_server_win.exe](https://github.com/fabie250/bambu-filament-managerPro/releases/download/v1.5.4/siGuan_server_win.exe) |
| Linux 服务端 | 当前源码 | MySQL，Docker 部署 | [`backend/`](backend/) + [`Dockerfile`](Dockerfile) |

校验文件：[`SHA256SUMS.txt`](https://github.com/fabie250/bambu-filament-managerPro/releases/download/v1.5.4/SHA256SUMS.txt)

> Windows 客户端和服务端是两个独立程序：服务端负责数据库与 API，客户端负责桌面操作界面。

---

## 5 分钟开始（Windows 单机）

### 1. 启动 Windows 服务端

下载 `siGuan_server_win.exe`，双击运行。按提示选择运行模式：

- `1`：全网卡监听，局域网内的客户端、手机和 ESP32 都能访问
- `2`：仅本机访问
- `3`：自定义端口

默认地址：`http://127.0.0.1:8000`  
API 文档：`http://127.0.0.1:8000/api/docs`

首次运行会在 EXE 同目录生成 `filament_db.db` 和 `firmware/`，升级前先备份。

<details>
<summary>用 Python 源码运行服务端</summary>

需要 Python 3.10+（本项目在 3.14 上验证）：

```powershell
cd "Windows服务端"
py -3.14 -m pip install fastapi uvicorn sqlalchemy "python-jose[cryptography]" pydantic python-multipart
py -3.14 "siGuan_server_1.2.4.py"
```

</details>

### 2. 注册账号

浏览器打开 `http://127.0.0.1:8000`，完成注册和登录。

### 3. 连接客户端

下载并运行 `SiGuan_1.5.4.exe`，首次启动填写服务端地址：

```text
http://127.0.0.1:8000
```

如果服务端在另一台电脑上，填写那台电脑的局域网地址，例如：

```text
http://192.168.1.100:8000
```

> 局域网访问失败时，请确认服务端选择了模式 `1`，并允许 Windows 防火墙放行 `8000` 端口。

---

## Linux 部署（Docker）

准备一台安装 Docker 的 Linux 服务器，克隆仓库后创建 `docker-compose.yml`：

```yaml
services:
  db:
    image: mysql:8.0
    restart: unless-stopped
    environment:
      MYSQL_ROOT_PASSWORD: change-me
      MYSQL_DATABASE: filament_db
    command: --character-set-server=utf8mb4 --collation-server=utf8mb4_unicode_ci
    volumes:
      - mysql_data:/var/lib/mysql

  filament-api:
    build: .
    container_name: filament-api
    restart: unless-stopped
    environment:
      DB_HOST: db
      DB_PORT: 3306
      DB_USER: root
      DB_PASSWORD: change-me
      DB_NAME: filament_db
      SECRET_KEY: change-me-to-a-random-string
    ports:
      - "8000:8000"
    depends_on:
      - db
    volumes:
      - ./firmware:/app/firmware

volumes:
  mysql_data:
```

启动：

```bash
docker compose up -d --build
docker compose logs -f filament-api
```

访问：

- 网页端：`http://服务器IP:8000`
- API 文档：`http://服务器IP:8000/api/docs`

> 必须修改 `MYSQL_ROOT_PASSWORD`、`DB_PASSWORD` 和 `SECRET_KEY`。  
> 1Panel 用户可把上面的 YAML 粘贴到「容器 → 编排 → 创建编排」中启动。

<details>
<summary>不用 Docker：Linux 源码运行</summary>

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt

# 先准备 MySQL 8.0 和数据库 filament_db，并设置 DB_* 环境变量
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000
```

</details>

---

## 功能

- **耗材台账**：品牌、材料、颜色、表面效果、线径（1.75 / 2.85 mm）、重量、价格、购买链接、备注。
- **AMS 多仓**：AMS 槽位映射；P3C 支持 5 个标配 + 2 个扩展位（最多 7 头），H3C 8 号位按 2.85 mm 专用头校验。
- **称重与校准**：配合丝衡 ESP32-S3 电子秤，称总重/剩余重量，自动对比账面数据。
- **NFC 识别**：PN532 读取耗材盘 UID，绑定耗材信息。
- **设备管理**：ESP32 心跳、在线状态、OLED 页面切换、远程重启与重新配网。
- **固件与 OTA**：上传固件、检查版本，并按设备返回结果下发升级。
- **多用户与 API Key**：JWT 登录，数据按用户隔离；脚本和 ESP32 使用 API Key 接入。
- **多端访问**：Windows 客户端、网页端、手机浏览器。

---

## 目录结构

```text
bambu-filament-managerPro/
├── 客户端/                 # Windows 客户端源码与 PyInstaller 配置
├── Windows服务端/          # Windows SQLite 服务端（1.2.0 / 1.2.3 / 1.2.4）
├── backend/                # Linux MySQL 服务端（Dockerfile 使用）
├── Linux服务端/            # Linux 服务端单文件副本，手动部署参考
├── frontend/               # 网页端（单文件 index.html）
├── Dockerfile              # Linux 服务端镜像
├── 更新公告_v1.5.4.md      # 当前客户端更新说明
└── README.md
```

Windows 服务端的数据默认保存在程序同目录的 `filament_db.db`，固件在 `firmware/`。EXE 运行时就是 EXE 所在目录；升级或迁移前请先复制这两个位置。

---

## 配置

### Windows 服务端

使用 SQLite，不需要 MySQL。生产环境建议通过 `JWT_SECRET` 环境变量设置独立的 JWT 密钥。数据库文件：

- EXE 运行：EXE 同目录下的 `filament_db.db` 和 `firmware/`
- 源码运行：`Windows服务端/filament_db.db` 和 `Windows服务端/firmware/`

### Linux 服务端

| 环境变量 | 说明 | 示例 |
|---|---|---|
| `DB_HOST` | MySQL 地址 | `db` 或 `127.0.0.1` |
| `DB_PORT` | MySQL 端口 | `3306` |
| `DB_USER` | 数据库用户 | `root` |
| `DB_PASSWORD` | 数据库密码 | `change-me` |
| `DB_NAME` | 数据库名 | `filament_db` |
| `SECRET_KEY` | JWT 密钥，务必修改 | 随机长字符串 |
| `SERVER_HOST` | 监听地址 | `0.0.0.0` |
| `SERVER_PORT` | 监听端口 | `8000` |

---

## 构建 Windows 程序

### 客户端

```powershell
cd "客户端"
py -3.14 -m pip install pyinstaller
py -3.14 -m PyInstaller SiGuan_1.5.4.spec --clean --noconfirm
```

生成文件：`客户端/dist/SiGuan_1.5.4.exe`。

MiSans Regular / Bold 已打进 EXE，目标电脑不需要额外安装字体；源码运行时缺字体则回退微软雅黑。

### Windows 服务端 EXE

```powershell
cd "Windows服务端"
py -3.14 -m pip install pyinstaller
py -3.14 -m PyInstaller siGuan_server_1.2.4.spec --clean --noconfirm
```

生成文件：`Windows服务端/dist/siGuan_server_win.exe`。前端页面已打进 EXE；运行后数据库和固件目录生成在 EXE 同目录。

---

## 升级与备份

- **Windows 服务端**：先备份程序同目录的 `filament_db.db` 和 `firmware/`，再替换服务端文件或 EXE。
- **Windows 客户端**：直接覆盖旧 EXE。
- **Linux Docker**：`docker compose up -d --build` 重建；数据库在 `mysql_data` 卷中。
- **升级顺序**：先升级服务端，再升级客户端。

---

## 常见问题

**浏览器打不开服务端？**  
确认服务端已启动、端口未被占用；局域网访问时选择模式 `1`，并检查防火墙。

**客户端连不上？**  
确认地址包含 `http://` 和端口，客户端与服务端网络互通；ESP32 还需要正确的 API Key。

**Linux 容器连不上 MySQL？**  
`DB_HOST` 填 MySQL 容器名（上面的例子是 `db`），不要填 `127.0.0.1`；确认数据库已创建。

**数据在哪里？**  
Windows EXE 在 EXE 同目录的 `filament_db.db`；源码运行在 `Windows服务端/filament_db.db`；Docker 在 `mysql_data` 卷。定期备份即可。

**需要安装 MiSans 吗？**  
不需要。EXE 已内置；只有直接运行 Python 源码时才可能需要把字体放在同目录。

---

## 相关项目

- 丝衡 ESP32-S3 电子秤：<https://github.com/fabie250/siheng>
- 问题反馈：<https://github.com/fabie250/bambu-filament-managerPro/issues>

## 许可证

GPLv3，详见 [`LICENSE`](LICENSE)。

## 致谢

[FastAPI](https://fastapi.tiangolo.com/) · [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) · [U8g2](https://github.com/olikraus/u8g2) · [HX711](https://github.com/bogde/HX711) · [WiFiManager](https://github.com/tzapu/WiFiManager) · [Bambu Lab](https://bambulab.com/)


