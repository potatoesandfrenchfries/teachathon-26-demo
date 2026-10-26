import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Background, Controls, MarkerType, ReactFlow, type Connection, type Edge, type Node } from '@xyflow/react'
import { ArrowLeft, BadgeCheck, KeyRound } from 'lucide-react'
import '@xyflow/react/dist/style.css'
import { api, getAdminKey, setAdminKey } from '../../api/client'
import { useGraph, useGraphMutation } from '../../api/hooks'
import type { ApiEdge, ApiGraph, EdgeType } from '../../api/types'
import { computeDagreLayout } from '../../lib/autoLayout'
import { flowEdgeStyle } from '../../lib/edgeStyle'
import { countByStatus, edgeLabel, reviewQueue, toWorlds, visibleEdges, worldId } from '../../lib/graphAdapter'
import { Button } from '../common/Button'
import { LevelNode, type LevelNodeData } from '../WorldMap/LevelNode'
import { EdgePanel } from './EdgePanel'
import '../WorldMap/WorldMap.css'
import './Review.css'

const nodeTypes = { level: LevelNode }

type Selection = { kind: 'edge'; id: number } | { kind: 'node'; id: number } | null
type Message = { kind: 'error' | 'info'; text: string } | null

export function ReviewPage() {
  const { data: graph, error, isPending } = useGraph()
  if (isPending) return <div className="map-status">Loading the concept graph…</div>
  if (error || !graph) {
    return (
      <div className="map-status">
        <div>
          <p>{error?.message ?? 'The graph could not be loaded.'}</p>
          <Link to="/">Back to the map</Link>
        </div>
      </div>
    )
  }
  return <Workspace graph={graph} />
}

function Workspace({ graph }: { graph: ApiGraph }) {
  const [selection, setSelection] = useState<Selection>(null)
  const [showImplied, setShowImplied] = useState(false)
  const [message, setMessage] = useState<Message>(null)
  const [keyDraft, setKeyDraft] = useState(getAdminKey())
  const [hasKey, setHasKey] = useState(getAdminKey() !== '')

  const accept = useGraphMutation((id: number) => api.accept(id))
  const reject = useGraphMutation((id: number) => api.reject(id))
  const retype = useGraphMutation((v: { id: number; type: EdgeType }) => api.retype(v.id, v.type))
  const remove = useGraphMutation((id: number) => api.deleteEdge(id))
  const add = useGraphMutation((v: { src: number; dst: number }) => api.addEdge(v.src, v.dst))
  const approve = useGraphMutation((acceptRemaining: boolean) => api.approve(acceptRemaining))
  const busy = [accept, reject, retype, remove, add, approve].some((m) => m.isPending)

  const approved = graph.course.graph_status === 'approved'
  const canEdit = hasKey && !approved
  const counts = countByStatus(graph)
  const queue = useMemo(() => reviewQueue(graph), [graph])
  const worlds = useMemo(() => toWorlds(graph), [graph])
  const colorOf = useMemo(() => new Map(worlds.map((w) => [w.id, w.color])), [worlds])

  // Run a change and show the server's answer. A refused change (a cycle, say) shows its message.
  function run<V>(
    mutation: { mutate: (v: V, o: { onSuccess: () => void; onError: (e: Error) => void }) => void },
    vars: V,
    done?: string,
  ) {
    mutation.mutate(vars, {
      onSuccess: () => setMessage(done ? { kind: 'info', text: done } : null),
      onError: (e) => setMessage({ kind: 'error', text: e.message }),
    })
  }

  // dagre gives the same positions for the same nodes and edge pairs, so a review decision (which
  // changes a status, not a pair) never moves the map.
  const positions = useMemo(
    () =>
      computeDagreLayout(
        graph.nodes.map((n) => String(n.id)),
        graph.edges.map((e) => ({ source: String(e.src_node), target: String(e.dst_node) })),
      ),
    [graph.nodes, graph.edges],
  )

  const flowNodes: Node<LevelNodeData>[] = graph.nodes.map((n) => ({
    id: String(n.id),
    type: 'level',
    position: positions[String(n.id)] ?? { x: 0, y: 0 },
    data: {
      title: n.title,
      status: 'available',
      worldColor: colorOf.get(worldId(n.world_group)) ?? '#999',
      meta: `${n.question_count} questions`,
      selected: selection?.kind === 'node' && selection.id === n.id,
      editable: canEdit,
    },
    draggable: false,
    deletable: false,
  }))

  const flowEdges: Edge[] = visibleEdges(graph, showImplied).map((e) => {
    const style = flowEdgeStyle(e, selection?.kind === 'edge' && selection.id === e.id)
    return {
      id: String(e.id),
      source: String(e.src_node),
      target: String(e.dst_node),
      type: 'smoothstep',
      label: style.label,
      markerEnd: { type: MarkerType.ArrowClosed, color: style.stroke, width: 16, height: 16 },
      style: {
        stroke: style.stroke,
        strokeWidth: style.strokeWidth,
        strokeDasharray: style.strokeDasharray,
        opacity: style.opacity,
      },
      labelStyle: { fill: style.flagged ? '#b42318' : '#667085', fontSize: 11, fontWeight: 600 },
      labelBgStyle: { fill: style.flagged ? '#ffecec' : '#fff' },
      labelBgPadding: [4, 2] as [number, number],
      labelBgBorderRadius: 4,
      interactionWidth: 24,
    }
  })

  function onConnect(connection: Connection) {
    if (!connection.source || !connection.target) return
    run(add, { src: Number(connection.source), dst: Number(connection.target) }, 'Edge added by hand.')
  }

  function onApprove() {
    const open = counts.proposed
    if (open > 0) {
      const ok = window.confirm(
        `${open} edges are still unreviewed. Approve anyway and accept them all? The graph is frozen afterwards.`,
      )
      if (!ok) return
    }
    run(approve, open > 0, 'Graph approved. It is now frozen.')
  }

  function saveKey() {
    setAdminKey(keyDraft.trim())
    setHasKey(keyDraft.trim() !== '')
    setMessage(null)
  }

  const selectedEdge: ApiEdge | undefined =
    selection?.kind === 'edge' ? graph.edges.find((e) => e.id === selection.id) : undefined
  const selectedNode = selection?.kind === 'node' ? graph.nodes.find((n) => n.id === selection.id) : undefined
  const rejected = graph.edges.filter((e) => e.status === 'rejected')

  return (
    <div className="review">
      <div className="app-bar">
        <div className="app-bar-left">
          <Link to="/" className="review__back" aria-label="Back to the map">
            <ArrowLeft size={20} color="#fff" />
          </Link>
          <div>
            <p className="app-bar-title">Graph review</p>
            <p className="app-bar-subtitle">{graph.course.name}</p>
          </div>
        </div>
        <div className="review__bar-right">
          <span className={`status-pill status-pill--${graph.course.graph_status}`}>
            {approved ? 'Approved and frozen' : 'Draft graph'}
          </span>
          <form
            className="key-form"
            onSubmit={(e) => {
              e.preventDefault()
              saveKey()
            }}
          >
            <KeyRound size={16} color="#fff" />
            <input
              type="password"
              placeholder="Admin key"
              aria-label="Admin key"
              value={keyDraft}
              onChange={(e) => setKeyDraft(e.target.value)}
            />
            <Button type="submit" inverted>
              {hasKey ? 'Update' : 'Save'}
            </Button>
          </form>
          <Button inverted disabled={!canEdit || busy} onClick={onApprove}>
            <BadgeCheck size={14} style={{ verticalAlign: 'text-bottom', marginRight: 4 }} />
            Approve graph
          </Button>
        </div>
      </div>

      <div className="review__toolbar">
        <span>
          <strong>{counts.proposed}</strong> to review · <strong>{counts.accepted}</strong> accepted ·{' '}
          <strong>{counts.rejected}</strong> rejected
        </span>
        <label className="toggle">
          <input type="checkbox" checked={showImplied} onChange={(e) => setShowImplied(e.target.checked)} />
          Show implied edges
        </label>
        <span className="muted">Drag from one concept to another to add an edge.</span>
      </div>

      {message && (
        <div className={`review__message review__message--${message.kind}`} role="alert">
          {message.text}
          <button type="button" onClick={() => setMessage(null)} aria-label="Dismiss">
            ×
          </button>
        </div>
      )}
      {!hasKey && !approved && (
        <div className="review__message review__message--info">
          Read-only until you enter the admin key above.
        </div>
      )}

      <div className="review__body">
        <aside className="review__queue" aria-label="Review queue">
          <h3>Review queue ({queue.length})</h3>
          {queue.length === 0 && <p className="muted">Nothing left to review.</p>}
          <ul>
            {queue.map((e) => (
              <li key={e.id}>
                <button
                  type="button"
                  className={selection?.kind === 'edge' && selection.id === e.id ? 'is-selected' : ''}
                  onClick={() => setSelection({ kind: 'edge', id: e.id })}
                >
                  <span>{edgeLabel(graph, e)}</span>
                  {e.disagreement && <span className="chip chip--danger">A≠B</span>}
                  <span className="muted">{e.type}</span>
                </button>
              </li>
            ))}
          </ul>
          {rejected.length > 0 && (
            <>
              <h3>Rejected ({rejected.length})</h3>
              <ul>
                {rejected.map((e) => (
                  <li key={e.id}>
                    <button
                      type="button"
                      className={selection?.kind === 'edge' && selection.id === e.id ? 'is-selected' : ''}
                      onClick={() => setSelection({ kind: 'edge', id: e.id })}
                    >
                      <span>{edgeLabel(graph, e)}</span>
                    </button>
                  </li>
                ))}
              </ul>
            </>
          )}
        </aside>

        <div className="review__canvas">
          <ReactFlow
            nodes={flowNodes}
            edges={flowEdges}
            nodeTypes={nodeTypes}
            onNodeClick={(_, n) => setSelection({ kind: 'node', id: Number(n.id) })}
            onEdgeClick={(_, e) => setSelection({ kind: 'edge', id: Number(e.id) })}
            onPaneClick={() => setSelection(null)}
            onConnect={onConnect}
            nodesDraggable={false}
            nodesConnectable={canEdit}
            deleteKeyCode={null}
            panOnScroll
            zoomOnScroll={false}
            fitView
            fitViewOptions={{ padding: 0.08 }}
            minZoom={0.2}
            proOptions={{ hideAttribution: true }}
          >
            <Background gap={24} color="#dfe3ea" />
            <Controls showInteractive={false} />
          </ReactFlow>
        </div>

        <aside className="review__detail" aria-label="Details">
          {selectedEdge && (
            <EdgePanel
              graph={graph}
              edge={selectedEdge}
              canEdit={canEdit}
              busy={busy}
              onAccept={() => run(accept, selectedEdge.id)}
              onReject={() => run(reject, selectedEdge.id)}
              onRetype={(type) => run(retype, { id: selectedEdge.id, type })}
              onDelete={() => {
                run(remove, selectedEdge.id, 'Edge deleted.')
                setSelection(null)
              }}
            />
          )}
          {selectedNode && (
            <div className="edge-panel">
              <p className="edge-panel__eyebrow">Concept</p>
              <h2 className="edge-panel__title">{selectedNode.title}</h2>
              <div className="chips">
                <span className="chip">{selectedNode.world_group ?? 'no group'}</span>
                <span className="chip">{selectedNode.question_count} questions</span>
              </div>
              <h3>Prerequisites</h3>
              <EdgeList graph={graph} edges={graph.edges.filter((e) => e.dst_node === selectedNode.id)} onPick={(id) => setSelection({ kind: 'edge', id })} />
              <h3>Leads to</h3>
              <EdgeList graph={graph} edges={graph.edges.filter((e) => e.src_node === selectedNode.id)} onPick={(id) => setSelection({ kind: 'edge', id })} />
            </div>
          )}
          {!selectedEdge && !selectedNode && (
            <div className="edge-panel">
              <p className="muted">
                Select an edge to see the evidence for it, or a concept to see what leads into and out of it.
              </p>
            </div>
          )}
        </aside>
      </div>
    </div>
  )
}

function EdgeList({ graph, edges, onPick }: { graph: ApiGraph; edges: ApiEdge[]; onPick: (id: number) => void }) {
  if (edges.length === 0) return <p className="muted">None.</p>
  return (
    <ul className="edge-list">
      {edges.map((e) => (
        <li key={e.id}>
          <button type="button" onClick={() => onPick(e.id)}>
            {edgeLabel(graph, e)} <span className="muted">{e.status}</span>
          </button>
        </li>
      ))}
    </ul>
  )
}

