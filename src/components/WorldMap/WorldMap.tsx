import { useMemo, type ReactNode } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ReactFlow, Background, MarkerType, type Edge, type Node } from '@xyflow/react'
import { Network, RotateCcw, ClipboardCheck } from 'lucide-react'
import '@xyflow/react/dist/style.css'
import { levels as sampleLevels } from '../../data/levels'
import { worlds as sampleWorlds } from '../../data/worlds'
import { useProgress } from '../../context/ProgressContext'
import type { LevelData, LevelStatus, WorldData } from '../../types'
import { Button } from '../common/Button'
import { LevelNode, type LevelNodeData } from './LevelNode'
import { computeDagreLayout, type LayoutEdge } from '../../lib/autoLayout'
import './WorldMap.css'

const nodeTypes = { level: LevelNode }

interface WorldMapProps {
  /** The graph to draw. Defaults to the built-in sample levels. */
  levels?: LevelData[]
  worlds?: WorldData[]
  /**
   * Overrides the progress-based status. Used for a graph where nothing gates yet, so every level
   * is open and there is no progress to reset.
   */
  statusOf?: (levelId: string) => LevelStatus
  subtitle?: string
  /** A banner under the toolbar, for example "draft graph". */
  notice?: ReactNode
  /** Called instead of opening the level page. */
  onOpen?: (levelId: string) => void
}

export function WorldMap({
  levels = sampleLevels,
  worlds = sampleWorlds,
  statusOf,
  subtitle = 'Complete levels to unlock the next challenges.',
  notice,
  onOpen,
}: WorldMapProps) {
  const navigate = useNavigate()
  const progress = useProgress()
  const getStatus = statusOf ?? progress.getStatus
  const { resetProgress } = progress

  const worldColor = useMemo(() => {
    const map = new Map(worlds.map((w) => [w.id, w.color]))
    return (worldId: string) => map.get(worldId) ?? '#999'
  }, [worlds])

  // Layout only depends on the level graph's shape (ids + edges), not on
  // progress, so it's computed once per mount rather than on every unlock.
  const levelPositions = useMemo(() => {
    const nodeIds = levels.map((l) => l.id)
    const layoutEdges: LayoutEdge[] = []
    for (const level of levels) {
      for (const prereqId of level.prerequisites) layoutEdges.push({ source: prereqId, target: level.id })
      for (const prereqId of level.optionalPrerequisites ?? [])
        layoutEdges.push({ source: prereqId, target: level.id })
    }
    return computeDagreLayout(nodeIds, layoutEdges)
  }, [levels])

  const nodes: Node<LevelNodeData>[] = levels.map((level) => ({
    id: level.id,
    type: 'level',
    position: levelPositions[level.id] ?? { x: 0, y: 0 },
    data: {
      title: level.title,
      status: getStatus(level.id),
      worldColor: worldColor(level.worldId),
    },
    draggable: false,
  }))

  const completedCount = levels.filter((l) => getStatus(l.id).startsWith('complete')).length
  const progressPct = Math.round((completedCount / levels.length) * 100)

  const edges: Edge[] = []
  for (const level of levels) {
    for (const prereqId of level.prerequisites) {
      const done = getStatus(prereqId).startsWith('complete')
      edges.push({
        id: `${prereqId}->${level.id}`,
        source: prereqId,
        target: level.id,
        type: 'smoothstep',
        markerEnd: { type: MarkerType.ArrowClosed, color: done ? '#17b26a' : '#b5bac3', width: 16, height: 16 },
        style: {
          stroke: done ? '#17b26a' : '#c7cbd4',
          strokeWidth: 2.5,
        },
      })
    }
    for (const optPrereqId of level.optionalPrerequisites ?? []) {
      edges.push({
        id: `${optPrereqId}~>${level.id}`,
        source: optPrereqId,
        target: level.id,
        type: 'smoothstep',
        label: 'optional',
        style: {
          stroke: '#f5a524',
          strokeWidth: 2,
          strokeDasharray: '6 4',
        },
        labelStyle: { fill: '#b3760a', fontSize: 11, fontWeight: 600 },
        labelBgStyle: { fill: '#fff6e5' },
        labelBgPadding: [4, 2],
        labelBgBorderRadius: 4,
      })
    }
  }

  function handleNodeClick(_: unknown, node: Node) {
    const status = getStatus(node.id)
    if (status === 'locked') return
    if (onOpen) onOpen(node.id)
    else navigate(`/level/${node.id}`)
  }

  return (
    <div className="world-map">
      <div className="app-bar">
        <div className="app-bar-left">
          <Network size={22} strokeWidth={2.25} color="#fff" />
          <div>
            <p className="app-bar-title">QnA Quest</p>
            <p className="app-bar-subtitle">{subtitle}</p>
          </div>
        </div>
        <div className="world-map__progress-pill">
          <span>
            {completedCount}/{levels.length} complete
          </span>
          <span className="world-map__progress-track">
            <span className="world-map__progress-fill" style={{ width: `${progressPct}%` }} />
          </span>
        </div>
      </div>
      <div className="world-map__toolbar">
        <Legend />
        {statusOf ? (
          <Link to="/review" className="btn">
            <ClipboardCheck size={14} strokeWidth={2.25} style={{ verticalAlign: 'text-bottom', marginRight: 4 }} />
            Professor review
          </Link>
        ) : (
          <Button onClick={resetProgress}>
            <RotateCcw size={14} strokeWidth={2.25} style={{ verticalAlign: 'text-bottom', marginRight: 4 }} />
            Reset progress
          </Button>
        )}
      </div>
      {notice}
      <div className="world-map__canvas">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          onNodeClick={handleNodeClick}
          nodesDraggable={false}
          nodesConnectable={false}
          elementsSelectable={false}
          panOnScroll
          zoomOnScroll={false}
          fitView
          fitViewOptions={{ padding: 0.08 }}
          minZoom={0.2}
          proOptions={{ hideAttribution: true }}
        >
          <Background gap={24} color="#dfe3ea" />
        </ReactFlow>
      </div>
    </div>
  )
}

function Legend() {
  return (
    <div className="legend">
      <span className="legend__item">
        <span className="legend__swatch legend__swatch--locked" /> Locked
      </span>
      <span className="legend__item">
        <span className="legend__swatch legend__swatch--available" /> Available
      </span>
      <span className="legend__item">
        <span className="legend__swatch legend__swatch--warning" /> Complete (warnings)
      </span>
      <span className="legend__item">
        <span className="legend__swatch legend__swatch--complete" /> Complete
      </span>
      <span className="legend__item">
        <span className="legend__edge legend__edge--optional" /> Optional prerequisite
      </span>
    </div>
  )
}
