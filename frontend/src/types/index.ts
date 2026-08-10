/**
 * Types barrel — 统一从 `@/types` 引入。
 *
 * 用法：
 *   import type { User, ResponseModel } from '@/types'
 */
export type { ResponseModel, PageData, PageResponse } from './api'
export type {
  BehaviorType,
  TemplateKind,
  Template,
  AgentConfig,
  ModelParams,
  Agent,
  Message,
} from './agent'
export type {
  User,
  UserRegisterPayload,
  UserLoginPayload,
  UserStatusPayload,
  TokenPayload,
} from './user'
export type {
  ProviderType,
  ModelType,
  CredentialField,
  ParamField,
  ModelTypeParams,
  Provider,
  AIModel,
  CatalogItem,
  AvailableModel,
  AvailableModelGroup,
} from './model'
// 值导出（非 type-only）：解析后端的枚举全集与展示文案，组件直接用
export {
  ALL_PARSE_BACKENDS,
  PARSE_BACKEND_HINTS,
  PARSE_BACKEND_LABELS,
} from './knowledge'
export type {
  KnowledgeBaseStatus,
  RetrievalMode,
  ParseBackend,
  ChunkConfig,
  KnowledgeBase,
  KnowledgeBaseCreatePayload,
  KnowledgeBaseUpdatePayload,
  Document,
  DocumentStatus,
  DocumentStage,
  UploadStrategy,
  UploadInitOut,
  Paragraph,
  RetrievalHit,
  RetrievalTestResult,
  BatchProcessResult,
} from './knowledge'
export type {
  Workspace,
  WorkspaceCreatePayload,
  WorkspaceUpdatePayload,
  Conversation,
  ConversationCreatePayload,
  ConversationTitle,
  ConversationUpdatePayload,
  MessageRole,
  SenderKind,
  MessageStatus,
  WorkspaceMessage,
  WorkspaceArtifact,
  MemberAgentInfo,
  WorkspaceMemberOut,
  MemberRecruitPayload,
} from './workspace'
export type { ToolSource, ToolCategory, Tool } from './tool'
export type { SkillSource, Skill } from './skill'
export type { MCPTransport, MCPServer } from './mcp'
export type {
  // 协议层
  ApiTextBlock,
  ApiArtifactRefBlock,
  ApiAskBlock,
  ApiContentBlock,
  ApiHistoryMessage,
  ChatStreamRequest,
  // 人工确认（HITL）
  AskField,
  AskAction,
  AskPayload,
  AskAnswer,
  // SSE event payload
  MessageStartPayload,
  MessageStopPayload,
  Usage,
  TokenUsage,
  TokenUsageRow,
  MessageDeltaPayload,
  ContentBlockStartPayload,
  ContentBlockDeltaPayload,
  ContentBlockStopPayload,
  ToolUseStartPayload,
  ToolUseDeltaPayload,
  ToolUseStopPayload,
  ToolResultPayload,
  ErrorPayload,
  Artifact,
  CompactStartPayload,
  CompactStopPayload,
  ArtifactsPayload,
  InterruptPayload,
  // 渲染层
  TextBlock,
  ThinkingBlock,
  ToolUseBlock,
  DelegateBlock,
  AskBlock,
  RenderBlock,
  // Message union
  UserMessage,
  AssistantMessage,
  ChatMessage,
} from './chat'
