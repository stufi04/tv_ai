import { useQuery } from '@tanstack/react-query'
import { fetchGenres } from '../api/client'

export function useGenres(refreshKey: unknown) {
  return useQuery({
    // `refreshKey` lets the caller refetch once the catalogue finishes its first download.
    queryKey: ['genres', refreshKey],
    queryFn: fetchGenres,
    staleTime: Infinity,
  })
}
