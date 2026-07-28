"""沙箱容器启动开销实测（一次性探针脚本，不进产品）。

设计稿 §5 把「容器启动 1-3 秒」标为「经验值，未实测」，而这个数承着三条结论的
重量：决策 11（复用省的几秒不值）、决策 22a（懒启动，1-3 秒可接受）、
§4（不做容器池）。数错了这三条都要重估，所以在接 web 侧之前先量一次。

**量的是「模型第一次调文件工具要干等多久」**，即三段之和：
建+启动容器 → 第一条命令跑通 → 把 skill 灌进 /skills。
另外单量一次「已就绪容器上再跑一条空命令」当基线 —— 远程 daemon 走 paramiko、
没有连接复用，每趟往返约 0.5 秒是固定成本，不剥出来会把网络延迟错记成容器慢。

直接调 container 层，不走 sandboxd 的 HTTP（loopback 那一跳相对可忽略），
所以**不需要 sandboxd 在跑**，但需要 DOCKER_HOST 指向的 daemon 可达、镜像已存在。

用法（在 backend/ 目录下）::

    uv run python -m scripts.probe_sandbox_startup
    uv run python -m scripts.probe_sandbox_startup -n 10 --skill svg-chart
"""

import argparse
import io
import statistics
import tarfile
import time
from contextlib import contextmanager
from pathlib import Path

from app.core.config import settings
from app.sandbox import container as docker_ops

# 与 mount 层一致：skill 目录里的这些东西不该被打进包
_TAR_EXCLUDE = ("__pycache__", ".pyc")

_PHASES = ("create", "first_exec", "upload", "destroy")

_PHASE_LABEL = {
    "create": "建容器 + 启动",
    "first_exec": "第一条命令跑通",
    "upload": "灌 skill 进 /skills",
    "destroy": "销毁",
    "warm_exec": "已就绪容器再跑一条（往返基线）",
}


def _builtin_skill_dir(name: str) -> Path:
    """内置 skill 的源目录。本体在代码里，不查库（决策 3）。"""
    path = Path(__file__).resolve().parent.parent / "app" / "skills" / "builtin" / name
    if not path.is_dir():
        raise SystemExit(f"内置 skill 不存在：{path}")
    return path


def _tar_bytes(src: Path) -> bytes:
    """把一个 skill 目录打成 tar 字节，形状与 web 侧将来要灌的一致。"""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        for item in sorted(src.rglob("*")):
            if any(part in _TAR_EXCLUDE or part.endswith(_TAR_EXCLUDE) for part in item.parts):
                continue
            tar.add(item, arcname=str(Path(src.name) / item.relative_to(src)))
    return buf.getvalue()


@contextmanager
def _timed(bucket: dict[str, float], phase: str):
    start = time.perf_counter()
    yield
    bucket[phase] = time.perf_counter() - start


def _one_round(session_id: str, skill_tar: bytes) -> dict[str, float]:
    """跑一轮完整借还，返回各段耗时（秒）。"""
    took: dict[str, float] = {}

    with _timed(took, "create"):
        instance = docker_ops.create_container(session_id, env={})

    try:
        with _timed(took, "first_exec"):
            docker_ops.exec_command(instance, "true", timeout=30)

        with _timed(took, "upload"):
            docker_ops.upload(instance, "/skills", skill_tar)

        # 基线：容器早就绪、skill 也灌完了，这一条纯粹是一趟往返 + 进程 fork
        with _timed(took, "warm_exec"):
            docker_ops.exec_command(instance, "true", timeout=30)
    finally:
        with _timed(took, "destroy"):
            docker_ops.destroy(instance)

    return took


def _report(rounds: list[dict[str, float]]) -> None:
    print(f"\n{'':<32}{'中位':>8}{'最快':>8}{'最慢':>8}")
    for phase in (*_PHASES, "warm_exec"):
        samples = [r[phase] for r in rounds if phase in r]
        if not samples:
            continue
        print(
            f"{_PHASE_LABEL[phase]:<30}"
            f"{statistics.median(samples):>8.2f}"
            f"{min(samples):>8.2f}"
            f"{max(samples):>8.2f}"
        )

    # 决策 22a 关心的就是这个和：模型第一次碰文件工具，要干等多久
    blocking = [sum(r[p] for p in ("create", "first_exec", "upload")) for r in rounds]
    baseline = [r["warm_exec"] for r in rounds if "warm_exec" in r]

    print(f"\n首次调用阻塞时长（前三段之和）中位 {statistics.median(blocking):.2f}s")
    if baseline:
        print(
            f"  其中约 {statistics.median(baseline):.2f}s/趟 是传输层往返固定成本，"
            f"本机 unix socket 下会显著更低"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="沙箱容器启动开销实测")
    parser.add_argument("-n", type=int, default=5, help="跑几轮，默认 5")
    parser.add_argument("--skill", default="svg-chart", help="拿哪个内置 skill 打包，默认 svg-chart")
    args = parser.parse_args()

    skill_dir = _builtin_skill_dir(args.skill)
    skill_tar = _tar_bytes(skill_dir)

    print(f"daemon   : {settings.SANDBOX_DOCKER_HOST or '本机 docker.sock'}")
    print(f"镜像     : {settings.SANDBOX_IMAGE}")
    print(f"skill 包 : {args.skill}（{len(skill_tar) / 1024:.1f} KB）")
    print(f"轮数     : {args.n}")

    docker_ops.ensure_network()

    rounds: list[dict[str, float]] = []
    for i in range(1, args.n + 1):
        took = _one_round(f"probe-{int(time.time())}-{i}", skill_tar)
        rounds.append(took)
        detail = "  ".join(f"{p}={took[p]:.2f}s" for p in (*_PHASES, "warm_exec"))
        print(f"第 {i} 轮  {detail}")

    _report(rounds)


if __name__ == "__main__":
    main()
