import { useQuery } from '@tanstack/react-query'
import { fetchShows } from '../api/client'

export function useShows() {
  return useQuery({
    queryKey: ['shows'],
    queryFn: fetchShows,
    // The catalogue is static for the lifetime of the page.
    staleTime: Infinity,
  })
}
