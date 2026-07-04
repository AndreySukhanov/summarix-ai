"""
Business constants: tiers, limits, prices, referral bonuses.
Add a tier = add one enum member + one row in each dict below.
"""
import enum


class Tier(str, enum.Enum):
    FREE = "free"
    PRO = "pro"


class SubStatus(str, enum.Enum):
    ACTIVE = "active"
    EXPIRED = "expired"


# Monthly AI request quota per tier
TIER_LIMITS = {
    Tier.FREE: {"requests": 10},
    Tier.PRO: {"requests": 500},
}

# Price in Telegram Stars (XTR). Stars need no payment provider setup at all.
TIER_PRICES_STARS = {
    Tier.PRO: 375,  # ≈ $4.99
}

SUBSCRIPTION_DAYS = 30

# Referral program: both sides get bonus requests on top of their quota
REFERRAL_REFERRER_BONUS = 10
REFERRAL_REFERRED_BONUS = 5
REFERRAL_MAX_USES = 100
REFERRAL_DEEP_LINK_PREFIX = "ref_"
