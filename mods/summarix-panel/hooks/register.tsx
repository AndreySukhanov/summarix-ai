import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import type { SummarixDigest } from '../types'

const PANE = 'summarix'
const TITLE = 'Summarix digest'
const TOOL = 'mcp__summarix-panel__show_digest'
const KEEP = 10
const MAX_CHARS = 100_000

const history = atom({ plugin: 'summarix-panel', key: 'history' } as const, [], {
  shape: 'history-1',
})
const index = atom({ plugin: 'summarix-panel', key: 'index' } as const, 0)

function isDigest(x: unknown): x is SummarixDigest {
  if (typeof x !== 'object' || x === null) return false
  const d = x as Record<string, unknown>
  return typeof d.title === 'string' && typeof d.markdown === 'string' && typeof d.at === 'number'
}

// Digests outlive the session in $.store; the state is what the pane draws from.
async function loadStored($: EngineInterface): Promise<void> {
  if ((await read($, history)).length > 0) return
  let stored: unknown
  try {
    stored = await $.store.get('history')
  } catch {
    stored = undefined
  }
  if (!Array.isArray(stored)) return
  const list = stored.filter(isDigest).slice(0, KEEP)
  if (list.length > 0) await update($, history, () => list)
}

async function addDigest($: EngineInterface, digest: SummarixDigest): Promise<void> {
  await update($, history, list => [digest, ...list].slice(0, KEEP))
  await update($, index, () => 0)
  try {
    await $.store.set('history', await read($, history))
  } catch {
    // The pane still shows it; only the copy for the next session is lost.
  }
}

function stamp(ms: number): string {
  const d = new Date(ms)
  const z = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${z(d.getMonth() + 1)}-${z(d.getDate())} ${z(d.getHours())}:${z(d.getMinutes())}`
}

function periodPrompt(period: string): string {
  return `Make a digest of my Telegram channels for the ${period}, then show it in the Summarix panel.`
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({
      name: 'summarix-panel',
      description: 'Show your latest Telegram channel digest in a pane',
    })
    await $.tool.register({
      name: 'show_digest',
      description:
        'Show a finished Telegram channel digest in the Summarix panel beside the chat. Call it once, right after you write a digest of the person\'s Telegram channels, with the same Markdown, keeping every link to its post. The person reads it there and can page back through earlier digests.',
      inputSchema: {
        type: 'object',
        properties: {
          markdown: {
            type: 'string',
            description: 'The digest as Markdown, with the links to the posts.',
          },
          title: {
            type: 'string',
            description: 'A short heading, e.g. "Last 24 hours, 12 channels" or "Search: GPT-6".',
          },
        },
        required: ['markdown'],
      },
      isDeferred: false,
    })
    await loadStored($)

    return next(e)
  })

  on('command.run', { command: 'summarix-panel' }, async $ => {
    await loadStored($)
    await $.ui.open({ id: PANE, title: TITLE })

    return { text: 'Summarix pane opened.' }
  })

  on('tool.call', { tool: TOOL }, async ($, e) => {
    const input = e as unknown as { markdown?: unknown; title?: unknown }
    const markdown = typeof input.markdown === 'string' ? input.markdown.trim() : ''
    if (markdown === '') {
      return { deny: 'show_digest needs the finished digest as Markdown in `markdown`.' }
    }
    const title =
      typeof input.title === 'string' && input.title.trim() !== ''
        ? input.title.trim().slice(0, 120)
        : 'Telegram digest'
    await addDigest($, { title, markdown: markdown.slice(0, MAX_CHARS), at: await $.clock.now() })
    void $.ui.open({ id: PANE, title: TITLE })

    return { result: 'Shown in the Summarix panel beside the chat.' }
  }).catch(($, e, next) =>
    next.called ? next(e) : { deny: 'summarix-panel could not show the digest; it is still in the chat.' },
  )

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Box, Button, Markdown, Text } = $.ui.resolve(e)
    const list = await read($, history)
    const i = Math.min(await read($, index), Math.max(0, list.length - 1))
    const digest = list[i]

    return (
      <Box flexDirection="column" gap={1}>
        {digest === undefined ? (
          <Box flexDirection="column">
            <Text dimColor>No digest yet.</Text>
            <Text dimColor>Press a period below, or ask for a digest of your channels.</Text>
          </Box>
        ) : (
          <Box flexDirection="column">
            <Text bold>{digest.title}</Text>
            <Text dimColor>
              {stamp(digest.at)}
              {list.length > 1 ? ` · ${i + 1} of ${list.length}` : ''}
            </Text>
          </Box>
        )}

        {digest !== undefined && <Markdown text={digest.markdown} />}

        {list.length > 1 && (
          <Box gap={1}>
            <Button
              key="older"
              label="< Older"
              onPress={() => update($, index, n => Math.min(n + 1, list.length - 1))}
            />
            <Button key="newer" label="Newer >" onPress={() => update($, index, n => Math.max(n - 1, 0))} />
          </Box>
        )}

        <Box gap={1}>
          <Text dimColor>New digest:</Text>
          <Button
            key="day"
            label="24 h"
            variant="primary"
            onPress={() => void $.prompt.submit({ text: periodPrompt('last 24 hours') })}
          />
          <Button
            key="days3"
            label="3 days"
            onPress={() => void $.prompt.submit({ text: periodPrompt('last 3 days') })}
          />
          <Button
            key="week"
            label="Week"
            onPress={() => void $.prompt.submit({ text: periodPrompt('last 7 days') })}
          />
        </Box>
      </Box>
    )
  })
}
