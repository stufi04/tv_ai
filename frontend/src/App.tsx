import { useCallback, useMemo, useRef, useState } from 'react'
import { EpisodeView } from './components/EpisodeView'
import { SelectionBar } from './components/SelectionBar'
import { ShowFilters } from './components/ShowFilters'
import { ShowGrid } from './components/ShowGrid'
import { useDebouncedValue } from './hooks/useDebouncedValue'
import { useGenerateEpisode } from './hooks/useGenerateEpisode'
import { useGenres } from './hooks/useGenres'
import { useShowSelection } from './hooks/useShowSelection'
import { useShows } from './hooks/useShows'

const SEARCH_DEBOUNCE_MS = 250

export default function App() {
  const [search, setSearch] = useState('')
  const [genre, setGenre] = useState('')
  // One random seed per page load: a fresh mix of popular shows each visit, stable while scrolling.
  const [seed] = useState(() => Math.floor(Math.random() * 2 ** 31))
  const debouncedSearch = useDebouncedValue(search, SEARCH_DEBOUNCE_MS)

  const showsQuery = useShows({ q: debouncedSearch.trim(), genre, seed })
  const { data, isPending: showsLoading, error: showsError, hasNextPage, isFetchingNextPage, fetchNextPage } = showsQuery
  const syncing = data?.pages[0]?.syncing ?? false
  const { data: genres = [] } = useGenres(syncing)

  const { selectedShows, selectedIds, isFull, toggle, clear } = useShowSelection()
  const generation = useGenerateEpisode()
  const resultRef = useRef<HTMLElement>(null)

  // The same show can't appear twice in a seeded listing, but dedupe defensively in case pages shift.
  const shows = useMemo(() => {
    const seen = new Set<string>()
    return (data?.pages ?? []).flatMap((page) =>
      page.items.filter((show) => !seen.has(show.id) && seen.add(show.id)),
    )
  }, [data])

  const loadMore = useCallback(() => {
    if (hasNextPage && !isFetchingNextPage) void fetchNextPage()
  }, [hasNextPage, isFetchingNextPage, fetchNextPage])

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
        {syncing && (
          <p className="loading">
            Downloading the show catalogue from TVmaze for the first time. This takes about 3 minutes and only
            happens once.
          </p>
        )}
        {data && !syncing && (
          <ShowGrid
            shows={shows}
            selectedIds={selectedIds}
            selectionFull={isFull}
            onToggle={toggle}
            hasMore={hasNextPage}
            loadingMore={isFetchingNextPage}
            onLoadMore={loadMore}
          />
        )}
      </section>

      <footer className="app__footer muted">
        Show data from{' '}
        <a href="https://www.tvmaze.com" target="_blank" rel="noreferrer">
          TVmaze
        </a>{' '}
        (CC BY-SA).
      </footer>
    </main>
  )
}
