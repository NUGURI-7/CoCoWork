import { createFileRoute } from '@tanstack/react-router'
import { Wrench } from 'lucide-react'
import ToolsPage from '@/pages/tools/ToolsPage'

export const Route = createFileRoute('/_authenticated/tools')({
  staticData: { tabTitle: '工具', tabIcon: Wrench },
  component: ToolsPage,
})
