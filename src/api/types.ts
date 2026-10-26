// Mirrors backend/schemas/graph.py. Keep the two in step.

export type EdgeType = 'required' | 'optional'
export type EdgeStatus = 'proposed' | 'accepted' | 'rejected'
export type Verdict = EdgeType | 'none'

export interface ApiCourse {
  id: number
  name: string
  graph_status: 'draft' | 'approved'
  graph_version: number
  lock_mode: string
}

export interface ApiNode {
  id: number
  title: string
  section_number: string | null
  world_group: string | null
  threshold: number | null
  k_required: number | null
  origin: string
  question_count: number
}

export interface ApiClassification {
  type: Verdict
  justification: string
  confidence: number
  provider: string
  model: string
  prompt_version: string
}

export interface ApiCrossRef {
  referring: string
  referring_section: string
  referred: string
  referred_section: string
  count: number
}

export interface ApiEdge {
  id: number
  src_node: number
  dst_node: number
  type: EdgeType
  weight: number
  source: 'xref' | 'llm' | 'manual'
  status: EdgeStatus
  justification: string | null
  classifications: Record<string, ApiClassification>
  disagreement: boolean
  hidden: boolean
  evidence: { total: number; crossrefs: ApiCrossRef[] }
}

export interface ApiGraph {
  course: ApiCourse
  nodes: ApiNode[]
  edges: ApiEdge[]
  review_queue: number[]
}

export interface ApiEdit {
  id: number
  graph_version: number
  actor: string
  ts: string
  op: string
  target_id: number | null
  before: Record<string, unknown> | null
  after: Record<string, unknown> | null
}
