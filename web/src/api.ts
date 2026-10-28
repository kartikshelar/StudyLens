import type { Draft, HealthStatus, Report } from './types'

const apiBase = import.meta.env.VITE_API_BASE_URL || ''

async function unwrap<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    throw new Error(body?.detail || `Request failed (${response.status})`)
  }
  return response.json() as Promise<T>
}

export async function getHealth(): Promise<HealthStatus> {
  return unwrap(await fetch(`${apiBase}/api/health`))
}

export async function extractText(text: string): Promise<Draft> {
  return unwrap(await fetch(`${apiBase}/api/claims/extract-text`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
  }))
}

export async function extractImage(file: File): Promise<Draft> {
  const body = new FormData()
  body.append('image', file)
  return unwrap(await fetch(`${apiBase}/api/claims/extract-image`, { method: 'POST', body }))
}

export async function investigate(claim: string, searchQuery: string): Promise<Report> {
  return unwrap(await fetch(`${apiBase}/api/investigations`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ claim, search_query: searchQuery }),
  }))
}

export async function getReport(id: string): Promise<Report> {
  return unwrap(await fetch(`${apiBase}/api/investigations/${encodeURIComponent(id)}`))
}

export async function correctSource(id: string, sourceUrl: string): Promise<Report> {
  return unwrap(await fetch(`${apiBase}/api/investigations/${encodeURIComponent(id)}/source`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ source_url: sourceUrl }),
  }))
}
