"""Skill zip 包的解析与校验。

skills_ref 的 API 吃「目录路径」，我们手里是 zip 字节，中间这层胶水负责
把前者变成后者。规范只管「解开之后长什么样」，不管 zip 内部怎么摆，故
两种打包形态都得收，在此归一化。
"""

import posixpath
import io
import zipfile
import tempfile
from pathlib import Path

from skills_ref import SkillError, SkillProperties, read_properties, validate

from app.core.exceptions import ValidationException

# 规范允许两种拼写，skills_ref.find_skill_md 也是这么认的，此处与之保持一致
_SKILL_MD_NAMES = ("SKILL.md", "skill.md")

# SKILL.md 正文上限。规范建议正文控制在 5000 tokens（约 20 KiB）以内，
# 1 MiB 是宽松兜底，不是目标值。Dify 取的同一个数。
_MAX_SKILL_MD_BYTES = 1024 * 1024


def load_skill_manifest(archive: bytes) -> SkillProperties:
    """从 skill zip 里读出并校验 SKILL.md，返回规范定义的元数据。

    skills_ref 的 API 一律吃「目录路径」，故此处把 SKILL.md 落成一个符合
    规范形态的临时目录再喂进去，临时目录随 with 块自动销毁。

    内置 skill seed 与用户上传共用本函数 —— 两者都是「一包字节」，
    不分叉（同 Skill 模型「内置只是启动时 seed 进来的种子数据」那条）。

    Raises:
        ValidationException: zip / SKILL.md 任一环不合规。规范校验失败时
            `data` 携带 validate() 返回的逐条消息，接口原样回给用户。
    """
    content, directory_name = _read_skill_md(archive)
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)

        # 目录名此刻可能还不知道（B 型），先落进一个中转目录
        staging = root / "_staging"
        staging.mkdir()
        (staging / "SKILL.md").write_text(content, encoding="utf-8")

        if directory_name is None:
            # B 型：包里没有「目录名」这个信息，据 frontmatter 的 name 补一个。
            # read_properties 只解析、不做完整校验（官方 docstring 明写
            # "It does NOT perform full validation"），更不查目录名一致性 ——
            # 正是此处所需，完整校验交给下面的 validate()。
            try:
                directory_name = read_properties(staging).name
            except SkillError as exc:
                raise ValidationException(f"SKILL.md 解析失败：{exc}") from exc

        # 目录名来自用户（zip 里的目录名 / frontmatter 的 name），拼进路径前必须自证。
        # 不指望「zip 层会拦」—— 拼路径的这一处对自己的输入负责。
        if (
                directory_name in ("", ".", "..")
                or "/" in directory_name
                or "\\" in directory_name
        ):
            raise ValidationException(f"非法的 skill 目录名：{directory_name!r}")

        skill_dir = root / directory_name
        staging.rename(skill_dir)

        errors = validate(skill_dir)
        if errors:
            raise ValidationException("SKILL.md 不符合 Agent Skills 规范", data=errors)

        return read_properties(skill_dir)

def _read_skill_md(archive: bytes) -> tuple[str, str | None]:
    """打开 zip，取出 SKILL.md 全文与它的父目录名。

    只解 SKILL.md 这一个成员 —— zip bomb 要靠「整包解开」才炸得起来，
    单独掏一个带上限的小文件炸不动。其余成员在 web 进程里一律不碰：
    它们原样传进容器再解（设计稿决策 21a）。

    Returns:
        (SKILL.md 全文, 父目录名)。父目录名语义见 _locate_skill_md。

    Raises:
        ValidationException: 不是合法 zip / 没有 SKILL.md / 正文超限 / 非 UTF-8
    """

    try:
        with zipfile.ZipFile(io.BytesIO(archive)) as zf:
            member, directory_name = _locate_skill_md(zf.namelist())
            with zf.open(member) as fp:
                # 多要 1 字节：读满就说明超限了，不必知道它到底多大
                raw = fp.read(_MAX_SKILL_MD_BYTES + 1)
    except zipfile.BadZipFile as exc:
        raise ValidationException("这不是一个有效的 zip 文件") from exc

    if len(raw) > _MAX_SKILL_MD_BYTES:
        raise ValidationException(
            f"SKILL.md 超过 {_MAX_SKILL_MD_BYTES // 1024} KiB —— "
            "正文应当精简，详细参考资料请另存成独立文件"
        )

    try:
        return raw.decode("utf-8"), directory_name
    except UnicodeDecodeError as exc:
        raise ValidationException("SKILL.md 必须是 UTF-8 编码") from exc


def _locate_skill_md(member_names: list[str]) -> tuple[str, str | None]:
    """在 zip 成员名单里定位 SKILL.md，并算出它的父目录名。

    两种合法打包形态：
        A 型  svg-chart/SKILL.md  →  ("svg-chart/SKILL.md", "svg-chart")
        B 型  SKILL.md            →  ("SKILL.md", None)

    Returns:
        (成员路径, 父目录名)。父目录名为 None 即 B 型 —— 包里没有「目录名」
        这个信息，由调用方据 frontmatter 的 name 补一个。

    Raises:
        ValidationException: 没有 SKILL.md，或同一层有多个（分不清哪个是主的）
    """

    candidates = [
        name
        for name in member_names
        if not name.endswith("/")  # 目录条目本身，不是文件
           and not name.startswith("__MACOSX/")  # macOS 右键压缩塞进来的元数据副本
           and posixpath.basename(name) in _SKILL_MD_NAMES
    ]

    if not candidates:
        raise ValidationException("zip 里没有 SKILL.md —— 一个 skill 包必须含这个文件")

    # 取路径最浅的那层：从 GitHub 下载的包会多一层仓库名外壳
    # （skills-main/svg-chart/SKILL.md），最浅的那个才是这个 skill 自己的
    shallowest = min(name.count("/") for name in candidates)
    top = [name for name in candidates if name.count("/") == shallowest]
    if len(top) > 1:
        raise ValidationException(
            f"zip 里有 {len(top)} 个 SKILL.md，一个包只能装一个 skill："
            + "、".join(sorted(top))
        )

    member = top[0]
    parent = posixpath.dirname(member)
    return member, posixpath.basename(parent) or None
