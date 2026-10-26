import type { CSSProperties } from 'react'
import { Handle, Position, type NodeProps } from '@xyflow/react'
import { Lock, Check, AlertTriangle } from 'lucide-react'
import type { LevelStatus } from '../../types'

export interface LevelNodeData {
  title: string
  status: LevelStatus
  worldColor: string
  /** A second, smaller line under the title, for example a question count. */
  meta?: string
  selected?: boolean
  /** Show connection handles so the professor can drag a new edge from here. */
  editable?: boolean
  [key: string]: unknown
}

export function LevelNode({ data }: NodeProps) {
  const { title, status, worldColor, meta, selected, editable } = data as LevelNodeData
  const classes = ['level-node', `level-node--${status}`]
  if (selected) classes.push('level-node--selected')
  if (editable) classes.push('level-node--editable')

  return (
    <div className={classes.join(' ')}>
      <Handle type="target" position={Position.Top} className="level-node__handle" />
      <div
        className="level-node__circle"
        style={
          status === 'available' || status === 'complete'
            ? ({ '--world-color': worldColor } as CSSProperties)
            : undefined
        }
      >
        {status === 'locked' && <Lock size={20} strokeWidth={2.25} />}
        {status === 'complete' && <Check size={26} strokeWidth={3} />}
        {status === 'complete-warning' && <AlertTriangle size={22} strokeWidth={2.25} />}
        {status === 'available' && <span className="level-node__dot" />}
      </div>
      <div className="level-node__label">{title}</div>
      {meta && <div className="level-node__meta">{meta}</div>}
      <Handle type="source" position={Position.Bottom} className="level-node__handle" />
    </div>
  )
}
