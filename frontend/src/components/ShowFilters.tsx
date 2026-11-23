const ALL_GENRES = ''

interface ShowFiltersProps {
  search: string
  genre: string
  genres: string[]
  onSearchChange: (search: string) => void
  onGenreChange: (genre: string) => void
}

export function ShowFilters({ search, genre, genres, onSearchChange, onGenreChange }: ShowFiltersProps) {
  return (
    <div className="filters">
      <label className="field">
        <span>Search shows</span>
        <input
          type="search"
          placeholder="Title or network…"
          value={search}
          onChange={(event) => onSearchChange(event.target.value)}
        />
      </label>
      <label className="field">
        <span>Genre</span>
        <select value={genre} onChange={(event) => onGenreChange(event.target.value)}>
          <option value={ALL_GENRES}>All genres</option>
          {genres.map((name) => (
            <option key={name} value={name}>
              {name}
            </option>
          ))}
        </select>
      </label>
    </div>
  )
}
