"""
Interface strings in the 5 languages of the original bot: ru, en, es, fr, kk.
The digest itself is written by the model in the digest language chosen in /settings.
"""

TEXTS = {
    "ru": {
        "help": (
            "Я собираю дайджест твоих Telegram-каналов.\n\n"
            "/add &lt;ссылка или @канал&gt; - добавить (можно несколько через пробел)\n"
            "Или перешли мне пост из канала, или пришли ссылку на папку t.me/addlist/…\n"
            "/remove &lt;номер или @канал&gt; - убрать\n"
            "/channels - список\n"
            "/digest - дайджест непрочитанного сейчас\n"
            "/digest 48 - пересказ за последние 48 часов, не отмечая прочитанным\n"
            "/status - последний запуск и расписание\n"
            "/settings - стиль, языки, время, часовой пояс, свой промпт\n\n"
            "Сам присылаю дайджест каждый день в {time} ({tz})."
        ),
        "settings": (
            "<b>Настройки</b>\n\n"
            "Стиль: {style}\n"
            "Язык дайджеста: {language}\n"
            "Язык интерфейса: {ui_language}\n"
            "Время: {time}\n"
            "Часовой пояс: {tz}"
        ),
        "btn_style": "🎨 Стиль",
        "btn_language": "🌍 Язык дайджеста",
        "btn_ui_language": "🗣 Язык интерфейса",
        "btn_time": "⏰ Время",
        "btn_tz": "🌐 Часовой пояс",
        "btn_prompt": "✍️ Свой промпт",
        "back": "← Назад",
        "choose_style": "Выбери стиль дайджеста:",
        "choose_language": "На каком языке писать дайджест:",
        "choose_ui_language": "Язык кнопок и сообщений бота:",
        "choose_tz": "Часовой пояс. Нет нужного - пришли, например, <code>/tz Europe/Astrakhan</code>",
        "time_hint": "Пришли время дайджеста командой, например <code>/time 08:30</code>",
        "tz_invalid": "Не знаю часовой пояс «{tz}». Формат как <code>Europe/Moscow</code> или <code>Asia/Almaty</code>.",
        "prompt_hint": (
            "Свой промпт заменяет стиль. Пришли <code>/prompt</code> и текст, например:\n"
            "<code>/prompt пиши как аналитик для инвестора, только цифры и выводы</code>\n\n"
            "Вернуть обычный стиль: <code>/prompt off</code>"
        ),
        "custom_prompt_on": "заменён своим промптом",
        "added": "Добавил: <b>{title}</b>",
        "already": "Уже в списке: <b>{title}</b>",
        "folder_added": "Папка <b>{title}</b>: добавлено {added}, уже были {existing}",
        "folder_skipped": "Пропустил закрытые каналы, на которые ты не подписан: {items}",
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
            "Or forward me a post from the channel, or send a folder link t.me/addlist/…\n"
            "/remove &lt;number or @channel&gt; - remove\n"
            "/channels - list\n"
            "/digest - digest of unread posts now\n"
            "/digest 48 - recap of the last 48 hours without marking anything read\n"
            "/status - last run and schedule\n"
            "/settings - style, languages, time, timezone, custom prompt\n\n"
            "I send the digest every day at {time} ({tz})."
        ),
        "settings": (
            "<b>Settings</b>\n\n"
            "Style: {style}\n"
            "Digest language: {language}\n"
            "Interface language: {ui_language}\n"
            "Time: {time}\n"
            "Timezone: {tz}"
        ),
        "btn_style": "🎨 Style",
        "btn_language": "🌍 Digest language",
        "btn_ui_language": "🗣 Interface language",
        "btn_time": "⏰ Time",
        "btn_tz": "🌐 Timezone",
        "btn_prompt": "✍️ Custom prompt",
        "back": "← Back",
        "choose_style": "Pick a digest style:",
        "choose_language": "Language of the digest:",
        "choose_ui_language": "Language of the bot's buttons and messages:",
        "choose_tz": "Timezone. Not listed? Send e.g. <code>/tz America/New_York</code>",
        "time_hint": "Send the digest time as a command, e.g. <code>/time 08:30</code>",
        "tz_invalid": "Unknown timezone \"{tz}\". Use a name like <code>Europe/Moscow</code>.",
        "prompt_hint": (
            "A custom prompt replaces the style. Send <code>/prompt</code> with your text, e.g.\n"
            "<code>/prompt write like an analyst briefing an investor, numbers and conclusions only</code>\n\n"
            "Back to the regular style: <code>/prompt off</code>"
        ),
        "custom_prompt_on": "replaced by custom prompt",
        "added": "Added: <b>{title}</b>",
        "already": "Already in the list: <b>{title}</b>",
        "folder_added": "Folder <b>{title}</b>: added {added}, already had {existing}",
        "folder_skipped": "Skipped private channels you have not joined: {items}",
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
    "es": {
        "help": (
            "Preparo un resumen de tus canales de Telegram.\n\n"
            "/add &lt;enlace o @canal&gt; - añadir (puedes poner varios)\n"
            "O reenvíame una publicación del canal, o envía un enlace de carpeta t.me/addlist/…\n"
            "/remove &lt;número o @canal&gt; - quitar\n"
            "/channels - lista\n"
            "/digest - resumen de lo no leído ahora\n"
            "/digest 48 - repaso de las últimas 48 horas sin marcar nada como leído\n"
            "/status - última ejecución y horario\n"
            "/settings - estilo, idiomas, hora, zona horaria, prompt propio\n\n"
            "Envío el resumen cada día a las {time} ({tz})."
        ),
        "settings": (
            "<b>Ajustes</b>\n\n"
            "Estilo: {style}\n"
            "Idioma del resumen: {language}\n"
            "Idioma de la interfaz: {ui_language}\n"
            "Hora: {time}\n"
            "Zona horaria: {tz}"
        ),
        "btn_style": "🎨 Estilo",
        "btn_language": "🌍 Idioma del resumen",
        "btn_ui_language": "🗣 Idioma de la interfaz",
        "btn_time": "⏰ Hora",
        "btn_tz": "🌐 Zona horaria",
        "btn_prompt": "✍️ Prompt propio",
        "back": "← Atrás",
        "choose_style": "Elige el estilo del resumen:",
        "choose_language": "Idioma del resumen:",
        "choose_ui_language": "Idioma de los botones y mensajes del bot:",
        "choose_tz": "Zona horaria. ¿No está la tuya? Envía por ejemplo <code>/tz Europe/Madrid</code>",
        "time_hint": "Envía la hora del resumen con un comando, por ejemplo <code>/time 08:30</code>",
        "tz_invalid": "No conozco la zona horaria «{tz}». Usa un nombre como <code>Europe/Madrid</code>.",
        "prompt_hint": (
            "Un prompt propio reemplaza el estilo. Envía <code>/prompt</code> con tu texto, por ejemplo:\n"
            "<code>/prompt escribe como un analista para un inversor, solo cifras y conclusiones</code>\n\n"
            "Volver al estilo normal: <code>/prompt off</code>"
        ),
        "custom_prompt_on": "reemplazado por prompt propio",
        "added": "Añadido: <b>{title}</b>",
        "already": "Ya está en la lista: <b>{title}</b>",
        "folder_added": "Carpeta <b>{title}</b>: añadidos {added}, ya estaban {existing}",
        "folder_skipped": "Omití canales privados a los que no estás unido: {items}",
        "add_failed": "No se pudo añadir {ref}: {reason}",
        "add_usage": "Envía un enlace o @nombre: /add @durov",
        "removed": "Quitado: <b>{title}</b>",
        "not_found": "Ese canal no está en la lista. Los números están en /channels",
        "no_channels": "Aún no hay canales. Usa /add o reenvía una publicación de un canal.",
        "channels_header": "<b>Canales ({count})</b>",
        "collecting": "Preparando el resumen…",
        "busy": "Ya estoy preparando un resumen, espera un minuto.",
        "digest_title": "<b>Resumen · {date}</b>",
        "digest_window_title": "<b>Últimas {hours} h · {date}</b>",
        "digest_stats": "Canales con novedades: {channels} · publicaciones: {posts}",
        "highlights": "<b>Lo más importante</b>",
        "nothing_new": "No hay publicaciones nuevas.",
        "failed_channels": "<i>No se pudo leer: {items}</i>",
        "status": (
            "Modelo: <code>{model}</code>\n"
            "Canales: {channels}\n"
            "Próximo resumen: {next_run}\n"
            "Última ejecución: {last}"
        ),
        "last_run": "{when}, publicaciones {posts}, imágenes {images}, tokens {tokens}",
        "never": "todavía ninguna",
        "error": "Algo salió mal: {reason}",
    },
    "fr": {
        "help": (
            "Je prépare un digest de tes chaînes Telegram.\n\n"
            "/add &lt;lien ou @chaîne&gt; - ajouter (plusieurs à la fois, c'est possible)\n"
            "Ou transfère-moi une publication de la chaîne, ou envoie un lien de dossier t.me/addlist/…\n"
            "/remove &lt;numéro ou @chaîne&gt; - retirer\n"
            "/channels - liste\n"
            "/digest - digest des messages non lus maintenant\n"
            "/digest 48 - récap des 48 dernières heures sans rien marquer comme lu\n"
            "/status - dernière exécution et planning\n"
            "/settings - style, langues, heure, fuseau horaire, prompt personnel\n\n"
            "J'envoie le digest chaque jour à {time} ({tz})."
        ),
        "settings": (
            "<b>Réglages</b>\n\n"
            "Style : {style}\n"
            "Langue du digest : {language}\n"
            "Langue de l'interface : {ui_language}\n"
            "Heure : {time}\n"
            "Fuseau horaire : {tz}"
        ),
        "btn_style": "🎨 Style",
        "btn_language": "🌍 Langue du digest",
        "btn_ui_language": "🗣 Langue de l'interface",
        "btn_time": "⏰ Heure",
        "btn_tz": "🌐 Fuseau horaire",
        "btn_prompt": "✍️ Prompt personnel",
        "back": "← Retour",
        "choose_style": "Choisis le style du digest :",
        "choose_language": "Langue du digest :",
        "choose_ui_language": "Langue des boutons et messages du bot :",
        "choose_tz": "Fuseau horaire. Pas dans la liste ? Envoie par exemple <code>/tz Europe/Paris</code>",
        "time_hint": "Envoie l'heure du digest avec une commande, par exemple <code>/time 08:30</code>",
        "tz_invalid": "Fuseau horaire inconnu « {tz} ». Utilise un nom comme <code>Europe/Paris</code>.",
        "prompt_hint": (
            "Un prompt personnel remplace le style. Envoie <code>/prompt</code> avec ton texte, par exemple :\n"
            "<code>/prompt écris comme un analyste pour un investisseur, chiffres et conclusions seulement</code>\n\n"
            "Revenir au style normal : <code>/prompt off</code>"
        ),
        "custom_prompt_on": "remplacé par un prompt personnel",
        "added": "Ajoutée : <b>{title}</b>",
        "already": "Déjà dans la liste : <b>{title}</b>",
        "folder_added": "Dossier <b>{title}</b> : {added} ajoutées, {existing} déjà présentes",
        "folder_skipped": "Chaînes privées ignorées, tu n'y es pas abonné : {items}",
        "add_failed": "Impossible d'ajouter {ref} : {reason}",
        "add_usage": "Envoie un lien ou un @nom : /add @durov",
        "removed": "Retirée : <b>{title}</b>",
        "not_found": "Cette chaîne n'est pas dans la liste. Les numéros sont dans /channels",
        "no_channels": "Pas encore de chaînes. Utilise /add ou transfère une publication d'une chaîne.",
        "channels_header": "<b>Chaînes ({count})</b>",
        "collecting": "Je prépare le digest…",
        "busy": "Un digest est déjà en préparation, attends une minute.",
        "digest_title": "<b>Digest · {date}</b>",
        "digest_window_title": "<b>Dernières {hours} h · {date}</b>",
        "digest_stats": "Chaînes avec du nouveau : {channels} · publications : {posts}",
        "highlights": "<b>L'essentiel</b>",
        "nothing_new": "Aucune nouvelle publication.",
        "failed_channels": "<i>Lecture impossible : {items}</i>",
        "status": (
            "Modèle : <code>{model}</code>\n"
            "Chaînes : {channels}\n"
            "Prochain digest : {next_run}\n"
            "Dernière exécution : {last}"
        ),
        "last_run": "{when}, publications {posts}, images {images}, tokens {tokens}",
        "never": "pas encore",
        "error": "Un problème est survenu : {reason}",
    },
    "kk": {
        "help": (
            "Мен сенің Telegram-арналарыңның дайджестін жинаймын.\n\n"
            "/add &lt;сілтеме немесе @арна&gt; - қосу (бірнешеуін бірден жіберуге болады)\n"
            "Немесе арнадан жазбаны маған жібер, не t.me/addlist/… қалтасының сілтемесін жібер\n"
            "/remove &lt;нөмір немесе @арна&gt; - алып тастау\n"
            "/channels - тізім\n"
            "/digest - оқылмағандардың дайджесті қазір\n"
            "/digest 48 - соңғы 48 сағаттың шолуы, ештеңе оқылды деп белгіленбейді\n"
            "/status - соңғы іске қосу және кесте\n"
            "/settings - стиль, тілдер, уақыт, сағат белдеуі, өз промптың\n\n"
            "Дайджестті күн сайын {time} ({tz}) уақытта жіберемін."
        ),
        "settings": (
            "<b>Баптаулар</b>\n\n"
            "Стиль: {style}\n"
            "Дайджест тілі: {language}\n"
            "Интерфейс тілі: {ui_language}\n"
            "Уақыт: {time}\n"
            "Сағат белдеуі: {tz}"
        ),
        "btn_style": "🎨 Стиль",
        "btn_language": "🌍 Дайджест тілі",
        "btn_ui_language": "🗣 Интерфейс тілі",
        "btn_time": "⏰ Уақыт",
        "btn_tz": "🌐 Сағат белдеуі",
        "btn_prompt": "✍️ Өз промптың",
        "back": "← Артқа",
        "choose_style": "Дайджест стилін таңда:",
        "choose_language": "Дайджест қай тілде жазылсын:",
        "choose_ui_language": "Боттың батырмалары мен хабарламаларының тілі:",
        "choose_tz": "Сағат белдеуі. Керегі жоқ болса, мысалы, <code>/tz Asia/Almaty</code> жібер",
        "time_hint": "Дайджест уақытын командамен жібер, мысалы <code>/time 08:30</code>",
        "tz_invalid": "«{tz}» сағат белдеуін білмеймін. <code>Asia/Almaty</code> сияқты атау қолдан.",
        "prompt_hint": (
            "Өз промптың стильді ауыстырады. <code>/prompt</code> командасын мәтінмен жібер, мысалы:\n"
            "<code>/prompt инвесторға арналған талдаушы сияқты жаз, тек сандар мен қорытындылар</code>\n\n"
            "Кәдімгі стильге оралу: <code>/prompt off</code>"
        ),
        "custom_prompt_on": "өз промптыңмен ауыстырылды",
        "added": "Қосылды: <b>{title}</b>",
        "already": "Тізімде бар: <b>{title}</b>",
        "folder_added": "<b>{title}</b> қалтасы: {added} қосылды, {existing} бұрыннан бар",
        "folder_skipped": "Сен жазылмаған жабық арналар өткізілді: {items}",
        "add_failed": "{ref} қосылмады: {reason}",
        "add_usage": "Сілтеме немесе @атау жібер: /add @durov",
        "removed": "Алып тасталды: <b>{title}</b>",
        "not_found": "Мұндай арна тізімде жоқ. Нөмірлер /channels ішінде",
        "no_channels": "Әзірге арна жоқ. /add арқылы қос немесе арнадан жазба жібер.",
        "channels_header": "<b>Арналар ({count})</b>",
        "collecting": "Дайджест жиналып жатыр…",
        "busy": "Дайджест қазір жиналып жатыр, бір минут күте тұр.",
        "digest_title": "<b>Дайджест · {date}</b>",
        "digest_window_title": "<b>Соңғы {hours} сағ · {date}</b>",
        "digest_stats": "Жаңалығы бар арналар: {channels} · жазбалар: {posts}",
        "highlights": "<b>Ең маңыздысы</b>",
        "nothing_new": "Жаңа жазбалар жоқ.",
        "failed_channels": "<i>Оқу мүмкін болмады: {items}</i>",
        "status": (
            "Модель: <code>{model}</code>\n"
            "Арналар: {channels}\n"
            "Келесі дайджест: {next_run}\n"
            "Соңғы іске қосу: {last}"
        ),
        "last_run": "{when}, жазбалар {posts}, суреттер {images}, токендер {tokens}",
        "never": "әлі болған жоқ",
        "error": "Бірдеңе дұрыс болмады: {reason}",
    },
}

# Buttons and menus
_BUTTONS = {
    "ru": {
        "menu_digest": "📰 Дайджест",
        "menu_channels": "📋 Каналы",
        "menu_add": "➕ Добавить",
        "menu_settings": "⚙️ Настройки",
        "menu_status": "📊 Статус",
        "menu_help": "❓ Помощь",
        "add_prompt": "Пришли ссылку на канал, @имя или ссылку на папку t.me/addlist/… Можно просто переслать пост из канала.",
        "digest_choose": "Какой дайджест собрать?",
        "btn_unread": "🆕 Непрочитанное",
        "btn_24h": "24 часа",
        "btn_48h": "48 часов",
        "btn_7d": "7 дней",
        "channels_hint": "Нажми на канал, чтобы убрать его из списка.",
        "choose_time": "Выбери время или пришли своё: <code>/time 08:30</code>",
        "cmd_digest": "дайджест непрочитанного",
        "cmd_channels": "список каналов",
        "cmd_add": "добавить канал или папку",
        "cmd_settings": "стиль, язык, время",
        "cmd_status": "расписание и последний запуск",
        "cmd_help": "что умеет бот",
    },
    "en": {
        "menu_digest": "📰 Digest",
        "menu_channels": "📋 Channels",
        "menu_add": "➕ Add",
        "menu_settings": "⚙️ Settings",
        "menu_status": "📊 Status",
        "menu_help": "❓ Help",
        "add_prompt": "Send a channel link, an @name or a folder link t.me/addlist/… Or just forward a post from the channel.",
        "digest_choose": "Which digest?",
        "btn_unread": "🆕 Unread",
        "btn_24h": "24 hours",
        "btn_48h": "48 hours",
        "btn_7d": "7 days",
        "channels_hint": "Tap a channel to remove it.",
        "choose_time": "Pick a time or send your own: <code>/time 08:30</code>",
        "cmd_digest": "digest of unread posts",
        "cmd_channels": "channel list",
        "cmd_add": "add a channel or folder",
        "cmd_settings": "style, language, time",
        "cmd_status": "schedule and last run",
        "cmd_help": "what the bot does",
    },
    "es": {
        "menu_digest": "📰 Resumen",
        "menu_channels": "📋 Canales",
        "menu_add": "➕ Añadir",
        "menu_settings": "⚙️ Ajustes",
        "menu_status": "📊 Estado",
        "menu_help": "❓ Ayuda",
        "add_prompt": "Envía un enlace de canal, un @nombre o un enlace de carpeta t.me/addlist/… O reenvía una publicación del canal.",
        "digest_choose": "¿Qué resumen preparo?",
        "btn_unread": "🆕 No leído",
        "btn_24h": "24 horas",
        "btn_48h": "48 horas",
        "btn_7d": "7 días",
        "channels_hint": "Pulsa un canal para quitarlo.",
        "choose_time": "Elige una hora o envía la tuya: <code>/time 08:30</code>",
        "cmd_digest": "resumen de lo no leído",
        "cmd_channels": "lista de canales",
        "cmd_add": "añadir canal o carpeta",
        "cmd_settings": "estilo, idioma, hora",
        "cmd_status": "horario y última ejecución",
        "cmd_help": "qué hace el bot",
    },
    "fr": {
        "menu_digest": "📰 Digest",
        "menu_channels": "📋 Chaînes",
        "menu_add": "➕ Ajouter",
        "menu_settings": "⚙️ Réglages",
        "menu_status": "📊 Statut",
        "menu_help": "❓ Aide",
        "add_prompt": "Envoie un lien de chaîne, un @nom ou un lien de dossier t.me/addlist/… Ou transfère une publication de la chaîne.",
        "digest_choose": "Quel digest préparer ?",
        "btn_unread": "🆕 Non lus",
        "btn_24h": "24 heures",
        "btn_48h": "48 heures",
        "btn_7d": "7 jours",
        "channels_hint": "Touche une chaîne pour la retirer.",
        "choose_time": "Choisis une heure ou envoie la tienne : <code>/time 08:30</code>",
        "cmd_digest": "digest des non lus",
        "cmd_channels": "liste des chaînes",
        "cmd_add": "ajouter une chaîne ou un dossier",
        "cmd_settings": "style, langue, heure",
        "cmd_status": "planning et dernière exécution",
        "cmd_help": "ce que fait le bot",
    },
    "kk": {
        "menu_digest": "📰 Дайджест",
        "menu_channels": "📋 Арналар",
        "menu_add": "➕ Қосу",
        "menu_settings": "⚙️ Баптаулар",
        "menu_status": "📊 Күйі",
        "menu_help": "❓ Көмек",
        "add_prompt": "Арна сілтемесін, @атауын немесе t.me/addlist/… қалта сілтемесін жібер. Не арнадан жазбаны жай ғана жібер.",
        "digest_choose": "Қандай дайджест жинайын?",
        "btn_unread": "🆕 Оқылмаған",
        "btn_24h": "24 сағат",
        "btn_48h": "48 сағат",
        "btn_7d": "7 күн",
        "channels_hint": "Арнаны тізімнен алып тастау үшін оны бас.",
        "choose_time": "Уақытты таңда немесе өзіңдікін жібер: <code>/time 08:30</code>",
        "cmd_digest": "оқылмағандардың дайджесті",
        "cmd_channels": "арналар тізімі",
        "cmd_add": "арна немесе қалта қосу",
        "cmd_settings": "стиль, тіл, уақыт",
        "cmd_status": "кесте және соңғы іске қосу",
        "cmd_help": "бот не істейді",
    },
}
for _lang, _strings in _BUTTONS.items():
    TEXTS[_lang].update(_strings)

UI_LANGUAGES = tuple(TEXTS)


def t(lang: str, key: str, **kwargs) -> str:
    table = TEXTS.get(lang, TEXTS["en"])
    text = table.get(key, TEXTS["en"][key])
    return text.format(**kwargs) if kwargs else text
