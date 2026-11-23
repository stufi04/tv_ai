import type { Episode, ShowPage, ShowQuery } from './types'

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  })
  if (!response.ok) {
    throw new ApiError(response.status, await readErrorMessage(response))
  }
  return response.json() as Promise<T>
}

async function readErrorMessage(response: Response): Promise<string> {
  try {
    const body: unknown = await response.json()
    // FastAPI returns { detail: string } for handled errors and { detail: [...] } for validation errors.
    if (body && typeof body === 'object' && 'detail' in body && typeof body.detail === 'string') {
      return body.detail
    }
  } catch {
    // Not JSON: fall through to a generic message.
  }
  return `Request failed with status ${response.status}`
}

export const SHOWS_PAGE_SIZE = 24

export function fetchShows({ q, genre, seed }: ShowQuery, offset: number, signal?: AbortSignal): Promise<ShowPage> {
  const params = new URLSearchParams({
    q,
    genre,
    seed: String(seed),
    offset: String(offset),
    limit: String(SHOWS_PAGE_SIZE),
  })
  return request<ShowPage>(`/api/shows?${params}`, { signal })
}

export function fetchGenres(): Promise<string[]> {
  return request<string[]>('/api/genres')
}

export function createEpisode(showIds: string[]): Promise<Episode> {
  return request<Episode>('/api/episodes', {
    method: 'POST',
    body: JSON.stringify({ showIds }),
  })
}
