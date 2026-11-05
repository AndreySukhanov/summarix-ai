# Contributing to Summarix

Thanks for your interest! Contributions are welcome — the bot is built from small, replaceable parts, so most valuable additions are self-contained.

## Great first contributions

### 1. A new digest style
Styles live in `services/styles.py`. A style is one entry in `STYLES`: a `title` per interface language and a `prompt` per digest language. The prompt shapes the per-channel bullets; citations, links and HTML stay the bot's job, so a style never has to handle them. `style_words()` caps the length if the style needs it.

### 2. A new language
Interface strings are in `bot/texts.py` (one dictionary per language; keys must stay in sync), digest languages are listed in `LANGUAGES` in `services/styles.py` and in the `Literal` types in `config/settings.py`, and every style needs a prompt in the new digest language. `test_interface_texts_complete_in_all_languages` catches a missing key.

### 3. A reader feature
Telegram access is `services/reader.py` (Telethon). Tests never touch the network: `tests/fakes.py` has a fake reader and a fake model — extend them and test against them.

## Development setup

```bash
pip install -r requirements.txt
pytest
```

The tests are offline and need no keys. CI runs them on Python 3.13 with a flake8 pass for syntax errors and undefined names:

```bash
flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
```

## Ground rules

- **English everywhere** — code, comments, commits, PRs. Interface strings in other languages are product data.
- Settings go through `config/settings.py` (pydantic-settings) — no scattered `os.getenv`.
- Never commit `.env`, `data/` or a `.session` file: a session file is full access to a Telegram account.

## Bigger changes

Open an issue first and describe the approach — happy to discuss the design before you invest time.

## License

By contributing you agree that your contribution is licensed under the project's [LICENSE](LICENSE).
