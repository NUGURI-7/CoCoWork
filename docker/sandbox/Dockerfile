# CoCoWork 沙箱镜像 —— skill 脚本的运行环境，不含任何应用代码。
#
#   docker build -t cocowork-sandbox:0.1 docker/sandbox
#
# 加固参数（--read-only / --user / --memory / --cpus / 专用网络）全部在**起容器时**给，
# 一条都不写进镜像 —— 镜像只回答「里面有什么可执行」，隔离归 sandboxd 那一侧（决策 16/17）。

# 必须与下面的 python 镜像同一个 debian 版本，否则拷过去的 node 会撞 glibc
FROM node:22-bookworm-slim AS node

FROM python:3.13-slim-bookworm

# Node：skill 可能是 JS 脚本（决策 16）。从官方 node 镜像整份拷过来而不走 apt ——
# debian 仓库里的 node 常年落后好几个大版本。
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -sf /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm

# uv：给「skill 自带依赖」留的路（PEP 723 脚本头 / requirements.txt 都靠它装），
# 同时**不预装任何重包**。实测本机 36 个真实 skill 无一带第三方依赖，
# 现在预装 pandas/numpy 那套是凭空猜；真需要时加一行重新 build 即可。
# 版本策略同项目根 Dockerfile（同一个官方镜像来源）。
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONIOENCODING=utf-8 \
    LANG=C.UTF-8

# 非 root 跑（决策 16）。nobody 是 debian 自带的 uid 65534，不必新建。
# 起容器时还会再给一次 --user；这里写上是防「有人不带参数直接 docker run」。
USER nobody

# 起来就挂着等 docker exec —— 一轮回复期间容器一直活着（决策 12）。
# /skills、/workspace、/outputs、/tmp 都是起容器时挂的 tmpfs，docker 会自建挂载点，
# 故此处不 mkdir。
CMD ["sleep", "infinity"]
