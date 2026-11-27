#!/usr/bin/env bash
set -Eeuo pipefail

REPO_OWNER="${SIHENG_REPO_OWNER:-fabie250}"
REPO_NAME="${SIHENG_REPO_NAME:-bambu-filament-managerPro}"
BRANCH="${SIHENG_BRANCH:-main}"
INSTALL_DIR="${SIHENG_DIR:-/opt/siheng}"
APP_DIR="$INSTALL_DIR/app"
DATA_DIR="$INSTALL_DIR/data"
ENV_FILE="$APP_DIR/deploy/.env"

log() { printf '\033[1;32m[丝衡]\033[0m %s\n' "$*"; }
die() { printf '\033[1;31m[错误]\033[0m %s\n' "$*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "请用 root 运行：curl -fsSL ... | sudo bash"
command -v curl >/dev/null 2>&1 || die "缺少 curl"
command -v openssl >/dev/null 2>&1 || die "缺少 openssl"

if ! command -v docker >/dev/null 2>&1; then
  if [ "${SIHENG_SKIP_DOCKER_INSTALL:-0}" = "1" ]; then
    die "未检测到 Docker，已跳过自动安装。请先安装 Docker Engine 和 Compose v2。"
  fi
  log "未检测到 Docker，使用 Docker 官方脚本安装..."
  curl -fsSL https://get.docker.com | sh
  command -v docker >/dev/null 2>&1 || die "Docker 安装失败"
  if command -v systemctl >/dev/null 2>&1; then
    systemctl enable --now docker >/dev/null 2>&1 || true
  fi
fi

if ! docker info >/dev/null 2>&1; then
  if command -v systemctl >/dev/null 2>&1; then
    systemctl start docker >/dev/null 2>&1 || true
  fi
  docker info >/dev/null 2>&1 || die "Docker 已安装但没有运行"
fi

if ! docker compose version >/dev/null 2>&1; then
  die "未检测到 Docker Compose v2。请安装 docker-compose-plugin 后重试。"
fi
COMPOSE=(docker compose)

mkdir -p "$INSTALL_DIR" "$DATA_DIR/firmware"
chmod 700 "$INSTALL_DIR"

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

if [ -f "$ENV_FILE" ]; then
  cp "$ENV_FILE" "$TMP_DIR/env.backup"
fi

rm -rf "$APP_DIR"

CLONED=0
if command -v git >/dev/null 2>&1; then
  log "拉取源码：$REPO_OWNER/$REPO_NAME@$BRANCH"
  if GIT_TERMINAL_PROMPT=0 git -c http.version=HTTP/1.1 clone --depth 1 --branch "$BRANCH" "https://github.com/$REPO_OWNER/$REPO_NAME.git" "$APP_DIR"; then
    CLONED=1
  else
    log "git clone 失败，尝试源码压缩包..."
    rm -rf "$APP_DIR"
  fi
fi

if [ "$CLONED" != "1" ]; then
  command -v tar >/dev/null 2>&1 || die "缺少 tar，且 git clone 失败"
  log "下载源码压缩包..."
  ARCHIVE="$TMP_DIR/repo.tar.gz"
  SOURCE_URL="${SIHENG_SOURCE_URL:-https://github.com/$REPO_OWNER/$REPO_NAME/releases/latest/download/siheng-source.tar.gz}"
  curl -fsSL --connect-timeout 15 --max-time 180 "$SOURCE_URL" -o "$ARCHIVE" || die "源码下载失败，请检查服务器能否访问 GitHub，或用 SIHENG_SOURCE_URL 指定源码包地址"
  mkdir -p "$TMP_DIR/src"
  tar -xzf "$ARCHIVE" -C "$TMP_DIR/src"
  SRC_DIR="$(find "$TMP_DIR/src" -mindepth 1 -maxdepth 1 -type d | head -n 1)"
  [ -n "$SRC_DIR" ] || die "源码解压失败"
  mkdir -p "$APP_DIR"
  cp -a "$SRC_DIR/." "$APP_DIR/"
fi

[ -f "$APP_DIR/Dockerfile" ] || die "源码缺少 Dockerfile"

if [ -f "$TMP_DIR/env.backup" ]; then
  mkdir -p "$APP_DIR/deploy"
  cp "$TMP_DIR/env.backup" "$ENV_FILE"
  chmod 600 "$ENV_FILE"
fi

if [ ! -f "$ENV_FILE" ]; then
  MYSQL_ROOT_PASSWORD="$(openssl rand -hex 24)"
  JWT_SECRET="$(openssl rand -hex 32)"
  PORT="${SIHENG_PORT:-8000}"
  case "$PORT" in
    *[!0-9]*|'') die "SIHENG_PORT 必须是数字端口" ;;
  esac
  umask 077
  cat > "$ENV_FILE" <<EOF
MYSQL_ROOT_PASSWORD=$MYSQL_ROOT_PASSWORD
JWT_SECRET=$JWT_SECRET
SERVER_PORT=$PORT
EOF
  chmod 600 "$ENV_FILE"
  log "已生成随机数据库密码和 JWT 密钥：$ENV_FILE"
else
  PORT="$(sed -n 's/^SERVER_PORT=//p' "$ENV_FILE" | head -n 1)"
  PORT="${PORT:-8000}"
  if [ -n "${SIHENG_PORT:-}" ]; then
    case "$SIHENG_PORT" in
      *[!0-9]*|'') die "SIHENG_PORT 必须是数字端口" ;;
    esac
    PORT="$SIHENG_PORT"
    sed -i "s/^SERVER_PORT=.*/SERVER_PORT=$PORT/" "$ENV_FILE"
  fi
  log "保留已有配置：$ENV_FILE"
fi

log "构建并启动容器（首次构建需要几分钟）..."
(
  cd "$APP_DIR"
  "${COMPOSE[@]}" -p siheng -f deploy/docker-compose.yml up -d --build
)

log "等待服务就绪..."
READY=0
for _ in $(seq 1 60); do
  if curl -fsS "http://127.0.0.1:$PORT/api/docs" >/dev/null 2>&1; then
    READY=1
    break
  fi
  sleep 2
done

if [ "$READY" != "1" ]; then
  (
    cd "$APP_DIR"
    "${COMPOSE[@]}" -p siheng -f deploy/docker-compose.yml logs --tail=80 api || true
  )
  die "服务未在 120 秒内就绪，请查看上面的日志"
fi

PUBLIC_IP="$(curl -fsS --max-time 5 https://api.ipify.org 2>/dev/null || true)"
log "安装完成"
log "网页端：http://${PUBLIC_IP:-服务器IP}:$PORT"
log "API 文档：http://${PUBLIC_IP:-服务器IP}:$PORT/api/docs"
log "安装目录：$INSTALL_DIR（配置在 $ENV_FILE，数据在 $DATA_DIR，更新会保留）"