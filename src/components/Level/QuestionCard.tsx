import { useState, type CSSProperties, type FormEvent } from 'react'
import { CheckCircle2, XCircle, Lightbulb, ArrowRight } from 'lucide-react'
import { Button } from '../common/Button'
import type { Question } from '../../types'

function normalize(value: string) {
  return value.trim().toLowerCase()
}

export function QuestionCard({
  question,
  onSolved,
  accentColor = '#1976d2',
}: {
  question: Question
  onSolved: () => void
  accentColor?: string
}) {
  const [selectedOption, setSelectedOption] = useState<string | null>(null)
  const [textAnswer, setTextAnswer] = useState('')
  const [feedback, setFeedback] = useState<'correct' | 'incorrect' | null>(null)
  const [solved, setSolved] = useState(false)
  const [hintsRevealed, setHintsRevealed] = useState(0)

  function currentAnswer() {
    return question.type === 'multiple-choice' ? selectedOption ?? '' : textAnswer
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (solved) return
    const isCorrect = normalize(currentAnswer()) === normalize(question.answer)
    setFeedback(isCorrect ? 'correct' : 'incorrect')
    if (isCorrect) setSolved(true)
  }

  function revealNextHint() {
    setHintsRevealed((n) => Math.min(n + 1, question.hints.length))
  }

  // The `Button` component reads `--clr-primary` for its background, so scoping
  // that variable here lets it pick up this level's world color.
  const accentStyle = { '--clr-primary': accentColor } as CSSProperties

  return (
    <div className="question-card" style={{ '--accent': accentColor } as CSSProperties}>
      <p className="question-card__prompt">{question.prompt}</p>

      <form onSubmit={handleSubmit}>
        {question.type === 'multiple-choice' ? (
          <div className="question-card__options">
            {question.options?.map((option) => (
              <label
                key={option}
                className={`question-card__option${selectedOption === option ? ' question-card__option--selected' : ''}${solved ? ' question-card__option--disabled' : ''}`}
              >
                <input
                  type="radio"
                  name={question.id}
                  value={option}
                  disabled={solved}
                  checked={selectedOption === option}
                  onChange={() => setSelectedOption(option)}
                />
                <span className="question-card__option-marker" />
                {option}
              </label>
            ))}
          </div>
        ) : (
          <input
            className="question-card__text-input"
            type="text"
            value={textAnswer}
            disabled={solved}
            onChange={(e) => setTextAnswer(e.target.value)}
            placeholder="Type your answer..."
          />
        )}

        <div className="question-card__actions">
          {!solved && (
            <Button type="submit" style={accentStyle} disabled={!currentAnswer()}>
              Submit
            </Button>
          )}
          {question.hints.length > 0 && hintsRevealed < question.hints.length && !solved && (
            <button type="button" className="question-card__hint-btn" onClick={revealNextHint}>
              <Lightbulb size={15} strokeWidth={2.25} />
              Hint ({hintsRevealed}/{question.hints.length})
            </button>
          )}
          {solved && (
            <Button type="button" style={accentStyle} onClick={onSolved}>
              Continue
              <ArrowRight size={15} strokeWidth={2.25} style={{ verticalAlign: 'text-bottom', marginLeft: 4 }} />
            </Button>
          )}
        </div>
      </form>

      {feedback && (
        <div className={`message ${feedback === 'correct' ? 'question-card__feedback-success' : 'error'} question-card__feedback`}>
          {feedback === 'correct' ? (
            <>
              <CheckCircle2 size={16} strokeWidth={2.25} /> Correct!
            </>
          ) : (
            <>
              <XCircle size={16} strokeWidth={2.25} /> Not quite — try again.
            </>
          )}
        </div>
      )}

      {hintsRevealed > 0 && (
        <ul className="question-card__hints">
          {question.hints.slice(0, hintsRevealed).map((hint, i) => (
            <li key={i} className="message information">
              {hint}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
