import type { Show } from '../api/types'
import { ShowCard } from './ShowCard'

interface ShowGridProps {
  shows: Show[]
  selectedIds: string[]
  selectionFull: boolean
  onToggle: (id: string) => void
}

export function ShowGrid({ shows, selectedIds, selectionFull, onToggle }: ShowGridProps) {
  if (shows.length === 0) {
    return <p className="muted">No shows match your filters.</p>
  }

  return (
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
  )
}
