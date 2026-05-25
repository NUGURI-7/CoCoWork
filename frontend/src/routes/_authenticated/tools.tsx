import { createFileRoute } from '@tanstack/react-router'
import ToolsPage from '@/pages/tools/ToolsPage'

export const Route = createFileRoute('/_authenticated/tools')({
  component: ToolsPage,
})
