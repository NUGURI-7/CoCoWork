/// <reference types="vite/client" />

// @fontsource/* 是纯 CSS 副作用导入，不带类型声明；
// 在 noUncheckedSideEffectImports 严格模式下需声明模块以通过类型检查。
declare module '@fontsource/*'

