import { Outlet, useParams } from 'react-router-dom'

import { LogoMark } from '@/components/Logo'
import { ThreadSidebar } from '@/components/chat/ThreadSidebar'
import { ThreadsProvider } from '@/components/chat/ThreadsProvider'
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from '@/components/ui/sidebar'
import { useThreads } from '@/hooks/useThreads'

function ChatHeader() {
  const { threadId } = useParams()
  const { threads } = useThreads()
  const activeThread = threads.find((thread) => thread.id === threadId)

  return (
    <header className="flex h-14 shrink-0 items-center gap-3 border-b border-border bg-background/80 px-3 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <SidebarTrigger className="text-muted-foreground" />
      <LogoMark className="size-7 rounded-md" />
      <span className="text-sm font-semibold tracking-tight text-foreground">ShelfLife</span>
      <span className="text-muted-foreground/50">/</span>
      <span className="truncate text-sm text-muted-foreground">
        {activeThread?.title ?? 'Research workspace'}
      </span>
    </header>
  )
}

export function ChatLayout() {
  return (
    <ThreadsProvider>
      <SidebarProvider>
        <ThreadSidebar />
        <SidebarInset className="flex h-svh min-h-0 flex-col">
          <ChatHeader />
          <div className="flex min-h-0 flex-1 flex-col">
            <Outlet />
          </div>
        </SidebarInset>
      </SidebarProvider>
    </ThreadsProvider>
  )
}
