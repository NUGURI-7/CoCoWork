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

    uv run python -m scripts.verify_docker_driver
    SANDBOXD_PORT=8101 uv run python -m scripts.verify_docker_driver   # 指到另一个实例
"""

import asyncio
from uuid import uuid4

from app.db.postgresql import pg_client
from app.models import User
from app.sandbox.container import LABEL_MARKER, get_client
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

    result = backend.execute(f"ls /skills && echo --- && ls /skills/{_SKILL}")
    print(f"3. 首条命令   exit={result.exit_code}\n{result.output.strip()}")
    print(f"   此刻容器数={live_containers()}（应为 1 —— 到这一刻才起）")

    result = backend.execute(
        f"test -d {mount.paths.outputs} && echo 交付区在 && id -un && ls -d /workspace /tmp"
    )
    print(f"4. 交付区/身份/挂载点  exit={result.exit_code}\n{result.output.strip()}")

    print(f"5. upload_files      {backend.upload_files([('/workspace/hello.txt', '你好，容器'.encode())])}")
    print(f"6. read（派生路径）   {backend.read('/workspace/hello.txt')}")

    downloaded = backend.download_files(["/workspace/hello.txt", "/workspace/不存在.txt"])
    print(f"7. download_files    {[(d.path, d.content, d.error) for d in downloaded]}")

    result = backend.execute(
        f"python3 /skills/{_SKILL}/scripts/bar.py --help > /dev/null 2>&1; echo 退出码=$?"
    )
    print(f"8. 真跑 skill 脚本   {result.output.strip()}")

    await mount.close()
    print(f"9. close 之后        容器数={live_containers()}（应为 0）")


if __name__ == "__main__":
    asyncio.run(main())
