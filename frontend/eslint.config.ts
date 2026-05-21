import { globalIgnores } from 'eslint/config'
import { defineConfigWithVueTs, vueTsConfigs } from '@vue/eslint-config-typescript'
import pluginVue from 'eslint-plugin-vue'
import pluginOxlint from 'eslint-plugin-oxlint'
import skipFormatting from 'eslint-config-prettier/flat'

// To allow more languages other than `ts` in `.vue` files, uncomment the following lines:
// import { configureVueProject } from '@vue/eslint-config-typescript'
// configureVueProject({ scriptLangs: ['ts', 'tsx'] })
// More info at https://github.com/vuejs/eslint-config-typescript/#advanced-setup

export default defineConfigWithVueTs(
  {
    name: 'app/files-to-lint',
    files: ['**/*.{vue,ts,mts,tsx}'],
  },

  globalIgnores([
    '**/dist/**',
    '**/dist-ssr/**',
    '**/coverage/**',
    '**/node_modules/**',
    'src/components/ui/**', // shadcn-vue 生成的组件不参与项目 lint
  ]),

  // Vue 推荐档（含命名 / 顺序 / 风格），比 DaisyWind 的 essential 严
  ...pluginVue.configs['flat/recommended'],
  vueTsConfigs.recommended,

  ...pluginOxlint.configs['flat/recommended'],

  {
    name: 'app/custom-rules',
    rules: {
      // 允许单词组件名（Login.vue / Home.vue / Register.vue 等业务页面常见）
      'vue/multi-word-component-names': 'off',
      // 显式 any 警告而非报错，方便快速原型，但留可见性
      '@typescript-eslint/no-explicit-any': 'warn',
    },
  },

  // 必须放在最后：关闭与 Prettier 冲突的格式化类规则
  skipFormatting,
)
