import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { levelsById } from '../data/levels'
import type { LevelStatus } from '../types'

const STORAGE_KEY = 'qna-quest-progress'

interface CompletionRecord {
  hasWarning: boolean
}

type CompletionMap = Record<string, CompletionRecord>

function loadProgress(): CompletionMap {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? (JSON.parse(raw) as CompletionMap) : {}
  } catch {
    return {}
  }
}

interface ProgressContextValue {
  completed: CompletionMap
  isUnlocked: (levelId: string) => boolean
  isCompleted: (levelId: string) => boolean
  getStatus: (levelId: string) => LevelStatus
  completeLevel: (levelId: string) => void
  resetProgress: () => void
}

const ProgressContext = createContext<ProgressContextValue | null>(null)

export function ProgressProvider({ children }: { children: ReactNode }) {
  const [completed, setCompleted] = useState<CompletionMap>(() => loadProgress())

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(completed))
  }, [completed])

  const isUnlocked = useMemo(
    () => (levelId: string) => {
      const level = levelsById.get(levelId)
      if (!level) return false
      return level.prerequisites.every((prereqId) => prereqId in completed)
    },
    [completed],
  )

  const getStatus = useMemo(
    () =>
      (levelId: string): LevelStatus => {
        const record = completed[levelId]
        if (record) return record.hasWarning ? 'complete-warning' : 'complete'
        return isUnlocked(levelId) ? 'available' : 'locked'
      },
    [completed, isUnlocked],
  )

  function completeLevel(levelId: string) {
    const level = levelsById.get(levelId)
    const hasWarning = (level?.optionalPrerequisites ?? []).some((id) => !(id in completed))
    setCompleted((prev) => ({ ...prev, [levelId]: { hasWarning } }))
  }

  function resetProgress() {
    setCompleted({})
  }

  function isCompleted(levelId: string) {
    return levelId in completed
  }

  return (
    <ProgressContext.Provider
      value={{ completed, isUnlocked, isCompleted, getStatus, completeLevel, resetProgress }}
    >
      {children}
    </ProgressContext.Provider>
  )
}

export function useProgress() {
  const ctx = useContext(ProgressContext)
  if (!ctx) throw new Error('useProgress must be used within a ProgressProvider')
  return ctx
}
