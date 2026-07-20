# 服务器基础设施档案

> 两台云服务器：**开发机**（裸 IP、无域名）+ **部署机**（有域名、对外服务）。
> 本文档只记代号与规格，不记 IP / 域名 / 任何凭据。
> 最后体检：2026-07-19（hostnamectl / lscpu / free / df / docker ps 实测输出，非手填）。

## 机器一览

| | 开发机 | 部署机 |
|---|---|---|
| 角色 | 开发共享基础设施（远端 dev DB / Redis） | 生产部署（对外服务） |
| 系统 | CentOS 7（内核 3.10.0-1160，老但稳） | Ubuntu 24.04.3 LTS（内核 6.8） |
| CPU | 2 核 Intel Xeon Gold 6133 @ 2.5GHz | 1 核 AMD EPYC-Rome @ 2.0GHz |
| 内存 | 2G，**swap = 0** | ~1G（961M），swap 2G |
| 磁盘 | 50G（2026-07-19 清理后余 27G） | 8.7G（2026-07-19 清理后约 80%，余 ~1.7G） |
| Docker | 已装 | 29.5.3 |

## 容器清单

### 开发机（CentOS）

| 容器 | 镜像 | 端口绑定 | 说明 |
|---|---|---|---|
| 1Panel-postgresql-1JEO | postgres:18.3-alpine | 0.0.0.0:5432 | **开发主 PG**（1Panel 管理），DaisyWind 与 CoCoWork 共用、仅库名不同（本项目 = `cocowork`）；已启用 pgvector 0.8.1；**RAG 基准数据（医疗/电商）都在这** |
| redis | redis:7 | 0.0.0.0:6379 | 开发共用 Redis |
| cocowork-app-1 | …/nuguri_ddd/cocowork:latest | 0.0.0.0:9000 | CoCoWork 后端（开发机实例） |
| daisywind-app-1 | …/nuguri_ddd/ddd:latest | 0.0.0.0:8000 | DaisyWind 后端 |
| mysql020121 | mysql:8.4.7 | — | 已停约 4 个月 |

### 部署机（Ubuntu）

| 容器 | 镜像 | 端口绑定 | 说明 |
|---|---|---|---|
| cocowork-pg | pgvector/pgvector:pg16 | 127.0.0.1:5432 | **生产 PG**（仅本机可达） |
| cocowork-redis | redis:7-alpine | 127.0.0.1:6379 | 生产 Redis |
| cocowork-app | …/nuguri_ddd/cocowork:latest | 127.0.0.1:8000 | CoCoWork 生产后端 |
| fital-app-1 | …/nuguri_ddd/fital:latest | 0.0.0.0:8002 | FitAl 应用 |
| ~~sillytavern~~ | — | — | 2026-07-19 已删（容器+镜像，回收 ~900M） |

## 资源账本（RAG 基准相关）

- 医疗基准 1 万段（Paragraph + 向量 + HNSW partial 索引）已在开发机 PG，占用很小。
- 全量 96 万段向量 + 索引估算 5-8G：2026-07-19 清理 build cache（回收 16.5G，余 27G）后**不再构成阻碍**。
- 电商基准 1 万段：与医疗同量级，无压力。

## 注意事项 / 风险

1. **开发机 swap=0 且仅 2G 内存**：HNSW 建索引等内存尖峰操作有被 OOM killer 直接杀掉的风险。别调大 PG 的 `maintenance_work_mem`；大批量建索引避开其他负载。
2. **开发机 PG / Redis 绑 0.0.0.0 对公网暴露**（本机开发要远程直连，属有意为之）：PG 保持强密码；Redis 若未设 `requirepass` 建议补上，或用云安全组把 5432/6379 收紧到自己的出口 IP。
3. **部署机磁盘小（8.7G），刚性占用高**：系统 2.2G + swapfile 2G（`/swapfile`，1G 内存机的 OOM 保险，**不许动**）+ 生产栈镜像 ~2.4G，清理后的健康水位就是 ~80%。日常维护：`journalctl --vacuum-size=100M`；镜像更新后旧镜像 prune；`/var/log/sing-box/access.log` 会持续增长，肥了就 `truncate -s 0`。
4. **部署机 SSH 长期被暴力破解**（btmp 曾累积 183M 失败登录记录）：2026-07-19 已装 fail2ban（`jail.local`：10 分钟错 5 次封 1 小时，backend=systemd），装机几分钟即封 4 IP。封禁不影响已建立的会话；自误封等 1 小时或走云控制台 VNC。
5. **部署机有内核更新待重启**：在跑 6.8.0-90，已装好 6.8.0-136 未生效；下次维护窗口重启后可 `apt-get autoremove --purge` 清旧内核（约省几百 M）。
6. **PG 版本错位**：开发 18.3 vs 生产 16。SQL 特性以 **16 为下限**写，避免用到 17+ 才有的语法。
7. **Docker build cache 无自动 GC**：开发机曾累积 16.5G（190 条、最老 15 个月，2026-07-19 清空）。在服务器上 build 镜像后记得 `docker builder prune -a`。
