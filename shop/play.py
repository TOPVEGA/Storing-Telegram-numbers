#لوجيك | Logic وجهتك البرمجية الأولى  بالوطن العربي
#شروحات - أكواد - وأحدث تقنيات برمجية - وحلول تقنية
#بواسطه: t.me/Logii3

#الترخيص: @TopVeGa
#العلامة التجارية: VEGA & Logic
#حقوق الطبع والنشر: © 2015 - 2025

import asyncio
import re
import secrets
import logging
from datetime import datetime, timedelta

from pyrogram import Client, filters
from pyrogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, Message,
    ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton
)
from pyrogram.enums import ParseMode
from pyrogram.handlers import MessageHandler
from pyrogram.errors import (
    SessionPasswordNeeded, PhoneCodeInvalid, PhoneCodeExpired,
    PasswordHashInvalid, AuthKeyUnregistered, UserDeactivated,
    SessionRevoked, FloodWait,
)
from pyrogram.raw.functions.account import GetAuthorizations

from config import (
    API_ID, API_HASH, CHANNEL_BOT, FIXED_2FA_PASSWORD,
    EXPENSIVE_NUMBER_THRESHOLD, OWNER_ID
)
from Database import (
    db, encrypt, decrypt, generate_2fa_password,
    generate_transaction_id, safe_send, safe_edit, format_datetime
)

logger = logging.getLogger(__name__)

temp_clients = {}
waiting_for = {}
buy_sessions = {}
active_code_watchers = {}
buy_locks = set()

TELEGRAM_SERVICE_IDS = [777000, 42777, 333000]

SESSION_FETCH_TIMEOUT = 15
MAX_SESSION_FETCH_RETRIES = 3


def main_reply_keyboard(is_owner: bool = False) -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton("🛒 شراء رقم"), KeyboardButton("💰 بيع رقم")],
        [KeyboardButton("👛 محفظتي"), KeyboardButton("📊 إحصائياتي")],
        [KeyboardButton("🔔 طلب مخصص"), KeyboardButton("🔍 بحث")],
        [KeyboardButton("👥 الإحالة"), KeyboardButton("👁️ مراقبة")],
        [KeyboardButton("🎁 مكافأة يومية"), KeyboardButton("🎫 الدعم")],
        [KeyboardButton("📜 سجل معاملاتي"), KeyboardButton("💳 إيداع")],
        [KeyboardButton("📢 قنوات الاشتراك")],
        [KeyboardButton("❌ إلغاء العملية"),
         KeyboardButton("❌ إخفاء الكيبورد")],
    ]
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)


def dev_reply_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([
        [KeyboardButton("👑 الرئيسية"), KeyboardButton("📊 إحصائيات البوت")],
        [KeyboardButton("👤 تفاصيل مستخدم"), KeyboardButton("🎁 إرسال هدية")],
        [KeyboardButton("💰 إضافة رصيد"), KeyboardButton("💸 خصم رصيد")],
        [KeyboardButton("💵 تصفير رصيد"), KeyboardButton("💵 تصفير كل الأرصدة")],
        [KeyboardButton("🚫 حظر"), KeyboardButton("✅ إلغاء حظر")],
        [KeyboardButton("📋 المحظورين"), KeyboardButton("🗑️ مسح المحظورين")],
        [KeyboardButton("👤 رفع ادمن"), KeyboardButton("🗑️ تنزيل ادمن")],
        [KeyboardButton("📋 الادمنية"), KeyboardButton("👑 صلاحياتي")],
        [KeyboardButton("🧊 تجميد رقم"), KeyboardButton("🔥 فك تجميد")],
        [KeyboardButton("📋 الأرقام المجمدة"), KeyboardButton("🗑️ تفريغ التخزين")],
        [KeyboardButton("💬 تفعيل التواصل"), KeyboardButton("🔇 تعطيل التواصل")],
        [KeyboardButton("➕ إضافة قناة"), KeyboardButton("🗑️ حذف قناة")],
        [KeyboardButton("🧹 مسح القنوات"), KeyboardButton("📋 قنوات الاشتراك")],
        [KeyboardButton("📊 تقرير اليوم"), KeyboardButton("📈 تقرير عام")],
        [KeyboardButton("🏆 أفضل البائعين"), KeyboardButton("🌍 أكثر الدول")],
        [KeyboardButton("📢 اذاعه"), KeyboardButton("📢 اذاعه بالتوجيه")],
        [KeyboardButton("📢 اذاعه بالتثبيت"), KeyboardButton("🎟️ كوبون")],
        [KeyboardButton("📱 اذاعه للارقام")],
        [KeyboardButton("💾 نسخ الأرقام"), KeyboardButton("📥 استيراد الأرقام")],
        [KeyboardButton("👥 نسخ المستخدمين"), KeyboardButton("📊 نسخ المعاملات")],
        [KeyboardButton("🏠 الرئيسية"), KeyboardButton("❌ إخفاء الكيبورد")],
    ], resize_keyboard=True)


def cancel_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[KeyboardButton("❌ إلغاء العملية")]],
        resize_keyboard=True
    )


async def _verify_2fa(client_obj: Client, password: str) -> bool:
    if not password or not password.strip():
        return False
    try:
        await asyncio.sleep(0.5)
        await client_obj.check_password(password)
        return True
    except PasswordHashInvalid:
        return False
    except SessionPasswordNeeded:
        return False
    except Exception as e:
        err = str(e).lower()
        if "password" in err and ("not" in err or "no" in err or "none" in err):
            return False
        if "invalid" in err or "hash" in err:
            return False
        logger.debug(f"_verify_2fa: {e}")
        return False


async def _is_account_2fa_protected(client_obj: Client) -> bool:
    try:
        await client_obj.check_password("__dummy_wrong_xyz_123__")
        return False
    except PasswordHashInvalid:
        return True
    except Exception as e:
        err = str(e).lower()
        if "invalid" in err or "hash" in err:
            return True
        if "not" in err or "no password" in err or "none" in err:
            return False
        logger.debug(f"_is_account_2fa_protected: {e}")
        return False


async def change_2fa_password(client_obj: Client, current_password: str = None,
                              new_password: str = None) -> tuple:
    if not new_password:
        new_password = generate_2fa_password()

    try:
        if current_password:
            try:
                await client_obj.change_cloud_password(
                    current_password=current_password,
                    new_password=new_password,
                    new_hint=""
                )
                await asyncio.sleep(1)
                ok = await _verify_2fa(client_obj, new_password)
                if ok:
                    return True, "✅ تم تغيير كلمة المرور", new_password
                return False, "⚠️ فشل التحقق", current_password
            except Exception as e:
                err = str(e).lower()
                if any(k in err for k in ("password", "hash", "invalid")):
                    try:
                        await client_obj.remove_cloud_password(
                            password=current_password
                        )
                        await asyncio.sleep(1)
                        await client_obj.enable_cloud_password(
                            password=new_password, hint=""
                        )
                        await asyncio.sleep(1)
                        ok = await _verify_2fa(client_obj, new_password)
                        if ok:
                            return True, "✅ تم إعادة تفعيل كلمة المرور", new_password
                        return False, "⚠️ فشل التحقق", current_password
                    except Exception as e2:
                        return False, f"⚠️ فشل: {str(e2)[:80]}", current_password
                return False, f"⚠️ فشل: {str(e)[:80]}", current_password

        try:
            await client_obj.enable_cloud_password(
                password=new_password, hint=""
            )
            await asyncio.sleep(1)
            ok = await _verify_2fa(client_obj, new_password)
            if ok:
                return True, "✅ تم تفعيل كلمة المرور", new_password
            return False, "⚠️ فشل التحقق", None
        except Exception as e:
            err = str(e).lower()
            if any(k in err for k in ("already", "enabled", "password")):
                return False, "⚠️ الحساب محمي بكلمة مرور مختلفة", None
            return False, f"⚠️ فشل: {str(e)[:80]}", None

    except Exception as e:
        logger.exception("change_2fa_password")
        return False, f"❌ خطأ: {str(e)[:80]}", None


async def _fetch_authorizations(client_obj: Client):
    result = await client_obj.invoke(GetAuthorizations())
    return result.authorizations or []


def _is_bot_session(auth) -> bool:
    try:
        dev = (getattr(auth, "device_model", "") or "").lower().strip()
        app = (getattr(auth, "app_name", "") or "").lower().strip()
        sys_ver = (getattr(auth, "system_version", "") or "").lower().strip()
        combined = f"{dev} | {app} | {sys_ver}"

        bot_keywords = (
            "python", "pyrogram", "telethon", "hydrogram",
            "tgcrypto", "mtproto", "gramjs", "madeline", "tdlib",
        )
        for kw in bot_keywords:
            if kw in combined:
                return True

        real_keywords = (
            "android", "iphone", "ipad", "ios",
            "web", "desktop", "windows", "macos",
            "telegram", "tg macos", "tg android",
            "nekogram", "xiaomi", "samsung", "huawei",
            "oppo", "vivo", "redmi", "poco", "realme",
            "oneplus", "google", "pixel", "nokia", "sony",
        )
        for kw in real_keywords:
            if kw in combined:
                return False

        return False
    except Exception:
        return False


async def count_other_sessions(client_obj: Client) -> int:
    last_err = None
    for attempt in range(MAX_SESSION_FETCH_RETRIES):
        try:
            auths = await asyncio.wait_for(
                _fetch_authorizations(client_obj),
                timeout=SESSION_FETCH_TIMEOUT,
            )
            count = 0
            for a in auths:
                try:
                    if getattr(a, "current", False):
                        continue
                    if _is_bot_session(a):
                        continue
                    count += 1
                except Exception:
                    continue
            return count
        except asyncio.TimeoutError as e:
            last_err = e
            await asyncio.sleep(1.5)
        except FloodWait as e:
            await asyncio.sleep(min(e.value, 30))
            last_err = e
        except Exception as e:
            last_err = e
            await asyncio.sleep(1.5)

    raise RuntimeError(
        f"فشل فحص الجلسات بعد {MAX_SESSION_FETCH_RETRIES} محاولات: {last_err}"
    )


async def list_other_sessions(client_obj: Client) -> list:
    last_err = None
    for attempt in range(MAX_SESSION_FETCH_RETRIES):
        try:
            auths = await asyncio.wait_for(
                _fetch_authorizations(client_obj),
                timeout=SESSION_FETCH_TIMEOUT,
            )
            result = []
            for a in auths:
                try:
                    if getattr(a, "current", False):
                        continue
                    if _is_bot_session(a):
                        continue
                    result.append({
                        "device": getattr(a, "device_model", "?") or "?",
                        "app": getattr(a, "app_name", "?") or "?",
                        "system": getattr(a, "system_version", "?") or "?",
                        "hash": getattr(a, "hash", None),
                    })
                except Exception:
                    continue
            return result
        except asyncio.TimeoutError as e:
            last_err = e
            await asyncio.sleep(1.5)
        except FloodWait as e:
            await asyncio.sleep(min(e.value, 30))
            last_err = e
        except Exception as e:
            last_err = e
            await asyncio.sleep(1.5)

    raise RuntimeError(
        f"فشل فحص الجلسات بعد {MAX_SESSION_FETCH_RETRIES} محاولات: {last_err}"
    )


async def terminate_bot_session(client_obj: Client) -> bool:
    current_hash = None
    try:
        if not client_obj.is_connected:
            await client_obj.connect()
            await asyncio.sleep(1)

        auths = await client_obj.invoke(GetAuthorizations())

        for a in auths.authorizations:
            if getattr(a, "current", False):
                current_hash = a.hash
                logger.info(
                    f"🔍 جلسة البوت الحالية: "
                    f"{getattr(a, 'device_model', '?')} | "
                    f"{getattr(a, 'app_name', '?')}"
                )
                break

        if not current_hash:
            logger.warning("⚠️ لم يتم العثور على جلسة البوت الحالية")
            return False

        reset_ok = False
        try:
            from pyrogram.raw.functions.account import ResetAuthorization
            await client_obj.invoke(ResetAuthorization(hash=current_hash))
            reset_ok = True
            logger.info("✅ تم تسجيل خروج جلسة البوت")
        except ImportError:
            pass
        except Exception as e:
            logger.debug(f"⚠️ ResetAuthorization فشل: {e}")

        if not reset_ok:
            try:
                import pyrogram.raw.functions.account as account_funcs
                for name in dir(account_funcs):
                    if ("Reset" in name and "Authorization" in name
                            and name != "ResetAuthorizations"):
                        cls = getattr(account_funcs, name)
                        try:
                            obj = cls(hash=current_hash)
                            await client_obj.invoke(obj)
                            reset_ok = True
                            logger.info(f"✅ تم تسجيل خروج جلسة البوت ({name})")
                            break
                        except Exception:
                            continue
            except Exception:
                pass

        if reset_ok:
            await asyncio.sleep(1)
            return True

        logger.warning("⚠️ استخدام log_out كحل أخير")
        try:
            await client_obj.log_out()
            logger.info("✅ تم تسجيل خروج جلسة البوت (log_out)")
            return True
        except Exception as e:
            logger.exception(f"❌ log_out فشل: {e}")
            return False

    except Exception as e:
        logger.exception(f"terminate_bot_session: {e}")
        return False


async def fetch_latest_otp(
    client_obj: Client,
    phone: str,
    buyer_id: int,
    max_age_minutes: int = 3,
    force_resend: bool = False,
):
    try:
        if not client_obj.is_connected:
            await client_obj.connect()
            await asyncio.sleep(1)
        cutoff = datetime.now() - timedelta(minutes=max_age_minutes)
        latest_code = None
        latest_date = None

        for sid in TELEGRAM_SERVICE_IDS:
            try:
                async for msg in client_obj.get_chat_history(sid, limit=20):
                    if not (msg and msg.text):
                        continue
                    msg_date = msg.date.replace(tzinfo=None) if msg.date else None
                    if msg_date and msg_date < cutoff:
                        continue
                    c = await _extract_code_from_text(msg.text)
                    if not c:
                        continue
                    if latest_date is None or (msg_date and msg_date > latest_date):
                        latest_code = c
                        latest_date = msg_date
            except Exception as e:
                logger.debug(f"fetch_latest_otp sid={sid}: {e}")
                continue

        if latest_code:
            try:
                await db.save_code(phone, buyer_id, latest_code)
            except Exception:
                pass
            return latest_code

        if not force_resend:
            return None

        phone_code_hash = None
        try:
            phone_code_hash = await db.get_phone_code_hash(phone, buyer_id)
        except Exception:
            pass

        sent_ok = False
        if phone_code_hash:
            try:
                sent = await client_obj.resend_code(phone, phone_code_hash)
                try:
                    await db.save_phone_code_hash(phone, buyer_id,
                                                  sent.phone_code_hash)
                except Exception:
                    pass
                sent_ok = True
            except FloodWait as e:
                await asyncio.sleep(e.value + 2)
                return None
            except Exception as e:
                logger.debug(f"resend_code فشل: {e}")

        if not sent_ok:
            try:
                sent = await client_obj.send_code(phone)
                try:
                    await db.save_phone_code_hash(phone, buyer_id,
                                                  sent.phone_code_hash)
                except Exception:
                    pass
                sent_ok = True
            except FloodWait as e:
                await asyncio.sleep(e.value + 2)
                return None
            except Exception as e:
                err = str(e).lower()
                if "already" in err or "sent" in err:
                    pass
                else:
                    logger.exception(f"send_code فشل: {e}")
                    return None

        if not sent_ok:
            return None

        await asyncio.sleep(3)
        for attempt in range(10):
            await asyncio.sleep(3)
            for sid in TELEGRAM_SERVICE_IDS:
                try:
                    async for msg in client_obj.get_chat_history(sid, limit=5):
                        if not (msg and msg.text):
                            continue
                        msg_date = msg.date.replace(tzinfo=None) if msg.date else None
                        if msg_date and msg_date < cutoff:
                            continue
                        c = await _extract_code_from_text(msg.text)
                        if c:
                            try:
                                await db.save_code(phone, buyer_id, c)
                            except Exception:
                                pass
                            return c
                except Exception:
                    continue
        return None
    except Exception as e:
        logger.exception(f"fetch_latest_otp: {e}")
        return None


async def pre_delivery_check(client_obj: Client) -> dict:
    result = {"ok": False, "session_count": 0, "sessions": [], "error": ""}
    try:
        if not client_obj.is_connected:
            await client_obj.connect()
            await asyncio.sleep(2)
        sessions = await list_other_sessions(client_obj)
        result["ok"] = True
        result["session_count"] = len(sessions)
        result["sessions"] = sessions
        return result
    except Exception as e:
        logger.exception(f"pre_delivery_check: {e}")
        result["error"] = str(e)
        return result


async def _extract_code_from_text(text: str):
    if not text:
        return None
    patterns = [
        r'(?:code|Code|رمز|كود|login|Login)[\s:]*(\d{4,6})',
        r'Telegram code[:\s]*(\d{4,6})',
        r'(\d{5,6})',
        r'\b(\d{4})\b',
    ]
    for pattern in patterns:
        m = re.search(pattern, text)
        if m:
            return m.group(1)
    return None


async def watch_for_code(bot_app, buyer_id: int, phone: str, client_obj: Client):
    logger.info(f"👁️ مراقبة {phone}")
    await asyncio.sleep(2)

    sent_codes = set()
    handler_ref = {"h": None}

    async def code_handler(client, message: Message):
        try:
            if not (message and message.text):
                return
            sender_id = message.from_user.id if message.from_user else None
            if sender_id not in TELEGRAM_SERVICE_IDS:
                return
            code = await _extract_code_from_text(message.text)
            if not code or code in sent_codes:
                return
            msg_age = datetime.now().timestamp() - message.date.timestamp()
            if msg_age > 300:
                return
            sent_codes.add(code)
            try:
                await db.save_code(phone, buyer_id, code)
            except Exception:
                pass
            try:
                await bot_app.send_message(
                    buyer_id,
                    f"🔑 **رمز الدخول: `{code}`**\n\n"
                    f"❗️ لا تعطه لأي شخص\n\n📞 `{phone}`",
                    parse_mode=ParseMode.MARKDOWN
                )
            except Exception as e:
                logger.error(f"إرسال الكود: {e}")
        except Exception as e:
            logger.exception(f"code_handler: {e}")

    service_filter = filters.private & filters.user(TELEGRAM_SERVICE_IDS)
    h = MessageHandler(code_handler, service_filter)
    handler_ref["h"] = h
    client_obj.add_handler(h)

    try:
        timeout = 900
        start = asyncio.get_event_loop().time()
        while (asyncio.get_event_loop().time() - start) < timeout:
            if buyer_id not in buy_sessions:
                break
            try:
                if not client_obj.is_connected:
                    await client_obj.connect()
                    await asyncio.sleep(2)
            except Exception:
                pass
            await asyncio.sleep(2)
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.exception(f"watch_for_code: {e}")
    finally:
        try:
            if handler_ref["h"]:
                client_obj.remove_handler(handler_ref["h"])
        except Exception:
            pass
        active_code_watchers.pop(phone, None)


async def complete_purchase(bot_app, buyer_id: int, phone: str,
                            login_client: Client, final_price: float = None):
    number = await db.get_number(phone)
    if not number:
        raise ValueError("الرقم غير موجود")
    seller_id = number['seller_id']

    if final_price is None:
        price = float(number['price'])
        discount = await db.get_user_discount(buyer_id)
        if discount > 0:
            price = price * (1 - discount / 100)
    else:
        price = float(final_price)

    success = await db.atomic_purchase(buyer_id, seller_id, phone, price)
    if not success:
        raise ValueError("❌ فشل الخصم — الرصيد غير كافٍ أو الرقم غير متاح")

    try:
        await db.upgrade_user_level(buyer_id)
        await db.check_and_upgrade_vip(buyer_id)
    except Exception:
        pass

    try:
        if not login_client.is_connected:
            await login_client.connect()
    except Exception as e:
        logger.error(f"reconnect: {e}")

    task = asyncio.create_task(
        watch_for_code(bot_app, buyer_id, phone, login_client)
    )
    active_code_watchers[phone] = {
        "client": login_client, "buyer_id": buyer_id, "task": task
    }

    try:
        pwd_2fa = None
        if number.get("password_2fa_enc"):
            pwd_2fa = decrypt(number["password_2fa_enc"]) or None
        if not pwd_2fa:
            pwd_2fa = FIXED_2FA_PASSWORD
        await safe_send(
            bot_app, buyer_id,
            f"✅ **تم الشراء بنجاح!**\n━━━━━━━━━━━━━━━\n\n"
            f"📱 الرقم: `{phone}`\n"
            f"💰 المبلغ: **${price:.2f}**\n\n"
            f"📲 الخطوات:\n"
            f"1️⃣ افتح تليجرام\n"
            f"2️⃣ سجّل دخول بالرقم `{phone}`\n"
            f"3️⃣ الكود هيوصلك هنا",
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception:
        pass

    try:
        seller_balance = await db.get_balance(seller_id)
        await safe_send(
            bot_app, seller_id,
            f"💰 **تم بيع رقمك!**\n📱 `{phone}`\n"
            f"💵 **${price:.2f}**\n💳 رصيدك: **${seller_balance:.2f}**",
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception:
        pass

    try:
        await safe_send(
            bot_app, OWNER_ID,
            f"🔔 **عملية بيع جديدة**\n📱 `{phone}`\n"
            f"💵 **${price:.2f}**\n👤 `{buyer_id}`\n👛 `{seller_id}`",
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception:
        pass

    return price, seller_id


async def get_otp_for_number(bot_app, buyer_id: int, phone: str) -> dict:
    result = {"ok": False, "code": None, "pwd_2fa": None, "message": ""}

    number = await db.get_number(phone)
    if not number:
        result["message"] = "❌ الرقم غير موجود"
        return result
    if number.get("buyer_id") != buyer_id:
        result["message"] = "❌ هذا الرقم ليس ملكك"
        return result

    pwd_2fa = None
    if number.get("password_2fa_enc"):
        try:
            pwd_2fa = decrypt(number["password_2fa_enc"]) or None
        except Exception:
            pwd_2fa = None
    if not pwd_2fa:
        pwd_2fa = FIXED_2FA_PASSWORD
    result["pwd_2fa"] = pwd_2fa

    code = None
    try:
        code = await db.get_last_code(phone, buyer_id)
    except Exception:
        code = None

    if not code:
        cli = None
        w = active_code_watchers.get(phone)
        if w:
            cli = w.get("client")
        if not cli:
            sess = buy_sessions.get(buyer_id)
            cli = sess.get("client") if sess else None
        if cli:
            try:
                code = await fetch_latest_otp(
                    cli, phone, buyer_id,
                    max_age_minutes=5, force_resend=True
                )
            except Exception as e:
                logger.debug(f"get_otp: {e}")

    if code:
        result["ok"] = True
        result["code"] = code
        result["message"] = "✅ تم جلب الكود"
        return result

    result["ok"] = False
    result["message"] = (
        f"❌ **لم يصل كود تحقق بعد**\n━━━━━━━━━━━━━━━\n\n"
        f"📞 الرقم: `{phone}`\n\n"
        f"⚠️ لازم تسجّل دخول بالرقم الأول\n\n"
        f"1️⃣ افتح تليجرام\n"
        f"2️⃣ سجّل دخول بالرقم `{phone}`\n"
        f"3️⃣ انتظر الكود\n"
        f"4️⃣ بعدها اضغط OTP"
    )
    return result


async def check_number_sessions_for_buy(phone: str, user_id: int) -> dict:
    result = {"ok": False, "has_sessions": False, "sessions": [], "error": ""}
    number = await db.get_number(phone)
    if not number or number['status'] != 'available':
        result["error"] = "❌ الرقم غير متاح"
        return result

    lc = None
    try:
        session_string = decrypt(number['session_enc'])
        lc = Client(
            f"check_{user_id}_{phone[-4:]}",
            api_id=API_ID, api_hash=API_HASH,
            session_string=session_string, in_memory=True
        )
        await lc.connect()
        await asyncio.sleep(1)
    except Exception as e:
        logger.exception(f"check_number_sessions_for_buy connect: {e}")
        result["error"] = "❌ فشل الاتصال بالرقم"
        return result

    try:
        sessions = await list_other_sessions(lc)
        result["ok"] = True
        result["sessions"] = sessions
        result["has_sessions"] = len(sessions) > 0
    except Exception as e:
        logger.exception(f"check_number_sessions_for_buy list FAILED: {e}")
        result["error"] = "❌ فشل فحص جلسات الرقم"
    finally:
        try:
            if lc:
                await lc.disconnect()
        except Exception:
            pass
    return result


async def verify_buyer_login(bot_app, buyer_id: int, phone: str) -> tuple:
    code = None
    try:
        code = await db.get_last_code(phone, buyer_id)
    except Exception:
        pass

    cli = None
    w = active_code_watchers.get(phone)
    if w:
        cli = w.get("client")
    if not cli:
        sess = buy_sessions.get(buyer_id)
        cli = sess.get("client") if sess else None

    if not code:
        return False, (
            f"❌ لم نتمكن من التحقق من تسجيل دخولك\n\n"
            f"📞 `{phone}`\n\n"
            f"سجّل دخول بالرقم ثم اضغط تأكيد الشراء مرة أخرى."
        )
    if not cli:
        return False, "❌ انتهت جلسة الشراء."

    try:
        if not cli.is_connected:
            await cli.connect()
            await asyncio.sleep(2)
    except Exception as e:
        logger.exception(f"verify_buyer_login connect: {e}")
        return False, "❌ فشل الاتصال بالحساب."

    try:
        user_devices = await list_other_sessions(cli)
    except Exception as e:
        logger.exception(f"verify_buyer_login list FAILED: {e}")
        return False, "❌ فشل فحص الجلسات."

    if len(user_devices) == 0:
        return False, (
            f"❌ لم نتمكن من التحقق\n📞 `{phone}`\n🔑 `{code}`\n\n"
            f"سجّل دخول بالرقم ثم أعد المحاولة."
        )
    return True, ""


async def confirm_purchase_session(bot_app, buyer_id: int, phone: str) -> dict:
    result = {"ok": False, "has_new_session": False, "message": ""}
    number = await db.get_number(phone)
    if not number:
        result["message"] = "❌ الرقم غير موجود"
        return result
    if number.get("buyer_id") != buyer_id:
        result["message"] = "❌ هذا الرقم ليس ملكك"
        return result

    cli = None
    w = active_code_watchers.get(phone)
    if w:
        cli = w.get("client")
    if not cli:
        sess = buy_sessions.get(buyer_id)
        cli = sess.get("client") if sess else None
    if not cli:
        result["message"] = "❌ انتهت الجلسة، ابدأ من جديد"
        return result

    try:
        if not cli.is_connected:
            await cli.connect()
            await asyncio.sleep(2)
    except Exception:
        result["message"] = "❌ فشل الاتصال بالحساب"
        return result

    try:
        other_sessions = await list_other_sessions(cli)
    except Exception as e:
        logger.exception(f"confirm_purchase_session list FAILED: {e}")
        result["message"] = "❌ فشل فحص الجلسات."
        return result

    others = len(other_sessions)
    if others == 0:
        result["message"] = (
            f"❌ لم نتمكن من التحقق\n📞 `{phone}`\n\n"
            f"سجّل دخول فعلي الأول ثم أعد المحاولة."
        )
        return result
    if others > 1:
        lines = []
        for i, s in enumerate(other_sessions[:7], 1):
            lines.append(f"{i}. 📱 {s['device']} — {s['app']}")
        result["has_new_session"] = True
        result["message"] = (
            f"⚠️ يوجد **{others}** جلسة نشطة\n\n"
            + "\n".join(lines) +
            f"\n\n🚪 اخرج من كل الجلسات ثم أعد المحاولة."
        )
        return result

    try:
        logged_out = await terminate_bot_session(cli)
        if logged_out:
            logger.info(f"✅ خروج البوت من {phone}")
    except Exception as e:
        logger.exception(f"terminate_bot_session FAILED: {e}")

    try:
        await db.save_completed_purchase(
            phone, buyer_id, number['seller_id'], float(number['price'])
        )
    except Exception as e:
        logger.debug(f"save_completed: {e}")
    try:
        await db.delete_number(phone)
    except Exception:
        pass

    w = active_code_watchers.pop(phone, None)
    if w and w.get("task"):
        w["task"].cancel()
    buy_sessions.pop(buyer_id, None)
    try:
        await cli.disconnect()
    except Exception:
        pass

    result["ok"] = True
    result["message"] = (
        "✅ **تم تأكيد الشراء بنجاح!**\n\n"
        "🎉 الحساب الآن ملكك بالكامل\n"
        "🔒 تم حذف بيانات الرقم من البوت"
    )
    return result


async def check_subscription(client, user_id: int) -> tuple:
    channels = await db.get_required_channels()
    if not channels:
        return True, []
    missing = []
    for ch in channels:
        ch_username = ch['channel_username']
        try:
            member = await client.get_chat_member(ch_username, user_id)
            status = str(member.status).lower()
            if status in ('left', 'kicked', 'banned', 'restricted'):
                missing.append(ch_username)
        except Exception as e:
            err_str = str(e).lower()
            if ("not enough rights" in err_str
                    or "chat admin" in err_str
                    or "bot is not" in err_str):
                continue
            if "user_not_participant" in err_str or "participant" in err_str:
                missing.append(ch_username)
                continue
            missing.append(ch_username)
    return len(missing) == 0, missing


async def send_home(client, user_id: int, chat_id: int = None):
    from shop import Admin as _admin_mod
    is_owner = (user_id == OWNER_ID)
    is_admin = user_id in _admin_mod.ADMINS
    if is_owner or is_admin:
        await send_dev_home(client, chat_id or user_id)
        return

    try:
        u = await client.get_users(user_id)
        name = u.first_name
    except Exception:
        name = "مستخدم"
    user = await db.get_user(user_id)
    balance = float(user['balance']) if user else 0
    text = (
        f"📮 مرحباً **SIMBot**، {name}.\n\n"
        f"🆔 `{user_id}`\n"
        f"💰 رصيدك: **${balance:.2f}**\n\n💡 استخدم الأزرار"
    )
    markup = main_reply_keyboard(is_owner=False)
    target = chat_id or user_id
    try:
        await safe_send(client, target, text, reply_markup=markup,
                        parse_mode=ParseMode.MARKDOWN)
    except Exception:
        pass


async def send_dev_home(client, chat_id: int):
    from config import OWNER_ID as _OWNER
    from shop import Admin as _admin_mod

    try:
        stats = await db.get_stats()
    except Exception:
        stats = {"users": 0, "available": 0, "sold": 0, "revenue": 0.0}
    try:
        banned = await db.get_banned_users()
        banned_count = len(banned)
    except Exception:
        banned_count = 0

    admins_count = len(_admin_mod.ADMINS)
    is_owner = (chat_id == _OWNER)

    if is_owner:
        title = "👑 *لوحة تحكم المالك*"
        role_line = "🎭 أنت: **المالك** (كل الصلاحيات)"
    else:
        title = "👤 *لوحة تحكم المشرف*"
        role_line = "🎭 أنت: **مشرف**"

    text = (
        f"{title}\n━━━━━━━━━━━━━━━\n\n"
        f"{role_line}\n\n"
        f"👥 المستخدمون: `{stats['users']}`\n"
        f"📦 متاحة: `{stats['available']}`\n"
        f"💰 مباعة: `{stats['sold']}`\n"
        f"💵 الإيرادات: **${stats['revenue']:.2f}**\n"
        f"🚫 محظورون: `{banned_count}`\n"
        f"👤 مشرفون: `{admins_count}`"
    )
    try:
        await safe_send(client, chat_id, text,
                        reply_markup=dev_reply_keyboard(),
                        parse_mode=ParseMode.MARKDOWN)
    except Exception:
        pass


async def cancel_all_user_operations(user_id: int, disconnect_clients: bool = True):
    """
    ✅ إلغاء كل عمليات المستخدم — شامل كل الحالات
    """
    result = {"cancelled": [], "disconnected": 0, "code_watchers_cancelled": 0}

    # 1) waiting_for
    if user_id in waiting_for:
        waiting_for.pop(user_id, None)
        result["cancelled"].append("waiting_for")

    # 2) dev_waiting
    try:
        from shop import Admin as _admin_mod
        if user_id in _admin_mod.dev_waiting:
            _admin_mod.dev_waiting.pop(user_id, None)
            result["cancelled"].append("dev_waiting")
    except Exception as e:
        logger.debug(f"cancel dev_waiting: {e}")

    # 3) temp_clients
    if user_id in temp_clients:
        cli = temp_clients.pop(user_id, None)
        if cli and disconnect_clients:
            try:
                if cli.is_connected:
                    await cli.disconnect()
                result["disconnected"] += 1
            except Exception as e:
                logger.debug(f"temp_clients disconnect: {e}")

    # 4) buy_sessions + active_code_watchers
    if user_id in buy_sessions:
        session = buy_sessions.pop(user_id, None)
        if session:
            cli = session.get("client")
            phone = session.get("phone")

            # إلغاء مراقب الكود
            if phone and phone in active_code_watchers:
                w = active_code_watchers.pop(phone, None)
                if w:
                    task = w.get("task")
                    if task and not task.done():
                        task.cancel()
                        result["code_watchers_cancelled"] += 1
                    w_cli = w.get("client")
                    if w_cli and disconnect_clients:
                        try:
                            if w_cli.is_connected:
                                await w_cli.disconnect()
                        except Exception:
                            pass

            # قطع عميل الشراء
            if cli and disconnect_clients:
                try:
                    if cli.is_connected:
                        await cli.disconnect()
                    result["disconnected"] += 1
                except Exception as e:
                    logger.debug(f"buy_session disconnect: {e}")

    # 5) clear temp data
    try:
        await db.clear_temp(user_id)
    except Exception as e:
        logger.debug(f"clear_temp: {e}")

    return result


async def send_communication_notice(client, user_id: int, message=None):
    try:
        from shop.Admin import ADMINS
        if user_id == OWNER_ID or user_id in ADMINS:
            return
        is_comm = await db.is_owner_comm_enabled(OWNER_ID)
        if not is_comm:
            return
        if not message:
            return

        try:
            sender = message.from_user
            name = sender.first_name or "مستخدم"
            username = sender.username or ""
        except Exception:
            name = "مستخدم"
            username = ""

        header = (
            f"💬 **رسالة من مستخدم**\n"
            f"━━━━━━━━━━━━━━━\n"
            f"👤 [{name}](tg://user?id={user_id})\n"
        )
        if username:
            header += f"📛 @{username}\n"
        header += f"🆔 `{user_id}`\n"
        header += "━━━━━━━━━━━━━━━\n"
        header += "📩 **للرد:** رد على هذه الرسالة\n"

        forward_msg = None
        try:
            if message.text:
                forward_msg = await client.send_message(
                    OWNER_ID, f"{header}\n{message.text}",
                    parse_mode=ParseMode.MARKDOWN
                )
            elif message.photo:
                cap = (message.caption or "")[:1024]
                forward_msg = await client.send_photo(
                    OWNER_ID, photo=message.photo.file_id,
                    caption=f"{header}\n{cap}",
                    parse_mode=ParseMode.MARKDOWN
                )
            elif message.video:
                cap = (message.caption or "")[:1024]
                forward_msg = await client.send_video(
                    OWNER_ID, video=message.video.file_id,
                    caption=f"{header}\n{cap}",
                    parse_mode=ParseMode.MARKDOWN
                )
            elif message.document:
                cap = (message.caption or "")[:1024]
                forward_msg = await client.send_document(
                    OWNER_ID, document=message.document.file_id,
                    caption=f"{header}\n{cap}",
                    parse_mode=ParseMode.MARKDOWN
                )
            elif message.voice:
                forward_msg = await client.send_voice(
                    OWNER_ID, voice=message.voice.file_id,
                    caption=header[:1024],
                    parse_mode=ParseMode.MARKDOWN
                )
            elif message.audio:
                cap = (message.caption or "")[:1024]
                forward_msg = await client.send_audio(
                    OWNER_ID, audio=message.audio.file_id,
                    caption=f"{header}\n{cap}",
                    parse_mode=ParseMode.MARKDOWN
                )
            elif message.video_note:
                await client.send_message(
                    OWNER_ID, header, parse_mode=ParseMode.MARKDOWN
                )
                forward_msg = await client.send_video_note(
                    OWNER_ID, video_note=message.video_note.file_id
                )
            elif message.sticker:
                await client.send_message(
                    OWNER_ID, header, parse_mode=ParseMode.MARKDOWN
                )
                forward_msg = await client.send_sticker(
                    OWNER_ID, sticker=message.sticker.file_id
                )
            else:
                forward_msg = await client.send_message(
                    OWNER_ID,
                    f"{header}\n(نوع رسالة غير مدعوم)",
                    parse_mode=ParseMode.MARKDOWN
                )
        except Exception as e:
            logger.debug(f"forward to owner: {e}")
            return

        if forward_msg:
            try:
                await db.save_twasl_message(
                    owner_id=OWNER_ID,
                    user_id=user_id,
                    user_message_id=message.id,
                    owner_message_id=forward_msg.id,
                    first_name=name,
                    username=username
                )
            except Exception as e:
                logger.debug(f"save_twasl: {e}")

    except Exception as e:
        logger.debug(f"send_communication_notice: {e}")


def register(app: Client):

    @app.on_message(filters.command("start"))
    async def start_cmd(client, message: Message):
        user_id = message.from_user.id
        if not await db.is_bot_enabled() and user_id != OWNER_ID:
            await message.reply_text("🔴 البوت معطل")
            return
        if await db.is_banned(user_id):
            await message.reply_text("🚫 أنت محظور")
            return
        await db.create_user(
            user_id, message.from_user.username, message.from_user.first_name
        )

        await send_communication_notice(client, user_id, message=message)

        if user_id in buy_sessions:
            old = buy_sessions.pop(user_id, None)
            if old:
                c = old.get("client")
                p = old.get("phone")
                if p and p in active_code_watchers:
                    w = active_code_watchers.pop(p, None)
                    if w and w.get("task"):
                        w["task"].cancel()
                if c:
                    try:
                        await c.disconnect()
                    except Exception:
                        pass

        if len(message.command) > 1:
            payload = message.command[1]
            if payload.startswith("ref_"):
                code = payload.replace("ref_", "")
                try:
                    await db.apply_referral(user_id, code)
                except Exception:
                    pass

        from shop import Admin as _admin_mod
        if user_id == OWNER_ID or user_id in _admin_mod.ADMINS:
            await send_dev_home(client, message.chat.id)
            return

        is_sub, missing = await check_subscription(client, user_id)
        if not is_sub:
            buttons = [
                [InlineKeyboardButton(
                    f"📢 اشترك في {ch}",
                    url=f"https://t.me/{ch.lstrip('@')}"
                )] for ch in missing
            ]
            buttons.append([InlineKeyboardButton(
                "✅ تحقق", callback_data="check_sub"
            )])
            await message.reply_text(
                "🔒 اشترك أولاً:\n\n" + "\n".join(f"• {ch}" for ch in missing),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(buttons)
            )
            return
        await send_home(client, user_id, message.chat.id)

    @app.on_message(filters.command("cancel"))
    async def cancel_cmd(client, message: Message):
        user_id = message.from_user.id
        result = await cancel_all_user_operations(user_id, disconnect_clients=True)
        from shop import Admin as _admin_mod
        if user_id == OWNER_ID or user_id in _admin_mod.ADMINS:
            keyboard = dev_reply_keyboard()
        else:
            keyboard = main_reply_keyboard()
        await message.reply_text(
            f"✅ تم إلغاء جميع العمليات\n\n"
            f"📋 العمليات: `{len(result.get('cancelled', []))}`",
            reply_markup=keyboard
        )