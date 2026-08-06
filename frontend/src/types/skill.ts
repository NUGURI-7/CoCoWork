/**
 * Skill 模块类型 — 对齐 backend/app/schemas/skill/skill_schema.py（SkillOut）。
 *
 * skill 与 tool 在建模上同级（都能挂到 agent 上），但运行机制不同：
 * tool 是函数签名，LLM 填参数拿返回值；skill 是一段说明书 + 捆绑脚本，
 * name/description 进 system prompt，真正干活的是沙箱里的通用文件/shell 工具。
 */

export type SkillSource = 'builtin' | 'user'

export interface Skill {
  /** 用户上传的才有（DB 行主键，删除与挂载都按它定位）；内置的没有行，为 null */
  id: string | null
  /** 规范里的 name（小写字母/数字/连字符），勾选后写进 config.builtin_skills */
  name: string
  /** SKILL.md 的 description，也是进 system prompt 供模型判断的那份 */
  description: string
  /** 来源，前端按此分组 */
  source_type: SkillSource
  /** 该 skill 声明需要的环境变量名；空数组 = 不需要配 key */
  required_env: string[]
}
