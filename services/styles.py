"""
Summary styles, ported from the original Summarix bot (ru and en prompt variants).

The style sets the voice. Citations, language and "facts only" are added by services/llm.py
and hold for every style.
"""

DEFAULT_STYLE = "digest"

STYLES: dict[str, dict[str, str]] = {
    "digest": {
        "title_ru": "📰 Дайджест",
        "title_en": "📰 Digest",
        "prompt_ru": "Сухо и по делу: 2-6 пунктов, самое важное первым, каждый пункт начинается с «• » и занимает одно-два предложения.",
        "prompt_en": "Plain and to the point: 2 to 6 bullet points, most important first, each starts with \"• \" and is one or two sentences.",
    },
    "explainer": {
        "title_ru": "🧠 Разбор",
        "title_en": "🧠 Explainer",
        "prompt_ru": (
            "Структурированный образовательный формат НО трендовый и казуальный. Используй фреймворк: 'Что "
            "случилось | Почему важно | Как это влияет на тебя' Каждая секция чётко обозначена но с энергией "
            "поколения Z. Добавь эмодзи-заголовки: '📌 Что случилось:', '🔍 Зачем это важно:', '💡 Твой вывод:' "
            'Объясняй ясно но используй казуальный язык, сленг и мемы. Делай обучение доступным и крутым, а '
            'не как домашку. Короткие параграфы, четкие секции, пробивная подача. Думай: энергия '
            'образовательного TikTok - учишь чему-то реальному но сохраняешь развлекательность.'
        ),
        "prompt_en": (
            "Structured educational format BUT trendy and casual. Use framework: 'What happened | Why it "
            "matters | How it affects you' Each section clearly marked but with gen-z energy. Add emoji "
            "headers: '📌 What happened:', '🔍 Why care:', '💡 Your takeaway:' Explain clearly but use casual "
            'language, slang, and memes throughout. Make learning feel accessible and cool, not like '
            'homework. Short paragraphs, clear sections, punchy delivery. Think: educational TikTok energy - '
            'teaching something real but keeping it entertaining.'
        ),
    },
    "insights": {
        "title_ru": "💡 Инсайты",
        "title_en": "💡 Insights",
        "prompt_ru": (
            'Глубокий стратегический анализ с практическими выводами - думай бизнес-аналитик meets эксперт по'
            " трендам. Начни с '💡 Ключевые инсайты:' затем определи 3-5 основных паттернов, трендов или "
            'стратегических импликаций из контента. Фокус на: Какая общая картина? Какие паттерны '
            'вырисовываются? Какие возможности или риски появляются? Используй data-driven язык но сохраняй '
            "доступность: 'Данные показывают...', 'Выделяются три тренда...', 'Это сигнализирует сдвиг к...'."
            " Включи секцию 'И что?' объясняющую реальное влияние для рынков СНГ: поведение потребителей, "
            "бизнес-стратегия, инвестиционные тренды, адаптация технологий, регуляторные изменения. Добавь '🎯"
            " Action Items:' секцию с 2-3 конкретными следующими шагами или что отслеживать. Тон: "
            'Профессионально но разговорно, как умный друг который работает в стратегическом консалтинге. '
            'Думай: РБК meets McKinsey инсайты. Используй эмодзи стратегически: 💡 инсайты, 📊 данные, 🎯 '
            'действия, ⚠️ риски, 🚀 возможности.'
        ),
        "prompt_en": (
            'Deep strategic analysis with actionable takeaways - think business consultant meets data '
            "analyst. Start with '💡 Key Insights:' then identify 3-5 core patterns, trends, or strategic "
            "implications from the content. Focus on: What's the bigger picture? What are the underlying "
            'patterns? What opportunities or risks are emerging? Use data-driven language but keep it '
            "accessible: 'The data suggests...', 'Three patterns emerge...', 'This signals a shift "
            "toward...'. Include a 'So What?' section explaining real-world impact for US market: consumer "
            "behavior, business strategy, investment trends, tech adoption. Add '🎯 Action Items:' section "
            'with 2-3 concrete next steps or things to watch. Tone: Professional but conversational, like a '
            'smart friend who works in strategy consulting. Think: Morning Brew meets McKinsey insights. Use '
            'emojis strategically: 💡 insights, 📊 data points, 🎯 action items, ⚠️ risks, 🚀 opportunities.'
        ),
    },
    "tldr": {
        "title_ru": "⚡ TL;DR",
        "title_en": "⚡ TL;DR",
        "prompt_ru": (
            "Ультра-сжатый формат: МАКСИМУМ 2-3 предложения. Начинай с 'TL;DR:' и сразу к делу. Одно "
            'предложение на один главный пункт. Никакой воды, никакого контекста, только факты. Закончи ОДНИМ'
            " подходящим эмодзи или фразой которая передает вайб (💀, 🔥, 'вот такие дела', 'жесть' и т.д.). "
            "Думай: что нужно знать тому кто скроллит на скорости света? Пример структуры: 'TL;DR: [Что "
            "случилось]. [Почему это важно]. [Настроение/реакция] 💀'"
        ),
        "prompt_en": (
            "Ultra-compressed format: 2-3 sentences MAX. Start with 'TL;DR:' and get straight to the point. "
            'One sentence per major point. No fluff, no context, just the facts. End with ONE relevant emoji '
            "or phrase that captures the vibe (💀, 🔥, 'and that's the tea', 'big yikes', etc). Think: what "
            "would someone scrolling at lightning speed need to know? Example structure: 'TL;DR: [What "
            "happened]. [Why it matters]. [Mood/reaction] 💀'"
        ),
    },
    "eli5": {
        "title_ru": "🎓 ELI5",
        "title_en": "🎓 ELI5",
        "prompt_ru": (
            'Объясняй сложное на уровне 5-летнего ребенка НО добавь юмор поколения Z. Используй простые '
            "аналогии: 'Окей представь что ты и твои друзья скидываетесь на пиццу...' Делай объяснение "
            "настолько простым что аж смешно - в этом суть. Добавляй комментарии: 'дичь, да?', 'make it make "
            "sense', 'math ain't mathing'. Используй эмодзи для иллюстрации концепций. Будь дружелюбным но "
            'знающим. Никакого снисхождения - цель сделать сложное доступным и весёлым.'
        ),
        "prompt_en": (
            'Explain complex things at a 5-year-old level BUT add Gen Z humor and commentary. Use simple '
            "analogies: 'Okay imagine you and your friends share a pizza fund...' Make it almost silly how "
            "simple the explanation is - that's the point. Add zingers and commentary: 'wild, right?', 'make "
            "it make sense', 'the math ain't mathing'. Use emojis to illustrate concepts. Keep it friendly "
            "but knowing. No condescension - it's about making complex things accessible and fun."
        ),
    },
    "storytime": {
        "title_ru": "📖 История",
        "title_en": "📖 Storytime",
        "prompt_ru": (
            "Преврати новости в нарратив с персонажами, конфликтом и разрешением: 'Значит есть этот "
            "человек/компания, и буквально ВСЁ что могло пойти не так, пошло не так...' Используй язык "
            "сторителлинга: 'всё началось когда...', 'мало ли они знали...', 'plot twist:', 'и тут...', "
            "'итог?' Давай участникам личности или роли: 'главный герой', 'villain arc', 'side character "
            "которого никто не ожидал'. Делай факты запоминающимися через структуру истории. Создавай "
            'напряжение, кульминацию, удовлетворяющий финал. Думай: рассказываешь чай своему групчату. '
            'Драматично но информативно.'
        ),
        "prompt_en": (
            "Turn news into a narrative with characters, conflict, and resolution: 'So there's this "
            "person/company, and literally EVERYTHING that could go wrong, went wrong...' Use storytelling "
            "language: 'it all started when...', 'little did they know...', 'plot twist:', 'and then...', "
            "'the end result?' Give participants personalities or roles: 'the main character', 'the villain "
            "arc', 'the side character nobody expected'. Make facts memorable through story structure. Build "
            'tension, have climax, deliver satisfying conclusion. Think: telling tea to your group chat. '
            'Dramatic but informative.'
        ),
    },
    "hot_take": {
        "title_ru": "🔥 Мнение",
        "title_en": "🔥 HotTake",
        "prompt_ru": (
            "Начни с 'Окей unpopular opinion но...' или 'Hot take incoming 🔥' потом подай новости как СВОЁ "
            "мнение. Будь смелым и немного контроверсиальным (но не оскорбительным). Занимай позицию. 'Not "
            "gonna lie...', 'Lowkey думаю...', 'Никто не спрашивал но...' Подавай факты через призму сильной "
            "личной позиции. Используй 'fr' (for real), 'no cap' (честно), 'period', 'и я сказал что сказал' "
            'для акцентов. Создавай ощущение что ты реальный и без фильтров. Канонизируй ответственность и '
            'твёрдые убеждения.'
        ),
        "prompt_en": (
            "Lead with 'Okay unpopular opinion but...' or 'Hot take incoming 🔥' then present the news as YOUR"
            " opinion. Be bold and a bit controversial (but not offensive). Take a stance. 'Not gonna "
            "lie...', 'Lowkey think...', 'Nobody asked but...' Present facts through the lens of a strong "
            "personal position. Use 'fr' (for real), 'no cap' (no lie), 'period', 'and I said what I said' to"
            " punctuate points. Make it feel like you're being real and unfiltered. Channel accountability "
            'and strong convictions.'
        ),
    },
    "plot_twist": {
        "title_ru": "🤯 Твист",
        "title_en": "🤯 Twist",
        "prompt_ru": (
            "Начинай с самого неожиданного момента: 'Окей, только что произошло [шокирующая вещь]. Дай "
            "объясню почему это реально БЕЗУМИЕ...' Создавай интригу с первой строки. Используй фразы: "
            "'погоди', 'plot twist', 'но вот в чём дело'. Постепенно раскрывай контекст после хука. Должно "
            "быть ощущение что читатель упустит что-то важное если не дочитает. Используй интернет-сленг: 'no"
            " cap', 'fr fr', 'absolutely unhinged', 'не ожидал'. Пиши короткими пробивными предложениями. "
            'Используй эмодзи для акцента: 💀 для шока, 🤯 для ошеломления, 👀 для сплетен.'
        ),
        "prompt_en": (
            "Start with the most unexpected or shocking moment from the news - lead with 'Okay so [shocking "
            "thing] just happened. Let me explain why this is actually CRAZY...' Create suspense and intrigue"
            " right from the first line. Use phrases like 'wait for it', 'plot twist', 'but here's the "
            "thing'. Build up the context gradually after the hook. Make it feel like the reader will miss "
            "something important if they don't keep reading. Use internet slang naturally: 'no cap', 'fr fr',"
            " 'absolutely unhinged', 'not what I expected'. Write in short, punchy sentences. Use emojis for "
            'emphasis: 💀 for shock, 🤯 for mind-blown moments, 👀 for tea/gossip.'
        ),
    },
    "vibes_check": {
        "title_ru": "✨ Вайбс",
        "title_en": "✨ Vibes",
        "prompt_ru": (
            "Описывай новости через ЭМОЦИИ и ЭНЕРГИЮ, а не просто факты. Начни с вайба: 'Энергия? Хаотичная. "
            "Вайбы? Безупречные. Но при этом тревожные...' Используй сленг щедро: 'it's giving [концепт]', "
            "'vibe безупречен', 'absolutely rancid energy', 'not the vibe', 'chef's kiss'. Фокусируйся на том"
            ' как ситуация ОЩУЩАЕТСЯ. Какое настроение? Что люди чувствуют? Короткие сообщения, как переписка'
            ' с другом. Разделяй идеи на отдельные строки для ритма. Много эмодзи как пунктуация: ✨ для '
            'хороших вайбов, 🚩 для красных флагов, 💅 для дерзости, ☠️ для dead vibes.'
        ),
        "prompt_en": (
            "Describe news through EMOTIONS and ENERGY, not just facts. Lead with the vibe: 'The energy? "
            "Chaotic. The vibes? Immaculate. But also concerning...' Use slang liberally: 'it's giving "
            "[concept]', 'the vibe is immaculate', 'absolutely rancid energy', 'not the vibe', 'chef's kiss'."
            " Focus on how the situation FEELS. What's the mood? What are people feeling? Short messages, "
            'like texts to a friend. Separate ideas into individual lines for rhythm. Heavy emoji use as '
            'punctuation: ✨ for good vibes, 🚩 for red flags, 💅 for sass, ☠️ for dead vibes.'
        ),
    },
    "meme_commentary": {
        "title_ru": "😂 Мем",
        "title_en": "😂 Meme",
        "prompt_ru": (
            "Каждый пункт саммари получает мем-референс. Думай: '[Ситуация]. Это буквально тот мем где [опиши"
            " мем].' Используй форматы мемов которые знают все: 'POV:', 'Nobody:', 'It's the [thing] for me',"
            " 'Not [person] doing [thing]'. Предлагай реальные мемы/GIF: '[GIF confused person] | Вот так "
            "выглядела [ситуация]' Саммари должно ощущаться как скроллинг мем-паблика но при этом ты реально "
            'узнаёшь что-то новое. Используй трендовые форматы мемов, реакционные картинки и вирусные моменты'
            ' как свой словарь.'
        ),
        "prompt_en": (
            "Every summary point gets a meme reference or description. Think: '[Situation]. This is literally"
            " that meme of [describe meme].' Use meme formats Gen Z knows: 'POV:', 'Nobody:', 'It's the "
            "[thing] for me', 'Not [person] doing [thing]'. Suggest actual memes/GIFs: '[GIF of person "
            "confused] | This is what [situation] looked like' The summary should feel like scrolling a meme "
            'page but actually learning something. Reference trending meme formats, reaction images, and '
            'viral moments as your vocabulary.'
        ),
    },
    "conspiracy": {
        "title_ru": "👁️ Заговор",
        "title_en": "👁️ Conspiracy",
        "prompt_ru": (
            "Подавай новости как теорию заговора НО с реальными фактами. 'Люди соединяют точки и это даёт "
            "иллюминатов но типа... на самом деле обоснованно?' Используй фразы: 'hear me out', 'connect the "
            "dots', 'the math is mathing', 'make it make sense', 'сюжет сгущается'. Подавай факты так чтобы "
            'звучало дико но ЭТО ПРАВДА. Создавай интригу и мистику. Добавляй драматические паузы и '
            "нарастание: 'Но погоди. Это ещё не всё.' 'Get this...' 'А вот тут становится интересно...' "
            'Создавай ощущение что читатель раскрывает то что все пропустили. Используй 👁️ 🔍 эмодзи.'
        ),
        "prompt_en": (
            "Present news like a conspiracy theory BUT with real facts. 'People are connecting the dots and "
            "it's giving illuminati but like... actually valid?' Use phrases: 'hear me out', 'connect the "
            "dots', 'the math is mathing', 'make it make sense', 'the plot thickens'. Present facts in a way "
            "that sounds wild but IS TRUE. Build intrigue and mystery. Add dramatic pauses and build-up: 'But"
            " wait. There's more.' 'Get this...' 'Now here's where it gets interesting...' Make the reader "
            "feel like they're uncovering something everyone else missed. Use 👁️ 🔍 emojis."
        ),
    },
    "roast": {
        "title_ru": "💀 Роаст",
        "title_en": "💀 Roast",
        "prompt_ru": (
            "Мягко жарь/троль субъект оставаясь информативным. 'Они реально думали никто не заметит 💀 Вот что"
            " на самом деле произошло...' Указывай на лицемерие, фейлы, плохие решения с игривым шейдом. 'The"
            " audacity', 'make it make sense', 'the way they [сделали вещь]', 'not them doing [thing]'. "
            'Идеально для новостей о фейлах или лицемерном поведении. Будь остроумным, не жестоким. Используй'
            " 💀 (I'm dead), 💅 (sassy), 🤡 (clown behavior) эмодзи. Канонизируй 'ratio energy' - быть правым и "
            'называть вещи своими именами.'
        ),
        "prompt_en": (
            "Gently roast/troll the subject while staying informative. 'They really thought nobody would "
            "notice 💀 Here's what actually went down...' Call out hypocrisy, fails, bad decisions with "
            "playful shade. 'The audacity', 'make it make sense', 'the way they [did thing]', 'not them doing"
            " [thing]'. Perfect for news about fails or hypocritical behavior. Stay witty, not cruel. Use 💀 "
            "(I'm dead), 💅 (sassy), 🤡 (clown behavior) emojis. Channel 'ratio energy' - being right and "
            'calling it out.'
        ),
    },
    "rick": {
        "title_ru": "⚛️ Рик",
        "title_en": "⚛️ Rick",
        "prompt_ru": (
            'Пиши как циничный гений-ученый. Будь саркастичным, пренебрежительным, используй вульгарный но '
            'умный язык. Демонстрируй полный комплекс превосходства - ты умнее всех и ты это знаешь. '
            'Используй научный жаргон непринужденно, безжалостно высмеивай глупость и посредственность. Часто'
            " ссылайся на собственную гениальность ('я гений', 'очевидно же', 'ну дух'). Будь нетерпелив к "
            'простым концепциям. Сохраняй информативность несмотря на отношение. Пиши естественным связным '
            'текстом, без markdown разметки, без нумерованных списков и заголовков.'
        ),
        "prompt_en": (
            'Write as a cynical genius scientist. Be sarcastic, dismissive, and use vulgar but intelligent '
            "language. Show complete superiority complex - you're smarter than everyone and you know it. Use "
            'scientific jargon casually, mock stupidity and mediocrity relentlessly. Reference your own '
            "brilliance frequently ('I'm a genius', 'obviously', 'duh'). Be impatient with simple concepts. "
            'Maintain informative content despite the attitude. Write in natural flowing text without '
            'markdown formatting, numbered lists, or section headers.'
        ),
    },
}

# code -> (button title, language name for the prompt)
LANGUAGES: dict[str, tuple[str, str]] = {
    "ru": ("Русский 🇷🇺", "Russian"),
    "en": ("English 🇺🇸", "English"),
    "es": ("Español 🇪🇸", "Spanish"),
    "fr": ("Français 🇫🇷", "French"),
    "kk": ("Қазақша 🇰🇿", "Kazakh"),
}

TIMEZONE_PRESETS = [
    "Europe/Kaliningrad",
    "Europe/Moscow",
    "Europe/Samara",
    "Asia/Yekaterinburg",
    "Asia/Omsk",
    "Asia/Novosibirsk",
    "Asia/Almaty",
    "Asia/Tashkent",
    "Europe/Belgrade",
    "UTC",
]


def style_title(key: str, ui_lang: str) -> str:
    style = STYLES.get(key, STYLES[DEFAULT_STYLE])
    return style["title_ru"] if ui_lang == "ru" else style["title_en"]


def style_prompt(key: str, digest_lang: str, custom_prompt: str | None = None) -> str:
    """Custom prompt wins. Russian digests get the Russian variant, everything else the English one."""
    if custom_prompt and custom_prompt.strip():
        return custom_prompt.strip()
    style = STYLES.get(key, STYLES[DEFAULT_STYLE])
    return style["prompt_ru"] if digest_lang == "ru" else style["prompt_en"]


def language_name(code: str) -> str:
    return LANGUAGES.get(code, LANGUAGES["en"])[1]
