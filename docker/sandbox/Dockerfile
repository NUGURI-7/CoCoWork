# CoCoWork 沙箱镜像 —— skill 脚本的运行环境，不含任何应用代码。
#
# 在仓库根目录构建（skills 是附加构建上下文，指向内置 skill 目录）：
#
#   docker build --build-context skills=backend/app/skills/builtin \
#     -t cocowork-sandbox:0.2 docker/sandbox
#
# 依赖不写死在这里：每个内置 skill 在自己目录里声明 apt.txt（系统包）、requirements.txt（pip）、
# package.json（npm），构建时取并集安装。改了某个 skill 的依赖，只需重新构建，不用改本文件。
# 同一个包在两个 skill 里版本不同时构建直接失败，不悄悄挑一个。
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

# uv：装 pip 依赖用，也留给「skill 自带依赖」的脚本（PEP 723 脚本头）。
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONIOENCODING=utf-8 \
    LANG=C.UTF-8 \
    # skill 脚本在工作区里 require('docx') 时，从这里找到全局安装的 npm 包
    NODE_PATH=/usr/local/lib/node_modules

# 只读挂进依赖清单，不拷 skill 本体（本体在起容器时以只读方式投进 /skills）
RUN --mount=type=bind,from=skills,target=/tmp/skills \
    set -eu; \
    # 系统包：各 skill 的 apt.txt 并集 + 中文字体（PDF 嵌入用）
    pkgs="$(cat /tmp/skills/*/apt.txt 2>/dev/null | sed 's/#.*//' | tr -s ' \n' '\n' | sort -u | tr '\n' ' ')"; \
    apt-get update; \
    apt-get install -y --no-install-recommends fonts-wqy-zenhei $pkgs; \
    rm -rf /var/lib/apt/lists/*; \
    # pip：各 skill 的 requirements.txt 并集，装进系统 Python
    cat /tmp/skills/*/requirements.txt 2>/dev/null | sed 's/#.*//' | grep -v '^\s*$' | sort -u > /tmp/requirements.txt; \
    if [ -s /tmp/requirements.txt ]; then uv pip install --system --no-cache -r /tmp/requirements.txt; fi; \
    # npm：各 skill 的 package.json 依赖并集，版本冲突即失败，全局安装
    node -e ' \
      const fs = require("fs"), path = require("path"); \
      const root = "/tmp/skills", merged = {}; \
      for (const dir of fs.readdirSync(root)) { \
        const file = path.join(root, dir, "package.json"); \
        if (!fs.existsSync(file)) continue; \
        for (const [name, ver] of Object.entries(JSON.parse(fs.readFileSync(file, "utf8")).dependencies || {})) { \
          if (merged[name] && merged[name] !== ver) throw new Error(`${name} 版本冲突：${merged[name]} / ${ver}（${dir}）`); \
          merged[name] = ver; \
        } \
      } \
      fs.writeFileSync("/tmp/npm-packages", Object.entries(merged).map(([n, v]) => `${n}@${v}`).join(" ")); \
    '; \
    if [ -s /tmp/npm-packages ]; then npm install -g --omit=dev $(cat /tmp/npm-packages); npm cache clean --force; fi; \
    rm -f /tmp/requirements.txt /tmp/npm-packages

# 渲染预览图时的字体替换：文件里写的是用户电脑上的中文字体（微软雅黑、宋体等），沙箱里没有，
# fontconfig 默认会退到不含中文的 DejaVu，cairo 又不逐字回退，中文就成了方块。
# 这里把常见中文字体名映射到文泉驿正黑；只影响沙箱里的渲染，文件本身仍写原字体名。
COPY fontconfig-cjk.conf /etc/fonts/conf.d/64-cocowork-cjk.conf

# 非 root 跑（决策 16）。nobody 是 debian 自带的 uid 65534，不必新建。
# 起容器时还会再给一次 --user；这里写上是防「有人不带参数直接 docker run」。
USER nobody

# 起来就挂着等 docker exec —— 一轮回复期间容器一直活着（决策 12）。
# /skills、/workspace、/outputs、/tmp 都是起容器时挂的 tmpfs，docker 会自建挂载点，
# 故此处不 mkdir。
CMD ["sleep", "infinity"]
