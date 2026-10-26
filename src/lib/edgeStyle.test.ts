import { describe, expect, it } from 'vitest'
import type { ApiEdge } from '../api/types'
import { EDGE_COLORS, flowEdgeStyle } from './edgeStyle'

const edge = (over: Partial<ApiEdge> = {}): ApiEdge => ({
  id: 1,
  src_node: 1,
  dst_node: 2,
  type: 'required',
  weight: 2,
  source: 'xref',
  status: 'proposed',
  justification: null,
  classifications: {},
  disagreement: false,
  hidden: false,
  evidence: { total: 2, crossrefs: [] },
  ...over,
})

describe('flowEdgeStyle', () => {
  it('colours by review status', () => {
    expect(flowEdgeStyle(edge(), false).stroke).toBe(EDGE_COLORS.proposed)
    expect(flowEdgeStyle(edge({ status: 'accepted' }), false).stroke).toBe(EDGE_COLORS.accepted)
  })

  it('dashes and labels an optional edge, and leaves a required one solid and unlabelled', () => {
    const optional = flowEdgeStyle(edge({ type: 'optional' }), false)
    expect(optional.strokeDasharray).toBeDefined()
    expect(optional.label).toBe('optional')
    const required = flowEdgeStyle(edge(), false)
    expect(required.strokeDasharray).toBeUndefined()
    expect(required.label).toBeUndefined()
  })

  it('flags a disagreement in the label and combines it with optional', () => {
    const style = flowEdgeStyle(edge({ disagreement: true, type: 'optional' }), false)
    expect(style.flagged).toBe(true)
    expect(style.label).toBe('optional · pipelines disagree')
  })

  it('fades an implied edge unless it is selected', () => {
    expect(flowEdgeStyle(edge({ hidden: true }), false).opacity).toBeLessThan(1)
    expect(flowEdgeStyle(edge({ hidden: true }), true).opacity).toBe(1)
  })

  it('highlights the selected edge', () => {
    const style = flowEdgeStyle(edge({ status: 'accepted' }), true)
    expect(style.stroke).toBe(EDGE_COLORS.selected)
    expect(style.strokeWidth).toBeGreaterThan(flowEdgeStyle(edge(), false).strokeWidth)
  })
})
