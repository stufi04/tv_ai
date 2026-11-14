export interface Show {
  id: string
  title: string
  year: number
  network: string
  genres: string[]
  summary: string
}

export interface Episode {
  showIds: string[]
  title: string
  logline: string
  story: string
  imageDataUrl: string | null
}
