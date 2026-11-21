import type { ReactNode } from 'react'
import { ArrowUpRight, Layers3, Quote, Sparkles, TrendingUp } from 'lucide-react'

import { LogoMark } from '@/components/Logo'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'

type AuthLayoutProps = {
  title: string
  description?: string
  children: ReactNode
}

const SAMPLE_PROMPTS = [
  'Compare Blinkit and Swiggy Instamart dark-store expansion and contribution margins',
  'What regulatory and supply-chain risks are disclosed in the latest quick-commerce filings?',
  'Break down quick-commerce AOV and take-rate trends across FY24–FY25',
]

const PLATFORM_PILLS = [
  { icon: Layers3, label: 'Eternal · Swiggy · Zepto Filings' },
  { icon: TrendingUp, label: 'Hybrid Vector + Keyword RAG' },
  { icon: Quote, label: 'Inline Source Citations' },
]

export function AuthLayout({ title, description, children }: AuthLayoutProps) {
  return (
    <main className="relative isolate h-dvh bg-background text-foreground">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_18%_40%,rgba(16,185,129,0.13),transparent_42%),radial-gradient(ellipse_at_90%_10%,rgba(245,158,11,0.08),transparent_30%)]"
      />
      <div className="relative mx-auto grid h-full w-full max-w-[1440px] grid-cols-1 lg:grid-cols-[minmax(0,1.08fr)_minmax(400px,0.82fr)]">
        <section className="hidden min-h-0 flex-col justify-between px-10 py-8 lg:flex xl:px-16 xl:py-10">
          <div className="space-y-12">
            <div className="flex items-center gap-3">
              <LogoMark className="size-11 rounded-xl" />
              <div>
                <p className="text-lg font-semibold tracking-tight">ShelfLife</p>
                <p className="text-xs tracking-wide text-muted-foreground">shelflife.ai</p>
              </div>
            </div>

            <div className="max-w-2xl space-y-5">
              <div className="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/10 px-3 py-1.5 text-xs font-medium text-primary">
                <Sparkles className="size-3.5" />
                Financial intelligence, grounded in filings
              </div>
              <h1 className="max-w-xl text-4xl leading-[1.08] font-semibold tracking-tight xl:text-5xl">
                Audited answers from India&apos;s quick-commerce filings — in seconds, not days.
              </h1>
              <p className="max-w-xl text-sm leading-6 text-muted-foreground xl:text-base">
                Ask sharper questions across more than 1,500 pages of Eternal (Blinkit), Swiggy
                (Instamart), and Zepto reports. Every answer is grounded in filing passages with
                citations you can open and verify.
              </p>
            </div>

            <div className="flex flex-wrap gap-2">
              {PLATFORM_PILLS.map(({ icon: Icon, label }) => (
                <span
                  key={label}
                  className="inline-flex items-center gap-2 rounded-full border border-white/[0.08] bg-white/[0.035] px-3 py-2 text-xs text-zinc-300"
                >
                  <Icon className="size-3.5 text-primary" />
                  {label}
                </span>
              ))}
            </div>
          </div>

          <div className="max-w-2xl my-4 rounded-2xl border border-white/[0.08] bg-[#111318]/80 p-5 shadow-[0_24px_80px_rgba(0,0,0,0.22)] backdrop-blur-xl">
            <div className="mb-3 flex items-center justify-between">
              <div>
                <p className="text-sm font-medium">Sample research prompts</p>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  Start with a question. Follow every answer to its source.
                </p>
              </div>
              <span className="rounded-md border border-white/[0.08] px-2 py-1 font-mono text-[10px] tracking-wide text-muted-foreground">
                RESEARCH
              </span>
            </div>
            <div className="space-y-2">
              {SAMPLE_PROMPTS.map((prompt, index) => (
                <div
                  key={prompt}
                  className="flex items-start gap-3 rounded-xl border border-white/[0.05] bg-white/[0.02] px-3 py-2.5 text-xs leading-5 text-zinc-300"
                >
                  <span className="pt-0.5 font-mono text-[10px] text-primary">
                    0{index + 1}
                  </span>
                  <span>{prompt}</span>
                  <ArrowUpRight className="mt-0.5 ml-auto size-3.5 shrink-0 text-zinc-600" />
                </div>
              ))}
            </div>
          </div>

          <p className="text-xs text-zinc-600 pb-4">
            Built for analysts and founders tracking India&apos;s quick-commerce market.
          </p>
        </section>

        <section className="flex min-h-0 flex-col items-center justify-center px-5 py-5 sm:px-8 lg:px-10">
          <div className="mb-5 flex items-center gap-3 lg:hidden">
            <LogoMark className="size-9 rounded-xl" />
            <div>
              <p className="text-base font-semibold leading-tight">ShelfLife</p>
              <p className="text-xs text-muted-foreground">shelflife.ai</p>
            </div>
          </div>
          <Card className="w-full max-w-md gap-0 border border-white/[0.08] bg-[#111318]/90 py-0 shadow-[0_32px_120px_rgba(0,0,0,0.45)] ring-0 backdrop-blur-2xl motion-safe:animate-[rise-in_600ms_cubic-bezier(0.16,1,0.3,1)_both]">
            <CardHeader className="px-6 pt-6 pb-4">
              <div className="mb-2 inline-flex w-fit items-center gap-1.5 rounded-full border border-primary/20 bg-primary/10 px-2.5 py-1 text-[10px] font-semibold tracking-[0.14em] text-primary uppercase">
                <span className="size-1.5 rounded-full bg-primary shadow-[0_0_10px_rgba(16,185,129,0.8)]" />
                Secure workspace
              </div>
              <CardTitle className="text-2xl font-semibold tracking-tight">{title}</CardTitle>
              {description ? (
                <CardDescription className="leading-5">{description}</CardDescription>
              ) : null}
            </CardHeader>
            <CardContent className="px-6 pb-6">{children}</CardContent>
          </Card>
          <p className="mt-4 text-center text-[11px] text-zinc-600 lg:hidden">
            Source-grounded research across Indian quick-commerce filings.
          </p>
        </section>
      </div>
    </main>
  )
}
