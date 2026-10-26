import { describe, expect, it } from 'vitest'
import type { ApiEdge, ApiGraph, ApiNode } from '../api/types'
import { countByStatus, edgeLabel, reviewQueue, toLevels, toWorlds, visibleEdges, worldId } from './graphAdapter'

const node = (id: number, number: string, group: string | null): ApiNode => ({
  id,
  title: `${number} Title`,
  section_number: number,
  world_group: group,
  threshold: null,
  k_required: null,
  origin: 'section',
  question_count: id * 2,
})

const edge = (id: number, src: number, dst: number, over: Partial<ApiEdge> = {}): ApiEdge => ({
  id,
  src_node: src,
  dst_node: dst,
  type: 'required',
  weight: 3,
  source: 'xref',
  status: 'proposed',
  justification: null,
  classifications: {},
  disagreement: false,
  hidden: false,
  evidence: { total: 3, crossrefs: [] },
  ...over,
})

const graph: ApiGraph = {
  course: { id: 1, name: 'Mock', graph_status: 'draft', graph_version: 1, lock_mode: 'soft' },
  nodes: [node(1, '1.1', 'Foundations'), node(2, '2.1', 'Kinematics'), node(3, '2.2', 'Kinematics'), node(4, '3.1', null)],
  edges: [
    edge(10, 1, 2),
    edge(11, 2, 3, { type: 'optional' }),
    edge(12, 1, 3, { hidden: true }),
    edge(13, 3, 4, { status: 'rejected' }),
    edge(14, 2, 4, { status: 'accepted', disagreement: true }),
  ],
  review_queue: [11, 10, 12],
}

describe('worlds', () => {
  it('makes a url-safe id from a group name', () => {
    expect(worldId('Foundations & Units')).toBe('foundations-units')
    expect(worldId(null)).toBe('other')
  })

  it('creates one world per group, in first-seen order, with a colour each', () => {
    const worlds = toWorlds(graph)
    expect(worlds.map((w) => w.title)).toEqual(['Foundations', 'Kinematics', 'Other'])
    expect(new Set(worlds.map((w) => w.color)).size).toBe(3)
  })

  it('reuses the palette when there are more groups than colours', () => {
    const many: ApiGraph = {
      ...graph,
      nodes: Array.from({ length: 8 }, (_, i) => node(i + 1, `${i}.1`, `Group ${i}`)),
    }
    const worlds = toWorlds(many)
    expect(worlds).toHaveLength(8)
    expect(worlds[6].color).toBe(worlds[0].color)
  })
})

describe('visibleEdges', () => {
  it('never shows rejected edges and hides implied ones unless asked', () => {
    expect(visibleEdges(graph, false).map((e) => e.id)).toEqual([10, 11, 14])
    expect(visibleEdges(graph, true).map((e) => e.id)).toEqual([10, 11, 12, 14])
  })
})

describe('toLevels', () => {
  const levels = toLevels(graph)
  const byId = new Map(levels.map((l) => [l.id, l]))

  it('has one level per node, keyed by the node id', () => {
    expect(levels.map((l) => l.id)).toEqual(['1', '2', '3', '4'])
    expect(byId.get('2')?.worldId).toBe('kinematics')
    expect(byId.get('2')?.summary).toBe('4 practice questions')
  })

  it('turns required edges into prerequisites and optional ones into optional prerequisites', () => {
    expect(byId.get('2')?.prerequisites).toEqual(['1'])
    expect(byId.get('3')?.prerequisites).toEqual([])
    expect(byId.get('3')?.optionalPrerequisites).toEqual(['2'])
  })

  it('leaves out implied and rejected edges', () => {
    expect(byId.get('3')?.prerequisites).not.toContain('1') // edge 12 is implied
    expect(byId.get('4')?.prerequisites).toEqual(['2']) // edge 13 is rejected, edge 14 stays
  })

  it('has no questions yet', () => {
    expect(levels.every((l) => l.questions.length === 0)).toBe(true)
  })
})

describe('review helpers', () => {
  it('keeps the server order for the queue and skips ids it cannot find', () => {
    expect(reviewQueue(graph).map((e) => e.id)).toEqual([11, 10, 12])
    expect(reviewQueue({ ...graph, review_queue: [99, 10] }).map((e) => e.id)).toEqual([10])
  })

  it('counts edges by status', () => {
    expect(countByStatus(graph)).toEqual({ proposed: 3, accepted: 1, rejected: 1 })
  })

  it('labels an edge by section numbers', () => {
    expect(edgeLabel(graph, graph.edges[0])).toBe('1.1 → 2.1')
    const noNumber: ApiGraph = { ...graph, nodes: [{ ...graph.nodes[0], section_number: null }, graph.nodes[1]] }
    expect(edgeLabel(noNumber, graph.edges[0])).toBe('1.1 Title → 2.1')
  })
})
