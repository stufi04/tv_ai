import type { Show } from '../api/types'

interface SelectionBarProps {
  selectedShows: Show[]
  isGenerating: boolean
  onGenerate: () => void
  /** Clear is also useful with nothing selected, e.g. to dismiss a generated episode. */
  canClear: boolean
  onClear: () => void
}

export function SelectionBar({ selectedShows, isGenerating, onGenerate, canClear, onClear }: SelectionBarProps) {
  const isCrossover = selectedShows.length > 1

  return (
    <section className="selection-bar" aria-label="Selection">
      <p className="selection-bar__summary">
        {selectedShows.length === 0
          ? 'Pick one show for a new episode, or two for a crossover.'
          : selectedShows.map((show) => show.title).join(' × ')}
      </p>
      <div className="selection-bar__actions">
        <button type="button" className="button button--ghost" onClick={onClear} disabled={!canClear}>
          Clear
        </button>
        <button
          type="button"
          className="button"
          onClick={onGenerate}
          disabled={selectedShows.length === 0 || isGenerating}
        >
          {isGenerating ? 'Writing…' : isCrossover ? 'Generate crossover' : 'Generate episode'}
        </button>
      </div>
    </section>
  )
}
