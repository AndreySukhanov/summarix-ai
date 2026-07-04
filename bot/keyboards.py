from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from config.constants import Tier, TIER_LIMITS, TIER_PRICES_STARS
from utils.i18n import _


def main_menu(lang: str = "en") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=_("menu_subscription", lang), callback_data="subscription"),
            InlineKeyboardButton(text=_("menu_invite", lang), callback_data="referral"),
        ],
    ])


def subscription_menu(lang: str = "en") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=_("sub_upgrade", lang,
                   price=TIER_PRICES_STARS[Tier.PRO],
                   limit=TIER_LIMITS[Tier.PRO]["requests"]),
            callback_data="buy_pro",
        )],
    ])
