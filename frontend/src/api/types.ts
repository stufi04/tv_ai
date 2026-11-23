export interface Show {
  id: string
  title: string
  year: number | null
  network: string | null
  genres: string[]
  summary: string
  imageUrl: string | null
  popularity: number
}

export interface ShowPage {
  items: Show[]
  total: number
  nextOffset: number | null
  /** True while the backend downloads the catalogue for the first time. */
  syncing: boolean
}

export interface ShowQuery {
  q: string
  genre: string
  seed: number
}

export interface Episode {
  showIds: string[]
  title: string
  logline: string
  story: string
  /** A data: URL; null when images are off or the image model failed. */
  imageDataUrl: string | null
}
