"""
Interface strings. The digest itself is written in DIGEST_LANGUAGE by the model.
"""

TEXTS = {
    "ru": {
        "help": (
            "Я собираю дайджест твоих Telegram-каналов.\n\n"
            "/add &lt;ссылка или @канал&gt; - добавить (можно несколько через пробел)\n"
            "Или просто перешли мне пост из канала.\n"
            "/remove &lt;номер или @канал&gt; - убрать\n"
            "/channels - список\n"
            "/digest - дайджест непрочитанного сейчас\n"
            "/digest 48 - пересказ за последние 48 часов, не отмечая прочитанным\n"
            "/status - последний запуск и расписание\n\n"
            "Сам присылаю дайджест каждый день в {time} ({tz})."
        ),
        "added": "Добавил: <b>{title}</b>",
        "already": "Уже в списке: <b>{title}</b>",
        "add_failed": "Не получилось добавить {ref}: {reason}",
        "add_usage": "Пришли ссылку или @имя канала: /add @durov",
        "removed": "Убрал: <b>{title}</b>",
        "not_found": "Такого канала нет в списке. Номера - в /channels",
        "no_channels": "Каналов пока нет. Добавь через /add или перешли пост из канала.",
        "channels_header": "<b>Каналы ({count})</b>",
        "collecting": "Собираю дайджест…",
        "busy": "Дайджест уже собирается, подожди минуту.",
        "digest_title": "<b>Дайджест · {date}</b>",
        "digest_window_title": "<b>Пересказ за {hours} ч · {date}</b>",
        "digest_stats": "Каналов с новым: {channels} · постов: {posts}",
        "highlights": "<b>Главное</b>",
        "nothing_new": "Новых постов нет.",
        "failed_channels": "<i>Не удалось прочитать: {items}</i>",
        "status": (
            "Модель: <code>{model}</code>\n"
            "Каналов: {channels}\n"
            "Следующий дайджест: {next_run}\n"
            "Последний запуск: {last}"
        ),
        "last_run": "{when}, постов {posts}, картинок {images}, токенов {tokens}",
        "never": "ещё не было",
        "error": "Что-то пошло не так: {reason}",
    },
    "en": {
        "help": (
            "I build a digest of your Telegram channels.\n\n"
            "/add &lt;link or @channel&gt; - add (several at once is fine)\n"
            "Or just forward me a post from the channel.\n"
            "/remove &lt;number or @channel&gt; - remove\n"
            "/channels - list\n"
            "/digest - digest of unread posts now\n"
            "/digest 48 - recap of the last 48 hours without marking anything read\n"
            "/status - last run and schedule\n\n"
            "I send the digest every day at {time} ({tz})."
        ),
        "added": "Added: <b>{title}</b>",
        "already": "Already in the list: <b>{title}</b>",
        "add_failed": "Could not add {ref}: {reason}",
        "add_usage": "Send a link or @name: /add @durov",
        "removed": "Removed: <b>{title}</b>",
        "not_found": "No such channel in the list. Numbers are in /channels",
        "no_channels": "No channels yet. Use /add or forward a post from a channel.",
        "channels_header": "<b>Channels ({count})</b>",
        "collecting": "Building the digest…",
        "busy": "A digest is already being built, give it a minute.",
        "digest_title": "<b>Digest · {date}</b>",
        "digest_window_title": "<b>Last {hours} h · {date}</b>",
        "digest_stats": "Channels with news: {channels} · posts: {posts}",
        "highlights": "<b>Highlights</b>",
        "nothing_new": "No new posts.",
        "failed_channels": "<i>Could not read: {items}</i>",
        "status": (
            "Model: <code>{model}</code>\n"
            "Channels: {channels}\n"
            "Next digest: {next_run}\n"
            "Last run: {last}"
        ),
        "last_run": "{when}, posts {posts}, images {images}, tokens {tokens}",
        "never": "none yet",
        "error": "Something went wrong: {reason}",
    },
}


def t(lang: str, key: str, **kwargs) -> str:
    text = TEXTS.get(lang, TEXTS["en"])[key]
    return text.format(**kwargs) if kwargs else text
