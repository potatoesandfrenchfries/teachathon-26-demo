export type QuestionType = 'multiple-choice' | 'short-answer'

export interface Question {
  id: string
  type: QuestionType
  prompt: string
  /** Only present for multiple-choice questions. */
  options?: string[]
  /** Correct answer. For short-answer, matched case-insensitively after trimming. */
  answer: string
  /** Revealed one at a time when the player asks for help. */
  hints: string[]
}

export interface LevelData {
  id: string
  worldId: string
  title: string
  summary: string
  /** Level ids that MUST be completed before this level unlocks. */
  prerequisites: string[]
  /**
   * Level ids that are recommended but not required. Skipping them doesn't
   * block access, but completing this level without them marks it "complete
   * with warnings" instead of fully clean.
   */
  optionalPrerequisites?: string[]
  questions: Question[]
}

export interface WorldData {
  id: string
  title: string
  color: string
}

export type LevelStatus = 'locked' | 'available' | 'complete-warning' | 'complete'
