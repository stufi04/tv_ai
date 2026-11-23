import { useInfiniteQuery } from '@tanstack/react-query'
import { fetchShows } from '../api/client'
import type { ShowQuery } from '../api/types'

/** While the backend is still downloading the catalogue for the first time, check back this often. */
const SYNC_POLL_MS = 5000

export function useShows(query: ShowQuery) {
  return useInfiniteQuery({
    queryKey: ['shows', query],
    queryFn: ({ pageParam, signal }) => fetchShows(query, pageParam, signal),
    initialPageParam: 0,
    getNextPageParam: (lastPage) => lastPage.nextOffset ?? undefined,
    // Keep showing the previous results while a new search loads, instead of flashing a spinner.
    placeholderData: (previous) => previous,
    refetchInterval: (q) => (q.state.data?.pages[0]?.syncing ? SYNC_POLL_MS : false),
    staleTime: 5 * 60 * 1000,
  })
}
