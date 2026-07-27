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
export type { User, UserRegisterPayload, UserLoginPayload, TokenPayload } from './user'
export type {
  ProviderType,
  ModelType,
  ParamField,
  ModelTypeParams,
  Provider,
  AIModel,
  CatalogItem,
  AvailableModel,
  AvailableModelGroup,
} from './model'
export type {
  KnowledgeBaseStatus,
  RetrievalMode,
  ChunkConfig,
  KnowledgeBase,
  KnowledgeBaseCreatePayload,
  KnowledgeBaseUpdatePayload,
  Document,
  DocumentStatus,
  DocumentStage,
  UploadStrategy,
  UploadInitOut,
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
  ConversationUpdatePayload,
  MessageRole,
  SenderKind,
  MessageStatus,
  WorkspaceMessage,
  MemberAgentInfo,
  WorkspaceMemberOut,
  MemberRecruitPayload,
} from './workspace'
export type { ToolSource, Tool } from './tool'
export type { SkillSource, Skill } from './skill'
export type { MCPTransport, MCPServer } from './mcp'
export type {
  // 协议层
  ApiTextBlock,
  ApiContentBlock,
  ApiHistoryMessage,
  ChatStreamRequest,
  // SSE event payload
  MessageStartPayload,
  MessageStopPayload,
  Usage,
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
  ArtifactsPayload,
  // 渲染层
  TextBlock,
  ThinkingBlock,
  ToolUseBlock,
  DelegateBlock,
  RenderBlock,
  // Message union
  UserMessage,
  AssistantMessage,
  ChatMessage,
} from './chat'
