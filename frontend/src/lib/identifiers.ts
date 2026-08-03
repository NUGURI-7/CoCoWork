/**
 * 标识符工具 —— 必须与后端 `app/core/identifiers.py` 的 `short_id` 算出同一个值。
 */

/**
 * 取 UUID 的短标识 —— **必须取后 8 位，不能取前 8 位**。
 *
 * 项目的 id 是 UUIDv7：前 48 位是毫秒时间戳，后面才是随机数。取前 8 位拿到的
 * 是时间戳高位，**每 65 秒才变一次** —— 同一分钟内创建的两个成员短标识必然
 * 相同，派活会静默派给错的那个人（2026-08-03 真出过这个 bug）。
 *
 * UUID 字符串末段有 12 个 hex 字符，所以对字符串取后 8 位，
 * 等价于后端对无连字符 hex 取后 8 位。
 */
export function shortId(id: string): string {
  return id.slice(-8)
}

/** 成员在派活协议里的机器键 —— 对应后端 `member_key()`。 */
export function memberKey(memberId: string): string {
  return `member_${shortId(memberId)}`
}
