import type { Show } from '../api/types'

interface ShowCardProps {
  show: Show
  selected: boolean
  disabled: boolean
  onToggle: (show: Show) => void
}

export function ShowCard({ show, selected, disabled, onToggle }: ShowCardProps) {
  const meta = [show.year, show.network].filter(Boolean).join(' · ')

  return (
    <button
      type="button"
      className="show-card"
      aria-pressed={selected}
      disabled={disabled}
      onClick={() => onToggle(show)}
    >
      <span className="show-card__poster">
        {show.imageUrl ? (
          // Decorative: the title is right next to it.
          <img src={show.imageUrl} alt="" loading="lazy" decoding="async" />
        ) : (
          <span className="show-card__poster-placeholder" aria-hidden="true">
            {show.title.charAt(0)}
          </span>
        )}
      </span>
      <span className="show-card__body">
        <span className="show-card__title">{show.title}</span>
        {meta && <span className="show-card__meta">{meta}</span>}
        <span className="show-card__summary">{show.summary}</span>
        <span className="show-card__genres">
          {show.genres.map((genre) => (
            <span key={genre} className="tag">
              {genre}
            </span>
          ))}
        </span>
      </span>
    </button>
  )
}
