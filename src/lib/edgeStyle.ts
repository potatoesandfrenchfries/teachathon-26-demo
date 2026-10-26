import type { ApiEdge } from '../api/types'

export const EDGE_COLORS = {
  proposed: '#667085',
  accepted: '#17b26a',
  selected: '#1976d2',
  warning: '#b3760a',
  disagreement: '#e5484d',
} as const

export interface FlowEdgeStyle {
  stroke: string
  strokeWidth: number
  strokeDasharray?: string
  /** Implied edges are faded: the map would be clear without them. */
  opacity: number
  label?: string
  /** Pipelines disagree about this edge. */
  flagged: boolean
}

/** How one prerequisite edge looks: colour for its review status, dashes for optional. */
export function flowEdgeStyle(edge: ApiEdge, selected: boolean): FlowEdgeStyle {
  const labels: string[] = []
  if (edge.type === 'optional') labels.push('optional')
  if (edge.disagreement) labels.push('pipelines disagree')
  const base = edge.status === 'accepted' ? EDGE_COLORS.accepted : EDGE_COLORS.proposed
  return {
    stroke: selected ? EDGE_COLORS.selected : base,
    strokeWidth: selected ? 4 : 2.5,
    strokeDasharray: edge.type === 'optional' ? '6 4' : undefined,
    opacity: edge.hidden && !selected ? 0.45 : 1,
    label: labels.length ? labels.join(' · ') : undefined,
    flagged: edge.disagreement,
  }
}
