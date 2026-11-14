import { useMemo, useRef, useState } from 'react'
import type { Show } from './api/types'
import { EpisodeView } from './components/EpisodeView'
import { SelectionBar } from './components/SelectionBar'
import { ShowFilters } from './components/ShowFilters'
import { ShowGrid } from './components/ShowGrid'
import { ALL_GENRES, collectGenres, filterShows } from './filterShows'
import { useGenerateEpisode } from './hooks/useGenerateEpisode'
import { useShowSelection } from './hooks/useShowSelection'
import { useShows } from './hooks/useShows'

const NO_SHOWS: Show[] = []

export default function App() {
  const { data: shows = NO_SHOWS, isPending: showsLoading, error: showsError } = useShows()
  const [search, setSearch] = useState('')
  const [genre, setGenre] = useState(ALL_GENRES)
  const { selectedIds, isFull, toggle, clear } = useShowSelection()
  const generation = useGenerateEpisode()
  const resultRef = useRef<HTMLElement>(null)

  const genres = useMemo(() => collectGenres(shows), [shows])
  const visibleShows = useMemo(() => filterShows(shows, search, genre), [shows, search, genre])
  const selectedShows = useMemo(
    () => selectedIds.map((id) => shows.find((show) => show.id === id)).filter((show) => show !== undefined),
    [shows, selectedIds],
  )

  const generate = () => {
    generation.mutate(selectedIds)
    resultRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  return (
    <main className="app">
      <header className="app__header">
        <h1>Episode Generator</h1>
        <p className="muted">Dream up a brand-new episode of your favourite show, or a crossover nobody asked for.</p>
      </header>

      <SelectionBar
        selectedShows={selectedShows}
        isGenerating={generation.isPending}
        onGenerate={generate}
        onClear={clear}
      />

      <section ref={resultRef} aria-live="polite" className="result">
        {generation.isPending && <p className="loading">Writing your episode… this can take a few seconds.</p>}
        {generation.isError && (
          <p role="alert" className="error">
            {generation.error.message}
          </p>
        )}
        {generation.isSuccess && <EpisodeView episode={generation.data} />}
      </section>

      <section className="browser" aria-label="Browse shows">
        <ShowFilters
          search={search}
          genre={genre}
          genres={genres}
          onSearchChange={setSearch}
          onGenreChange={setGenre}
        />
        {showsLoading && <p className="muted">Loading shows…</p>}
        {showsError && (
          <p role="alert" className="error">
            Could not load shows: {showsError.message}
          </p>
        )}
        {!showsLoading && !showsError && (
          <ShowGrid shows={visibleShows} selectedIds={selectedIds} selectionFull={isFull} onToggle={toggle} />
        )}
      </section>
    </main>
  )
}
