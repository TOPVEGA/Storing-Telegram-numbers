#لوجيك | Logic وجهتك البرمجية الأولى  بالوطن العربي
#شروحات - أكواد - وأحدث تقنيات برمجية - وحلول تقنية
#بواسطه: t.me/Logii3

#الترخيص: @TopVeGa
#العلامة التجارية: VEGA & Logic
#حقوق الطبع والنشر: © 2015 - 2025
import os
import base64
import hashlib
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "8")
API_ID = int(os.getenv("API_ID", "36524609"))
API_HASH = os.getenv("API_HASH", "540e9a496782be063cc779d7fd9c6355")
OWNER_ID = int(os.getenv("OWNER_ID", "8368077406"))
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    ""
)
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")
#قناه اللي يرسل فيها البوت الرسيل عند شراء او البيع
CHANNEL_BOT = os.getenv("CHANNEL_BOT", "python2015")
BOT_NAME = os.getenv("BOT_NAME", "SIMBot")
WEB_PORT = int(os.getenv("WEB_PORT", "8080"))
# الاسم اللي هيتحط على الحساب الجديد الي البوت خده 
NUMBER_NAME = os.getenv("BOT_DISPLAY_NAME", "SIMBOT")
NUMBER_BIO = os.getenv("NUMBER_BIO", "🤖 بوت بيع أرقام | أرخص الأسعار")
NUMBER_PHOTO_PATH = os.getenv("NUMBER_PHOTO_PATH", "photo.jpg")
# رابط البوت (اللي هيظهر في الأزرار)
BOT_USERNAME = os.getenv("BOT_USERNAME", "https://t.me/GenStrngBot")
# قنوات الإشتراك و الانضمام
GROUPS_TO_JOIN = [
    "vegaone",
    "CyberCodeing",
    "BetagramNinja",
    "Cybervega",
    "Python2015",
]

if not ENCRYPTION_KEY and BOT_TOKEN:
    ENCRYPTION_KEY = base64.urlsafe_b64encode(
        hashlib.sha256(BOT_TOKEN.encode()).digest()
    ).decode()

REDIS_URL = os.getenv("REDIS_URL")
WEB_SECRET_KEY = os.getenv("WEB_SECRET_KEY", "change-me-in-production")
WEB_ADMIN_USER = os.getenv("WEB_ADMIN_USER", "admin")
WEB_ADMIN_PASSWORD = os.getenv("WEB_ADMIN_PASSWORD", "admin123")

# ✅ توحيد كلمة مرور 2FA
FIXED_2FA_PASSWORD = "VEGA"

# ✅ إعدادات عامة
MIN_BALANCE_TO_BUY = 10.0
DAILY_LIMIT_NORMAL = 1
DAILY_LIMIT_VIP = 10
VIP_BALANCE_THRESHOLD = 100.0

# ✅ توحيد مبلغ المكافأة اليومية
DAILY_BONUS_AMOUNT = 1.0

# ✅ توحيد مكافأة الإحالة
REFERRAL_BONUS_AMOUNT = 1.0

# ✅ توحيد مكافأة/عقوبة القنوات
CHANNEL_JOIN_REWARD = 1.0
CHANNEL_LEAVE_PENALTY = 2.0

EXPENSIVE_NUMBER_THRESHOLD = 50.0




try:
    from zoneinfo import ZoneInfo
    from datetime import datetime
    EGYPT_TZ = ZoneInfo("Africa/Cairo")
except Exception:
    EGYPT_TZ = None

_MISSING = [
    name for name, val in {
        "BOT_TOKEN": BOT_TOKEN,
        "API_ID": API_ID,
        "API_HASH": API_HASH,
        "DATABASE_URL": DATABASE_URL,
        "ENCRYPTION_KEY": ENCRYPTION_KEY,
    }.items() if val in (None, "", 0)
]

if _MISSING:
    raise RuntimeError(f"❌ متغيرات ناقصة في .env: {', '.join(_MISSING)}")