import dagre from '@dagrejs/dagre'

export interface LayoutEdge {
  source: string
  target: string
}

export interface LayoutOptions {
  /** 'TB' = top-to-bottom, 'LR' = left-to-right. */
  rankdir?: 'TB' | 'LR'
  /** Gap between nodes in the same rank. */
  nodesep?: number
  /** Gap between ranks (i.e. between prerequisite tiers). */
  ranksep?: number
}

// Must match (or exceed) the rendered footprint of a level node so dagre
// doesn't pack nodes closer than they actually appear on screen.
const NODE_WIDTH = 150
const NODE_HEIGHT = 110

/**
 * Auto-layout a prerequisite graph: any node/edge set works, not just this
 * project's specific level data — this is the seam a knowledge-graph import
 * would plug into (map KG nodes -> nodeIds, KG edges -> `edges`, done).
 */
export function computeDagreLayout(
  nodeIds: string[],
  edges: LayoutEdge[],
  options: LayoutOptions = {},
): Record<string, { x: number; y: number }> {
  const g = new dagre.graphlib.Graph()
  g.setGraph({
    rankdir: options.rankdir ?? 'TB',
    nodesep: options.nodesep ?? 70,
    ranksep: options.ranksep ?? 90,
  })
  g.setDefaultEdgeLabel(() => ({}))

  for (const id of nodeIds) {
    g.setNode(id, { width: NODE_WIDTH, height: NODE_HEIGHT })
  }
  for (const edge of edges) {
    if (g.hasNode(edge.source) && g.hasNode(edge.target)) {
      g.setEdge(edge.source, edge.target)
    }
  }

  dagre.layout(g)

  // dagre positions are node centers; React Flow positions are top-left corners.
  const positions: Record<string, { x: number; y: number }> = {}
  for (const id of nodeIds) {
    const node = g.node(id)
    positions[id] = { x: node.x - NODE_WIDTH / 2, y: node.y - NODE_HEIGHT / 2 }
  }
  return positions
}
