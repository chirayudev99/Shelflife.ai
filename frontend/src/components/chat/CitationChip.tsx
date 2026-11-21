import { citationLabel, type CitationPayload } from '@/lib/citations'
import { cn } from '@/lib/utils'

type CitationChipProps = {
  citation: CitationPayload
  selected?: boolean
  onSelect: (citation: CitationPayload) => void
}

export function CitationChip({ citation, selected, onSelect }: CitationChipProps) {
  return (
    <button
      type="button"
      onClick={() => onSelect(citation)}
      className={cn(
        'inline-flex max-w-full items-center gap-1.5 rounded-full border py-1 pr-3 pl-1 text-left text-xs transition-colors',
        selected
          ? 'border-[#F59E0B]/50 bg-[#F59E0B]/10 text-[#FBBF24]'
          : 'border-[#F59E0B]/20 bg-[#F59E0B]/[0.04] text-amber-200/80 hover:border-[#F59E0B]/45 hover:bg-[#F59E0B]/[0.08] hover:text-amber-100',
      )}
    >
      <span className="flex size-4 shrink-0 items-center justify-center rounded-full bg-[#F59E0B] text-[0.6rem] font-semibold text-[#09090B] tabular-nums">
        {citation.citationIndex}
      </span>
      <span className="truncate font-medium">{citationLabel(citation)}</span>
    </button>
  )
}
