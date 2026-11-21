import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { LogoMark } from '@/components/Logo'
import { PromptSuggestion } from '@/components/ui/prompt-suggestion'
import { useThreads } from '@/hooks/useThreads'
import { EXAMPLE_QUESTIONS } from '@/lib/suggestions'

export function ChatEmptyPage() {
  const navigate = useNavigate()
  const { createNewThread } = useThreads()
  const [isStarting, setIsStarting] = useState(false)

  async function startConversation(prompt?: string) {
    if (isStarting) return
    setIsStarting(true)
    try {
      const id = await createNewThread()
      navigate(`/chats/${id}`, prompt ? { state: { initialPrompt: prompt } } : undefined)
    } finally {
      setIsStarting(false)
    }
  }

  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-8 p-6">
      <div className="flex flex-col items-center gap-4 text-center">
        <LogoMark className="size-12" />
        <div className="space-y-1.5">
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">
            Research beyond the headlines.
          </h1>
          <p className="max-w-md text-sm text-muted-foreground">
            Ask about Eternal, Swiggy, or Zepto filings. Get source-grounded answers with
            citations you can open and verify.
          </p>
        </div>
      </div>

      <div className="grid w-full max-w-xl gap-2 sm:grid-cols-2">
        {EXAMPLE_QUESTIONS.map((question) => (
          <PromptSuggestion
            key={question}
            variant="outline"
            size="default"
            className="h-auto justify-start rounded-xl border-white/[0.08] bg-[#111318]/70 px-4 py-3 text-left text-sm font-normal whitespace-normal transition-colors hover:border-primary/30 hover:bg-primary/5"
            disabled={isStarting}
            onClick={() => void startConversation(question)}
          >
            {question}
          </PromptSuggestion>
        ))}
      </div>
    </div>
  )
}
