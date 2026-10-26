import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from './client'
import type { ApiGraph } from './types'

export const GRAPH_KEY = ['graph'] as const

/** The concept graph. Not retried: when the backend is down the UI should say so at once. */
export function useGraph() {
  return useQuery({ queryKey: GRAPH_KEY, queryFn: () => api.graph(), retry: false })
}

/**
 * Run a graph-changing request. The server answers with the resulting graph, so on success that
 * graph simply replaces the cached one.
 */
export function useGraphMutation<Vars>(run: (vars: Vars) => Promise<ApiGraph>) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: run,
    onSuccess: (graph) => queryClient.setQueryData(GRAPH_KEY, graph),
  })
}
