import { useEffect, useRef } from 'react'
import type { Show } from '../api/types'
import { ShowCard } from './ShowCard'

interface ShowGridProps {
  shows: Show[]
  selectedIds: string[]
  selectionFull: boolean
  onToggle: (show: Show) => void
  hasMore: boolean
  loadingMore: boolean
  onLoadMore: () => void
}

export function ShowGrid({ shows, selectedIds, selectionFull, onToggle, hasMore, loadingMore, onLoadMore }: ShowGridProps) {
  const sentinelRef = useRef<HTMLDivElement>(null)

  // Load the next page when the end of the list scrolls into view (with a head start of one screen).
  useEffect(() => {
    const sentinel = sentinelRef.current
    if (!sentinel || !hasMore || loadingMore) return
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) onLoadMore()
      },
      { rootMargin: '100% 0px' },
    )
    observer.observe(sentinel)
    return () => observer.disconnect()
  }, [hasMore, loadingMore, onLoadMore])

  if (shows.length === 0) {
    return <p className="muted">No shows match your filters.</p>
  }

  return (
    <>
      <ul className="show-grid" aria-label="Shows">
        {shows.map((show) => {
          const selected = selectedIds.includes(show.id)
          return (
            <li key={show.id}>
              <ShowCard show={show} selected={selected} disabled={selectionFull && !selected} onToggle={onToggle} />
            </li>
          )
        })}
      </ul>
      <div ref={sentinelRef} className="show-grid__footer">
        {loadingMore && <p className="muted">Loading more shows…</p>}
        {hasMore && !loadingMore && (
          <button type="button" className="button button--ghost" onClick={onLoadMore}>
            Load more
          </button>
        )}
      </div>
    </>
  )
}
