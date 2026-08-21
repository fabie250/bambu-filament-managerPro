# Bambu Filament Manager Pro

> 3D打印耗材全生命周期管理系统 - 专业版
>
> 从耗材入库、使用追踪、余量校准到补货提醒，一站式管理你的3D打印耗材。配合「丝衡」智能称重节点，实现物理重量与账面数据实时同步。

![License](https://img.shields.io/badge/license-GPLv3-blue.svg)
![Python](https://img.shields.io/badge/python-3.8+-green.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-orange.svg)
![MySQL](https://img.shields.io/badge/MySQL-8.0+-blue.svg)
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

```
┌─────────────────────────────────────────────────────────────┐
│                        用户层                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │  Windows 客户端 │  │   网页端      │  │   手机浏览器      │  │
│  │  (CustomTkinter)│  │  (原生HTML/JS)│  │  (响应式网页)    │  │
│  └──────┬───────┘  └──────┬───────┘  └────────┬─────────┘  │
└─────────┼───────────────────┼─────────────────────┼────────────┘
          │                   │                     │
          └───────────────────┼─────────────────────┘
                              │ HTTP/HTTPS
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                       服务端层                                │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              FastAPI 后端服务                          │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐ │   │
│  │  │ 耗材管理  │ │ 设备管理  │ │ 称重管理  │ │ OTA管理 │ │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └────────┘ │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐            │   │
│  │  │ 用户鉴权  │ │ API Key  │ │ 统计分析  │            │   │
│  │  └──────────┘ └──────────┘ └──────────┘            │   │
│  └──────────────────────────────────────────────────────┘   │
│         │              │              │                       │
│         ▼              ▼              ▼                       │
│  ┌──────────┐   ┌──────────┐  ┌──────────┐                 │
│  │  MySQL   │   │ SQLite   │  │ 固件存储  │                 │
│  │ (Linux)  │   │(Windows) │  │ (本地/OSS)│                 │
│  └──────────┘   └──────────┘  └──────────┘                 │
└─────────────────────────────────────────────────────────────┘
                              │ HTTP
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      硬件层                                   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │          丝衡 - ESP32-S3 智能称重节点                 │   │
│  │  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐      │   │
│  │  │ HX711  │ │ OLED   │ │ PN532  │ │ WS2812 │      │   │
│  │  │ 称重    │ │ 显示屏  │ │ NFC    │ │ RGB灯  │      │   │
│  │  └────────┘ └────────┘ └────────┘ └────────┘      │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## 🚀 快速开始

### 环境要求

- **Python**：3.8 或更高版本
- **操作系统**：Windows 10/11 或 Linux（Ubuntu 20.04+ / Debian 11+）
- **数据库**：
  - Linux：MySQL 8.0+（推荐）
  - Windows：SQLite（内置，无需额外安装）
- **硬件**（可选）：ESP32-S3 开发板 + HX711 + OLED + PN532

### Linux 部署（Docker 推荐）

```bash
# 克隆仓库
git clone https://github.com/你的用户名/bambu-filament-managerPro.git
cd bambu-filament-managerPro

# 配置数据库
cp .env.example .env
# 编辑 .env，填写 MySQL 连接信息

# 构建并启动
docker-compose up -d

# 访问
# 网页端：http://localhost:8000
# API 文档：http://localhost:8000/docs
```

### Linux 部署（手动）

```bash
# 安装依赖
pip install -r requirements.txt

# 初始化数据库
python -c "from main import Base, engine; Base.metadata.create_all(bind=engine)"

# 启动服务
uvicorn main:app --host 0.0.0.0 --port 8000
```

### Windows 部署

```bash
# 安装依赖
pip install -r requirements.txt

# 启动服务（自动使用 SQLite）
python server3.1.0.py
```

### Windows 客户端

```bash
# 安装依赖
pip install customtkinter requests Pillow

# 运行客户端
python BambuFilamentStudio_v3.1.0.py
```

---

## ⚙️ 配置说明

### 环境变量（.env）

```env
# 数据库配置（Linux MySQL）
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=filament_db

# JWT 配置
SECRET_KEY=your-secret-key-change-this
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# 服务配置
SERVER_HOST=0.0.0.0
SERVER_PORT=8000
```

### 智能称重节点配置

ESP32 固件采用 WiFiManager 配网，无需硬编码配置：

1. 首次开机自动进入配网模式，OLED 显示热点名
2. 手机连接热点 `Siheng_Scale_XXXX`
3. 浏览器访问 `192.168.4.1`
4. 填写 WiFi 密码、服务器地址、API Key
5. 保存后自动重启连接

---

## 📱 功能模块详解

### 1. 耗材台账

- 录入耗材信息：品牌、材质、颜色、初始重量、当前重量、空盘皮重、价格
- NFC UID 绑定：扫描耗材盘 NFC，自动关联
- 搜索筛选：按品牌、材质、颜色、剩余量筛选
- 批量操作：批量导入导出、批量调整重量

### 2. 设备管理（AMS）

- 打印机管理：添加打印机，记录型号、IP地址
- AMS 仓位管理：多仓位耗材实时状态
- 打印记录：每次打印自动记录使用的耗材和用量
- 远程控制：（待开发）连接 Bambu Studio API 远程控制

### 3. 数据洞察

- 耗材使用趋势：按日/周/月统计使用量
- 成本分析：单卷耗材成本、单次打印成本
- 损耗统计：打印失败率、废料总量
- 库存预警：低于阈值自动提醒补货

### 4. 补货清单

- 自动生成：低库存耗材自动加入补货清单
- 购买链接：一键跳转购买页面
- 价格对比：记录历史价格，提醒涨价
- 采购统计：月度/季度采购花费

### 5. 智能称重工作台

- 实时称重：放上耗材自动识别，显示实测重量
- 账面对比：并排显示系统理论剩余 vs 秤端实测剩余
- 误差标注：负数标红（少了），正数标绿（多了）
- 三种操作：
  - 🔴 打印失败纠正：记录废料，覆盖重量
  - 🔵 常规误差同步：日常累积误差校准
  - 🟢 新料盘/重置皮重：新耗材入库，录入空盘重量

### 6. ESP 管理

- 设备列表：所有在线设备状态一览
- 屏幕预览：实时显示 ESP32 OLED 画面
- 页面切换：远程切换称重/设备信息/WiFi状态页面
- 远程重启：一键重启设备
- 重置配网：远程清除配置，重新进入配网模式
- 固件管理：上传固件，发布 OTA 更新
- 升级日志：查看 OTA 升级进度和结果

### 7. API 密钥

- 生成 API Key：用于脚本和设备接入
- 密钥管理：查看、禁用、删除 API Key
- 权限控制：每个 API Key 关联对应用户
- 使用日志：（待开发）API 调用记录

---

## 🔌 API 文档

启动服务后访问 `http://localhost:8000/docs` 查看完整的 Swagger API 文档。

### 主要接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/auth/register` | POST | 用户注册 |
| `/api/auth/login` | POST | 用户登录 |
| `/api/auth/api-keys` | POST | 生成 API Key |
| `/api/filaments` | GET | 获取耗材列表 |
| `/api/filaments` | POST | 添加耗材 |
| `/api/filaments/{id}` | PUT | 更新耗材 |
| `/api/filaments/{id}` | DELETE | 删除耗材 |
| `/api/scale/report` | POST | ESP32 称重数据上报 |
| `/api/scale/status` | GET | 获取待确认称重记录 |
| `/api/scale/correct` | POST | 确认/纠正称重数据 |
| `/api/scale/heartbeat` | POST | 设备心跳上报 |
| `/api/scale/device/status` | GET | 获取设备状态 |
| `/api/scale/device/command` | POST | 下发远程指令 |
| `/api/scale/device/pending_command` | GET | 获取待执行指令 |
| `/api/scale/ota_check` | POST | 检查固件更新 |
| `/api/ingest/script-filaments` | GET | 脚本同步耗材数据 |

---

## ⚖️ 丝衡 - 智能称重节点

本项目配套的 ESP32-S3 智能称重节点固件，独立仓库：

**项目地址**：https://github.com/fabie250/siheng

### 硬件清单

| 组件 | 型号 | 说明 |
|------|------|------|
| 主控 | ESP32-S3-Zero | 4MB Flash + 2MB PSRAM |
| 称重 | HX711 + 悬臂梁传感器 | 5kg 量程，精度 0.1g |
| 显示 | OLED 1.3寸 SH1106 | 128x64，I2C，黄蓝双色 |
| NFC | PN532 | I2C 接口，读取耗材 NFC UID |
| 电源 | 锂电池 3.7V + TP4056 | 充电保护一体板 |

### 引脚定义

| ESP32-S3 | 外设 | 说明 |
|-----------|------|------|
| GPIO 8 | OLED SDA | I2C 数据 |
| GPIO 9 | OLED SCL | I2C 时钟 |
| GPIO 10 | HX711 DT | 称重数据 |
| GPIO 11 | HX711 SCK | 称重时钟 |
| GPIO 21 | WS2812 | RGB 状态灯 |

### 固件功能

- WiFi 智能配网（WiFiManager）
- HTTP POST 称重数据上报
- 30秒心跳 + 10秒指令轮询
- OTA 在线升级（GitHub 镜像加速）
- 远程页面切换（称重/设备信息/WiFi状态）
- 远程重启和重置配网
- Deep Sleep 低功耗模式
- OLED 全中文显示，WiFi 信号格数

---

## 📸 截图

（待补充）

- 耗材台账页面
- 智能称重工作台
- 数据洞察图表
- ESP 管理页面
- Windows 客户端界面
- 丝衡节点实物图

---

## 🛠️ 开发说明

### 项目结构

```
bambu-filament-managerPro/
├── server/
│   ├── main.py                  # Linux 服务端（MySQL）
│   ├── server3.1.0.py          # Windows 服务端（SQLite）
│   ├── requirements.txt         # Python 依赖
│   └── Dockerfile               # Docker 构建文件
├── client/
│   └── BambuFilamentStudio_v3.1.0.py  # Windows CTk 客户端
├── web/
│   └── index.html               # 前端网页（单文件）
├── docs/
│   ├── API.md                   # API 文档
│   ├── DEPLOY.md                # 部署指南
│   └── HARDWARE.md              # 硬件接线指南
├── .env.example                 # 环境变量示例
├── docker-compose.yml           # Docker Compose 配置
├── CHANGELOG.md                 # 更新日志
├── LICENSE                      # GPLv3 协议
└── README.md                    # 项目说明
```

### 开发环境搭建

```bash
# 克隆仓库
git clone https://github.com/你的用户名/bambu-filament-managerPro.git
cd bambu-filament-managerPro

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux
# venv\Scripts\activate   # Windows

# 安装依赖
pip install -r requirements.txt

# 启动开发服务
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 代码规范

- Python：遵循 PEP 8，使用 black 格式化
- 前端：原生 HTML/CSS/JS，不依赖框架
- 注释：关键函数必须有中文注释
- 提交信息：使用中文，格式如 `[模块] 说明`

---

## 📄 更新日志

详见 [CHANGELOG.md](CHANGELOG.md)。

### [3.1.0] - 2026-08-22

#### 新增
- 🎉 Pro 版本首次发布
- ⚖️ 智能称重工作台（账面对比、误差标注、三种纠正模式）
- 📡 ESP32 远程设备管理（心跳、屏幕预览、页面切换、远程重启）
- 🔧 远程初始化重置配网
- 🔄 OTA 在线升级（固件管理、GitHub 镜像加速、MD5校验）
- 📇 NFC 耗材绑定（PN532 支持）
- 📊 对账校准流水（损耗追踪）
- 🔐 API Key 管理（脚本/设备接入）
- 📱 响应式网页端（手机适配）

#### 优化
- 从 bambu-filament-manager 升级，协议改为 GPLv3
- 数据库结构优化，支持多用户数据隔离
- 称重算法优化，增加滤波和校准功能

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

### 贡献流程

1. Fork 本仓库
2. 创建特性分支：`git checkout -b feature/AmazingFeature`
3. 提交更改：`git commit -m '[模块] 添加某个功能'`
4. 推送分支：`git push origin feature/AmazingFeature`
5. 提交 Pull Request

### 开发计划

- [ ] Bambu Studio API 集成，自动同步打印记录
- [ ] 多用户协作，团队共享耗材库
- [ ] 移动端 App（Flutter）
- [ ] 耗材价格爬虫，自动比价
- [ ] 打印质量分析，关联耗材与打印成功率
- [ ] 更多品牌 AMS 支持

---

## 📜 许可证

本项目采用 **GNU General Public License v3.0** 协议开源。

```
Bambu Filament Manager Pro - 3D打印耗材全生命周期管理系统
Copyright (C) 2026  fabie

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
```

详见 [LICENSE](LICENSE) 文件。

---

## 📮 联系方式

- **作者**：fabie
- **项目地址**：https://github.com/你的用户名/bambu-filament-managerPro
- **配套固件**：https://github.com/fabie250/siheng（丝衡 - 智能称重节点）
- **问题反馈**：[提交 Issue](https://github.com/你的用户名/bambu-filament-managerPro/issues)

---

## 🙏 致谢

- [FastAPI](https://fastapi.tiangolo.com/) - 高性能 Python Web 框架
- [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) - 现代化 Python GUI 库
- [U8g2](https://github.com/olikraus/u8g2) - ESP32 OLED 显示库
- [HX711](https://github.com/bogde/HX711) - 称重传感器库
- [WiFiManager](https://github.com/tzapu/WiFiManager) - ESP32 智能配网库
- [Bambu Lab](https://bambulab.com/) - 优秀的3D打印设备

---

**如果这个项目对你有帮助，欢迎给个 Star ⭐ 支持一下！**
