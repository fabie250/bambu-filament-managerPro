# Bambu Filament Manager Pro

> 3D打印耗材全生命周期管理系统 - 专业版
>
> 从耗材入库、使用追踪、余量校准到补货提醒，一站式管理你的3D打印耗材。配合「丝衡」智能电子秤，实现物理重量与账面数据实时同步。

![License](https://img.shields.io/badge/license-GPLv3-blue.svg)
![Python](https://img.shields.io/badge/python-3.8+-green.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-orange.svg)
![MySQL](https://img.shields.io/badge/MySQL-8.0+-blue.svg)
![Docker](https://img.shields.io/badge/docker-supported-blue.svg)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux-lightgrey.svg)

---

## ✨ 功能特性

### 📦 耗材管理
- **耗材台账**：品牌、型号、颜色、材质、重量、价格、购买链接全记录
- **NFC 绑定**：PN532 读取耗材盘 NFC UID，一键绑定耗材信息
- **多仓管理**：支持 AMS 多仓位耗材管理，实时同步仓位状态
- **使用记录**：每次打印自动扣减耗材，记录使用历史

### 📊 数据洞察
- **耗材统计**：按品牌、材质、颜色统计使用量和剩余量
- **成本分析**：打印成本核算，耗材花费趋势图
- **损耗追踪**：打印失败废料记录，对账校准流水
- **补货提醒**：低库存自动提醒，一键生成补货清单

### ⚖️ 智能称重（丝衡节点）
- **实时称重**：HX711 + 悬臂梁传感器，精度 0.1g
- **自动校准**：放上去自动识别耗材，对比账面与实测重量
- **两种模式**：
  - 全新耗材模式：称总重，自动扣减空盘皮重
  - 老耗材校准模式：称剩余重量，校准账面数据
- **失败纠正**：打印失败后一键扣减废料，记录损耗

### 📡 远程设备管理
- **ESP32 节点管理**：心跳上报，在线状态实时显示
- **远程屏幕预览**：网页端/客户端实时查看 ESP32 OLED 屏幕内容
- **远程页面切换**：称重页 / 设备信息页 / WiFi 状态页，一键切换
- **远程重启**：网页端一键重启设备
- **初始化重置配网**：远程清除 WiFi 和 API Key 配置，重新配网

### 🔄 OTA 在线升级
- **固件管理**：网页端上传固件，自动解析版本号
- **自动检查更新**：ESP32 启动时自动检查新版本
- **GitHub 镜像加速**：多镜像轮询，解决国内下载慢问题
- **MD5 校验**：固件下载后自动校验完整性

### 🔐 安全与权限
- **用户系统**：注册登录，JWT 鉴权
- **API Key 管理**：脚本/设备接入用 API Key，支持生成和禁用
- **数据隔离**：多用户数据隔离，每人只能看自己的耗材
- **HTTPS 支持**：生产环境建议配置 HTTPS

---

## 🏗️ 系统架构

```text
┌─────────────────────────────────────────────────────────────┐
│                         用户层                              │
│                                                             │
│  ┌────────────────┐  ┌────────────────┐  ┌──────────────┐  │
│  │ Windows 客户端 │  │    网页端       │  │   手机浏览器  │  │
│  │      EXE       │  │   HTML / JS    │  │  响应式网页   │  │
│  └───────┬────────┘  └───────┬────────┘  └──────┬───────┘  │
└──────────┼────────────────────┼───────────────────┼─────────┘
           │                    │                   │
           └────────────────────┼───────────────────┘
                                │ HTTP / HTTPS
                                ▼
┌─────────────────────────────────────────────────────────────┐
│                         服务端层                             │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐ │
│  │                 FastAPI 后端服务                       │ │
│  │                                                       │ │
│  │  耗材管理 │ 设备管理 │ 称重管理 │ OTA │ 用户 │ API Key │ │
│  └───────────────────────────────────────────────────────┘ │
│                                                             │
│      SQLite（Windows） / MySQL（Linux） / 固件存储          │
└─────────────────────────────────────────────────────────────┘
                                │
                                │ HTTP
                                ▼
┌─────────────────────────────────────────────────────────────┐
│                         硬件层                              │
│                                                             │
│             丝衡 - ESP32-S3 智能电子秤                      │
│                                                             │
│       HX711 │ OLED │ PN532 │ WS2812 │ WiFi                  │
└─────────────────────────────────────────────────────────────┘
```

---

## 🚀 快速开始

### ⭐ 普通 Windows 用户

**不需要安装 Python，也不需要配置开发环境。**

如果你只是想使用本项目，直接下载 GitHub Releases 中提供的 Windows 版本即可。

Windows 版本包含：
- **Windows 服务端 EXE**
- **Windows 客户端 EXE**

推荐安装/使用顺序：

```text
① 下载 Windows 服务端
        ↓
② 启动服务端 EXE
        ↓
③ 浏览器访问服务端地址
        ↓
④ 注册/登录账号
        ↓
⑤ 下载并启动 Windows 客户端 EXE
        ↓
⑥ 在客户端填写服务端地址
        ↓
⑦ 开始管理 3D 打印耗材
```

> ⚠️ Windows 服务端和客户端是两个独立程序。
>
> 服务端负责数据库、API、耗材管理以及 ESP32 设备通信。
>
> 客户端负责提供 Windows 桌面操作界面。

---

## 🪟 Windows 服务端

### 方式一：直接使用 EXE（推荐）

Windows 用户无需安装 Python。

从 GitHub Releases 下载最新的 Windows 服务端压缩包。

例如：
```text
BambuFilamentManagerPro-Server-Windows-x64.zip
```

解压后：
```text
BambuFilamentManagerPro-Server/
├── BambuFilamentManagerPro-Server.exe
├── data/
├── firmware/
├── config/
└── README.txt
```

双击：
```text
BambuFilamentManagerPro-Server.exe
```

启动服务端。

默认情况下服务端监听：
```text
http://127.0.0.1:8000
```

浏览器访问：
```text
http://127.0.0.1:8000
```

API 文档：
```text
http://127.0.0.1:8000/docs
```

### 局域网访问

如果需要让手机、其他电脑或者 ESP32 访问这台 Windows 电脑：

```text
http://你的电脑局域网IP:8000
```

例如：
```text
http://192.168.1.100:8000
```

如果无法访问，请检查 Windows 防火墙是否允许 `8000` 端口。

### Windows 服务端数据

Windows 版本默认使用 SQLite，因此：

**不需要安装 MySQL。**

程序运行后数据库和相关数据会保存在服务端程序的数据目录中。

建议不要删除：
```text
data/
```

否则可能导致耗材、用户和设备数据丢失。

---

## 🖥️ Windows 客户端

### 方式一：直接使用 EXE（推荐）

普通用户不需要安装 Python。

从 GitHub Releases 下载：
```text
BambuFilamentManagerPro-Client-Windows-x64.zip
```

解压后：
```text
BambuFilamentManagerPro-Client/
├── BambuFilamentManagerPro-Client.exe
├── config/
└── README.txt
```

双击：
```text
BambuFilamentManagerPro-Client.exe
```

即可启动 Windows 客户端。

### 🔗 首次连接服务端

客户端首次启动后，需要填写服务端地址。

如果服务端和客户端在同一台电脑：
```text
http://127.0.0.1:8000
```

如果服务端运行在另一台电脑：
```text
http://192.168.1.100:8000
```

填写完成后连接服务端。

之后即可使用：
- 耗材台账
- 智能称重
- 数据统计
- ESP32 管理
- OTA 固件管理
- API Key 管理
- 补货清单

等功能。

---

## 🔧 Windows 开发者模式

如果你是开发者，或者需要修改源码，可以直接使用 Python 源码运行。

### 环境要求
- Python 3.8+
- Windows 10/11

### 服务端
```bash
pip install -r requirements.txt
python server.py
```

### 客户端
```bash
pip install customtkinter requests Pillow
python client.py
```

> 普通用户无需执行以上步骤。
>
> **直接使用 Releases 中提供的 EXE 即可。**

---

## 🐧 Linux 部署

Linux 用户推荐使用 Docker 部署，也可以使用 Python 源码手动部署。

### 🐳 Docker 部署（推荐）

本项目已构建 Docker 镜像，托管于 GitHub Container Registry。

**镜像地址**：`ghcr.io/fabie250/bambu-filament-managerpro:latest`

#### 1. 创建项目目录

```bash
mkdir -p /opt/bambu-filament
cd /opt/bambu-filament
```

#### 2. 创建编排文件

新建 `docker-compose.yml`：

```yaml
version: '3.8'

services:
  filament-api:
    image: ghcr.io/fabie250/bambu-filament-managerpro:latest
    container_name: filament-api
    restart: unless-stopped
    environment:
      # 数据库配置（推荐 MySQL 8.0+）
      - DB_HOST=你的数据库IP
      - DB_PORT=3306
      - DB_USER=你的数据库用户名
      - DB_PASSWORD=你的数据库密码
      - DB_NAME=filament_db
      # JWT 密钥（请自定义复杂随机字符串）
      - SECRET_KEY=请自定义一个复杂的随机字符串
      # 服务配置
      - SERVER_HOST=0.0.0.0
      - SERVER_PORT=8000
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
      - ./firmware:/app/firmware
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/docs"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 20s
```

#### 3. 一键启动

```bash
docker-compose up -d
```

系统会自动从 GitHub 下载最新镜像并启动服务。

#### 4. 查看日志

```bash
docker-compose logs -f
```

#### 5. 访问系统

启动完成后，在浏览器中访问：

- 网页控制台：`http://你的服务器IP:8000`
- API 接口文档：`http://你的服务器IP:8000/docs`

---

### 📦 Docker Run 单行命令

如果不想用 docker-compose，也可以直接用 docker run：

```bash
docker run -d \
  --name filament-api \
  --restart unless-stopped \
  -p 8000:8000 \
  -v /opt/bambu-filament/data:/app/data \
  -v /opt/bambu-filament/firmware:/app/firmware \
  -e DB_HOST=你的数据库IP \
  -e DB_PORT=3306 \
  -e DB_USER=你的数据库用户名 \
  -e DB_PASSWORD=你的数据库密码 \
  -e DB_NAME=filament_db \
  -e SECRET_KEY=你的自定义密钥 \
  ghcr.io/fabie250/bambu-filament-managerpro:latest
```

---

### 🖥️ 1Panel 面板快速部署

如果使用 1Panel 可视化面板，操作会更简单：

1. 进入左侧菜单 **容器 → 编排 → 创建编排**
2. 将上方的 `docker-compose.yml` 配置粘贴到代码框中
3. 修改好对应的数据库账号密码和 SECRET_KEY
4. 点击 **保存并启动**，面板会自动拉取镜像并完成部署

---

### 🔄 Docker 升级流程

```bash
# 拉取最新镜像
docker-compose pull

# 重启容器
docker-compose up -d

# 查看日志确认启动成功
docker-compose logs -f
```

---

### 💾 数据备份

```bash
# 备份数据目录
tar -czvf filament-backup-$(date +%Y%m%d).tar.gz ./data ./firmware

# MySQL 备份（如果使用外部 MySQL）
mysqldump -h 数据库IP -u 用户名 -p filament_db > filament_db_$(date +%Y%m%d).sql
```

---

### 📝 Python 源码手动部署

如果不想用 Docker，也可以手动部署：

```bash
# 克隆仓库
git clone https://github.com/fabie250/bambu-filament-managerPro.git
cd bambu-filament-managerPro

# 安装依赖
pip install -r requirements.txt

# 初始化数据库
python -c "from main import Base, engine; Base.metadata.create_all(bind=engine)"

# 启动服务
uvicorn main:app --host 0.0.0.0 --port 8000
```

Linux 推荐使用 MySQL 8.0+。

---

## ⚙️ 服务端配置

### Windows

Windows EXE 版本默认使用：
```text
SQLite
```

无需安装 MySQL。

### Linux

Linux 推荐使用：
```text
MySQL 8.0+
```

环境变量说明：

| 环境变量 | 说明 | 示例值 |
|----------|------|--------|
| `DB_HOST` | 数据库地址 | `127.0.0.1` |
| `DB_PORT` | 数据库端口 | `3306` |
| `DB_USER` | 数据库用户名 | `root` |
| `DB_PASSWORD` | 数据库密码 | `your_password` |
| `DB_NAME` | 数据库名 | `filament_db` |
| `SECRET_KEY` | JWT 加密密钥（务必修改） | `your-secret-key-change-this` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access Token 过期时间（分钟） | `30` |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Refresh Token 过期时间（天） | `7` |
| `SERVER_HOST` | 服务监听地址 | `0.0.0.0` |
| `SERVER_PORT` | 服务监听端口 | `8000` |

---

## ⚖️ 丝衡 - 智能电子秤

本项目配套 ESP32-S3 智能电子秤：

**项目地址**：https://github.com/fabie250/siheng

丝衡节点负责：
- HX711 精准称重
- NFC 耗材识别
- OLED 显示
- WiFi 通信
- 称重数据上报
- 心跳上报
- 远程指令
- OTA 固件升级

---

## 📡 网络连接示意图

推荐网络结构：

```text
                 ┌──────────────────────┐
                 │   Windows 服务端 EXE │
                 │      :8000           │
                 └──────────┬───────────┘
                            │
                ┌───────────┼───────────┐
                │           │           │
                ▼           ▼           ▼
        Windows客户端     手机浏览器    丝衡ESP32
            EXE
```

只要这些设备处于可以互相访问的网络中即可。

例如 Windows 电脑 IP：
```text
192.168.1.100
```

服务端：
```text
http://192.168.1.100:8000
```

那么：
- Windows 客户端连接 `http://192.168.1.100:8000`
- 手机浏览器访问 `http://192.168.1.100:8000`
- 丝衡 ESP32 配置服务器地址为 `http://192.168.1.100:8000`

---

## 📦 GitHub Releases

建议每个版本发布时提供：

```text
BambuFilamentManagerPro/
│
├── Windows/
│   ├── BambuFilamentManagerPro-Server-Windows-x64.zip
│   └── BambuFilamentManagerPro-Client-Windows-x64.zip
│
├── Linux/
│   └── Docker部署说明
│
└── Source/
    └── Source code.zip
```

Windows 用户只需要下载：
```text
Server-Windows-x64.zip
Client-Windows-x64.zip
```

不需要下载 Python 源码，也不需要安装 Python。

---

## 📁 项目结构

```text
bambu-filament-managerPro/
│
├── server/
│   ├── main.py                 # Linux 服务端（MySQL）
│   ├── server.py               # Windows 服务端（SQLite）
│   ├── requirements.txt        # Python 依赖
│   └── Dockerfile              # Docker 构建文件
│
├── client/
│   └── client.py               # Windows CTk 客户端
│
├── web/
│   └── index.html              # 前端网页（单文件）
│
├── docs/
│   ├── API.md                  # API 文档
│   ├── DEPLOY.md               # 部署指南
│   └── HARDWARE.md             # 硬件接线指南
│
├── .env.example                # 环境变量示例
├── docker-compose.yml          # Docker Compose 配置
├── CHANGELOG.md                # 更新日志
├── LICENSE                     # GPLv3 协议
└── README.md                   # 项目说明
```

> `build/` 中的 EXE 可以不直接提交到 Git 仓库。
>
> 推荐通过 GitHub Releases 发布 Windows EXE。

---

## 🔄 版本更新

项目同时提供：
- Windows 服务端 EXE 更新
- Windows 客户端 EXE 更新
- Web 端更新
- 丝衡 ESP32 固件 OTA 更新
- Docker 镜像更新

Windows 用户只需要下载最新 Release 即可。

如果使用旧版本服务端，请优先升级服务端，再升级客户端。

Docker 用户执行 `docker-compose pull && docker-compose up -d` 即可升级。

---

## ❓ 常见问题

### Q: Windows 服务端启动后浏览器访问不了？
A: 检查是否有其他程序占用了 8000 端口，或者 Windows 防火墙是否拦截。可以尝试修改端口号。

### Q: ESP32 连不上服务端？
A: 确保 ESP32 和服务端在同一局域网，检查服务端地址和端口是否正确，API Key 是否填写正确。

### Q: Docker 启动后数据库连接失败？
A: 检查 DB_HOST 是否能从容器内访问，如果 MySQL 也在 Docker 里，建议用容器名或 docker network 连接。

### Q: 数据会丢失吗？
A: Windows 数据存在 `data/` 目录，Docker 数据在挂载的卷里，只要不删除这些目录，数据就不会丢失。建议定期备份。

### Q: 可以多人使用吗？
A: 支持多用户注册，每个用户的数据互相隔离，只能看到自己的耗材。

---

## 📜 许可证

本项目采用 **GNU General Public License v3.0（GPLv3）** 协议开源。

```text
Bambu Filament Manager Pro - 3D打印耗材全生命周期管理系统
Copyright (C) 2026 fabie

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program. If not, see <https://www.gnu.org/licenses/>.
```

详见 [`LICENSE`](LICENSE) 文件。

---

## 📮 联系方式

- **作者**：fabie
- **项目地址**：https://github.com/fabie250/bambu-filament-managerPro
- **配套固件**：https://github.com/fabie250/siheng
- **问题反馈**：[GitHub Issues](https://github.com/fabie250/bambu-filament-managerPro/issues)

---

## 🙏 致谢

- [FastAPI](https://fastapi.tiangong.com/) - 高性能 Python Web 框架
- [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) - 现代化 Python GUI 库
- [U8g2](https://github.com/olikraus/u8g2) - ESP32 OLED 显示库
- [HX711](https://github.com/bogde/HX711) - 称重传感器库
- [WiFiManager](https://github.com/tzapu/WiFiManager) - ESP32 智能配网库
- [Bambu Lab](https://bambulab.com/) - 优秀的3D打印设备

---

**如果这个项目对你有帮助，欢迎给个 Star ⭐ 支持一下！**
