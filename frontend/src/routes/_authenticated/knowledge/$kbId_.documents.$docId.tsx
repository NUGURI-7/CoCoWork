/** /knowledge/:kbId/documents/:docId — 文档分段页
 *
 * 文件名里的尾下划线（`$kbId_`）表示**不嵌套进 `$kbId` 的布局**：URL 仍是
 * `/knowledge/{kbId}/documents/{docId}`，但它是一个独立页面，不会要求
 * 知识库详情页去渲染 `<Outlet />`。
 */
import { createFileRoute } from '@tanstack/react-router'
import { FileText } from 'lucide-react'
import DocumentParagraphsPage from '@/pages/knowledge/DocumentParagraphsPage'

export const Route = createFileRoute('/_authenticated/knowledge/$kbId_/documents/$docId')({
  staticData: { tabTitle: '文档分段', tabIcon: FileText },
  component: DocumentParagraphsPage,
})
