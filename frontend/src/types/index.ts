/**
 * Types barrel — 统一从 `@/types` 引入。
 *
 * 用法：
 *   import type { User, ResponseModel } from '@/types'
 */
export type { ResponseModel, PageData, PageResponse } from './api'
export type { BehaviorType, Template, AgentConfig, Agent, Message } from './agent'
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
  ChunkConfig,
  KnowledgeBase,
  KnowledgeBaseCreatePayload,
  KnowledgeBaseUpdatePayload,
  Document,
  DocumentStatus,
  DocumentStage,
  UploadStrategy,
  UploadInitOut,
} from './knowledge'
export type { WorkspaceMember, Conversation, Workspace } from './workspace'
