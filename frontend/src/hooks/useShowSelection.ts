import { useCallback, useState } from 'react'

export const MAX_SELECTED_SHOWS = 2

export function useShowSelection() {
  const [selectedIds, setSelectedIds] = useState<string[]>([])

  const toggle = useCallback((id: string) => {
    setSelectedIds((current) => {
      if (current.includes(id)) return current.filter((selectedId) => selectedId !== id)
      if (current.length >= MAX_SELECTED_SHOWS) return current
      return [...current, id]
    })
  }, [])

  const clear = useCallback(() => setSelectedIds([]), [])

  return {
    selectedIds,
    isFull: selectedIds.length >= MAX_SELECTED_SHOWS,
    toggle,
    clear,
  }
}
