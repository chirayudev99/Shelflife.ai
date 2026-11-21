import { TrendingUp } from 'lucide-react'

import { cn } from '@/lib/utils'

type LogoProps = {
  className?: string
}

export function LogoMark({ className }: LogoProps) {
  return (
    <span
      className={cn(
        'flex size-8 shrink-0 items-center justify-center rounded-lg border border-primary/20 bg-primary/10 text-primary',
        className,
      )}
    >
      <TrendingUp aria-hidden="true" className="size-4" />
    </span>
  )
}

export function Logo({ className }: LogoProps) {
  return (
    <div className={cn('flex items-center gap-2.5', className)}>
      <LogoMark />
      <div className="flex flex-col leading-none">
        <span className="text-sm font-semibold tracking-tight text-foreground">
          ShelfLife
        </span>
        <span className="text-xs text-muted-foreground">Indian filings research</span>
      </div>
    </div>
  )
}
