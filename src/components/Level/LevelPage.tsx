import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, Lock, CheckCircle2, AlertTriangle, Sparkles } from 'lucide-react'
import { levelsById } from '../../data/levels'
import { worlds } from '../../data/worlds'
import { useProgress } from '../../context/ProgressContext'
import { Button } from '../common/Button'
import { QuestionCard } from './QuestionCard'
import './Level.css'

export function LevelPage() {
  const { levelId } = useParams<{ levelId: string }>()
  const navigate = useNavigate()
  const { getStatus, isCompleted, completeLevel } = useProgress()

  const level = levelId ? levelsById.get(levelId) : undefined
  const [questionIndex, setQuestionIndex] = useState(0)
  const [finished, setFinished] = useState(false)

  if (!level) {
    return (
      <div className="level-page">
        <p>Level not found.</p>
        <Button className="level-page__primary-btn" onClick={() => navigate('/')}>
          Back to map
        </Button>
      </div>
    )
  }

  const status = getStatus(level.id)
  if (status === 'locked') {
    return (
      <div className="level-page">
        <div className="level-locked">
          <div className="level-locked__icon">
            <Lock size={28} strokeWidth={2.25} />
          </div>
          <h2>This level is locked</h2>
          <p>Complete its prerequisites on the world map first.</p>
          <Button className="level-page__primary-btn" onClick={() => navigate('/')}>
            Back to map
          </Button>
        </div>
      </div>
    )
  }

  const world = worlds.find((w) => w.id === level.worldId)
  const missingOptional = (level.optionalPrerequisites ?? []).filter((id) => !isCompleted(id))

  function handleQuestionSolved() {
    if (!level) return
    if (questionIndex + 1 < level.questions.length) {
      setQuestionIndex((i) => i + 1)
    } else {
      completeLevel(level.id)
      setFinished(true)
    }
  }

  if (finished) {
    const finalStatus = getStatus(level.id)
    const warning = finalStatus === 'complete-warning'
    return (
      <div className="level-page">
        <div className={`level-complete level-complete--${finalStatus}`}>
          <div className="level-complete__icon">
            {warning ? <AlertTriangle size={32} strokeWidth={2.25} /> : <CheckCircle2 size={32} strokeWidth={2.25} />}
          </div>
          <h2>{warning ? 'Level complete — with warnings' : 'Level complete!'}</h2>
          {warning && (
            <p className="level-warning-text">
              You skipped a recommended level: {missingOptional.map((id) => levelsById.get(id)?.title).join(', ')}.
              You can still continue, but consider reviewing it.
            </p>
          )}
          <Button className="level-page__primary-btn" onClick={() => navigate('/')}>
            Back to world map
          </Button>
        </div>
      </div>
    )
  }

  const question = level.questions[questionIndex]

  return (
    <div className="level-page">
      <header className="level-page__header">
        <button className="level-page__back" onClick={() => navigate('/')}>
          <ArrowLeft size={16} strokeWidth={2.25} />
          World map
        </button>
        <span className="level-page__world" style={{ color: world?.color, background: `${world?.color}1a` }}>
          {world?.title}
        </span>
      </header>

      <h1 className="level-page__title">{level.title}</h1>
      <p className="level-page__summary">{level.summary}</p>

      {missingOptional.length > 0 && (
        <div className="level-warning-banner">
          <AlertTriangle size={16} strokeWidth={2.25} />
          Recommended (not required): {missingOptional.map((id) => levelsById.get(id)?.title).join(', ')}
        </div>
      )}

      <div className="level-page__stepper">
        {level.questions.map((q, i) => (
          <span
            key={q.id}
            className={`level-page__step${i < questionIndex ? ' level-page__step--done' : ''}${
              i === questionIndex ? ' level-page__step--current' : ''
            }`}
          />
        ))}
        <span className="level-page__step-label">
          Question {questionIndex + 1} of {level.questions.length}
        </span>
      </div>

      <QuestionCard
        key={question.id}
        question={question}
        onSolved={handleQuestionSolved}
        accentColor={world?.color ?? '#2563eb'}
      />

      {questionIndex === level.questions.length - 1 && (
        <p className="level-page__last-hint">
          <Sparkles size={13} strokeWidth={2.25} /> Last question — completing it finishes the level.
        </p>
      )}
    </div>
  )
}
