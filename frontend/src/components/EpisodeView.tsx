import type { Episode } from '../api/types'

interface EpisodeViewProps {
  episode: Episode
}

export function EpisodeView({ episode }: EpisodeViewProps) {
  const paragraphs = episode.story.split(/\n\s*\n/).filter((paragraph) => paragraph.trim() !== '')

  return (
    <article className={episode.imageDataUrl ? 'episode episode--illustrated' : 'episode'} aria-label="Generated episode">
      {episode.imageDataUrl && (
        <img className="episode__image" src={episode.imageDataUrl} alt={`Illustration for “${episode.title}”`} />
      )}
      <div className="episode__body">
        <h2>{episode.title}</h2>
        <p className="episode__logline">{episode.logline}</p>
        {paragraphs.map((paragraph, index) => (
          <p key={index}>{paragraph}</p>
        ))}
      </div>
    </article>
  )
}
