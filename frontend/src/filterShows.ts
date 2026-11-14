import type { Show } from './api/types'

export const ALL_GENRES = ''

export function filterShows(shows: Show[], search: string, genre: string): Show[] {
  const term = search.trim().toLowerCase()
  return shows.filter(
    (show) =>
      (genre === ALL_GENRES || show.genres.includes(genre)) &&
      (term === '' || show.title.toLowerCase().includes(term) || show.network.toLowerCase().includes(term)),
  )
}

export function collectGenres(shows: Show[]): string[] {
  return [...new Set(shows.flatMap((show) => show.genres))].sort()
}
