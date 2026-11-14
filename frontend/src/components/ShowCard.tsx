import type { Show } from '../api/types'

interface ShowCardProps {
  show: Show
  selected: boolean
  disabled: boolean
  onToggle: (id: string) => void
}

export function ShowCard({ show, selected, disabled, onToggle }: ShowCardProps) {
  return (
    <button
      type="button"
      className="show-card"
      aria-pressed={selected}
      disabled={disabled}
      onClick={() => onToggle(show.id)}
    >
      <span className="show-card__title">{show.title}</span>
      <span className="show-card__meta">
        {show.year} · {show.network}
      </span>
      <span className="show-card__summary">{show.summary}</span>
      <span className="show-card__genres">
        {show.genres.map((genre) => (
          <span key={genre} className="tag">
            {genre}
          </span>
        ))}
      </span>
    </button>
  )
}
