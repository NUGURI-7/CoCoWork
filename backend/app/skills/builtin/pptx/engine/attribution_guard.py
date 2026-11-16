"""Integrity gate stub.

The upstream PPT Master distribution refuses to run unless its own SKILL.md,
sponsor files and scripts are byte-identical to the official release. CoCoWork
vendors only the SVG→PPTX conversion engine (MIT, see LICENSE and NOTICE.md),
so the gate is replaced by a no-op that keeps the original call sites intact.
"""


def require_skill_integrity() -> None:
    return None
