import { cn } from '@/lib/utils'

type CitationMarkerProps = {
  index: number
  selected?: boolean
  onSelect: (index: number) => void
}

export function CitationMarker({ index, selected, onSelect }: CitationMarkerProps) {
  return (
    <button
      type="button"
      onClick={() => onSelect(index)}
      aria-label={`Show source ${index}`}
      className={cn(
        'mx-0.5 inline-flex h-4 min-w-4 -translate-y-1 items-center justify-center rounded px-1 align-baseline text-[0.65rem] font-semibold tabular-nums no-underline transition-colors',
        selected
          ? 'bg-[#F59E0B] text-[#09090B]'
          : 'bg-[#F59E0B]/15 text-[#FBBF24] hover:bg-[#F59E0B]/25',
      )}
    >
      {index}
    </button>
  )
}
