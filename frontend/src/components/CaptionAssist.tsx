/**
 * Caption assist — three drafts from a one-line brief.
 *
 * Deliberately not a magic "write my caption" button. The server cannot watch
 * the video, so the operator says what the reel is about and gets three angles
 * back; picking one fills the caption field and flags the post as
 * AI-assisted. See backend/core/captions.py.
 *
 * The whole block hides itself when the server reports the feature
 * unconfigured, rather than offering a button that always errors.
 */
import { useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import {
  getCaptionStatus,
  suggestCaptions,
  type CaptionOption,
} from '../api/captions'
import { BANNER_DANGER, BTN_QUIET, EYEBROW, FIELD, META } from '../ui'

export default function CaptionAssist({
  reelFilename,
  durationSeconds,
  onPick,
}: {
  reelFilename?: string
  durationSeconds?: number | null
  /** Called with the chosen caption; the caller owns the caption field. */
  onPick: (text: string) => void
}) {
  const [brief, setBrief] = useState('')
  const [options, setOptions] = useState<CaptionOption[]>([])

  const status = useQuery({
    queryKey: ['captionStatus'],
    queryFn: getCaptionStatus,
    staleTime: 5 * 60_000,
    retry: false,
    throwOnError: false,
  })

  const suggest = useMutation({
    mutationFn: () => suggestCaptions({ brief, reelFilename, durationSeconds }),
    onSuccess: (res) => setOptions(res.captions),
  })

  // Only render once the server has confirmed it can actually do this. An
  // errored status query is treated the same as unavailable — better to show
  // nothing than a control that cannot work.
  if (!status.data?.available) return null

  const canAsk = brief.trim().length > 0 && !suggest.isPending

  return (
    <div className="mt-6 border border-line bg-ink-950 p-5">
      <h3 className={EYEBROW}>Caption assist</h3>
      <p className={`${META} mt-2`}>
        Say what the reel is about in a sentence. Captions are written from
        this, not from the video.
      </p>

      <textarea
        value={brief}
        onChange={(e) => setBrief(e.target.value)}
        rows={2}
        maxLength={2000}
        placeholder="Three things I learned shipping an OAuth integration in a week"
        className={`${FIELD} mt-4`}
      />

      <button
        type="button"
        disabled={!canAsk}
        onClick={() => suggest.mutate()}
        className={`${BTN_QUIET} mt-3`}
      >
        {suggest.isPending ? 'Writing…' : options.length ? 'Try again' : 'Suggest captions'}
      </button>

      {suggest.isError && (
        <div className={`${BANNER_DANGER} mt-4`}>
          <p className="text-[15px] text-danger-soft">
            {(suggest.error as Error).message}
          </p>
        </div>
      )}

      {options.length > 0 && (
        <ul className="mt-4 flex flex-col gap-px bg-line">
          {options.map((option, i) => (
            <li key={`${option.angle}-${i}`} className="bg-ink-900 p-4">
              <p className={EYEBROW}>{option.angle}</p>
              <p className="mt-2 text-[15px] leading-[1.6] whitespace-pre-wrap text-mist-200">
                {option.text}
              </p>
              <button
                type="button"
                onClick={() => onPick(option.text)}
                className={`${BTN_QUIET} mt-3`}
              >
                Use this
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
