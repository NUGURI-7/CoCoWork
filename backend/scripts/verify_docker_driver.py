"""LocalDocker driver 端到端验证（手动跑的验证工具，不进 pytest）。

**为什么不做成单元测试**：它要真 docker daemon、真 sandboxd 进程、真数据库。
tests/ 里的东西必须随手就能跑，塞进去会让「跑测试」变成「先备环境」。
纯逻辑那部分（pack_skill_dirs / _pack_tar 的往返 / 降级路径用 MockTransport）
才是单元测试该管的。

验的是 web 侧接线这一整条：`build_skill_mount` 按 driver 造出 DockerSandbox →
懒启动 → skill 灌进容器 → 交付区建好 → 那三个方法 → mount.close() 销毁。
**不含 LLM**，所以失败一定是我们的代码，不会是模型不听话。

前置：sandboxd 在跑（`uv run sandboxd`）、`SANDBOX_DRIVER=docker`、镜像已 build。

用法（在 backend/ 目录下）::

    uv run python -m scripts.verify_docker_driver                      # 按 .env 的 driver
    SANDBOX_DRIVER=local uv run python -m scripts.verify_docker_driver # local 那条的回归
    SANDBOXD_PORT=8101 uv run python -m scripts.verify_docker_driver   # 指到另一个实例
"""

import asyncio
from uuid import uuid4

from app.core.config import settings
from app.core.storage import storage
from app.db.postgresql import pg_client
from app.models import User
from app.models.sandbox import SandboxArtifact
from app.sandbox.container import LABEL_MARKER, get_client
from app.services.sandbox.artifact import collect_artifacts
from app.services.sandbox.docker_sandbox import DockerSandbox
from app.schemas.agent import AgentConfig
from app.services.skill.builtin import load_builtin_skills
from app.services.skill.mount import build_skill_mount

_SKILL = "svg-chart"


def live_containers() -> int:
    """当前在跑的沙箱容器数 —— 懒启动与销毁都靠这个数字证明。"""
    return len(get_client().containers.list(filters={"label": LABEL_MARKER}))


async def main() -> None:
    await pg_client.connect()
    load_builtin_skills()  # 平时由 web 的 lifespan 扫一次，脚本里自己来

    user = await User.all().first()
    if user is None:
        raise SystemExit("库里没有用户，先注册一个再跑")

    cfg = AgentConfig.model_validate({"builtin_skills": [_SKILL]})
    message_id = uuid4()

    mount = await build_skill_mount([cfg], user, scope_id=user.id, message_id=message_id)
    if mount is None:
        raise SystemExit(f"挂了 {_SKILL} 却拿到 None，内置注册表可能没扫到")

    print(f"1. mount 造好  backend={type(mount.backend).__name__}  outputs={mount.paths.outputs}")
    print(f"2. 懒启动     此刻容器数={live_containers()}（应为 0 —— 造对象不该起容器）")

    backend = mount.backend

    skills = mount.paths.skills
    result = backend.execute(f"ls {skills} && echo --- && ls {skills}/{_SKILL}")
    print(f"3. 首条命令   exit={result.exit_code}\n{result.output.strip()}")
    expect = "1 —— 到这一刻才起" if isinstance(backend, DockerSandbox) else "0 —— local driver 不起容器"
    print(f"   此刻容器数={live_containers()}（应为 {expect}）")

    result = backend.execute(
        f"test -d {mount.paths.outputs} && echo 交付区在 && id -un && "
        f"ls -d {mount.paths.workspace} {mount.paths.tmp}"
    )
    print(f"4. 交付区/身份/挂载点  exit={result.exit_code}\n{result.output.strip()}")

    probe = f"{mount.paths.workspace}/hello.txt"
    print(f"5. upload_files      {backend.upload_files([(probe, '你好，容器'.encode())])}")
    print(f"6. read（派生路径）   {backend.read(probe)}")

    downloaded = backend.download_files([probe, f"{mount.paths.workspace}/不存在.txt"])
    print(f"7. download_files    {[(d.path, d.content, d.error) for d in downloaded]}")

    result = backend.execute(
        f"python3 {skills}/{_SKILL}/scripts/bar.py --help > /dev/null 2>&1; echo 退出码=$?"
    )
    print(f"8. 真跑 skill 脚本   {result.output.strip()}")

    await _verify_artifacts(mount, user=user, message_id=message_id)

    await mount.close()
    print(f"13. close 之后       容器数={live_containers()}（应为 0）")


async def _verify_artifacts(mount, *, user: User, message_id) -> None:
    """产物回收：列清单 → 过滤超限 → 取字节 → 入库 → 收完删交付区。

    **跑完自己清干净**：这段会往真实对象存储写文件、往 sandbox_artifacts 写行，
    验证脚本不该在正式桶和正式库里留垃圾。
    """
    backend = mount.backend
    outputs = mount.paths.outputs
    payload = "hello 图表".encode()
    created: list[SandboxArtifact] = []

    async def collect() -> list[SandboxArtifact]:
        got = await collect_artifacts(
            backend, mount.paths, user=user, scope_id=user.id, message_id=message_id
        )
        created.extend(got)
        return got

    def remains() -> str:
        # LocalShellBackend 在命令无输出时回的是字面量 "<no output>"，不是空串 ——
        # 两个 driver 的「什么都没有」长得不一样，判据得同时认这两种
        out = backend.execute(f"ls {outputs} 2>/dev/null | tr '\\n' ' '").output.strip()
        return out if out and out != "<no output>" else "（目录已删）"

    try:
        # 一正常一超限。超限那个用 dd 现造，大小压着 SANDBOX_ARTIFACT_MAX_SIZE 之上
        over_mb = settings.SANDBOX_ARTIFACT_MAX_SIZE // (1024 * 1024) + 1
        backend.execute(
            f"printf '%s' '{payload.decode()}' > {outputs}/chart.svg && "
            f"dd if=/dev/zero of={outputs}/big.bin bs=1M count={over_mb} 2>/dev/null"
        )

        got = await collect()
        names = [a.filename for a in got]
        print(f"9.  回收（含 1 个超限）收到 {names}（应只有 chart.svg）")
        print(f"    交付区剩余        {remains()}（有失败 → 应保留，big.bin 还在）")

        raw = await storage.read(got[0].storage_key) if got else b""
        print(f"10. 存储里读回        {raw!r}  与原始一致={raw == payload}")

        # 第二轮：只留一个正常文件，验「全成功才删交付区」
        backend.execute(f"rm -f {outputs}/big.bin {outputs}/chart.svg && printf 'x' > {outputs}/report.txt")
        got = await collect()
        print(f"11. 回收（全部正常）  收到 {[a.filename for a in got]}")
        print(f"    交付区剩余        {remains()}（全成功 → 应已删除）")
    finally:
        for artifact in created:
            await storage.delete(artifact.storage_key)
            await artifact.delete()
        print(f"12. 清理             删掉 {len(created)} 条测试产物（存储 + 库）")


if __name__ == "__main__":
    asyncio.run(main())
