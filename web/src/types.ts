export type NebiusBudget = {
  call_count: number
  total_tokens: number
  call_limit: number
  calls_remaining: number
}

export type HealthStatus = {
  status: string
  providers_configured: {
    nebius: boolean
    tavily: boolean
  }
  nebius_budget: NebiusBudget
  live_research_enabled?: boolean
}

export type Draft = {
  claim: string
  search_query: string
  model: string
}

export type Source = {
  title: string
  url: string
  snippet: string
  authors?: string
  published?: string
  metadata_source?: string
}

export type Comparison = {
  is_original_study?: boolean
  supporting_excerpt: string
  study_tested: string
  study_found: string
  wording_gap: string
  uncertainties: string[]
  excerpt_verified: boolean
  relation?: 'supports' | 'partly_supports' | 'contradicts' | 'does_not_address'
  text_coverage?: 'abstract_only' | 'full_text' | 'unclear'
  quote_method?: 'indexed_passages' | 'model_copy' | string
  quote_selection?: number[]
  model?: string
  assessed_at?: string
  source_mode?: string
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
  evaluation_mode?: string
  reassessment_of?: string
  trace: string[]
  corrections: { at: string; previous_url: string | null; new_url: string; accepted?: boolean; reason?: string }[]
}
