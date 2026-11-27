# Linux 服务端

- `main.py`：Linux / MySQL 后端，含 `surface_effect`、`diameter_mm` 字段和耗材编辑接口。
- `requirements.txt`：运行依赖。

Docker 部署时把本目录挂载到容器 `/app`，启动命令为 `uvicorn main:app --host 0.0.0.0 --port 8000`。数据库、JWT 密钥等通过环境变量传入，不要写进源码。