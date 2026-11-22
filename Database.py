#لوجيك | Logic وجهتك البرمجية الأولى  بالوطن العربي
#شروحات - أكواد - وأحدث تقنيات برمجية - وحلول تقنية
#بواسطه: t.me/Logii3

#الترخيص: @TopVeGa
#العلامة التجارية: VEGA & Logic
#حقوق الطبع والنشر: © 2015 - 2025

import asyncpg
import secrets
import logging
import json
import re
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from cryptography.fernet import Fernet

from config import (
    DATABASE_URL, ENCRYPTION_KEY, REDIS_URL,
    DAILY_LIMIT_NORMAL, DAILY_LIMIT_VIP,
    VIP_BALANCE_THRESHOLD, DAILY_BONUS_AMOUNT,
    CHANNEL_JOIN_REWARD, CHANNEL_LEAVE_PENALTY,
    FIXED_2FA_PASSWORD
)

logger = logging.getLogger(__name__)

_cipher = Fernet(ENCRYPTION_KEY.encode() if isinstance(ENCRYPTION_KEY, str) else ENCRYPTION_KEY)


def encrypt(text: str) -> str:
    if not text:
        return ""
    return _cipher.encrypt(text.encode()).decode()


def decrypt(token: str) -> str:
    if not token:
        return ""
    try:
        return _cipher.decrypt(token.encode()).decode()
    except Exception:
        return ""


def generate_2fa_password() -> str:
    return FIXED_2FA_PASSWORD


def generate_transaction_id() -> str:
    return secrets.token_hex(8).upper()


def _count_deleted(result_str: str) -> int:
    try:
        return int(result_str.split()[-1])
    except Exception:
        return 0


def _count_updated(result_str: str) -> int:
    try:
        return int(result_str.split()[-1])
    except Exception:
        return 0


class CacheManager:
    def __init__(self):
        self.redis = None

    async def connect(self):
        if not REDIS_URL:
            logger.info("ℹ️ Redis غير مفعّل")
            return
        try:
            import redis.asyncio as aioredis
            self.redis = aioredis.from_url(REDIS_URL, decode_responses=True)
            await self.redis.ping()
            logger.info("✅ متصل بـ Redis")
        except Exception as e:
            logger.warning(f"⚠️ Redis غير متاح: {e}")
            self.redis = None

    async def close(self):
        if self.redis:
            await self.redis.close()

    async def get(self, key: str) -> Optional[str]:
        if not self.redis:
            return None
        try:
            return await self.redis.get(key)
        except Exception:
            return None

    async def set(self, key: str, value: str, ttl: int = 60):
        if not self.redis:
            return
        try:
            await self.redis.set(key, value, ex=ttl)
        except Exception:
            pass

    async def delete(self, key: str):
        if not self.redis:
            return
        try:
            await self.redis.delete(key)
        except Exception:
            pass


cache = CacheManager()

from collections import defaultdict
import time

_rate_store: Dict[int, List[float]] = defaultdict(list)


def rate_limited(user_id: int, max_req: int = 10, window: int = 60) -> bool:
    now = time.time()
    _rate_store[user_id] = [t for t in _rate_store[user_id] if now - t < window]
    if len(_rate_store[user_id]) >= max_req:
        return True
    _rate_store[user_id].append(now)
    return False


async def audit_log(pool, user_id: int, action: str, details: str = ""):
    try:
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO audit_logs (user_id, action, details)
                VALUES ($1, $2, $3)
            """, user_id, action, details)
    except Exception as e:
        logger.debug(f"audit_log: {e}")


class Database:
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None
        self.bot_enabled = True

    async def connect(self):
        self.pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=5,
            max_size=20,
            command_timeout=30,
            max_inactive_connection_lifetime=300,
            statement_cache_size=0
        )
        await self._create_tables()
        await cache.connect()
        logger.info("✅ متصل بقاعدة البيانات PostgreSQL")

    async def close(self):
        if self.pool:
            await self.pool.close()
        await cache.close()

    async def _create_tables(self):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id BIGINT PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    balance NUMERIC(12,2) DEFAULT 0,
                    rating NUMERIC(3,2) DEFAULT 5.00,
                    total_sales INT DEFAULT 0,
                    total_purchases INT DEFAULT 0,
                    is_banned BOOLEAN DEFAULT FALSE,
                    level TEXT DEFAULT 'normal',
                    language TEXT DEFAULT 'ar',
                    referral_code TEXT UNIQUE,
                    referred_by BIGINT,
                    referral_count INT DEFAULT 0,
                    referral_earnings NUMERIC(12,2) DEFAULT 0,
                    daily_bonus_at TIMESTAMP,
                    daily_purchase_count INT DEFAULT 0,
                    daily_purchase_date DATE,
                    created_at TIMESTAMP DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS numbers (
                    phone TEXT PRIMARY KEY,
                    session_enc TEXT NOT NULL,
                    seller_id BIGINT NOT NULL,
                    country TEXT DEFAULT 'غير محدد',
                    password_2fa_enc TEXT DEFAULT '',
                    price NUMERIC(12,2) DEFAULT 0,
                    status TEXT DEFAULT 'available',
                    buyer_id BIGINT,
                    reserved_until TIMESTAMP,
                    created_at TIMESTAMP DEFAULT NOW(),
                    sold_at TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS transactions (
                    id TEXT PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    type TEXT NOT NULL,
                    amount NUMERIC(12,2) DEFAULT 0,
                    phone TEXT,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS reviews (
                    id SERIAL PRIMARY KEY,
                    reviewer_id BIGINT NOT NULL,
                    target_id BIGINT NOT NULL,
                    phone TEXT,
                    rating INT CHECK (rating BETWEEN 1 AND 5),
                    comment TEXT,
                    created_at TIMESTAMP DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS coupons (
                    code TEXT PRIMARY KEY,
                    discount_percent INT NOT NULL,
                    max_uses INT DEFAULT 100,
                    used_count INT DEFAULT 0,
                    expires_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS coupon_uses (
                    id SERIAL PRIMARY KEY,
                    code TEXT NOT NULL,
                    user_id BIGINT NOT NULL,
                    used_at TIMESTAMP DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS pending_requests (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    country TEXT,
                    max_price NUMERIC(12,2),
                    prefix TEXT,
                    created_at TIMESTAMP DEFAULT NOW(),
                    fulfilled BOOLEAN DEFAULT FALSE
                );

                CREATE TABLE IF NOT EXISTS temp_data (
                    user_id BIGINT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT,
                    PRIMARY KEY (user_id, key)
                );

                CREATE TABLE IF NOT EXISTS referrals (
                    id SERIAL PRIMARY KEY,
                    referrer_id BIGINT NOT NULL,
                    referred_id BIGINT UNIQUE NOT NULL,
                    bonus_paid BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS watchlist (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    pattern TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS deposits (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    method TEXT NOT NULL,
                    amount NUMERIC(12,2) NOT NULL,
                    status TEXT DEFAULT 'pending',
                    proof TEXT,
                    created_at TIMESTAMP DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS tickets (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    subject TEXT NOT NULL,
                    status TEXT DEFAULT 'open',
                    created_at TIMESTAMP DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS ticket_messages (
                    id SERIAL PRIMARY KEY,
                    ticket_id INT NOT NULL,
                    sender_id BIGINT NOT NULL,
                    message TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS audit_logs (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT,
                    action TEXT,
                    details TEXT,
                    created_at TIMESTAMP DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS required_channels (
                    id SERIAL PRIMARY KEY,
                    channel_username TEXT UNIQUE NOT NULL,
                    channel_title TEXT,
                    added_by BIGINT,
                    created_at TIMESTAMP DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS user_channel_subs (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    channel_username TEXT NOT NULL,
                    is_member BOOLEAN DEFAULT TRUE,
                    reward_paid BOOLEAN DEFAULT FALSE,
                    joined_at TIMESTAMP DEFAULT NOW(),
                    left_at TIMESTAMP,
                    UNIQUE(user_id, channel_username)
                );

                CREATE TABLE IF NOT EXISTS saved_codes (
                    id SERIAL PRIMARY KEY,
                    phone TEXT NOT NULL,
                    buyer_id BIGINT NOT NULL,
                    code TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS completed_purchases (
                    id SERIAL PRIMARY KEY,
                    phone TEXT NOT NULL,
                    buyer_id BIGINT NOT NULL,
                    seller_id BIGINT NOT NULL,
                    price NUMERIC(12,2) NOT NULL,
                    rated BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT NOW(),
                    UNIQUE(phone, buyer_id)
                );

                CREATE TABLE IF NOT EXISTS bot_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                );

                CREATE TABLE IF NOT EXISTS admins (
                    user_id BIGINT PRIMARY KEY,
                    added_by BIGINT,
                    added_at TIMESTAMP DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS otp_tracking (
                    phone TEXT NOT NULL,
                    buyer_id BIGINT NOT NULL,
                    phone_code_hash TEXT,
                    last_code TEXT,
                    updated_at TIMESTAMP DEFAULT NOW(),
                    PRIMARY KEY (phone, buyer_id)
                );

                CREATE TABLE IF NOT EXISTS frozen_numbers (
                    phone TEXT PRIMARY KEY,
                    frozen_by BIGINT,
                    reason TEXT,
                    frozen_at TIMESTAMP DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS communication_settings (
                    user_id BIGINT PRIMARY KEY,
                    enabled BOOLEAN DEFAULT TRUE,
                    updated_at TIMESTAMP DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS gifts (
                    id SERIAL PRIMARY KEY,
                    sender_id BIGINT NOT NULL,
                    receiver_id BIGINT NOT NULL,
                    amount NUMERIC(12,2) NOT NULL,
                    message TEXT,
                    created_at TIMESTAMP DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS twasl_messages (
                    id SERIAL PRIMARY KEY,
                    owner_id BIGINT NOT NULL,
                    user_id BIGINT NOT NULL,
                    user_message_id BIGINT NOT NULL,
                    owner_message_id BIGINT NOT NULL,
                    user_first_name TEXT,
                    user_username TEXT,
                    created_at TIMESTAMP DEFAULT NOW()
                );

                CREATE INDEX IF NOT EXISTS idx_numbers_status ON numbers(status);
                CREATE INDEX IF NOT EXISTS idx_numbers_country ON numbers(country);
                CREATE INDEX IF NOT EXISTS idx_transactions_user ON transactions(user_id);
                CREATE INDEX IF NOT EXISTS idx_numbers_seller ON numbers(seller_id);
                CREATE INDEX IF NOT EXISTS idx_referrals_referrer ON referrals(referrer_id);
                CREATE INDEX IF NOT EXISTS idx_watchlist_user ON watchlist(user_id);
                CREATE INDEX IF NOT EXISTS idx_user_channel_subs_user ON user_channel_subs(user_id);
                CREATE INDEX IF NOT EXISTS idx_saved_codes_phone ON saved_codes(phone);
                CREATE INDEX IF NOT EXISTS idx_completed_phone ON completed_purchases(phone);
                CREATE INDEX IF NOT EXISTS idx_completed_buyer ON completed_purchases(buyer_id);
                CREATE INDEX IF NOT EXISTS idx_otp_phone ON otp_tracking(phone);
                CREATE INDEX IF NOT EXISTS idx_frozen_phone ON frozen_numbers(phone);
                CREATE INDEX IF NOT EXISTS idx_gifts_receiver ON gifts(receiver_id);
                CREATE INDEX IF NOT EXISTS idx_admins_user ON admins(user_id);
                CREATE INDEX IF NOT EXISTS idx_twasl_owner_msg
                    ON twasl_messages(owner_message_id);
                CREATE INDEX IF NOT EXISTS idx_twasl_user
                    ON twasl_messages(user_id);
            """)

    # ============== 👤 إدارة المشرفين ==============
    async def add_admin(self, user_id: int, added_by: int) -> bool:
        async with self.pool.acquire() as conn:
            existing = await conn.fetchval(
                "SELECT user_id FROM admins WHERE user_id=$1", user_id
            )
            if existing:
                return False
            await conn.execute("""
                INSERT INTO admins (user_id, added_by) VALUES ($1, $2)
            """, user_id, added_by)
            return True

    async def remove_admin(self, user_id: int) -> bool:
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM admins WHERE user_id=$1", user_id
            )
            return "DELETE 1" in result

    async def get_all_admins(self) -> List[int]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("SELECT user_id FROM admins ORDER BY added_at")
            return [r['user_id'] for r in rows]

    async def is_admin(self, user_id: int) -> bool:
        async with self.pool.acquire() as conn:
            val = await conn.fetchval(
                "SELECT 1 FROM admins WHERE user_id=$1", user_id
            )
            return bool(val)

    # ============== 💎 الأرقام المميزة ==============
    async def is_number_premium(self, phone: str) -> bool:
        """
        يكشف الأرقام المميزة:
        - تكرار 4+ مرات (8888, 0000, 1111)
        - تكرار 3+ مرات (888, 000, 111)
        - تسلسل (1234, 4321)
        """
        digits = re.sub(r'\D', '', phone or '')
        if not digits:
            return False
        # تكرار 4 مرات أو أكثر
        if re.search(r'(\d)\1{3,}', digits):
            return True
        # تكرار 3 مرات
        if re.search(r'(\d)\1{2,}', digits):
            return True
        # تسلسل
        if re.search(
            r'(0123|1234|2345|3456|4567|5678|6789|'
            r'9876|8765|6543|5432|4321|3210)',
            digits
        ):
            return True
        return False

    # ============== 💬 التواصل (owner-level) ==============
    async def enable_owner_comm(self, owner_id: int) -> bool:
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO bot_settings (key, value)
                VALUES ($1, 'enabled')
                ON CONFLICT (key) DO UPDATE SET value='enabled'
            """, f"twasl_{owner_id}")
            return True

    async def disable_owner_comm(self, owner_id: int) -> bool:
        async with self.pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM bot_settings WHERE key=$1",
                f"twasl_{owner_id}"
            )
            return True

    async def is_owner_comm_enabled(self, owner_id: int) -> bool:
        async with self.pool.acquire() as conn:
            val = await conn.fetchval(
                "SELECT value FROM bot_settings WHERE key=$1",
                f"twasl_{owner_id}"
            )
            return val == "enabled"

    async def save_twasl_message(self, owner_id: int, user_id: int,
                                  user_message_id: int, owner_message_id: int,
                                  first_name: str = "", username: str = ""):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO twasl_messages
                (owner_id, user_id, user_message_id, owner_message_id,
                 user_first_name, user_username)
                VALUES ($1, $2, $3, $4, $5, $6)
            """, owner_id, user_id, user_message_id, owner_message_id,
                first_name, username)

    async def get_twasl_by_owner_msg(self, owner_message_id: int) -> Optional[Dict]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT * FROM twasl_messages
                WHERE owner_message_id = $1
                ORDER BY created_at DESC LIMIT 1
            """, owner_message_id)
            return dict(row) if row else None

    # ============== إعدادات البوت ==============
    async def get_setting(self, key: str) -> Optional[str]:
        async with self.pool.acquire() as conn:
            return await conn.fetchval(
                "SELECT value FROM bot_settings WHERE key=$1", key
            )

    async def set_setting(self, key: str, value: str):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO bot_settings (key, value) VALUES ($1, $2)
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
            """, key, value)

    async def is_bot_enabled(self) -> bool:
        val = await self.get_setting("bot_enabled")
        if val is None:
            return True
        return val == "true"

    async def set_bot_enabled(self, enabled: bool):
        await self.set_setting("bot_enabled", "true" if enabled else "false")
        self.bot_enabled = enabled

    # ============== المستخدمون ==============
    async def get_user(self, user_id: int) -> Optional[Dict]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM users WHERE id=$1", user_id)
            return dict(row) if row else None

    async def create_user(self, user_id: int, username: str = None, first_name: str = None):
        async with self.pool.acquire() as conn:
            existing = await conn.fetchval("SELECT id FROM users WHERE id=$1", user_id)
            if existing:
                await conn.execute("""
                    UPDATE users SET username=$2, first_name=$3 WHERE id=$1
                """, user_id, username, first_name)
                return
            referral_code = None
            for _ in range(10):
                code = secrets.token_hex(4).upper()
                if not await conn.fetchval(
                    "SELECT id FROM users WHERE referral_code=$1", code
                ):
                    referral_code = code
                    break
            await conn.execute("""
                INSERT INTO users (id, username, first_name, referral_code)
                VALUES ($1, $2, $3, $4)
            """, user_id, username, first_name, referral_code)

    async def get_all_users(self) -> List[int]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("SELECT id FROM users WHERE is_banned=FALSE")
            return [r['id'] for r in rows]

    async def get_banned_users(self) -> List[Dict]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT id, first_name, username FROM users WHERE is_banned=TRUE
            """)
            return [dict(r) for r in rows]

    async def clear_all_bans(self) -> int:
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                "UPDATE users SET is_banned=FALSE WHERE is_banned=TRUE"
            )
            try:
                return int(result.split()[-1])
            except Exception:
                return 0

    async def is_banned(self, user_id: int) -> bool:
        async with self.pool.acquire() as conn:
            row = await conn.fetchval("SELECT is_banned FROM users WHERE id=$1", user_id)
            return bool(row)

    async def ban_user(self, user_id: int, ban: bool = True):
        async with self.pool.acquire() as conn:
            await conn.execute("UPDATE users SET is_banned=$2 WHERE id=$1", user_id, ban)

    async def get_balance(self, user_id: int) -> float:
        async with self.pool.acquire() as conn:
            val = await conn.fetchval("SELECT balance FROM users WHERE id=$1", user_id)
            return float(val or 0)

    async def update_balance(self, user_id: int, delta: float):
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE users SET balance = balance + $2 WHERE id=$1", user_id, delta
            )

    async def increment_stat(self, user_id: int, field: str):
        if field not in ("total_sales", "total_purchases"):
            return
        async with self.pool.acquire() as conn:
            await conn.execute(f"UPDATE users SET {field} = {field} + 1 WHERE id=$1", user_id)

    async def update_rating(self, target_id: int):
        async with self.pool.acquire() as conn:
            avg = await conn.fetchval(
                "SELECT AVG(rating) FROM reviews WHERE target_id=$1", target_id
            )
            if avg:
                await conn.execute(
                    "UPDATE users SET rating=$2 WHERE id=$1", target_id, round(float(avg), 2)
                )

    async def get_user_language(self, user_id: int) -> str:
        async with self.pool.acquire() as conn:
            val = await conn.fetchval("SELECT language FROM users WHERE id=$1", user_id)
            return val or 'ar'

    async def set_user_language(self, user_id: int, language: str):
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE users SET language=$2 WHERE id=$1", user_id, language
            )

    async def get_user_level(self, user_id: int) -> str:
        async with self.pool.acquire() as conn:
            val = await conn.fetchval("SELECT level FROM users WHERE id=$1", user_id)
            return val or 'normal'

    async def get_user_discount(self, user_id: int) -> int:
        level = await self.get_user_level(user_id)
        return {'normal': 0, 'vip': 10, 'pro': 20}.get(level, 0)

    async def check_and_upgrade_vip(self, user_id: int):
        balance = await self.get_balance(user_id)
        if balance >= VIP_BALANCE_THRESHOLD:
            async with self.pool.acquire() as conn:
                current_level = await conn.fetchval(
                    "SELECT level FROM users WHERE id=$1", user_id
                )
                if current_level not in ('vip', 'pro'):
                    await conn.execute(
                        "UPDATE users SET level='vip' WHERE id=$1", user_id
                    )

    async def upgrade_user_level(self, user_id: int) -> str:
        async with self.pool.acquire() as conn:
            purchases = await conn.fetchval(
                "SELECT COUNT(*) FROM transactions WHERE user_id=$1 AND type='purchase'",
                user_id
            )
            total_spent = await conn.fetchval(
                "SELECT COALESCE(SUM(ABS(amount)), 0) FROM transactions "
                "WHERE user_id=$1 AND type='purchase'", user_id
            )
            purchases = purchases or 0
            total_spent = float(total_spent or 0)
            new_level = 'normal'
            if purchases >= 20 or total_spent >= 50:
                new_level = 'pro'
            elif purchases >= 10 or total_spent >= 25:
                new_level = 'vip'
            await conn.execute(
                "UPDATE users SET level=$2 WHERE id=$1", user_id, new_level
            )
            return new_level

    async def check_daily_purchase_limit(self, user_id: int):
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT daily_purchase_count, daily_purchase_date, level
                FROM users WHERE id=$1
            """, user_id)
            if not row:
                return False, 0, 0
            today = datetime.utcnow().date()
            count = row['daily_purchase_count'] or 0
            last_date = row['daily_purchase_date']
            level = row['level'] or 'normal'
            if last_date != today:
                await conn.execute("""
                    UPDATE users SET daily_purchase_count=0, daily_purchase_date=$2
                    WHERE id=$1
                """, user_id, today)
                count = 0
            if level in ('vip', 'pro'):
                limit = DAILY_LIMIT_VIP
            else:
                limit = DAILY_LIMIT_NORMAL
            remaining = limit - count
            return remaining > 0, max(0, remaining), limit

    async def increment_daily_purchase(self, user_id: int):
        async with self.pool.acquire() as conn:
            today = datetime.utcnow().date()
            await conn.execute("""
                UPDATE users 
                SET daily_purchase_count = daily_purchase_count + 1,
                    daily_purchase_date = $2
                WHERE id=$1
            """, user_id, today)

    async def apply_referral(self, referred_id: int, referral_code: str) -> bool:
        async with self.pool.acquire() as conn:
            referrer = await conn.fetchrow(
                "SELECT id FROM users WHERE referral_code=$1", referral_code
            )
            if not referrer:
                return False
            referrer_id = referrer['id']
            if referrer_id == referred_id:
                return False
            already = await conn.fetchval(
                "SELECT id FROM referrals WHERE referred_id=$1", referred_id
            )
            if already:
                return False
            bonus = 1.0
            await conn.execute("""
                INSERT INTO referrals (referrer_id, referred_id, bonus_paid)
                VALUES ($1, $2, TRUE)
            """, referrer_id, referred_id)
            await conn.execute("""
                UPDATE users SET balance = balance + $2,
                    referral_count = referral_count + 1,
                    referral_earnings = referral_earnings + $2
                WHERE id=$1
            """, referrer_id, bonus)
            await conn.execute(
                "UPDATE users SET referred_by=$2 WHERE id=$1", referred_id, referrer_id
            )
            return True

    async def get_referral_stats(self, user_id: int) -> Optional[Dict]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT referral_code, referral_count, referral_earnings
                FROM users WHERE id=$1
            """, user_id)
            if not row:
                return None
            return {
                "code": row['referral_code'],
                "count": row['referral_count'] or 0,
                "earnings": float(row['referral_earnings'] or 0),
            }

    async def claim_daily_bonus(self, user_id: int, amount: float = None) -> bool:
        if amount is None:
            amount = DAILY_BONUS_AMOUNT
        async with self.pool.acquire() as conn:
            last = await conn.fetchval(
                "SELECT daily_bonus_at FROM users WHERE id=$1", user_id
            )
            now = datetime.utcnow()
            if last and (now - last) < timedelta(hours=24):
                return False
            await conn.execute(
                "UPDATE users SET daily_bonus_at=$2, balance = balance + $3 WHERE id=$1",
                user_id, now, amount
            )
            await conn.execute("""
                INSERT INTO transactions (id, user_id, type, amount, description)
                VALUES ($1, $2, 'daily_bonus', $3, 'مكافأة يومية')
            """, generate_transaction_id(), user_id, amount)
            return True

    async def add_to_watchlist(self, user_id: int, pattern: str):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO watchlist (user_id, pattern) VALUES ($1, $2)
            """, user_id, pattern)

    async def get_watchlist(self, user_id: int) -> List[str]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT pattern FROM watchlist WHERE user_id=$1", user_id
            )
            return [r['pattern'] for r in rows]

    async def match_watchlist(self, phone: str) -> List[int]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT DISTINCT user_id FROM watchlist WHERE $1 LIKE pattern || '%'
            """, phone)
            return [r['user_id'] for r in rows]

    async def set_temp(self, user_id: int, key: str, value: str):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO temp_data (user_id, key, value)
                VALUES ($1, $2, $3)
                ON CONFLICT (user_id, key) DO UPDATE SET value = EXCLUDED.value
            """, user_id, key, value)

    async def get_temp(self, user_id: int, key: str) -> Optional[str]:
        async with self.pool.acquire() as conn:
            return await conn.fetchval(
                "SELECT value FROM temp_data WHERE user_id=$1 AND key=$2", user_id, key
            )

    async def clear_temp(self, user_id: int, key: str = None):
        async with self.pool.acquire() as conn:
            if key:
                await conn.execute(
                    "DELETE FROM temp_data WHERE user_id=$1 AND key=$2", user_id, key
                )
            else:
                await conn.execute("DELETE FROM temp_data WHERE user_id=$1", user_id)

    # ============== الأرقام ==============
    async def add_number(self, phone: str, session_enc: str, seller_id: int,
                         country: str, password_2fa_enc: str, price: float) -> bool:
        async with self.pool.acquire() as conn:
            existing = await conn.fetchval("SELECT phone FROM numbers WHERE phone=$1", phone)
            if existing:
                return False
            await conn.execute("""
                INSERT INTO numbers (phone, session_enc, seller_id, country, password_2fa_enc, price)
                VALUES ($1, $2, $3, $4, $5, $6)
            """, phone, session_enc, seller_id, country, password_2fa_enc, price)
            return True

    async def get_number(self, phone: str) -> Optional[Dict]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM numbers WHERE phone=$1", phone)
            return dict(row) if row else None

    async def get_available_numbers(self, limit: int = 100) -> List[Dict]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM numbers WHERE status='available'
                ORDER BY created_at DESC LIMIT $1
            """, limit)
            return [dict(r) for r in rows]

    async def get_all_numbers(self, limit: int = 5000) -> List[Dict]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM numbers ORDER BY created_at DESC LIMIT $1
            """, limit)
            return [dict(r) for r in rows]

    async def search_numbers(self, pattern: str, limit: int = 50) -> List[Dict]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM numbers WHERE status='available' AND phone LIKE $1
                ORDER BY created_at DESC LIMIT $2
            """, f"%{pattern}%", limit)
            return [dict(r) for r in rows]

    async def get_available_countries(self) -> Dict[str, int]:
        cached = await cache.get("available_countries")
        if cached:
            try:
                return json.loads(cached)
            except Exception:
                pass
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT country, COUNT(*) AS cnt FROM numbers
                WHERE status='available' GROUP BY country ORDER BY cnt DESC
            """)
            result = {r['country']: r['cnt'] for r in rows}
        await cache.set("available_countries", json.dumps(result), ttl=30)
        return result

    async def get_numbers_by_country(self, country: str) -> List[Dict]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM numbers WHERE country=$1 AND status='available'
                ORDER BY created_at DESC LIMIT 100
            """, country)
            return [dict(r) for r in rows]

    async def reserve_number(self, phone: str, buyer_id: int, minutes: int = 10) -> bool:
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    "SELECT status FROM numbers WHERE phone=$1 FOR UPDATE", phone
                )
                if not row or row['status'] != 'available':
                    return False
                await conn.execute("""
                    UPDATE numbers
                    SET status='reserved', buyer_id=$2,
                        reserved_until = NOW() + ($3 || ' minutes')::interval
                    WHERE phone=$1
                """, phone, buyer_id, str(minutes))
                return True

    async def mark_sold(self, phone: str, buyer_id: int):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                UPDATE numbers SET status='sold', buyer_id=$2,
                    sold_at=NOW(), reserved_until=NULL WHERE phone=$1
            """, phone, buyer_id)

    async def delete_number(self, phone: str):
        async with self.pool.acquire() as conn:
            await conn.execute("DELETE FROM numbers WHERE phone=$1", phone)

    async def release_expired_reservations(self):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                UPDATE numbers SET status='available', buyer_id=NULL, reserved_until=NULL
                WHERE status='reserved' AND reserved_until < NOW()
            """)

    async def expire_stale_numbers(self, days: int = 30) -> int:
        async with self.pool.acquire() as conn:
            result = await conn.execute("""
                DELETE FROM numbers WHERE status='available'
                AND created_at < NOW() - ($1 || ' days')::interval
            """, str(days))
            try:
                return int(result.split()[-1])
            except Exception:
                return 0

    async def get_number_status_by_seller(self, seller_id: int) -> Dict:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT status, COUNT(*) AS cnt FROM numbers
                WHERE seller_id=$1 GROUP BY status
            """, seller_id)
            return {r['status']: r['cnt'] for r in rows}

    async def atomic_purchase(self, buyer_id: int, seller_id: int,
                              phone: str, price: float) -> bool:
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                num_row = await conn.fetchrow(
                    "SELECT status, buyer_id, seller_id, price "
                    "FROM numbers WHERE phone=$1 FOR UPDATE",
                    phone
                )
                if not num_row:
                    return False
                if num_row['status'] not in ('available', 'reserved'):
                    return False
                if (num_row['status'] == 'reserved'
                        and num_row['buyer_id'] != buyer_id):
                    return False

                buyer_balance = await conn.fetchval(
                    "SELECT balance FROM users WHERE id=$1 FOR UPDATE",
                    buyer_id
                )
                if buyer_balance is None:
                    return False
                if float(buyer_balance) < price:
                    return False

                await conn.execute(
                    "UPDATE users SET balance = balance - $2 WHERE id=$1",
                    buyer_id, price
                )
                await conn.execute(
                    "UPDATE users SET balance = balance + $2 WHERE id=$1",
                    seller_id, price
                )
                await conn.execute("""
                    UPDATE numbers SET status='sold', buyer_id=$2,
                        sold_at=NOW(), reserved_until=NULL
                    WHERE phone=$1
                """, phone, buyer_id)
                await conn.execute("""
                    UPDATE users SET total_purchases = total_purchases + 1
                    WHERE id=$1
                """, buyer_id)
                await conn.execute("""
                    UPDATE users SET total_sales = total_sales + 1
                    WHERE id=$1
                """, seller_id)

                await conn.execute("""
                    INSERT INTO transactions (id, user_id, type, amount, phone, description)
                    VALUES ($1, $2, 'purchase', $3, $4, 'شراء رقم')
                """, generate_transaction_id(), buyer_id, -price, phone)
                await conn.execute("""
                    INSERT INTO transactions (id, user_id, type, amount, phone, description)
                    VALUES ($1, $2, 'sale_income', $3, $4, 'بيع رقم')
                """, generate_transaction_id(), seller_id, price, phone)

                return True

    async def save_completed_purchase(self, phone: str, buyer_id: int,
                                       seller_id: int, price: float):
        try:
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO completed_purchases
                        (phone, buyer_id, seller_id, price, rated)
                    VALUES ($1, $2, $3, $4, FALSE)
                    ON CONFLICT (phone, buyer_id) DO NOTHING
                """, phone, buyer_id, seller_id, price)
        except Exception as e:
            logger.debug(f"save_completed_purchase: {e}")

    async def get_completed_purchase(self, phone: str, buyer_id: int) -> Optional[Dict]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT * FROM completed_purchases
                WHERE phone=$1 AND buyer_id=$2
            """, phone, buyer_id)
            return dict(row) if row else None

    async def mark_purchase_rated(self, phone: str, buyer_id: int):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                UPDATE completed_purchases SET rated=TRUE
                WHERE phone=$1 AND buyer_id=$2
            """, phone, buyer_id)

    async def get_seller_analytics(self, seller_id: int) -> Dict:
        async with self.pool.acquire() as conn:
            total_listed = await conn.fetchval("""
                SELECT COUNT(*) FROM transactions
                WHERE user_id=$1 AND type='sale_listing'
            """, seller_id)
            total_sold = await conn.fetchval("""
                SELECT COUNT(*) FROM transactions
                WHERE user_id=$1 AND type='sale_income'
            """, seller_id)
            cancel_rate = 0.0
            if total_listed and total_listed > 0:
                cancel_rate = max(0.0, (total_listed - total_sold) / total_listed * 100)
            avg_sell_time = await conn.fetchval("""
                SELECT AVG(EXTRACT(EPOCH FROM (t2.created_at - t1.created_at)))
                FROM transactions t1
                JOIN transactions t2 ON t1.phone = t2.phone
                WHERE t1.user_id=$1 AND t1.type='sale_listing'
                  AND t2.type='sale_income'
            """, seller_id)
            complaints = await conn.fetchval("""
                SELECT COUNT(*) FROM reviews
                WHERE target_id=$1 AND rating <= 2
            """, seller_id)
            avg_rating = await conn.fetchval("""
                SELECT COALESCE(AVG(rating), 5.0) FROM reviews WHERE target_id=$1
            """, seller_id)
            return {
                "total_listed": total_listed or 0,
                "total_sold": total_sold or 0,
                "cancel_rate": round(cancel_rate, 2),
                "avg_sell_time_minutes": round((avg_sell_time or 0) / 60, 1),
                "complaints": complaints or 0,
                "avg_rating": round(float(avg_rating or 5.0), 2),
            }

    # ============== النسخ الاحتياطي ==============
    async def export_numbers_backup(self) -> List[Dict]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT phone, session_enc, seller_id, country,
                       password_2fa_enc, price, status
                FROM numbers
            """)
            return [dict(r) for r in rows]

    async def export_sessions_backup(self) -> List[Dict]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT phone, session_enc, password_2fa_enc, country
                FROM numbers WHERE status='available'
            """)
            return [dict(r) for r in rows]

    async def export_users_txt(self) -> List[Dict]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT id, username, first_name, balance, rating,
                       total_sales, total_purchases, is_banned,
                       level, referral_code, referral_count,
                       referral_earnings, created_at
                FROM users ORDER BY created_at DESC
            """)
            return [dict(r) for r in rows]

    async def import_numbers_backup(self, data: List[Dict]) -> int:
        imported = 0
        async with self.pool.acquire() as conn:
            for item in data:
                try:
                    phone = item.get("phone")
                    if not phone:
                        continue
                    existing = await conn.fetchval(
                        "SELECT phone FROM numbers WHERE phone=$1", phone
                    )
                    if existing:
                        await conn.execute("""
                            UPDATE numbers SET session_enc=$2, country=$3,
                                password_2fa_enc=$4, price=$5, status='available'
                            WHERE phone=$1
                        """, phone, item.get("session_enc", ""),
                            item.get("country", "غير محدد"),
                            item.get("password_2fa_enc", ""),
                            float(item.get("price", 5)))
                    else:
                        await conn.execute("""
                            INSERT INTO numbers
                                (phone, session_enc, seller_id, country,
                                 password_2fa_enc, price, status)
                            VALUES ($1, $2, $3, $4, $5, $6, 'available')
                        """, phone, item.get("session_enc", ""),
                            int(item.get("seller_id", 0)),
                            item.get("country", "غير محدد"),
                            item.get("password_2fa_enc", ""),
                            float(item.get("price", 5)))
                    imported += 1
                except Exception as e:
                    logger.error(f"import number {item.get('phone')}: {e}")
        return imported

    async def import_sessions_backup(self, data: List[Dict]) -> int:
        imported = 0
        async with self.pool.acquire() as conn:
            for item in data:
                try:
                    phone = item.get("phone")
                    if not phone:
                        continue
                    existing = await conn.fetchval(
                        "SELECT phone FROM numbers WHERE phone=$1", phone
                    )
                    if existing:
                        await conn.execute("""
                            UPDATE numbers SET session_enc=$2, password_2fa_enc=$3
                            WHERE phone=$1
                        """, phone, item.get("session_enc", ""),
                            item.get("password_2fa_enc", ""))
                        imported += 1
                except Exception as e:
                    logger.error(f"import session {item.get('phone')}: {e}")
        return imported

    # ============== المعاملات ==============
    async def add_transaction(self, tx_id: str, user_id: int, tx_type: str,
                              amount: float, phone: str = None, description: str = None):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO transactions (id, user_id, type, amount, phone, description)
                VALUES ($1, $2, $3, $4, $5, $6)
            """, tx_id, user_id, tx_type, amount, phone, description)

    async def get_user_transactions(self, user_id: int, limit: int = 20,
                                    offset: int = 0) -> List[Dict]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM transactions WHERE user_id=$1
                ORDER BY created_at DESC LIMIT $2 OFFSET $3
            """, user_id, limit, offset)
            return [dict(r) for r in rows]

    async def get_all_transactions(self, limit: int = 100) -> List[Dict]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM transactions ORDER BY created_at DESC LIMIT $1
            """, limit)
            return [dict(r) for r in rows]

    async def add_review(self, reviewer_id: int, target_id: int,
                         phone: str, rating: int, comment: str = None):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO reviews (reviewer_id, target_id, phone, rating, comment)
                VALUES ($1, $2, $3, $4, $5)
            """, reviewer_id, target_id, phone, rating, comment)
        await self.update_rating(target_id)

    async def add_coupon(self, code: str, discount: int, max_uses: int = 100):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO coupons (code, discount_percent, max_uses)
                VALUES ($1, $2, $3)
                ON CONFLICT (code) DO UPDATE SET discount_percent=$2, max_uses=$3
            """, code, discount, max_uses)

    async def use_coupon(self, code: str, user_id: int) -> Optional[int]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT * FROM coupons WHERE code=$1 AND used_count < max_uses
                  AND (expires_at IS NULL OR expires_at > NOW())
            """, code)
            if not row:
                return None
            used = await conn.fetchval(
                "SELECT 1 FROM coupon_uses WHERE code=$1 AND user_id=$2", code, user_id
            )
            if used:
                return None
            await conn.execute(
                "UPDATE coupons SET used_count = used_count + 1 WHERE code=$1", code
            )
            await conn.execute(
                "INSERT INTO coupon_uses (code, user_id) VALUES ($1, $2)", code, user_id
            )
            return row['discount_percent']

    async def add_pending_request(self, user_id: int, country: str,
                                  max_price: float, prefix: str = None):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO pending_requests (user_id, country, max_price, prefix)
                VALUES ($1, $2, $3, $4)
            """, user_id, country, max_price, prefix)

    async def get_matching_requests(self, country: str, price: float, phone: str) -> List[int]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT user_id FROM pending_requests
                WHERE fulfilled=FALSE
                  AND (country IS NULL OR country=$1)
                  AND (max_price IS NULL OR max_price >= $2)
                  AND (prefix IS NULL OR $3 LIKE prefix || '%')
            """, country, price, phone)
            return [r['user_id'] for r in rows]

    async def fulfill_request(self, user_id: int):
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE pending_requests SET fulfilled=TRUE WHERE user_id=$1", user_id
            )

    async def add_deposit(self, user_id: int, method: str, amount: float,
                          proof: str = None) -> int:
        async with self.pool.acquire() as conn:
            return await conn.fetchval("""
                INSERT INTO deposits (user_id, method, amount, proof)
                VALUES ($1, $2, $3, $4) RETURNING id
            """, user_id, method, amount, proof)

    async def approve_deposit(self, deposit_id: int) -> Optional[Dict]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM deposits WHERE id=$1 AND status='pending'", deposit_id
            )
            if not row:
                return None
            await conn.execute(
                "UPDATE deposits SET status='approved' WHERE id=$1", deposit_id
            )
            await conn.execute(
                "UPDATE users SET balance = balance + $2 WHERE id=$1",
                row['user_id'], row['amount']
            )
            await conn.execute("""
                INSERT INTO transactions (id, user_id, type, amount, description)
                VALUES ($1, $2, 'deposit', $3, $4)
            """, generate_transaction_id(), row['user_id'], row['amount'],
                f"إيداع عبر {row['method']}")
            return dict(row)

    async def create_ticket(self, user_id: int, subject: str) -> int:
        async with self.pool.acquire() as conn:
            return await conn.fetchval("""
                INSERT INTO tickets (user_id, subject) VALUES ($1, $2) RETURNING id
            """, user_id, subject)

    async def add_ticket_message(self, ticket_id: int, sender_id: int, message: str):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO ticket_messages (ticket_id, sender_id, message)
                VALUES ($1, $2, $3)
            """, ticket_id, sender_id, message)

    async def get_ticket(self, ticket_id: int) -> Optional[Dict]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM tickets WHERE id=$1", ticket_id)
            return dict(row) if row else None

    async def close_ticket(self, ticket_id: int):
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE tickets SET status='closed' WHERE id=$1", ticket_id
            )

    async def get_stats(self) -> Dict:
        async with self.pool.acquire() as conn:
            users = await conn.fetchval("SELECT COUNT(*) FROM users")
            numbers_avail = await conn.fetchval(
                "SELECT COUNT(*) FROM numbers WHERE status='available'"
            )
            numbers_sold = await conn.fetchval(
                "SELECT COUNT(*) FROM numbers WHERE status='sold'"
            )
            total_revenue = await conn.fetchval(
                "SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE type='purchase'"
            )
            return {
                "users": users,
                "available": numbers_avail,
                "sold": numbers_sold,
                "revenue": float(total_revenue or 0),
            }

    async def get_daily_stats(self) -> Dict:
        async with self.pool.acquire() as conn:
            today = datetime.utcnow().date()
            new_users = await conn.fetchval(
                "SELECT COUNT(*) FROM users WHERE DATE(created_at)=$1", today
            )
            sold = await conn.fetchval(
                "SELECT COUNT(*) FROM numbers WHERE status='sold' AND DATE(sold_at)=$1",
                today
            )
            revenue = await conn.fetchval("""
                SELECT COALESCE(SUM(ABS(amount)), 0) FROM transactions
                WHERE type='purchase' AND DATE(created_at)=$1
            """, today)
            return {
                "new_users": new_users or 0,
                "sold": sold or 0,
                "revenue": float(revenue or 0),
            }

    async def get_top_sellers(self, limit: int = 10) -> List[Dict]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT id, first_name, username, total_sales, rating
                FROM users WHERE total_sales > 0
                ORDER BY total_sales DESC LIMIT $1
            """, limit)
            return [dict(r) for r in rows]

    async def get_top_countries(self, limit: int = 10) -> List[Dict]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT country, COUNT(*) AS cnt FROM numbers
                WHERE status='sold' GROUP BY country
                ORDER BY cnt DESC LIMIT $1
            """, limit)
            return [dict(r) for r in rows]

    # ============== قنوات الاشتراك ==============
    async def add_required_channel(self, channel_username: str, title: str = None,
                                   added_by: int = None) -> bool:
        channel_username = channel_username.strip()
        if not channel_username.startswith("@"):
            channel_username = "@" + channel_username.lstrip("@")
        async with self.pool.acquire() as conn:
            existing = await conn.fetchval(
                "SELECT id FROM required_channels WHERE channel_username=$1",
                channel_username
            )
            if existing:
                return False
            await conn.execute("""
                INSERT INTO required_channels (channel_username, channel_title, added_by)
                VALUES ($1, $2, $3)
            """, channel_username, title, added_by)
            return True

    async def remove_required_channel(self, channel_username: str) -> bool:
        channel_username = channel_username.strip()
        if not channel_username.startswith("@"):
            channel_username = "@" + channel_username.lstrip("@")
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM required_channels WHERE channel_username=$1",
                channel_username
            )
            return "DELETE 1" in result

    async def clear_required_channels(self):
        async with self.pool.acquire() as conn:
            await conn.execute("DELETE FROM required_channels")

    async def get_required_channels(self) -> List[Dict]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM required_channels ORDER BY id")
            return [dict(r) for r in rows]

    async def get_channel_info(self, channel_username: str) -> Optional[Dict]:
        channel_username = channel_username.strip()
        if not channel_username.startswith("@"):
            channel_username = "@" + channel_username.lstrip("@")
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM required_channels WHERE channel_username=$1",
                channel_username
            )
            return dict(row) if row else None

    async def get_user_channel_subs(self, user_id: int) -> List[str]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT channel_username FROM user_channel_subs
                WHERE user_id=$1 AND is_member=TRUE
            """, user_id)
            return [r['channel_username'] for r in rows]

    async def record_channel_join(self, user_id: int, channel_username: str) -> bool:
        async with self.pool.acquire() as conn:
            existing = await conn.fetchrow("""
                SELECT id, is_member, reward_paid FROM user_channel_subs
                WHERE user_id=$1 AND channel_username=$2
            """, user_id, channel_username)

            if existing:
                if not existing['is_member']:
                    await conn.execute("""
                        UPDATE user_channel_subs
                        SET is_member=TRUE, joined_at=NOW(), left_at=NULL
                        WHERE id=$1
                    """, existing['id'])
                    if not existing['reward_paid']:
                        await conn.execute("""
                            UPDATE user_channel_subs SET reward_paid=TRUE WHERE id=$1
                        """, existing['id'])
                        await conn.execute(
                            "UPDATE users SET balance = balance + $2 WHERE id=$1",
                            user_id, CHANNEL_JOIN_REWARD
                        )
                        await conn.execute("""
                            INSERT INTO transactions (id, user_id, type, amount, description)
                            VALUES ($1, $2, 'channel_join', $3, $4)
                        """, generate_transaction_id(), user_id, CHANNEL_JOIN_REWARD,
                            f"مكافأة اشتراك في {channel_username}")
                        return True
                    return False
                return False

            await conn.execute("""
                INSERT INTO user_channel_subs (user_id, channel_username, reward_paid)
                VALUES ($1, $2, TRUE)
            """, user_id, channel_username)

            await conn.execute(
                "UPDATE users SET balance = balance + $2 WHERE id=$1",
                user_id, CHANNEL_JOIN_REWARD
            )
            await conn.execute("""
                INSERT INTO transactions (id, user_id, type, amount, description)
                VALUES ($1, $2, 'channel_join', $3, $4)
            """, generate_transaction_id(), user_id, CHANNEL_JOIN_REWARD,
                f"مكافأة اشتراك في {channel_username}")
            return True

    async def record_channel_leave(self, user_id: int, channel_username: str) -> bool:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT id, is_member FROM user_channel_subs
                WHERE user_id=$1 AND channel_username=$2
            """, user_id, channel_username)
            if not row or not row['is_member']:
                return False
            await conn.execute("""
                UPDATE user_channel_subs SET is_member=FALSE, left_at=NOW()
                WHERE id=$1
            """, row['id'])
            await conn.execute(
                "UPDATE users SET balance = balance - $2 WHERE id=$1",
                user_id, CHANNEL_LEAVE_PENALTY
            )
            await conn.execute("""
                INSERT INTO transactions (id, user_id, type, amount, description)
                VALUES ($1, $2, 'channel_leave', $3, $4)
            """, generate_transaction_id(), user_id, -CHANNEL_LEAVE_PENALTY,
                f"خصم مغادرة {channel_username}")
            return True

    # ============== أكواد التحقق ==============
    async def save_code(self, phone: str, buyer_id: int, code: str):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO saved_codes (phone, buyer_id, code)
                VALUES ($1, $2, $3)
            """, phone, buyer_id, code)

    async def get_last_code(self, phone: str, buyer_id: int) -> Optional[str]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT code FROM saved_codes
                WHERE phone=$1 AND buyer_id=$2
                ORDER BY created_at DESC LIMIT 1
            """, phone, buyer_id)
            return row['code'] if row else None

    async def save_phone_code_hash(self, phone: str, buyer_id: int, phone_code_hash: str):
        try:
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO otp_tracking (phone, buyer_id, phone_code_hash, updated_at)
                    VALUES ($1, $2, $3, NOW())
                    ON CONFLICT (phone, buyer_id) DO UPDATE SET
                        phone_code_hash = EXCLUDED.phone_code_hash,
                        updated_at = NOW()
                """, phone, buyer_id, phone_code_hash)
            return True
        except Exception as e:
            logger.error(f"save_phone_code_hash: {e}")
            return False

    async def get_phone_code_hash(self, phone: str, buyer_id: int) -> Optional[str]:
        try:
            async with self.pool.acquire() as conn:
                return await conn.fetchval("""
                    SELECT phone_code_hash FROM otp_tracking
                    WHERE phone=$1 AND buyer_id=$2
                """, phone, buyer_id)
        except Exception as e:
            logger.debug(f"get_phone_code_hash: {e}")
            return None

    async def save_otp_code(self, phone: str, buyer_id: int, code: str):
        try:
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO otp_tracking (phone, buyer_id, last_code, updated_at)
                    VALUES ($1, $2, $3, NOW())
                    ON CONFLICT (phone, buyer_id) DO UPDATE SET
                        last_code = EXCLUDED.last_code,
                        updated_at = NOW()
                """, phone, buyer_id, code)
            return True
        except Exception as e:
            logger.error(f"save_otp_code: {e}")
            return False

    async def get_latest_otp_code(self, phone: str, buyer_id: int,
                                   max_age_seconds: int = 300) -> Optional[str]:
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow("""
                    SELECT last_code, updated_at FROM otp_tracking
                    WHERE phone=$1 AND buyer_id=$2
                """, phone, buyer_id)
                if not row or not row['last_code']:
                    return None
                age = (datetime.utcnow() - row['updated_at'].replace(tzinfo=None)).total_seconds()
                if age > max_age_seconds:
                    return None
                return row['last_code']
        except Exception as e:
            logger.debug(f"get_latest_otp_code: {e}")
            return None

    async def clear_otp_tracking(self, phone: str, buyer_id: int):
        try:
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    DELETE FROM otp_tracking
                    WHERE phone=$1 AND buyer_id=$2
                """, phone, buyer_id)
        except Exception as e:
            logger.debug(f"clear_otp_tracking: {e}")

    # ============== 🧊 الأرقام المجمدة ==============
    async def freeze_number(self, phone: str, frozen_by: int,
                            reason: str = "") -> bool:
        async with self.pool.acquire() as conn:
            existing = await conn.fetchval(
                "SELECT phone FROM numbers WHERE phone=$1", phone
            )
            if not existing:
                return False
            await conn.execute("""
                INSERT INTO frozen_numbers (phone, frozen_by, reason)
                VALUES ($1, $2, $3)
                ON CONFLICT (phone) DO UPDATE SET
                    frozen_by = EXCLUDED.frozen_by,
                    reason = EXCLUDED.reason,
                    frozen_at = NOW()
            """, phone, frozen_by, reason)
            await conn.execute(
                "UPDATE numbers SET status='frozen' WHERE phone=$1", phone
            )
            return True

    async def unfreeze_number(self, phone: str) -> bool:
        async with self.pool.acquire() as conn:
            existing = await conn.fetchval(
                "SELECT phone FROM frozen_numbers WHERE phone=$1", phone
            )
            if not existing:
                return False
            await conn.execute(
                "DELETE FROM frozen_numbers WHERE phone=$1", phone
            )
            await conn.execute("""
                UPDATE numbers SET status='available'
                WHERE phone=$1 AND status='frozen'
            """, phone)
            return True

    async def is_number_frozen(self, phone: str) -> bool:
        async with self.pool.acquire() as conn:
            val = await conn.fetchval(
                "SELECT phone FROM frozen_numbers WHERE phone=$1", phone
            )
            return bool(val)

    async def get_frozen_numbers(self, limit: int = 100) -> List[Dict]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT f.phone, f.frozen_by, f.reason, f.frozen_at,
                       n.country, n.price, n.seller_id
                FROM frozen_numbers f
                LEFT JOIN numbers n ON n.phone = f.phone
                ORDER BY f.frozen_at DESC LIMIT $1
            """, limit)
            return [dict(r) for r in rows]

    # ============== 💬 التواصل (user-level القديم) ==============
    async def enable_communication(self, user_id: int) -> bool:
        async with self.pool.acquire() as conn:
            existing = await conn.fetchval(
                "SELECT user_id FROM communication_settings WHERE user_id=$1",
                user_id
            )
            if existing:
                await conn.execute("""
                    UPDATE communication_settings
                    SET enabled=TRUE, updated_at=NOW()
                    WHERE user_id=$1
                """, user_id)
                return False
            await conn.execute("""
                INSERT INTO communication_settings (user_id, enabled)
                VALUES ($1, TRUE)
            """, user_id)
            return True

    async def disable_communication(self, user_id: int) -> bool:
        async with self.pool.acquire() as conn:
            existing = await conn.fetchval(
                "SELECT user_id FROM communication_settings WHERE user_id=$1",
                user_id
            )
            if not existing:
                return False
            await conn.execute(
                "DELETE FROM communication_settings WHERE user_id=$1", user_id
            )
            return True

    async def is_communication_enabled(self, user_id: int) -> bool:
        async with self.pool.acquire() as conn:
            val = await conn.fetchval(
                "SELECT enabled FROM communication_settings WHERE user_id=$1",
                user_id
            )
            return bool(val) if val is not None else False

    async def get_communication_users(self) -> List[int]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT user_id FROM communication_settings
                WHERE enabled=TRUE
            """)
            return [r['user_id'] for r in rows]

    # ============== 🗑️ تفريغ التخزين ==============
    async def clear_all_storage(self, keep_owner_id: int) -> Dict:
        result = {
            "numbers_deleted": 0,
            "transactions_deleted": 0,
            "reviews_deleted": 0,
            "deposits_deleted": 0,
            "tickets_deleted": 0,
            "saved_codes_deleted": 0,
            "otp_deleted": 0,
            "frozen_deleted": 0,
            "users_balances_reset": 0,
            "gifts_deleted": 0,
        }
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                r = await conn.execute("DELETE FROM numbers")
                result["numbers_deleted"] = _count_deleted(r)

                r = await conn.execute("DELETE FROM transactions")
                result["transactions_deleted"] = _count_deleted(r)

                r = await conn.execute("DELETE FROM reviews")
                result["reviews_deleted"] = _count_deleted(r)

                r = await conn.execute("DELETE FROM deposits")
                result["deposits_deleted"] = _count_deleted(r)

                await conn.execute("DELETE FROM ticket_messages")
                r = await conn.execute("DELETE FROM tickets")
                result["tickets_deleted"] = _count_deleted(r)

                r = await conn.execute("DELETE FROM saved_codes")
                result["saved_codes_deleted"] = _count_deleted(r)

                r = await conn.execute("DELETE FROM otp_tracking")
                result["otp_deleted"] = _count_deleted(r)

                r = await conn.execute("DELETE FROM frozen_numbers")
                result["frozen_deleted"] = _count_deleted(r)

                r = await conn.execute("DELETE FROM gifts")
                result["gifts_deleted"] = _count_deleted(r)

                r = await conn.execute("""
                    UPDATE users SET
                        balance = 0,
                        total_sales = 0,
                        total_purchases = 0,
                        referral_count = 0,
                        referral_earnings = 0,
                        daily_purchase_count = 0
                    WHERE id != $1
                """, keep_owner_id)
                result["users_balances_reset"] = _count_updated(r)

                await conn.execute("DELETE FROM completed_purchases")
                await conn.execute("DELETE FROM referrals")
                await conn.execute("DELETE FROM watchlist")
                await conn.execute("DELETE FROM pending_requests")
                await conn.execute("DELETE FROM temp_data")
                await conn.execute("DELETE FROM coupon_uses")
                await conn.execute("DELETE FROM user_channel_subs")
                await conn.execute("DELETE FROM communication_settings")

        return result

    async def reset_all_balances(self, keep_owner_id: int) -> int:
        async with self.pool.acquire() as conn:
            result = await conn.execute("""
                UPDATE users SET balance = 0
                WHERE id != $1
            """, keep_owner_id)
            return _count_updated(result)

    # ============== 🎁 الهدايا ==============
    async def send_gift(self, sender_id: int, receiver_id: int,
                        amount: float, message: str = "") -> bool:
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                receiver = await conn.fetchrow(
                    "SELECT id, first_name, username FROM users WHERE id=$1",
                    receiver_id
                )
                if not receiver:
                    return False

                await conn.execute(
                    "UPDATE users SET balance = balance + $2 WHERE id=$1",
                    receiver_id, amount
                )

                await conn.execute("""
                    INSERT INTO transactions (id, user_id, type, amount, description)
                    VALUES ($1, $2, 'gift_received', $3, $4)
                """, generate_transaction_id(), receiver_id, amount,
                    message or f"هدية بقيمة ${amount:.2f}")

                await conn.execute("""
                    INSERT INTO gifts (sender_id, receiver_id, amount, message)
                    VALUES ($1, $2, $3, $4)
                """, sender_id, receiver_id, amount, message)

                return True

    async def get_gift_history(self, limit: int = 50) -> List[Dict]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT g.*, 
                       u1.first_name as sender_name,
                       u2.first_name as receiver_name
                FROM gifts g
                LEFT JOIN users u1 ON u1.id = g.sender_id
                LEFT JOIN users u2 ON u2.id = g.receiver_id
                ORDER BY g.created_at DESC LIMIT $1
            """, limit)
            return [dict(r) for r in rows]


def format_balance(amount: float) -> str:
    return f"${amount:.2f}"


def format_datetime(dt) -> str:
    if not dt:
        return "غير محدد"
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt)
        except Exception:
            return dt[:16]
    return dt.strftime("%Y-%m-%d %H:%M")


def stars(rating: float) -> str:
    full = int(rating)
    half = 1 if (rating - full) >= 0.5 else 0
    return "⭐" * full + ("✨" if half else "") + f" ({rating:.1f})"


async def safe_send(client, chat_id, text, **kwargs):
    import asyncio
    from pyrogram.errors import FloodWait
    try:
        return await client.send_message(chat_id, text, **kwargs)
    except FloodWait as e:
        await asyncio.sleep(e.value)
        return await client.send_message(chat_id, text, **kwargs)


async def safe_edit(message, text, **kwargs):
    import asyncio
    from pyrogram.errors import FloodWait, MessageNotModified
    try:
        return await message.edit_text(text, **kwargs)
    except MessageNotModified:
        return message
    except FloodWait as e:
        await asyncio.sleep(e.value)
        return await message.edit_text(text, **kwargs)


db = Database()