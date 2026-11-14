import { useMutation } from '@tanstack/react-query'
import { createEpisode } from '../api/client'

export function useGenerateEpisode() {
  return useMutation({ mutationFn: createEpisode })
}
