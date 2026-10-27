export type Draft = {
  claim: string
  search_query: string
  model: string
}

export type Source = {
  title: string
  url: string
  snippet: string
}

export type Comparison = {
  supporting_excerpt: string
  study_tested: string
  study_found: string
  wording_gap: string
  uncertainties: string[]
  excerpt_verified: boolean
}

export type Report = {
  id: string
  created_at: string
  claim: string
  search_query: string
  status: 'candidate_source' | 'source_not_confirmed'
  message: string
  candidates: Source[]
  selected_source: Source | null
  comparison: Comparison | null
  selection_reason?: string
  trace: string[]
  corrections: { at: string; previous_url: string | null; new_url: string }[]
}
