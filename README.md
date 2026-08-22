# 🐧 Linux 部署 (推荐 Docker)

Linux 用户推荐使用 Docker 进行部署。项目已全线接入 GitHub Actions CI/CD，每次更新都会自动构建最新镜像并推送到 GHCR，无需在本地配置繁琐的 Python 环境和依赖。

## 🐳 Docker / 1Panel 部署 (极力推荐)

新建一个目录，在其中创建一个 `docker-compose.yml` 文件，填入以下内容：

```yaml
services:
  filament-api:
    image: ghcr.io/fabie250/bambu-filament-managerpro:latest
    container_name: filament-api
    restart: always
    deploy:
      resources:
        limits:
          memory: 300M  # 限制内存，防止低配服务器内存泄漏溢出
    environment:
      - DB_HOST=你的数据库IP
      - DB_PORT=3306
      - DB_USER=你的数据库用户名
      - DB_PASS=你的数据库密码
      - DB_NAME=filament_db
      - JWT_SECRET=请修改为你自己的随机复杂字符串
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data          # 挂载本地数据目录
      - ./firmware:/app/firmware  # 挂载固件目录
