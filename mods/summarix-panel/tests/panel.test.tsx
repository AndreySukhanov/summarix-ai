import { expect, test } from 'claude-code/testing'

const TOOL = 'mcp__summarix-panel__show_digest'
const NOW = new Date(2026, 10, 6, 9, 30).getTime()

const PANE = {
  plugin: 'summarix-panel',
  component: 'Pane',
  requestId: 'summarix',
  props: {
    title: 'Summarix digest',
    isFocused: false,
    bodyColumns: 70,
    placement: 'dock',
    scroll: { offset: 0, bodyRows: 40 },
    view: {},
  },
} as const

function engine(on: any, stored: unknown = undefined) {
  const store: Record<string, unknown> = { history: stored }
  on('command.register', () => ({ value: { command: 'summarix-panel' } }))
  on('tool.register', (_: unknown, e: { name: string }) => ({ value: { tool: `mcp__summarix-panel__${e.name}` } }))
  on('ui.open', () => ({ value: { isPlaced: true } }))
  on('session.start', (_: unknown, e: { cwd: string }) => ({ cwd: e.cwd }))
  on('clock.now', () => ({ value: NOW }))
  on('store.get', (_: unknown, e: { key: string }) => ({ value: store[e.key] }))
  on('store.set', (_: unknown, e: { key: string; value: unknown }) => {
    store[e.key] = e.value
    return { value: undefined }
  })
  return store
}

const DIGEST = [
  '**Tech News**',
  '- GPT-6 pricing cut by half ([post](https://t.me/technews/101))',
].join('\n')

test('a digest the model shows lands in the pane, on every surface', async ($, on) => {
  const store = engine(on)
  await $.session.start({ cwd: '/', surface: 'desktop', isInteractive: true })
  const ran = await $.tool.call({ tool: TOOL, markdown: DIGEST, title: 'Last 24 hours, 1 channel' } as any)
  expect((ran as { result?: unknown }).result).toBe('Shown in the Summarix panel beside the chat.')
  expect(Array.isArray(store.history)).toBe(true)

  for (const surface of ['terminal', 'desktop'] as const) {
    const ui = await $.ui.mount({ ...PANE, surface })
    expect((await ui.find({ type: 'Text', text: /Last 24 hours/ }))?.text).toBe('Last 24 hours, 1 channel')
    expect(await ui.find({ type: 'Markdown' })).toBeTruthy()
    expect(await ui.find({ type: 'Button', key: 'day' })).toBeTruthy()
    await ui.unmount()
  }
})

test('older and newer page through earlier digests', async ($, on) => {
  engine(on)
  await $.session.start({ cwd: '/', surface: 'desktop', isInteractive: true })
  await $.tool.call({ tool: TOOL, markdown: DIGEST, title: 'Monday' } as any)
  await $.tool.call({ tool: TOOL, markdown: DIGEST, title: 'Tuesday' } as any)

  const ui = await $.ui.mount({ ...PANE, surface: 'desktop' })
  expect((await ui.find({ type: 'Text', text: /day$/ }))?.text).toBe('Tuesday')
  await ui.press({ key: 'older' })
  expect((await ui.find({ type: 'Text', text: /day$/ }))?.text).toBe('Monday')
  await ui.press({ key: 'newer' })
  expect((await ui.find({ type: 'Text', text: /day$/ }))?.text).toBe('Tuesday')
  await ui.unmount()
})

test('an empty digest is refused and nothing is stored', async ($, on) => {
  const store = engine(on)
  await $.session.start({ cwd: '/', surface: 'desktop', isInteractive: true })
  const ran = await $.tool.call({ tool: TOOL, markdown: '   ' } as any)
  expect(typeof (ran as { deny?: unknown }).deny === 'string' || (ran as { isError?: unknown }).isError === true).toBe(true)
  expect(store.history).toBe(undefined)
})

test('digests from an earlier session come back from the store', async ($, on) => {
  engine(on, [{ title: 'Yesterday', markdown: DIGEST, at: NOW - 86_400_000 }, { broken: true }])
  await $.session.start({ cwd: '/', surface: 'desktop', isInteractive: true })

  const ui = await $.ui.mount({ ...PANE, surface: 'desktop' })
  expect((await ui.find({ type: 'Text', text: /Yesterday/ }))?.text).toBe('Yesterday')
  await ui.unmount()
})
