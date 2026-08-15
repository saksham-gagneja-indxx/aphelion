import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { UNDO_WINDOW_MS, UndoProvider, useUndo } from './undo'

/** Exercises the provider through a consumer, as the pages use it. */
function Harness({ commit }: { commit: (init?: RequestInit) => Promise<unknown> }) {
  const { pendingKeys, scheduleDelete } = useUndo()
  const items = [
    { id: 1, name: 'first' },
    { id: 2, name: 'second' },
  ].filter((i) => !pendingKeys.has(`item:${i.id}`))

  return (
    <div>
      <ul>
        {items.map((i) => (
          <li key={i.id}>
            {i.name}
            <button
              onClick={() =>
                scheduleDelete({ key: `item:${i.id}`, label: `Deleted ${i.name}`, commit })
              }
            >
              Delete {i.name}
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}

beforeEach(() => {
  vi.useFakeTimers()
})

afterEach(() => {
  vi.useRealTimers()
  vi.restoreAllMocks()
})

/** fireEvent rather than userEvent: the latter is not a dependency here, and
 *  its internal delays fight the fake timers these tests need. */
const click = (el: HTMLElement) => act(() => { fireEvent.click(el) })

describe('undo window', () => {
  it('hides the item immediately but sends nothing yet', async () => {
    const commit = vi.fn().mockResolvedValue(undefined)
    render(
      <UndoProvider>
        <Harness commit={commit} />
      </UndoProvider>,
    )

    click(screen.getByRole('button', { name: 'Delete first' }))

    expect(screen.queryByText('first')).not.toBeInTheDocument()
    // The whole point: no request until the window closes.
    expect(commit).not.toHaveBeenCalled()
    expect(screen.getByText('Deleted first')).toBeInTheDocument()
  })

  it('commits once the window expires', async () => {
    const commit = vi.fn().mockResolvedValue(undefined)
    render(
      <UndoProvider>
        <Harness commit={commit} />
      </UndoProvider>,
    )

    click(screen.getByRole('button', { name: 'Delete first' }))
    await act(async () => {
      vi.advanceTimersByTime(UNDO_WINDOW_MS + 100)
    })

    expect(commit).toHaveBeenCalledTimes(1)
    expect(screen.queryByText('Deleted first')).not.toBeInTheDocument()
  })

  it('restores the item and never sends when undone', async () => {
    const commit = vi.fn().mockResolvedValue(undefined)
    render(
      <UndoProvider>
        <Harness commit={commit} />
      </UndoProvider>,
    )

    click(screen.getByRole('button', { name: 'Delete first' }))
    click(screen.getByRole('button', { name: 'Undo' }))

    expect(screen.getByText('first')).toBeInTheDocument()

    // And crucially the timer must not fire afterwards.
    await act(async () => {
      vi.advanceTimersByTime(UNDO_WINDOW_MS * 2)
    })
    expect(commit).not.toHaveBeenCalled()
  })

  it('tracks several deletions independently', async () => {
    const commit = vi.fn().mockResolvedValue(undefined)
    render(
      <UndoProvider>
        <Harness commit={commit} />
      </UndoProvider>,
    )

    click(screen.getByRole('button', { name: 'Delete first' }))
    click(screen.getByRole('button', { name: 'Delete second' }))

    expect(screen.getAllByRole('button', { name: 'Undo' })).toHaveLength(2)

    // Undo only the second; the first must still commit on schedule.
    const undos = screen.getAllByRole('button', { name: 'Undo' })
    click(undos[1])
    await act(async () => {
      vi.advanceTimersByTime(UNDO_WINDOW_MS + 100)
    })

    expect(commit).toHaveBeenCalledTimes(1)
    expect(screen.getByText('second')).toBeInTheDocument()
  })

  it('flushes pending deletions with keepalive when the page goes away', async () => {
    const commit = vi.fn().mockResolvedValue(undefined)
    render(
      <UndoProvider>
        <Harness commit={commit} />
      </UndoProvider>,
    )

    click(screen.getByRole('button', { name: 'Delete first' }))
    act(() => {
      window.dispatchEvent(new Event('pagehide'))
    })

    // Without this the request is dropped as the document unloads, and the
    // item silently reappears next time the user opens the app.
    expect(commit).toHaveBeenCalledWith({ keepalive: true })
  })

  it('runs onSettled after a commit so lists can refetch', async () => {
    const onSettled = vi.fn()
    const commit = vi.fn().mockResolvedValue(undefined)

    function One() {
      const { scheduleDelete } = useUndo()
      return (
        <button
          onClick={() => scheduleDelete({ key: 'k', label: 'gone', commit, onSettled })}
        >
          go
        </button>
      )
    }

    render(
      <UndoProvider>
        <One />
      </UndoProvider>,
    )

    click(screen.getByRole('button', { name: 'go' }))
    await act(async () => {
      vi.advanceTimersByTime(UNDO_WINDOW_MS + 100)
    })

    expect(onSettled).toHaveBeenCalled()
  })
})
