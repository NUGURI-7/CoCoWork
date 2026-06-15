import type { ChatState, ChatStore } from './chat-store'
import { useStreamStatusStore, type ConversationStatus } from './stream-status'

/**
 * 对话 store 常驻架子 —— conversationId → 桶（chat store）。
 *
 * 故意放在「模块顶层」而不是 React 组件里：模块只在页面加载时执行一次，
 * 这个 Map 的寿命 = 整个页面的寿命，组件挂载/卸载都不影响它。
 * 这就是「切走对话、桶还在、流继续」的根基。
 */

const registry = new Map<string, ChatStore>()
/** 每个桶的状态订阅退订函数，dispose 时统一调用，防订阅泄漏 */
const unsubs = new Map<string, () => void>()

/** 从桶的状态推出对话状态：在跑 = running，否则看最后一条 assistant 是否出错 */
function computeStatus(s: ChatState): ConversationStatus {
  if (s.isLoading) return 'running'
  const last = s.messages[s.messages.length - 1]
  if (last && last.role === 'assistant' && last.status === 'error') return 'error'
  return 'idle'
}

/** 拿桶：架子上有就返回，没有就用 create() 造一个放上去再返回。 */
export function getOrCreateChatStore(conversationId: string, create: () => ChatStore) {
  let store = registry.get(conversationId)
  if (!store) {
    const created = create()
    registry.set(conversationId, created)

    // 订阅桶的变化 → 写实时状态表。订阅活在 registry 里，与组件挂载无关，
    // 所以后台在跑的对话照样更新。只在状态「真正翻转」时写，避免每个 token 都触发。
    const push = () => {
      const next = computeStatus(created.getState())
      if (useStreamStatusStore.getState().statuses[conversationId] !== next) {
        useStreamStatusStore.getState().set(conversationId, next)
      }
    }
    push() // 落初值
    unsubs.set(conversationId, created.subscribe(push))

    store = created
  }
  return store
}

/**
 * 回收单个对话的桶 —— 删除对话时调用。
 *
 * reset() 中断在跑的流 + 清状态；退订防泄漏；从两个 Map 删 + 清该 id 的实时状态。
 * 跟 disposeAllChatStores 同套清理、只作用一条；架子上没有该条（从没开过）= noop。
 */
export function disposeChatStore(conversationId: string) {
  const store = registry.get(conversationId)
  if (store) store.getState().reset()
  const unsub = unsubs.get(conversationId)
  if (unsub) unsub()
  unsubs.delete(conversationId)
  registry.delete(conversationId)
  useStreamStatusStore.getState().remove(conversationId)
}

/**
 * 清空整个架子 —— 中断所有在跑的流并丢弃所有桶。
 *
 * 在「离开工作空间 / 切到另一个工作空间」时调用，给内存封顶：桶只在「逛当前
 * 工作空间」期间常驻，离开即回收。reset() 会 abort 流 + 清状态，clear() 后桶失去
 * 引用被 GC。
 */
export function disposeAllChatStores() {
  for (const store of registry.values()) {
    store.getState().reset()
  }
  for (const unsub of unsubs.values()) {
    unsub()
  }
  unsubs.clear()
  registry.clear()
  useStreamStatusStore.getState().clear()
}
