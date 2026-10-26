import { Check, RotateCcw, Trash2, X } from 'lucide-react'
import type { ApiEdge, ApiGraph, EdgeType } from '../../api/types'
import { Button } from '../common/Button'

interface EdgePanelProps {
  graph: ApiGraph
  edge: ApiEdge
  canEdit: boolean
  busy: boolean
  onAccept: () => void
  onReject: () => void
  onRetype: (type: EdgeType) => void
  onDelete: () => void
}

const titleOf = (graph: ApiGraph, id: number) => graph.nodes.find((n) => n.id === id)?.title ?? String(id)

/** Everything the professor needs to decide on one edge: what each pipeline said and why. */
export function EdgePanel({ graph, edge, canEdit, busy, onAccept, onReject, onRetype, onDelete }: EdgePanelProps) {
  const disabled = !canEdit || busy
  const otherType: EdgeType = edge.type === 'required' ? 'optional' : 'required'
  const pipelines = Object.entries(edge.classifications)

  return (
    <div className="edge-panel">
      <p className="edge-panel__eyebrow">Prerequisite</p>
      <h2 className="edge-panel__title">
        <span>{titleOf(graph, edge.src_node)}</span>
        <span className="edge-panel__arrow" aria-label="is a prerequisite of">
          ↓
        </span>
        <span>{titleOf(graph, edge.dst_node)}</span>
      </h2>

      <div className="chips">
        <span className={`chip chip--${edge.status}`}>{edge.status}</span>
        <span className="chip">{edge.type}</span>
        <span className="chip">{edge.source === 'manual' ? 'added by hand' : 'from cross-references'}</span>
        {edge.hidden && <span className="chip chip--muted">implied by a longer path</span>}
        {edge.disagreement && <span className="chip chip--danger">pipelines disagree</span>}
      </div>

      <section>
        <h3>Pipeline verdicts</h3>
        {pipelines.length === 0 ? (
          <p className="muted">No pipeline has classified this edge yet.</p>
        ) : (
          <ul className="verdicts">
            {pipelines.map(([name, c]) => (
              <li key={name}>
                <div className="verdicts__head">
                  <strong>Pipeline {name}</strong>
                  <span className={`chip chip--verdict-${c.type}`}>{c.type}</span>
                  <span className="muted">{Math.round(c.confidence * 100)}% sure</span>
                </div>
                <p>{c.justification}</p>
                <p className="muted small">
                  {c.provider} · {c.model} · {c.prompt_version}
                </p>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section>
        <h3>
          Evidence from the text <span className="muted">({edge.evidence.total} cross-references)</span>
        </h3>
        {edge.evidence.crossrefs.length === 0 ? (
          <p className="muted">No cross-references were recorded between these sections.</p>
        ) : (
          <ul className="crossrefs">
            {edge.evidence.crossrefs.map((ref, i) => (
              <li key={i}>
                <strong>{ref.referring}</strong> (§{ref.referring_section}) refers to{' '}
                <strong>{ref.referred}</strong> (§{ref.referred_section})
                {ref.count > 1 && <span className="muted"> × {ref.count}</span>}
              </li>
            ))}
          </ul>
        )}
      </section>

      <div className="edge-panel__actions">
        {edge.status === 'rejected' ? (
          <Button disabled={disabled} onClick={onAccept}>
            <RotateCcw size={14} /> Restore as accepted
          </Button>
        ) : (
          <>
            <Button disabled={disabled || edge.status === 'accepted'} onClick={onAccept}>
              <Check size={14} /> Accept
            </Button>
            <Button disabled={disabled} onClick={onReject}>
              <X size={14} /> Reject
            </Button>
            <Button disabled={disabled} onClick={() => onRetype(otherType)}>
              Make {otherType}
            </Button>
          </>
        )}
        {edge.source === 'manual' && (
          <Button disabled={disabled} onClick={onDelete}>
            <Trash2 size={14} /> Delete
          </Button>
        )}
      </div>
      {!canEdit && <p className="muted small">Editing needs the admin key and a graph that is not yet approved.</p>}
    </div>
  )
}
