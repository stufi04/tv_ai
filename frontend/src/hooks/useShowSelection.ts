import { useCallback, useState } from 'react'
import type { Show } from '../api/types'

export const MAX_SELECTED_SHOWS = 2

/** Keeps whole shows (not just ids) so a selection survives the visible results changing. */
export function useShowSelection() {
  const [selectedShows, setSelectedShows] = useState<Show[]>([])

  const toggle = useCallback((show: Show) => {
    setSelectedShows((current) => {
      if (current.some((selected) => selected.id === show.id)) {
        return current.filter((selected) => selected.id !== show.id)
      }
      if (current.length >= MAX_SELECTED_SHOWS) return current
      return [...current, show]
    })
  }, [])

  const clear = useCallback(() => setSelectedShows([]), [])

  return {
    selectedShows,
    selectedIds: selectedShows.map((show) => show.id),
    isFull: selectedShows.length >= MAX_SELECTED_SHOWS,
    toggle,
    clear,
  }
}
