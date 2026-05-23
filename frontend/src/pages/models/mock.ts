/** Mock 数据 — 后端 API 就绪后删除 */

import type { AIModel, AvailableModelGroup, ModelTypeParams, Provider } from '@/types'

export const mockProviders: Provider[] = [
  {
    id: '1',
    name: '阿里云 - 生产',
    provider_type: 'dashscope',
    base_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    description: '生产环境主力供应商',
    is_global: true,
    is_enabled: true,
    model_count: 5,
    created_at: '2026-05-20T10:00:00Z',
    updated_at: '2026-05-20T10:00:00Z',
  },
  {
    id: '2',
    name: '阿里云 - 测试',
    provider_type: 'dashscope',
    base_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    description: '测试环境，低优先级',
    is_global: false,
    is_enabled: true,
    model_count: 2,
    created_at: '2026-05-20T11:00:00Z',
    updated_at: '2026-05-20T11:00:00Z',
  },
  {
    id: '3',
    name: 'DeepSeek',
    provider_type: 'deepseek',
    base_url: 'https://api.deepseek.com/v1',
    description: '',
    is_global: true,
    is_enabled: true,
    model_count: 3,
    created_at: '2026-05-21T09:00:00Z',
    updated_at: '2026-05-21T09:00:00Z',
  },
  {
    id: '4',
    name: '硅基流动',
    provider_type: 'siliconflow',
    base_url: 'https://api.siliconflow.cn/v1',
    description: 'BGE embedding + rerank',
    is_global: false,
    is_enabled: false,
    model_count: 0,
    created_at: '2026-05-21T14:00:00Z',
    updated_at: '2026-05-21T14:00:00Z',
  },
]

/** 上游可用模型 mock（按 providerId 索引） */
export const mockAvailableModels: Record<string, AvailableModelGroup[]> = {
  '1': [
    {
      type: 'chat',
      label: '对话模型',
      models: [
        { model_name: 'qwen-turbo' },
        { model_name: 'qwen-plus' },
        { model_name: 'qwen-max' },
      ],
    },
    {
      type: 'embedding',
      label: '向量模型',
      models: [
        { model_name: 'text-embedding-v3' },
      ],
    },
    {
      type: 'rerank',
      label: '重排序模型',
      models: [
        { model_name: 'gte-rerank' },
      ],
    },
  ],
  '3': [
    {
      type: 'chat',
      label: '对话模型',
      models: [
        { model_name: 'deepseek-chat' },
        { model_name: 'deepseek-reasoner' },
      ],
    },
  ],
  '4': [
    {
      type: 'embedding',
      label: '向量模型',
      models: [
        { model_name: 'BAAI/bge-m3' },
        { model_name: 'BAAI/bge-large-zh-v1.5' },
      ],
    },
    {
      type: 'rerank',
      label: '重排序模型',
      models: [
        { model_name: 'BAAI/bge-reranker-v2-m3' },
      ],
    },
  ],
}

/** 已创建模型 mock（按 providerId 索引） */
export const mockAIModels: Record<string, AIModel[]> = {
  '1': [
    {
      id: 'm1',
      provider_id: '1',
      model_name: 'qwen-turbo',
      display_name: 'Qwen Turbo',
      model_type: 'chat',
      config: { temperature: 0.7 },
      is_enabled: true,
      created_at: '2026-05-20T12:00:00Z',
      updated_at: '2026-05-20T12:00:00Z',
    },
    {
      id: 'm2',
      provider_id: '1',
      model_name: 'qwen-plus',
      display_name: 'Qwen Plus',
      model_type: 'chat',
      config: { temperature: 0.7 },
      is_enabled: true,
      created_at: '2026-05-20T12:30:00Z',
      updated_at: '2026-05-20T12:30:00Z',
    },
    {
      id: 'm3',
      provider_id: '1',
      model_name: 'qwen-max',
      display_name: 'Qwen Max',
      model_type: 'chat',
      config: { temperature: 0.5 },
      is_enabled: false,
      created_at: '2026-05-20T13:00:00Z',
      updated_at: '2026-05-20T13:00:00Z',
    },
    {
      id: 'm4',
      provider_id: '1',
      model_name: 'text-embedding-v3',
      display_name: '通义向量',
      model_type: 'embedding',
      config: {},
      is_enabled: true,
      created_at: '2026-05-20T14:00:00Z',
      updated_at: '2026-05-20T14:00:00Z',
    },
    {
      id: 'm5',
      provider_id: '1',
      model_name: 'gte-rerank',
      display_name: 'GTE Rerank',
      model_type: 'rerank',
      config: {},
      is_enabled: true,
      created_at: '2026-05-20T15:00:00Z',
      updated_at: '2026-05-20T15:00:00Z',
    },
  ],
  '3': [
    {
      id: 'm6',
      provider_id: '3',
      model_name: 'deepseek-chat',
      display_name: 'DeepSeek Chat',
      model_type: 'chat',
      config: { temperature: 0.7 },
      is_enabled: true,
      created_at: '2026-05-21T10:00:00Z',
      updated_at: '2026-05-21T10:00:00Z',
    },
    {
      id: 'm7',
      provider_id: '3',
      model_name: 'deepseek-reasoner',
      display_name: 'DeepSeek Reasoner',
      model_type: 'chat',
      config: { temperature: 0.3 },
      is_enabled: true,
      created_at: '2026-05-21T11:00:00Z',
      updated_at: '2026-05-21T11:00:00Z',
    },
  ],
}

/** 参数定义 mock — 对齐后端 PARAM_DEFINITIONS，后续通过 API 获取 */
export const mockParamDefinitions: Record<string, ModelTypeParams> = {
  chat: {
    config_fields: [
      { key: 'context_window', label: '上下文窗口', type: 'number', default: 128000 },
      { key: 'max_output_tokens', label: '最大输出 Token', type: 'number', default: 8192 },
    ],
    invocation_params: [
      { key: 'temperature', label: 'Temperature', type: 'slider', min: 0, max: 2, step: 0.1, default: 1.0 },
      { key: 'top_p', label: 'Top P', type: 'slider', min: 0, max: 1, step: 0.01, default: 1.0 },
      { key: 'max_tokens', label: 'Max Tokens', type: 'number', min: 1, default: null, description: '留空则使用模型默认值' },
      { key: 'frequency_penalty', label: 'Frequency Penalty', type: 'slider', min: -2, max: 2, step: 0.1, default: 0 },
      { key: 'presence_penalty', label: 'Presence Penalty', type: 'slider', min: -2, max: 2, step: 0.1, default: 0 },
    ],
  },
  embedding: {
    config_fields: [
      { key: 'dimensions', label: '向量维度', type: 'number', default: 1024 },
      { key: 'max_input_tokens', label: '最大输入 Token', type: 'number', default: 8192 },
    ],
    invocation_params: [],
  },
  rerank: {
    config_fields: [
      { key: 'max_input_tokens', label: '最大输入 Token', type: 'number', default: 4096 },
    ],
    invocation_params: [
      { key: 'top_n', label: 'Top N', type: 'number', min: 1, default: 10 },
    ],
  },
}
