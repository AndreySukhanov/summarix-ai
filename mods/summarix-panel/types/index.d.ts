export type SummarixDigest = {
  title: string
  markdown: string
  at: number
}

declare module 'claude-code' {
  interface PluginState {
    'summarix-panel': {
      history: Shaped<SummarixDigest[]>
      index: number
    }
  }
}
