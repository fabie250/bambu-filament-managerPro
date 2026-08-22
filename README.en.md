English | [中文](README.zh.md)

# Bambu Filament Manager Pro

> 3D Printing Filament Full Lifecycle Management System - Professional Edition
>
> Manage your 3D printing filaments in one stop: from inventory, usage tracking, weight calibration to restock reminders. Works with the "Siheng" smart scale for real-time synchronization between physical weight and book data.

![License](https://img.shields.io/badge/license-GPLv3-blue.svg)
![Python](https://img.shields.io/badge/python-3.8+-green.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-orange.svg)
![MySQL](https://img.shields.io/badge/MySQL-8.0+-blue.svg)
![Docker](https://img.shields.io/badge/docker-supported-blue.svg)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux-lightgrey.svg)

---

## ✨ Features

### 📦 Filament Management
- **Filament Inventory**: Full records of brand, model, color, material, weight, price, and purchase links
- **NFC Binding**: Read filament spool NFC UID with PN532, bind filament info with one click
- **Multi-Spool Management**: Support AMS multi-slot filament management, real-time slot status sync
- **Usage Records**: Auto-deduct filament after each print, record usage history

### 📊 Data Insights
- **Filament Statistics**: Usage and remaining stats by brand, material, and color
- **Cost Analysis**: Print cost accounting, filament spending trend charts
- **Waste Tracking**: Print failure waste records, reconciliation calibration logs
- **Restock Reminder**: Low stock auto-reminder, generate restock list with one click

### ⚖️ Smart Weighing (Siheng Node)
- **Real-time Weighing**: HX711 + load cell sensor, 0.1g precision
- **Auto Calibration**: Auto-identify filament when placed, compare book vs measured weight
- **Two Modes**:
  - New filament mode: Weigh total, auto-deduct empty spool weight
  - Old filament calibration mode: Weigh remaining, calibrate book data
- **Failure Correction**: One-click waste deduction after print failure, record loss

### 📡 Remote Device Management
- **ESP32 Node Management**: Heartbeat reporting, real-time online status display
- **Remote Screen Preview**: View ESP32 OLED screen content in real-time from web/client
- **Remote Page Switching**: Weighing page / Device info page / WiFi status page, one-click switch
- **Remote Reboot**: Reboot device from web with one click
- **Factory Reset Config**: Remote clear WiFi and API Key config, re-enter config mode

### 🔄 OTA Online Upgrade
- **Firmware Management**: Upload firmware from web, auto-parse version number
- **Auto Update Check**: ESP32 auto-checks for new versions on boot
- **GitHub Mirror Acceleration**: Multi-mirror polling, solve slow download in China
- **MD5 Verification**: Auto-verify firmware integrity after download

### 🔐 Security & Permissions
- **User System**: Register and login, JWT authentication
- **API Key Management**: API Keys for scripts/device access, support generation and disabling
- **Data Isolation**: Multi-user data isolation, each user can only see their own filaments
- **HTTPS Support**: Recommend configuring HTTPS for production environments

---

## 🏗️ System Architecture

```text
┌─────────────────────────────────────────────────────────────┐
│                        User Layer                           │
│                                                             │
│  ┌────────────────┐  ┌────────────────┐  ┌──────────────┐  │
│  │ Windows Client │  │    Web UI       │  │ Mobile Browser│  │
│  │      EXE       │  │   HTML / JS    │  │ Responsive Web│  │
│  └───────┬────────┘  └───────┬────────┘  └──────┬───────┘  │
└──────────┼────────────────────┼───────────────────┼─────────┘
           │                    │                   │
           └────────────────────┼───────────────────┘
                                │ HTTP / HTTPS
                                ▼
┌─────────────────────────────────────────────────────────────┐
│                       Server Layer                           │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐ │
│  │                FastAPI Backend Service                │ │
│  │                                                       │ │
│  │ Filament │ Device │ Weighing │ OTA │ User │ API Key │ │
│  └───────────────────────────────────────────────────────┘ │
│                                                             │
│      SQLite (Windows) / MySQL (Linux) / Firmware Storage    │
└─────────────────────────────────────────────────────────────┘
                                │
                                │ HTTP
                                ▼
┌─────────────────────────────────────────────────────────────┐
│                       Hardware Layer                         │
│                                                             │
│            Siheng - ESP32-S3 Smart Scale                   │
│                                                             │
│       HX711 │ OLED │ PN532 │ WS2812 │ WiFi                  │
└─────────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### ⭐ Regular Windows Users

**No need to install Python or configure a development environment.**

If you just want to use this project, simply download the Windows version provided in GitHub Releases.

The Windows version includes:
- **Windows Server EXE**
- **Windows Client EXE**

Recommended installation/usage order:

```text
① Download Windows Server
        ↓
② Launch Server EXE
        ↓
③ Access server address in browser
        ↓
④ Register/Login account
        ↓
⑤ Download and launch Windows Client EXE
        ↓
⑥ Fill in server address in client
        ↓
⑦ Start managing 3D printing filaments
```

> ⚠️ Windows Server and Client are two separate programs.
>
> The Server is responsible for database, API, filament management, and ESP32 device communication.
>
> The Client provides the Windows desktop interface.

---

## 🪟 Windows Server

### Method 1: Use EXE Directly (Recommended)

Windows users don't need to install Python.

Download the latest Windows Server archive from GitHub Releases.

Example:
```text
BambuFilamentManagerPro-Server-Windows-x64.zip
```

After extraction:
```text
BambuFilamentManagerPro-Server/
├── BambuFilamentManagerPro-Server.exe
├── data/
├── firmware/
├── config/
└── README.txt
```

Double-click:
```text
BambuFilamentManagerPro-Server.exe
```

to launch the server.

By default, the server listens on:
```text
http://127.0.0.1:8000
```

Access in browser:
```text
http://127.0.0.1:8000
```

API Documentation:
```text
http://127.0.0.1:8000/docs
```

### LAN Access

If you need to let phones, other computers, or ESP32 access this Windows computer:

```text
http://YourComputerLANIP:8000
```

Example:
```text
http://192.168.1.100:8000
```

If you can't access it, check if Windows Firewall allows port `8000`.

### Windows Server Data

The Windows version uses SQLite by default, therefore:

**No need to install MySQL.**

After the program runs, the database and related data are saved in the data directory of the server program.

It's recommended not to delete:
```text
data/
```

Otherwise, it may cause loss of filament, user, and device data.

---

## 🖥️ Windows Client

### Method 1: Use EXE Directly (Recommended)

Regular users don't need to install Python.

Download from GitHub Releases:
```text
BambuFilamentManagerPro-Client-Windows-x64.zip
```

After extraction:
```text
BambuFilamentManagerPro-Client/
├── BambuFilamentManagerPro-Client.exe
├── config/
└── README.txt
```

Double-click:
```text
BambuFilamentManagerPro-Client.exe
```

to launch the Windows client.

### 🔗 First Time Connecting to Server

After the client launches for the first time, you need to fill in the server address.

If server and client are on the same computer:
```text
http://127.0.0.1:8000
```

If server runs on another computer:
```text
http://192.168.1.100:8000
```

Fill in and connect to the server.

After that, you can use features such as:
- Filament inventory
- Smart weighing
- Data statistics
- ESP32 management
- OTA firmware management
- API Key management
- Restock list

---

## 🔧 Windows Developer Mode

If you are a developer, or need to modify the source code, you can run directly with Python source code.

### Requirements
- Python 3.8+
- Windows 10/11

### Server
```bash
pip install -r requirements.txt
python server.py
```

### Client
```bash
pip install customtkinter requests Pillow
python client.py
```

> Regular users don't need to execute the above steps.
>
> **Just use the EXE provided in Releases.**

---

## 🐧 Linux Deployment

Linux users are recommended to use Docker deployment, or manual deployment with Python source code.

### 🐳 Docker Deployment (Recommended)

This project has built a Docker image, hosted on GitHub Container Registry.

**Image Address**: `ghcr.io/fabie250/bambu-filament-managerpro:latest`

#### 1. Create Project Directory

```bash
mkdir -p /opt/bambu-filament
cd /opt/bambu-filament
```

#### 2. Create Compose File

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  filament-api:
    image: ghcr.io/fabie250/bambu-filament-managerpro:latest
    container_name: filament-api
    restart: unless-stopped
    environment:
      # Database config (MySQL 8.0+ recommended)
      - DB_HOST=YourDatabaseIP
      - DB_PORT=3306
      - DB_USER=YourDatabaseUsername
      - DB_PASSWORD=YourDatabasePassword
      - DB_NAME=filament_db
      # JWT secret (please customize a complex random string)
      - SECRET_KEY=PleaseCustomizeAComplexRandomString
      # Server config
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

#### 3. One-Click Start

```bash
docker-compose up -d
```

The system will automatically download the latest image from GitHub and start the service.

#### 4. View Logs

```bash
docker-compose logs -f
```

#### 5. Access System

After startup, access in browser:

- Web Console: `http://YourServerIP:8000`
- API Documentation: `http://YourServerIP:8000/docs`

---

### 📦 Docker Run Single Command

If you don't want to use docker-compose, you can directly use docker run:

```bash
docker run -d \
  --name filament-api \
  --restart unless-stopped \
  -p 8000:8000 \
  -v /opt/bambu-filament/data:/app/data \
  -v /opt/bambu-filament/firmware:/app/firmware \
  -e DB_HOST=YourDatabaseIP \
  -e DB_PORT=3306 \
  -e DB_USER=YourDatabaseUsername \
  -e DB_PASSWORD=YourDatabasePassword \
  -e DB_NAME=filament_db \
  -e SECRET_KEY=YourCustomSecret \
  ghcr.io/fabie250/bambu-filament-managerpro:latest
```

---

### 🖥️ 1Panel Quick Deployment

If you use the 1Panel visual panel, it's even simpler:

1. Go to left menu **Container → Compose → Create Compose**
2. Paste the `docker-compose.yml` config above into the code box
3. Modify the corresponding database username/password and SECRET_KEY
4. Click **Save and Start**, the panel will automatically pull the image and complete deployment

---

### 🔄 Docker Upgrade Process

```bash
# Pull latest image
docker-compose pull

# Restart container
docker-compose up -d

# View logs to confirm successful startup
docker-compose logs -f
```

---

### 💾 Data Backup

```bash
# Backup data directory
tar -czvf filament-backup-$(date +%Y%m%d).tar.gz ./data ./firmware

# MySQL backup (if using external MySQL)
mysqldump -h DatabaseIP -u Username -p filament_db > filament_db_$(date +%Y%m%d).sql
```

---

### 📝 Python Source Manual Deployment

If you don't want to use Docker, you can also deploy manually:

```bash
# Clone repository
git clone https://github.com/fabie250/bambu-filament-managerPro.git
cd bambu-filament-managerPro

# Install dependencies
pip install -r requirements.txt

# Initialize database
python -c "from main import Base, engine; Base.metadata.create_all(bind=engine)"

# Start service
uvicorn main:app --host 0.0.0.0 --port 8000
```

MySQL 8.0+ is recommended for Linux.

---

## ⚙️ Server Configuration

### Windows

Windows EXE version uses by default:
```text
SQLite
```

No need to install MySQL.

### Linux

Linux recommends using:
```text
MySQL 8.0+
```

Environment variable description:

| Environment Variable | Description | Example Value |
|---------------------|-------------|---------------|
| `DB_HOST` | Database address | `127.0.0.1` |
| `DB_PORT` | Database port | `3306` |
| `DB_USER` | Database username | `root` |
| `DB_PASSWORD` | Database password | `your_password` |
| `DB_NAME` | Database name | `filament_db` |
| `SECRET_KEY` | JWT encryption secret (must change) | `your-secret-key-change-this` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access Token expiry (minutes) | `30` |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Refresh Token expiry (days) | `7` |
| `SERVER_HOST` | Service listen address | `0.0.0.0` |
| `SERVER_PORT` | Service listen port | `8000` |

---

## ⚖️ Siheng - Smart Scale

This project is paired with the ESP32-S3 smart scale:

**Project Address**: https://github.com/fabie250/siheng

The Siheng node is responsible for:
- HX711 precision weighing
- NFC filament identification
- OLED display
- WiFi communication
- Weighing data reporting
- Heartbeat reporting
- Remote commands
- OTA firmware upgrade

---

## 📡 Network Connection Diagram

Recommended network structure:

```text
                 ┌──────────────────────┐
                 │  Windows Server EXE  │
                 │      :8000           │
                 └──────────┬───────────┘
                            │
                ┌───────────┼───────────┐
                │           │           │
                ▼           ▼           ▼
        WindowsClient   MobileBrowser  SihengESP32
            EXE
```

As long as these devices are on a network that can access each other.

For example, Windows computer IP:
```text
192.168.1.100
```

Server:
```text
http://192.168.1.100:8000
```

Then:
- Windows Client connects to `http://192.168.1.100:8000`
- Mobile browser accesses `http://192.168.1.100:8000`
- Siheng ESP32 configures server address as `http://192.168.1.100:8000`

---

## 📦 GitHub Releases

It's recommended to provide for each version release:

```text
BambuFilamentManagerPro/
│
├── Windows/
│   ├── BambuFilamentManagerPro-Server-Windows-x64.zip
│   └── BambuFilamentManagerPro-Client-Windows-x64.zip
│
├── Linux/
│   └── Docker deployment instructions
│
└── Source/
    └── Source code.zip
```

Windows users only need to download:
```text
Server-Windows-x64.zip
Client-Windows-x64.zip
```

No need to download Python source code, and no need to install Python.

---

## 📁 Project Structure

```text
bambu-filament-managerPro/
│
├── server/
│   ├── main.py                 # Linux server (MySQL)
│   ├── server.py               # Windows server (SQLite)
│   ├── requirements.txt        # Python dependencies
│   └── Dockerfile              # Docker build file
│
├── client/
│   └── client.py               # Windows CTk client
│
├── web/
│   └── index.html              # Frontend web (single file)
│
├── docs/
│   ├── API.md                  # API documentation
│   ├── DEPLOY.md               # Deployment guide
│   └── HARDWARE.md             # Hardware wiring guide
│
├── .env.example                # Environment variable example
├── docker-compose.yml          # Docker Compose config
├── CHANGELOG.md                # Changelog
├── LICENSE                     # GPLv3 license
└── README.md                   # Project description
```

> EXE files in `build/` don't need to be committed directly to the Git repository.
>
> It's recommended to publish Windows EXE through GitHub Releases.

---

## 🔄 Version Updates

The project provides simultaneously:
- Windows Server EXE updates
- Windows Client EXE updates
- Web UI updates
- Siheng ESP32 firmware OTA updates
- Docker image updates

Windows users only need to download the latest Release.

If using an older version server, please upgrade the server first, then upgrade the client.

Docker users can upgrade by executing `docker-compose pull && docker-compose up -d`.

---

## ❓ FAQ

### Q: Can't access in browser after Windows Server starts?
A: Check if another program is using port 8000, or if Windows Firewall is blocking it. You can try changing the port number.

### Q: ESP32 can't connect to server?
A: Ensure ESP32 and server are on the same LAN, check if server address and port are correct, and if API Key is filled in correctly.

### Q: Database connection fails after Docker starts?
A: Check if DB_HOST is accessible from inside the container. If MySQL is also in Docker, it's recommended to use container name or docker network connection.

### Q: Will data be lost?
A: Windows data is in the `data/` directory, Docker data is in the mounted volume. As long as these directories are not deleted, data won't be lost. Regular backup is recommended.

### Q: Can multiple people use it?
A: Multi-user registration is supported. Each user's data is isolated from each other, and they can only see their own filaments.

---

## 📜 License

This project is open source under the **GNU General Public License v3.0 (GPLv3)**.

```text
Bambu Filament Manager Pro - 3D Printing Filament Full Lifecycle Management System
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

See the [`LICENSE`](LICENSE) file for details.

---

## 📮 Contact

- **Author**: fabie
- **Project Address**: https://github.com/fabie250/bambu-filament-managerPro
- **Companion Firmware**: https://github.com/fabie250/siheng
- **Issue Feedback**: [GitHub Issues](https://github.com/fabie250/bambu-filament-managerPro/issues)

---

## 🙏 Acknowledgments

- [FastAPI](https://fastapi.tiangong.com/) - High-performance Python Web framework
- [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) - Modern Python GUI library
- [U8g2](https://github.com/olikraus/u8g2) - ESP32 OLED display library
- [HX711](https://github.com/bogde/HX711) - Weighing sensor library
- [WiFiManager](https://github.com/tzapu/WiFiManager) - ESP32 smart config library
- [Bambu Lab](https://bambulab.com/) - Excellent 3D printing equipment

---

**If this project is helpful to you, welcome to give a Star ⭐ to support!**
