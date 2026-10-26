import type { ApiEdge, ApiGraph } from '../api/types'
import type { LevelData, WorldData } from '../types'

const WORLD_COLORS = ['#1976d2', '#8e24aa', '#d84315', '#00897b', '#c77800', '#5e35b1']

export function worldId(group: string | null): string {
  return (group ?? 'other').toLowerCase().replace(/[^a-z0-9]+/g, '-')
}

/** One world per distinct group, in the order the groups first appear, with a repeating palette. */
export function toWorlds(graph: ApiGraph): WorldData[] {
  const seen = new Map<string, WorldData>()
  for (const node of graph.nodes) {
    const id = worldId(node.world_group)
    if (!seen.has(id)) {
      seen.set(id, {
        id,
        title: node.world_group ?? 'Other',
        color: WORLD_COLORS[seen.size % WORLD_COLORS.length],
      })
    }
  }
  return [...seen.values()]
}

/** Edges worth drawing: never the rejected ones, and the implied ones only if asked for. */
export function visibleEdges(graph: ApiGraph, showImplied: boolean): ApiEdge[] {
  return graph.edges.filter((e) => e.status !== 'rejected' && (showImplied || !e.hidden))
}

/**
 * The graph in the shape the student map already understands. Levels ids are the node ids as
 * strings. Required edges become prerequisites and optional ones optional prerequisites.
 * Questions stay empty until the practice flow is built on the API.
 */
export function toLevels(graph: ApiGraph): LevelData[] {
  const edges = visibleEdges(graph, false)
  return graph.nodes.map((node) => {
    const into = edges.filter((e) => e.dst_node === node.id)
    return {
      id: String(node.id),
      worldId: worldId(node.world_group),
      title: node.title,
      summary: `${node.question_count} practice questions`,
      prerequisites: into.filter((e) => e.type === 'required').map((e) => String(e.src_node)),
      optionalPrerequisites: into.filter((e) => e.type === 'optional').map((e) => String(e.src_node)),
      questions: [],
    }
  })
}

/** Edges a professor still has to look at, in the server's order (disagreements first). */
export function reviewQueue(graph: ApiGraph): ApiEdge[] {
  const byId = new Map(graph.edges.map((e) => [e.id, e]))
  return graph.review_queue.map((id) => byId.get(id)).filter((e): e is ApiEdge => e !== undefined)
}

export function countByStatus(graph: ApiGraph): Record<ApiEdge['status'], number> {
  const counts = { proposed: 0, accepted: 0, rejected: 0 }
  for (const edge of graph.edges) counts[edge.status] += 1
  return counts
}

/** "2.1 -> 2.2", falling back to the titles when a node has no section number. */
export function edgeLabel(graph: ApiGraph, edge: ApiEdge): string {
  const name = (id: number) => {
    const node = graph.nodes.find((n) => n.id === id)
    return node?.section_number ?? node?.title ?? String(id)
  }
  return `${name(edge.src_node)} → ${name(edge.dst_node)}`
}
