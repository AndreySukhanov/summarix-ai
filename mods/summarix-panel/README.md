# summarix-panel

An optional mod for [Summarix](../../README.md): your Telegram channel digest in a pane beside the chat in Claude Code.

- When the `summarix-telegram` skill finishes a digest, Claude also hands it to the pane through the mod's `show_digest` tool: every point keeps its link to the post, and links open from the pane.
- **< Older / Newer >** page through the last 10 digests, kept across sessions.
- **24 h / 3 days / Week** ask Claude for a new digest of that period in one press.
- `/summarix-panel` opens the pane at any time.

The mod reads nothing from Telegram itself and needs no keys: the posts come through the skill, the digest is written by Claude.

## Install

Needs Claude Code 2.1.287 or later (mods). With the Summarix marketplace added:

```
/plugin install summarix-panel@summarix-telegram
```

## License

**Source-Available** — free to read, run and learn from. Commercial or derivative use requires written permission. See [LICENSE](../../LICENSE).
