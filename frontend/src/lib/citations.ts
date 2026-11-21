import { isDataUIPart, type UIMessage } from 'ai'

export type CitationPayload = {
  citationIndex: number
  chunkId: string
  excerpt: string
  ticker: string
  companyName?: string
  form: string
  filingDate: string
  page?: string
  section?: string
  documentTitle?: string
  fiscalYear?: number
}

export type PipelineStage =
  | 'analyzing'
  | 'searching'
  | 'reading'
  | 'verifying'
  | 'streaming'

export type PipelineStatus = {
  stage: PipelineStage
  message: string
}

function isCitationData(data: unknown): data is CitationPayload {
  if (typeof data !== 'object' || data === null) {
    return false
  }

  const record = data as Record<string, unknown>
  return (
    typeof record.citationIndex === 'number' &&
    typeof record.chunkId === 'string' &&
    typeof record.excerpt === 'string' &&
    typeof record.ticker === 'string' &&
    typeof record.form === 'string' &&
    typeof record.filingDate === 'string' &&
    (record.documentTitle === undefined || typeof record.documentTitle === 'string') &&
    (record.fiscalYear === undefined || typeof record.fiscalYear === 'number')
  )
}

export function isCitationPart(
  part: UIMessage['parts'][number],
): part is UIMessage['parts'][number] & { type: 'data-citation'; data: CitationPayload } {
  return isDataUIPart(part) && part.type === 'data-citation' && isCitationData(part.data)
}

export function isStatusPart(
  part: unknown,
): part is { type: 'data-status'; data: PipelineStatus } {
  if (typeof part !== 'object' || part === null) {
    return false
  }

  const record = part as Record<string, unknown>
  if (record.type !== 'data-status' || typeof record.data !== 'object' || record.data === null) {
    return false
  }

  const data = record.data as Record<string, unknown>
  return typeof data.stage === 'string' && typeof data.message === 'string'
}

export function citationsFromMessage(message: UIMessage): CitationPayload[] {
  const citations = message.parts
    .filter(isCitationPart)
    .map((part) => part.data)
  const knownChunkIds = new Set(citations.map((citation) => citation.chunkId.toLowerCase()))
  let nextIndex = citations.reduce(
    (maximum, citation) => Math.max(maximum, citation.citationIndex),
    0,
  ) + 1

  for (const match of textFromMessage(message).matchAll(
    /\[([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\]/gi,
  )) {
    const chunkId = match[1]
    if (!chunkId || knownChunkIds.has(chunkId.toLowerCase())) {
      continue
    }

    knownChunkIds.add(chunkId.toLowerCase())
    citations.push({
      citationIndex: nextIndex++,
      chunkId,
      excerpt: '',
      ticker: 'Source',
      form: 'Filing',
      filingDate: '',
    })
  }

  return citations.sort((a, b) => a.citationIndex - b.citationIndex)
}

export function textFromMessage(message: UIMessage): string {
  return message.parts
    .filter((part) => part.type === 'text')
    .map((part) => part.text)
    .join('')
}

export function citationLabel(citation: CitationPayload): string {
  const parts = [citation.companyName ?? citation.ticker, citation.form]
  if (citation.fiscalYear) {
    parts.push(`FY${citation.fiscalYear}`)
  } else if (citation.filingDate) {
    parts.push(citation.filingDate)
  }
  if (citation.page) {
    parts.push(`p.${citation.page}`)
  }
  return parts.join(' · ')
}

export function citationHeader(citation: CitationPayload): string {
  const company = citation.companyName ?? citation.ticker
  const year = citation.fiscalYear ? ` · FY${citation.fiscalYear}` : ''
  const reportDate = citation.filingDate ? ` · report date ${citation.filingDate}` : ''
  return `${company} · ${citation.form}${year}${reportDate}`
}

export function citationSubtitle(citation: CitationPayload): string | null {
  const parts: string[] = []
  if (citation.page) {
    parts.push(`Page ${citation.page}`)
  }
  if (citation.section) {
    parts.push(citation.section)
  }
  return parts.length > 0 ? parts.join(' · ') : null
}

export function citationByIndex(
  citations: CitationPayload[],
  index: number,
): CitationPayload | undefined {
  return citations.find((citation) => citation.citationIndex === index)
}
