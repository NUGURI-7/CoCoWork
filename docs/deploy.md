# 镜像构建与部署指南

> 本机 macOS / Apple Silicon（arm64），目标服务器 linux/amd64。
> 必须交叉构建 amd64 镜像，否则推上去服务器跑不起来。
> Registry：`crpi-cwyvl6vckkv4k4p7.cn-hangzhou.personal.cr.aliyuncs.com/nuguri_ddd/cocowork`

## 一句话流程

构建前先跑通前端 `npm run build`（Dockerfile 第一阶段会跑 `tsc -b`，TS 报错会让整个镜像构建失败）→ `buildx` 交叉构建 amd64 并直接 `--push` 到 registry（不留本地镜像）→ 服务器 `docker compose pull && up`。

## 前置（一次性）

```bash
# 1. 启动 Docker Desktop（daemon 没起，buildx 会连不上 docker API）

# 2. buildx builder：需要 docker-container 驱动才能跨平台 + 直接 push
#    本机已有 multibuilder（默认）。新机器上从零创建：
docker buildx create --name multibuilder --driver docker-container --use
docker buildx ls   # 确认目标 builder 带 * 且 driver 为 docker-container

# 3. 登录阿里云 registry
docker login crpi-cwyvl6vckkv4k4p7.cn-hangzhou.personal.cr.aliyuncs.com
```

## 构建 + 推送

```bash
cd <项目根目录>   # 含 Dockerfile

docker buildx build \
  --platform linux/amd64 \
  -t crpi-cwyvl6vckkv4k4p7.cn-hangzhou.personal.cr.aliyuncs.com/nuguri_ddd/cocowork:latest \
  --push .
```

标志说明：

- `--platform linux/amd64` — 在 arm64 本机交叉构建出服务器要的 amd64 镜像（Docker Desktop 自带 QEMU 模拟，无需额外安装）。
- `--push` — buildkit 构建完直接把 manifest + layers 推到 registry，**不会 `--load` 进本地镜像库**（`docker images` 里不会有镜像本体，只留 build cache 层）。
- 必须用 `docker buildx build`，不能用旧的 `docker build`：`--push` 与跨平台输出是 buildx 的能力。

## 服务器部署

`docker-compose.yml` 已指向上述 image，所以服务器侧只需拉新镜像重启：

```bash
docker compose pull        # 拉 registry 上的 :latest
docker compose up -d        # 重建容器（compose 内含 tortoise migrate）
```

> compose 的 `command` 已是 `sh -c "tortoise migrate && exec uvicorn ..."`，
> 容器启动会先跑数据库迁移再起服务，无需手动迁移。

## 常见坑

- **daemon 没起**：`docker buildx ls` 全报 `failed to connect to the docker API ... daemon running?` → 打开 Docker Desktop，等托盘图标变绿。
- **前端 TS 报错**：Dockerfile 第一阶段 `npm run build` 跑 `tsc -b`，任何类型错误都会让镜像构建在 frontend-builder 阶段失败。改前端后先本地 `cd frontend && npm run build` 验证。
- **lock 不同步**：后端 `uv sync --frozen` 要求 `uv.lock` 与 `pyproject.toml` 一致，改依赖后先 `uv lock` 再构建（`uv lock --check` 可校验）；前端 `npm ci` 要求 `package-lock.json` 在场且一致。
- **推成了 arm64**：忘了 `--platform linux/amd64`，服务器拉下来起容器报 `exec format error`。
