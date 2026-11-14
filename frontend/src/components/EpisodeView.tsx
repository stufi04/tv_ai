import type { Episode } from '../api/types'

interface EpisodeViewProps {
  episode: Episode
}

export function EpisodeView({ episode }: EpisodeViewProps) {
  const paragraphs = episode.story.split(/\n\s*\n/).filter((paragraph) => paragraph.trim() !== '')

  return (
    <article className="episode" aria-label="Generated episode">
      {episode.imageDataUrl ? (
        <img className="episode__image" src={episode.imageDataUrl} alt={`Illustration for “${episode.title}”`} />
      ) : (
        <p className="episode__no-image muted">No illustration this time (the image model may be out of quota).</p>
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
