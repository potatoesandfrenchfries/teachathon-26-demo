import { useMemo, useState } from 'react'
import { useGraph } from '../../api/hooks'
import { toLevels, toWorlds } from '../../lib/graphAdapter'
import { WorldMap } from './WorldMap'

const allOpen = () => 'available' as const

/**
 * The student map. It draws the graph the backend serves. Until the professor approves the graph
 * nothing is gated, and gating by mastery is not built yet, so every concept is open either way.
 * If the backend cannot be reached it falls back to the built-in sample levels, and says so.
 */
export function StudentMap() {
  const { data: graph, error, isPending, refetch } = useGraph()
  const levels = useMemo(() => (graph ? toLevels(graph) : []), [graph])
  const worlds = useMemo(() => (graph ? toWorlds(graph) : []), [graph])
  const [openId, setOpenId] = useState<string | null>(null)

  if (isPending) return <div className="map-status">Loading the concept graph…</div>

  if (error || !graph) {
    return (
      <WorldMap
        notice={
          <div className="map-notice" role="status">
            {error?.message ?? 'The graph could not be loaded.'} Showing the built-in sample levels.
            <button type="button" onClick={() => void refetch()}>
              Try again
            </button>
          </div>
        }
      />
    )
  }

  const draft = graph.course.graph_status === 'draft'
  const opened = levels.find((l) => l.id === openId)
  return (
    <>
      <WorldMap
        levels={levels}
        worlds={worlds}
        statusOf={allOpen}
        subtitle={graph.course.name}
        onOpen={setOpenId}
        notice={
          <div className="map-notice map-notice--info" role="status">
            {draft
              ? 'Draft graph: the professor has not approved it yet, so every concept is open.'
              : 'Approved graph. Gating by mastery arrives in week 3, so every concept is still open.'}
          </div>
        }
      />
      {opened && (
        <aside className="node-info" aria-label="Concept details">
          <h3>{opened.title}</h3>
          <p>{opened.summary} are tagged to this concept.</p>
          <p>The practice flow for these questions is built in week 2.</p>
          <button type="button" className="btn" onClick={() => setOpenId(null)}>
            Close
          </button>
        </aside>
      )}
    </>
  )
}
