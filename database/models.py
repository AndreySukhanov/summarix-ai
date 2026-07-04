"""
SQLAlchemy models. Telegram user IDs are BigInteger — they exceed int32.
"""
from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger, Boolean, Column, DateTime, Enum, ForeignKey, Integer, String
)
from sqlalchemy.orm import declarative_base, relationship

from config.constants import SubStatus, Tier

Base = declarative_base()


def utcnow():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, index=True, nullable=False)
    username = Column(String, nullable=True)
    first_name = Column(String, nullable=True)
    language = Column(String, default="en")
    is_banned = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utcnow)
    last_active = Column(DateTime, default=utcnow)

    subscription = relationship(
        "Subscription", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    tier = Column(Enum(Tier), default=Tier.FREE, nullable=False)
    status = Column(Enum(SubStatus), default=SubStatus.ACTIVE, nullable=False)
    requests_used = Column(Integer, default=0)
    bonus_requests = Column(Integer, default=0)  # referral bonuses, added on top of tier quota
    started_at = Column(DateTime, default=utcnow)
    expires_at = Column(DateTime, nullable=True)  # None = never (FREE)

    user = relationship("User", back_populates="subscription")


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    tier = Column(Enum(Tier), nullable=False)
    amount_stars = Column(Integer, nullable=False)
    telegram_charge_id = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime, default=utcnow)


class ReferralCode(Base):
    __tablename__ = "referral_codes"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    code = Column(String(16), unique=True, index=True, nullable=False)
    uses_count = Column(Integer, default=0)
    max_uses = Column(Integer, default=100)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)


class Referral(Base):
    __tablename__ = "referrals"

    id = Column(Integer, primary_key=True)
    referrer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    referred_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    code_id = Column(Integer, ForeignKey("referral_codes.id"), nullable=False)
    created_at = Column(DateTime, default=utcnow)
