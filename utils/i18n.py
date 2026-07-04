"""
Minimal i18n: nested dict per language, English fallback.
Add a language = add one top-level key.
"""

TRANSLATIONS = {
    "en": {
        "start": (
            "👋 Hi, {name}!\n\n"
            "I'm an AI assistant. Send me any message and I'll answer.\n\n"
            "Free plan: {free_limit} requests/month. /subscription to upgrade."
        ),
        "menu_subscription": "💳 Subscription",
        "menu_invite": "🎁 Invite a friend",
        "thinking": "🤔 Thinking...",
        "limit_reached": (
            "🚫 Monthly limit reached.\n\n"
            "Upgrade with /subscription or invite friends with /invite for bonus requests."
        ),
        "ai_error": "⚠️ Something went wrong. Please try again.",
        "sub_status": "Your plan: <b>{tier}</b>\nRequests used: {used}/{limit}",
        "sub_upgrade": "⭐ Upgrade to PRO — {price} Stars/month ({limit} requests)",
        "sub_invoice_title": "PRO subscription",
        "sub_invoice_desc": "{limit} AI requests per month for 30 days",
        "sub_activated": "🎉 PRO activated until {until}! Enjoy.",
        "referral_message": (
            "🎁 <b>Invite friends — get bonus requests!</b>\n\n"
            "Your friend gets +{referred} requests, you get +{referrer} for each friend.\n\n"
            "Your link:\n{link}\n\n"
            "Invited: {invited} | Bonus earned: {earned}"
        ),
        "referral_welcome": "🎁 Welcome bonus: +{bonus} requests!",
        "referral_reward": "🎉 A friend joined via your link: +{bonus} requests!",
        "banned": "⛔ You are banned.",
        "rate_limited": "⏳ Too fast, try again in a moment.",
    },
    "ru": {
        "start": (
            "👋 Привет, {name}!\n\n"
            "Я AI-ассистент. Отправь мне любое сообщение — я отвечу.\n\n"
            "Бесплатный план: {free_limit} запросов/месяц. /subscription — улучшить."
        ),
        "menu_subscription": "💳 Подписка",
        "menu_invite": "🎁 Пригласить друга",
        "thinking": "🤔 Думаю...",
        "limit_reached": (
            "🚫 Месячный лимит исчерпан.\n\n"
            "Улучшите план: /subscription или пригласите друзей: /invite — бонусные запросы."
        ),
        "ai_error": "⚠️ Что-то пошло не так. Попробуйте ещё раз.",
        "sub_status": "Ваш план: <b>{tier}</b>\nИспользовано запросов: {used}/{limit}",
        "sub_upgrade": "⭐ Улучшить до PRO — {price} Stars/мес ({limit} запросов)",
        "sub_invoice_title": "Подписка PRO",
        "sub_invoice_desc": "{limit} AI-запросов в месяц на 30 дней",
        "sub_activated": "🎉 PRO активирован до {until}! Пользуйтесь.",
        "referral_message": (
            "🎁 <b>Приглашайте друзей — получайте бонусные запросы!</b>\n\n"
            "Друг получает +{referred} запросов, вы — +{referrer} за каждого.\n\n"
            "Ваша ссылка:\n{link}\n\n"
            "Приглашено: {invited} | Бонусов заработано: {earned}"
        ),
        "referral_welcome": "🎁 Приветственный бонус: +{bonus} запросов!",
        "referral_reward": "🎉 Друг присоединился по вашей ссылке: +{bonus} запросов!",
        "banned": "⛔ Вы заблокированы.",
        "rate_limited": "⏳ Слишком часто, попробуйте через мгновение.",
    },
}


def _(key: str, lang: str = "en", **kwargs) -> str:
    text = TRANSLATIONS.get(lang, TRANSLATIONS["en"]).get(key) \
        or TRANSLATIONS["en"].get(key, key)
    return text.format(**kwargs) if kwargs else text
