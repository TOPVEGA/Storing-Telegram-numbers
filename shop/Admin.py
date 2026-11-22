#لوجيك | Logic وجهتك البرمجية الأولى  بالوطن العربي
#شروحات - أكواد - وأحدث تقنيات برمجية - وحلول تقنية
#بواسطه: t.me/Logii3

#الترخيص: @TopVeGa
#العلامة التجارية: VEGA & Logic
#حقوق الطبع والنشر: © 2015 - 2025

import asyncio
import logging
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton
)
from pyrogram.enums import ParseMode
from pyrogram.errors import FloodWait, UserIsBlocked, InputUserDeactivated

from config import OWNER_ID
from Database import (
    db, generate_transaction_id, safe_send, audit_log
)

logger = logging.getLogger(__name__)

ADMINS: set = set()
dev_waiting = {}


async def load_admins_from_db():
    try:
        admins = await db.get_all_admins()
        ADMINS.clear()
        ADMINS.update(admins)
        logger.info(f"✅ تم تحميل {len(ADMINS)} مشرف من DB")
    except Exception as e:
        logger.error(f"load_admins_from_db: {e}")


def is_admin(_, __, message: Message):
    uid = message.from_user.id
    return uid == OWNER_ID or uid in ADMINS


def is_dev(_, __, message: Message):
    return message.from_user.id == OWNER_ID


def is_staff(_, __, message: Message):
    uid = message.from_user.id
    return uid == OWNER_ID or uid in ADMINS


admin_filter = filters.create(is_admin)
dev_filter = filters.create(is_dev)
staff_filter = filters.create(is_staff)


def is_owner_or_admin(user_id: int) -> bool:
    return user_id == OWNER_ID or user_id in ADMINS


def _user_mention(uid: int, name: str = None) -> str:
    n = name or "مستخدم"
    n = str(n).replace("[", "").replace("]", "")
    return f"[{n}](tg://user?id={uid})"


def _clean_channel_input(text: str) -> str:
    t = (text or "").strip()
    if not t:
        return ""
    t = t.replace("https://", "").replace("http://", "")
    t = t.replace("telegram.me/", "").replace("t.me/", "")
    t = t.split("/")[0].split("?")[0].strip()
    t = t.lstrip("@").strip()
    if not t:
        return ""
    return "@" + t


# ═══════════════════════════════════════════════════════════
# ⌨️ كيبورد المطور
# ═══════════════════════════════════════════════════════════
def dev_keyboard() -> ReplyKeyboardMarkup:
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


def dev_cancel_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[KeyboardButton("❌ إلغاء العملية")], [KeyboardButton("👑 الرئيسية")]],
        resize_keyboard=True
    )


async def resolve_user_id(client, text: str):
    text = (text or "").strip()
    if text.isdigit():
        return int(text)
    username = text.lstrip("@")
    try:
        user = await client.get_users(username)
        return user.id
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════
# 📢 الإذاعة — إرسال رسالة لأي هدف
# ═══════════════════════════════════════════════════════════
async def send_broadcast_to(target_client, target_id: int, src_msg: Message,
                             mode: str = "copy") -> bool:
    """
    mode: 'copy' | 'forward' | 'pin'
    """
    try:
        if mode == "forward":
            await src_msg.forward(target_id)
            return True
        elif mode == "pin":
            m = await src_msg.copy(target_id)
            try:
                await m.pin(disable_notification=False, both_sides=True)
            except Exception as pe:
                logger.debug(f"pin err: {pe}")
            return True
        else:
            await src_msg.copy(target_id)
            return True
    except FloodWait as e:
        await asyncio.sleep(e.value)
        try:
            if mode == "forward":
                await src_msg.forward(target_id)
            elif mode == "pin":
                m = await src_msg.copy(target_id)
                try:
                    await m.pin(disable_notification=False, both_sides=True)
                except Exception:
                    pass
            else:
                await src_msg.copy(target_id)
            return True
        except Exception:
            return False
    except (UserIsBlocked, InputUserDeactivated):
        return False
    except Exception as e:
        logger.debug(f"broadcast to {target_id}: {e}")
        return False


async def run_broadcast(client, src_msg: Message, mode: str,
                         targets: list, progress_msg: Message = None):
    total = len(targets)
    success = 0
    failed = 0

    for i in range(0, total, 20):
        batch = targets[i:i+20]
        tasks = [
            send_broadcast_to(client, uid, src_msg, mode)
            for uid in batch
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if r is True:
                success += 1
            else:
                failed += 1
        await asyncio.sleep(1.2)

        if progress_msg and (i % 100 == 0):
            try:
                await progress_msg.edit_text(
                    f"📢 جاري الإذاعة...\n"
                    f"📊 التقدم: `{min(i+20, total)}`/{total}\n"
                    f"✅ نجح: `{success}`\n"
                    f"❌ فشل: `{failed}`"
                )
            except Exception:
                pass

    return success, failed


# ═══════════════════════════════════════════════════════════
# 🎛️ معالج أزرار المطور
# ═══════════════════════════════════════════════════════════
async def process_dev_button(client, message: Message, text: str) -> bool:
    user_id = message.from_user.id
    if not is_owner_or_admin(user_id):
        return False

    from shop.play import send_dev_home

    if text in ("🏠 الرئيسية", "👑 الرئيسية", "🔙 رجوع"):
        await send_dev_home(client, message.chat.id)
        return True

    if text == "👑 صلاحياتي":
        role = "👑 المالك" if user_id == OWNER_ID else "👤 مشرف"
        can = (
            "✅ كل الصلاحيات"
            if user_id == OWNER_ID
            else "✅ إدارة المستخدمين والأرصدة\n"
                 "✅ الحظر والإذاعة\n"
                 "✅ الأرقام المجمدة\n"
                 "✅ إدارة قنوات الاشتراك\n"
                 "❌ رفع/تنزيل مشرفين\n"
                 "❌ مسح القنوات أو تفريغ التخزين"
        )
        await message.reply_text(
            f"👑 *صلاحياتك*\n━━━━━━━━━━━━━━━\n\n"
            f"🆔 `{user_id}`\n🎭 الدور: **{role}**\n\n"
            f"**الصلاحيات:**\n{can}",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=dev_keyboard()
        )
        return True

    if text in ("📊 إحصائيات البوت", "📈 تقرير عام"):
        stats = await db.get_stats()
        await message.reply_text(
            f"📈 *التقرير العام*\n━━━━━━━━━━━━━━━\n\n"
            f"👥 المستخدمون: `{stats['users']}`\n"
            f"📦 متاحة: `{stats['available']}`\n"
            f"💰 مباعة: `{stats['sold']}`\n"
            f"💵 الإيرادات: **${stats['revenue']:.2f}**",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=dev_keyboard()
        )
        return True

    if text == "📊 تقرير اليوم":
        stats = await db.get_daily_stats()
        await message.reply_text(
            f"📊 *تقرير اليوم*\n━━━━━━━━━━━━━━━\n\n"
            f"👥 جدد: `{stats['new_users']}`\n"
            f"💰 مبيعات: `{stats['sold']}`\n"
            f"💵 إيرادات: **${stats['revenue']:.2f}**",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=dev_keyboard()
        )
        return True

    if text == "🏆 أفضل البائعين":
        sellers = await db.get_top_sellers(10)
        if not sellers:
            await message.reply_text("لا يوجد بائعون بعد", reply_markup=dev_keyboard())
            return True
        lines = ["🏆 *أفضل البائعين*\n━━━━━━━━━━━━━━━\n"]
        for i, s in enumerate(sellers, 1):
            name = s['first_name'] or s['username'] or "مستخدم"
            lines.append(
                f"{i}. {_user_mention(s['id'], name)} — "
                f"`{s['total_sales']}` — ⭐{float(s['rating']):.2f}"
            )
        await message.reply_text("\n".join(lines),
                                 parse_mode=ParseMode.MARKDOWN,
                                 reply_markup=dev_keyboard())
        return True

    if text == "🌍 أكثر الدول":
        rows = await db.get_top_countries(10)
        if not rows:
            await message.reply_text("لا توجد بيانات", reply_markup=dev_keyboard())
            return True
        lines = ["🌍 *أكثر الدول مبيعاً*\n━━━━━━━━━━━━━━━\n"]
        for i, r in enumerate(rows, 1):
            lines.append(f"{i}. {r['country']} — `{r['cnt']}` عملية")
        await message.reply_text("\n".join(lines),
                                 parse_mode=ParseMode.MARKDOWN,
                                 reply_markup=dev_keyboard())
        return True

    if text == "👤 تفاصيل مستخدم":
        dev_waiting[user_id] = {"action": "user_details"}
        await message.reply_text(
            "👤 *تفاصيل مستخدم*\n\n📝 أرسل ID أو @username:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=dev_cancel_keyboard()
        )
        return True

    if text == "💰 إضافة رصيد":
        dev_waiting[user_id] = {"action": "add_balance_user"}
        await message.reply_text(
            "💰 *إضافة رصيد*\n\n📝 أرسل معرف المستخدم:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=dev_cancel_keyboard()
        )
        return True

    if text == "💸 خصم رصيد":
        dev_waiting[user_id] = {"action": "remove_balance_user"}
        await message.reply_text(
            "💸 *خصم رصيد*\n\n📝 أرسل معرف المستخدم:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=dev_cancel_keyboard()
        )
        return True

    if text == "💵 تصفير رصيد":
        dev_waiting[user_id] = {"action": "reset_balance_user"}
        await message.reply_text(
            "💵 *تصفير رصيد*\n\n📝 أرسل معرف المستخدم:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=dev_cancel_keyboard()
        )
        return True

    if text == "💵 تصفير كل الأرصدة":
        if user_id != OWNER_ID:
            await message.reply_text("🚫 للمالك فقط", reply_markup=dev_keyboard())
            return True
        await message.reply_text(
            "⚠️ *تصفير كل الأرصدة*\n━━━━━━━━━━━━━━━\n\n"
            "سيتم تصفير رصيد كل المستخدمين.\n"
            "🔴 لا يمكن التراجع!",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⚠️ نعم، صفّر الكل",
                                      callback_data="dev_confirm_reset_balances")],
                [InlineKeyboardButton("❌ إلغاء",
                                      callback_data="dev_cancel_reset_balances")],
            ])
        )
        return True

    if text == "🎁 إرسال هدية":
        dev_waiting[user_id] = {"action": "gift_user"}
        await message.reply_text(
            "🎁 *إرسال هدية*\n\n📝 أرسل معرف المستخدم:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=dev_cancel_keyboard()
        )
        return True

    if text == "🚫 حظر":
        dev_waiting[user_id] = {"action": "ban_user"}
        await message.reply_text(
            "🚫 *حظر مستخدم*\n\n📝 أرسل معرف المستخدم:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=dev_cancel_keyboard()
        )
        return True

    if text == "✅ إلغاء حظر":
        dev_waiting[user_id] = {"action": "unban_user"}
        await message.reply_text(
            "✅ *إلغاء حظر*\n\n📝 أرسل معرف المستخدم:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=dev_cancel_keyboard()
        )
        return True

    if text == "📋 المحظورين":
        banned = await db.get_banned_users()
        if not banned:
            await message.reply_text("✅ لا يوجد محظورون",
                                     reply_markup=dev_keyboard())
            return True
        lines = [f"🚫 *المحظورون* ({len(banned)})\n━━━━━━━━━━━━━━━\n"]
        for u in banned[:40]:
            name = u['first_name'] or u['username'] or "مستخدم"
            lines.append(f"• {_user_mention(u['id'], name)}")
        if len(banned) > 40:
            lines.append(f"\n... و {len(banned) - 40} آخرين")
        await message.reply_text("\n".join(lines),
                                 parse_mode=ParseMode.MARKDOWN,
                                 reply_markup=dev_keyboard())
        return True

    if text == "🗑️ مسح المحظورين":
        count = await db.clear_all_bans()
        await message.reply_text(f"✅ تم إلغاء حظر {count} مستخدم",
                                 reply_markup=dev_keyboard())
        return True

    if text in ("👤 رفع ادمن", "👤 إضافة مشرف"):
        if user_id != OWNER_ID:
            await message.reply_text("🚫 للمالك فقط", reply_markup=dev_keyboard())
            return True
        dev_waiting[user_id] = {"action": "add_admin"}
        await message.reply_text(
            "👤 *رفع ادمن*\n\n📝 أرسل معرف المستخدم:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=dev_cancel_keyboard()
        )
        return True

    if text in ("🗑️ تنزيل ادمن", "🗑️ حذف مشرف"):
        if user_id != OWNER_ID:
            await message.reply_text("🚫 للمالك فقط", reply_markup=dev_keyboard())
            return True
        dev_waiting[user_id] = {"action": "del_admin"}
        await message.reply_text(
            "🗑️ *تنزيل ادمن*\n\n📝 أرسل معرف المستخدم:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=dev_cancel_keyboard()
        )
        return True

    if text in ("📋 الادمنية", "📋 قائمة المشرفين"):
        if not ADMINS:
            await message.reply_text("📋 لا يوجد مشرفون",
                                     reply_markup=dev_keyboard())
            return True
        lines = [f"👑 *المشرفون* ({len(ADMINS)})\n━━━━━━━━━━━━━━━\n"]
        for uid in ADMINS:
            u = await db.get_user(uid)
            name = (u['first_name'] if u else None) or "مشرف"
            lines.append(f"• {_user_mention(uid, name)} — `{uid}`")
        await message.reply_text("\n".join(lines),
                                 parse_mode=ParseMode.MARKDOWN,
                                 reply_markup=dev_keyboard())
        return True

    if text == "🧊 تجميد رقم":
        dev_waiting[user_id] = {"action": "freeze_number"}
        await message.reply_text(
            "🧊 *تجميد رقم*\n\n📝 أرسل رقم الهاتف:\nمثال: `+20123456789`",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=dev_cancel_keyboard()
        )
        return True

    if text == "🔥 فك تجميد":
        dev_waiting[user_id] = {"action": "unfreeze_number"}
        await message.reply_text(
            "🔥 *فك تجميد*\n\n📝 أرسل رقم الهاتف:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=dev_cancel_keyboard()
        )
        return True

    if text == "📋 الأرقام المجمدة":
        frozen = await db.get_frozen_numbers(limit=50)
        if not frozen:
            await message.reply_text("✅ لا توجد أرقام مجمدة",
                                     reply_markup=dev_keyboard())
            return True
        lines = [f"🧊 *الأرقام المجمدة* ({len(frozen)})\n━━━━━━━━━━━━━━━\n"]
        for f in frozen[:30]:
            country = f.get('country') or '؟'
            lines.append(f"• `{f['phone']}` — 🌍 {country}")
        if len(frozen) > 30:
            lines.append(f"\n... و {len(frozen) - 30} آخرين")
        await message.reply_text("\n".join(lines),
                                 parse_mode=ParseMode.MARKDOWN,
                                 reply_markup=dev_keyboard())
        return True

    if text == "💬 تفعيل التواصل":
        await db.enable_owner_comm(user_id)
        await message.reply_text(
            "✅ *تم تفعيل التواصل*\n\n"
            "أي رسالة من مستخدم عادي ستوصلك هنا.\n"
            "📩 للرد: قم بالرد على الرسالة المُعاد توجيهها.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=dev_keyboard()
        )
        return True

    if text == "🔇 تعطيل التواصل":
        await db.disable_owner_comm(user_id)
        await message.reply_text(
            "🔇 *تم تعطيل التواصل*",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=dev_keyboard()
        )
        return True

    if text in ("➕ إضافة قناة", "➕ إضافة قناة إشبارية"):
        dev_waiting[user_id] = {"action": "add_channel"}
        await message.reply_text(
            "➕ *إضافة قناة اشتراك*\n━━━━━━━━━━━━━━━\n\n"
            "📝 أرسل معرف القناة أو الرابط:\n"
            "• `@MyChannel`\n"
            "• `https://t.me/MyChannel`\n"
            "• `MyChannel`\n\n"
            "⚠️ يجب أن يكون البوت أدمن في القناة",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=dev_cancel_keyboard()
        )
        return True

    if text in ("🗑️ حذف قناة", "🗑️ حذف قناة إشبارية"):
        dev_waiting[user_id] = {"action": "del_channel"}
        await message.reply_text(
            "🗑️ *حذف قناة اشتراك*\n\n📝 أرسل معرف القناة أو الرابط:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=dev_cancel_keyboard()
        )
        return True

    if text in ("🧹 مسح القنوات", "🧹 مسح قنوات الاشتراك"):
        if user_id != OWNER_ID:
            await message.reply_text("🚫 للمالك فقط", reply_markup=dev_keyboard())
            return True
        channels = await db.get_required_channels()
        if not channels:
            await message.reply_text("📋 لا توجد قنوات",
                                     reply_markup=dev_keyboard())
            return True
        await message.reply_text(
            f"⚠️ *مسح القنوات*\n━━━━━━━━━━━━━━━\n\n"
            f"سيتم حذف **{len(channels)}** قناة.\n🔴 لا يمكن التراجع!",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⚠️ نعم، احذف الكل",
                                      callback_data="dev_confirm_wipe_channels")],
                [InlineKeyboardButton("❌ إلغاء",
                                      callback_data="dev_cancel_wipe_channels")],
            ])
        )
        return True

    if text in ("📋 قنوات الاشتراك", "📋 قنوات اشتراك"):
        channels = await db.get_required_channels()
        if not channels:
            await message.reply_text("📋 لا توجد قنوات",
                                     reply_markup=dev_keyboard())
            return True
        lines = [f"📢 *قنوات الاشتراك* ({len(channels)})\n━━━━━━━━━━━━━━━\n"]
        for ch in channels:
            title = ch.get('channel_title') or 'قناة'
            uname = ch['channel_username'].lstrip('@')
            lines.append(f"• [{title}](https://t.me/{uname})")
        await message.reply_text("\n".join(lines),
                                 parse_mode=ParseMode.MARKDOWN,
                                 reply_markup=dev_keyboard())
        return True

    if text == "🗑️ تفريغ التخزين":
        if user_id != OWNER_ID:
            await message.reply_text("🚫 للمالك فقط", reply_markup=dev_keyboard())
            return True
        await message.reply_text(
            "⚠️ *تفريغ التخزين*\n━━━━━━━━━━━━━━━\n\n"
            "سيتم حذف كل الأرقام والمعاملات والأرصدة.\n"
            "✅ سيتم تخطي حساب المطور\n\n🔴 لا يمكن التراجع!",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⚠️ نعم، احذف الكل",
                                      callback_data="dev_confirm_wipe")],
                [InlineKeyboardButton("❌ إلغاء",
                                      callback_data="dev_cancel_wipe")],
            ])
        )
        return True

    # ═══ 📢 الإذاعات ═══
    if text == "📢 اذاعه":
        dev_waiting[user_id] = {"action": "broadcast", "mode": "normal"}
        await message.reply_text(
            "📢 *إذاعة عادية*\n\n"
            "📝 أرسل الرسالة (نص/صورة/فيديو/ملف/ستيكر/أنيميشن/فويس/صوت):",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=dev_cancel_keyboard()
        )
        return True

    if text == "📢 اذاعه بالتوجيه":
        dev_waiting[user_id] = {"action": "broadcast", "mode": "forward"}
        await message.reply_text(
            "📢 *إذاعة بالتوجيه*\n\n"
            "📝 أرسل الرسالة (سيتم توجيهها كما هي):",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=dev_cancel_keyboard()
        )
        return True

    if text == "📢 اذاعه بالتثبيت":
        dev_waiting[user_id] = {"action": "broadcast", "mode": "pin"}
        await message.reply_text(
            "📢 *إذاعة بالتثبيت*\n\n"
            "📝 أرسل الرسالة (ستُثبَّت في كل محادثة):",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=dev_cancel_keyboard()
        )
        return True

    # ═══ 📱 إذاعة للأرقام ═══
    if text == "📱 اذاعه للارقام":
        await message.reply_text(
            "📱 *إذاعة للأرقام المسجلة*\n"
            "━━━━━━━━━━━━━━━\n\n"
            "🎯 اختر مكان الإرسال:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(
                    "👤 خاص فقط", callback_data="nums_bc_target_private"
                )],
                [InlineKeyboardButton(
                    "👥 مجموعات فقط", callback_data="nums_bc_target_groups"
                )],
                [InlineKeyboardButton(
                    "🌍 خاص + مجموعات", callback_data="nums_bc_target_both"
                )],
                [InlineKeyboardButton("❌ إلغاء", callback_data="nums_bc_cancel")],
            ])
        )
        return True

    if text == "🎟️ كوبون":
        dev_waiting[user_id] = {"action": "coupon"}
        await message.reply_text(
            "🎟️ *إنشاء كوبون*\n\n"
            "📝 أرسل بالصيغة:\n`CODE discount max_uses`\n\n"
            "مثال: `SALE20 20 100`",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=dev_cancel_keyboard()
        )
        return True

    if text == "💾 نسخ الأرقام":
        await message.reply_text("📩 استخدم /backup_numbers",
                                 reply_markup=dev_keyboard())
        return True

    if text == "📥 استيراد الأرقام":
        await message.reply_text("📩 استخدم /restore_numbers",
                                 reply_markup=dev_keyboard())
        return True

    if text == "👥 نسخ المستخدمين":
        await message.reply_text("📩 استخدم /backup_users",
                                 reply_markup=dev_keyboard())
        return True

    if text == "📊 نسخ المعاملات":
        await message.reply_text("📩 استخدم /backup_transactions",
                                 reply_markup=dev_keyboard())
        return True

    return False


# ═══════════════════════════════════════════════════════════
# 📝 معالج نصوص المطور
# ═══════════════════════════════════════════════════════════
async def process_dev_text(client, message: Message, user_id: int) -> bool:
    if user_id not in dev_waiting:
        return False

    data = dev_waiting[user_id]
    action = data.get("action")

    try:
        # ═══ 👤 تفاصيل مستخدم ═══
        if action == "user_details":
            text = (message.text or "").strip()
            dev_waiting.pop(user_id, None)
            uid = await resolve_user_id(client, text)
            if not uid:
                await message.reply_text("❌ معرف غير صالح",
                                         reply_markup=dev_keyboard())
                return True
            user = await db.get_user(uid)
            if not user:
                await message.reply_text("❌ المستخدم غير موجود",
                                         reply_markup=dev_keyboard())
                return True

            txs_count = total_spent = total_earned = numbers_count = 0
            try:
                async with db.pool.acquire() as conn:
                    txs_count = await conn.fetchval(
                        "SELECT COUNT(*) FROM transactions WHERE user_id=$1", uid
                    ) or 0
                    total_spent = await conn.fetchval(
                        "SELECT COALESCE(SUM(ABS(amount)),0) FROM transactions "
                        "WHERE user_id=$1 AND type='purchase'", uid
                    ) or 0
                    total_earned = await conn.fetchval(
                        "SELECT COALESCE(SUM(amount),0) FROM transactions "
                        "WHERE user_id=$1 AND type='sale_income'", uid
                    ) or 0
                    numbers_count = await conn.fetchval(
                        "SELECT COUNT(*) FROM numbers WHERE seller_id=$1", uid
                    ) or 0
            except Exception:
                pass

            ref_stats = await db.get_referral_stats(uid) or {}
            is_admin_tag = "👑 مشرف" if uid in ADMINS else "👤 مستخدم"
            comm = await db.is_communication_enabled(uid)
            banned = "🚫 محظور" if user['is_banned'] else "✅ نشط"

            text_r = (
                f"👤 *تفاصيل المستخدم*\n━━━━━━━━━━━━━━━\n\n"
                f"🆔 `{uid}`\n"
                f"📝 الاسم: {_user_mention(uid, user['first_name'] or '—')}\n"
                f"📛 اليوزر: @{user['username'] or '—'}\n"
                f"🎭 الدور: {is_admin_tag}\n"
                f"📌 الحالة: {banned}\n"
                f"🏅 المستوى: {user['level']}\n\n"
                f"💰 الرصيد: **${float(user['balance']):.2f}**\n"
                f"⭐ التقييم: {float(user['rating']):.2f}\n"
                f"🛒 مشتريات: {user['total_purchases']}\n"
                f"💰 مبيعات: {user['total_sales']}\n"
                f"📱 أرقام مملوكة: {numbers_count}\n\n"
                f"📜 المعاملات: {txs_count}\n"
                f"💸 المصروف: ${float(total_spent):.2f}\n"
                f"💵 الأرباح: ${float(total_earned):.2f}\n\n"
                f"👥 الإحالات: {ref_stats.get('count', 0)}\n"
                f"💰 أرباح الإحالة: ${float(ref_stats.get('earnings', 0)):.2f}\n"
                f"🔗 كود الإحالة: `{user.get('referral_code') or '—'}`\n\n"
                f"💬 التواصل: {'✅ مفعّل' if comm else '❌ معطّل'}"
            )
            await message.reply_text(text_r, parse_mode=ParseMode.MARKDOWN,
                                     reply_markup=dev_keyboard())
            return True

        # ═══ ➕ إضافة قناة ═══
        if action == "add_channel":
            text = (message.text or "").strip()
            dev_waiting.pop(user_id, None)
            channel_username = _clean_channel_input(text)
            if not channel_username:
                await message.reply_text("❌ معرف أو رابط غير صالح",
                                         reply_markup=dev_keyboard())
                return True

            status = await message.reply_text("🔎 جاري التحقق...")
            chat = None
            try:
                chat = await client.get_chat(channel_username)
            except Exception as e:
                await status.edit_text(
                    f"❌ **لم يتم العثور على القناة**\n\n"
                    f"`{channel_username}`\n\n"
                    f"⚠️ أضف البوت أولاً للقناة.\n\n"
                    f"`{str(e)[:150]}`",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=dev_keyboard()
                )
                return True

            me = await client.get_me()
            is_bot_admin = False
            check_error = None
            try:
                bot_member = await client.get_chat_member(chat.id, me.id)
                status_str = str(bot_member.status).lower()
                is_bot_admin = (
                    "administrator" in status_str
                    or "creator" in status_str
                    or "owner" in status_str
                )
            except Exception as e:
                check_error = str(e)
                is_bot_admin = False

            if not is_bot_admin:
                reason = (
                    "🚫 **البوت ليس عضواً في القناة**\n"
                    if "USER_NOT_PARTICIPANT" in (check_error or "")
                    else "⚠️ **البوت ليس أدمن في القناة**\n"
                )
                await status.edit_text(
                    f"{reason}━━━━━━━━━━━━━━━\n\n"
                    f"📢 `{channel_username}`\n"
                    f"📛 {chat.title}\n\n"
                    f"📝 **الخطوات:**\n"
                    f"1️⃣ افتح القناة\n"
                    f"2️⃣ إدارة → الأعضاء\n"
                    f"3️⃣ أضف **@{me.username}** كمشرف\n"
                    f"4️⃣ ارجع واضغط **🔄 إعادة المحاولة**",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton(
                            "🔄 إعادة المحاولة",
                            callback_data=f"retry_add_channel_{channel_username.lstrip('@')}"
                        )],
                    ])
                )
                return True

            added = await db.add_required_channel(
                channel_username, chat.title, user_id
            )
            if added:
                await audit_log(db.pool, user_id, "add_channel",
                                f"{channel_username} | {chat.title}")
                await status.edit_text(
                    f"✅ **تمت إضافة القناة بنجاح!**\n"
                    f"━━━━━━━━━━━━━━━\n\n"
                    f"📢 [{chat.title}](https://t.me/{channel_username.lstrip('@')})\n"
                    f"🆔 `{chat.id}`",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=dev_keyboard()
                )
            else:
                await status.edit_text(
                    f"⚠️ القناة `{channel_username}` مضافة مسبقاً",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=dev_keyboard()
                )
            return True

        # ═══ 🗑️ حذف قناة ═══
        if action == "del_channel":
            text = (message.text or "").strip()
            dev_waiting.pop(user_id, None)
            channel_username = _clean_channel_input(text)
            if not channel_username:
                await message.reply_text("❌ معرف أو رابط غير صالح",
                                         reply_markup=dev_keyboard())
                return True
            info = await db.get_channel_info(channel_username)
            if not info:
                await message.reply_text(
                    f"❌ القناة `{channel_username}` غير مضافة",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=dev_keyboard()
                )
                return True
            ok = await db.remove_required_channel(channel_username)
            if ok:
                await audit_log(db.pool, user_id, "del_channel", channel_username)
                await message.reply_text(
                    f"✅ *تم حذف القناة*\n\n📢 `{channel_username}`",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=dev_keyboard()
                )
            else:
                await message.reply_text("❌ فشل الحذف",
                                         reply_markup=dev_keyboard())
            return True

        # ═══ 🎁 هدية ═══
        if action == "gift_user":
            text = (message.text or "").strip()
            uid = await resolve_user_id(client, text)
            if not uid:
                await message.reply_text("❌ معرف غير صالح")
                return True
            target = await db.get_user(uid)
            if not target:
                await message.reply_text("❌ المستخدم غير موجود",
                                         reply_markup=dev_keyboard())
                dev_waiting.pop(user_id, None)
                return True
            dev_waiting[user_id] = {"action": "gift_amount", "target_uid": uid}
            await message.reply_text(
                f"🎁 *إرسال هدية*\n\n"
                f"👤 {_user_mention(uid, target.get('first_name'))}\n"
                f"🆔 `{uid}`\n\n"
                f"📝 أرسل المبلغ (`default` = $20):",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=dev_cancel_keyboard()
            )
            return True

        if action == "gift_amount":
            text = (message.text or "").strip()
            uid = data["target_uid"]
            if text.lower() == "default" or not text:
                amt = 20.0
            else:
                try:
                    amt = float(text.replace('$', '').strip())
                    if amt <= 0:
                        raise ValueError
                except ValueError:
                    await message.reply_text("❌ مبلغ غير صالح")
                    return True
            ok = await db.send_gift(user_id, uid, amt,
                                    f"🎁 هدية بقيمة ${amt:.2f}")
            if not ok:
                await message.reply_text("❌ فشل إرسال الهدية",
                                         reply_markup=dev_keyboard())
                dev_waiting.pop(user_id, None)
                return True
            await audit_log(db.pool, user_id, "send_gift",
                            f"to={uid} amount={amt}")
            await message.reply_text(
                f"🎁 *تم إرسال الهدية!*\n\n"
                f"👤 {_user_mention(uid)}\n💵 **${amt:.2f}**",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=dev_keyboard()
            )
            try:
                nb = await db.get_balance(uid)
                await safe_send(client, uid,
                    f"🎁 **هدية من الإدارة**\n💵 **${amt:.2f}**\n"
                    f"👛 رصيدك: **${nb:.2f}**",
                    parse_mode=ParseMode.MARKDOWN)
            except Exception:
                pass
            dev_waiting.pop(user_id, None)
            return True

        # ═══ 🚫 حظر ═══
        if action == "ban_user":
            text = (message.text or "").strip()
            uid = await resolve_user_id(client, text)
            if not uid:
                await message.reply_text("❌ معرف غير صالح")
                return True
            if uid == OWNER_ID:
                await message.reply_text("⚠️ لا يمكن حظر المالك",
                                         reply_markup=dev_keyboard())
                dev_waiting.pop(user_id, None)
                return True
            if await db.is_banned(uid):
                await message.reply_text("⚠️ محظور مسبقاً",
                                         reply_markup=dev_keyboard())
                dev_waiting.pop(user_id, None)
                return True
            await db.ban_user(uid, True)
            await audit_log(db.pool, user_id, "ban", f"target={uid}")
            await message.reply_text(
                f"✅ تم حظر {_user_mention(uid)}",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=dev_keyboard()
            )
            dev_waiting.pop(user_id, None)
            return True

        if action == "unban_user":
            text = (message.text or "").strip()
            uid = await resolve_user_id(client, text)
            if not uid:
                await message.reply_text("❌ معرف غير صالح")
                return True
            if not await db.is_banned(uid):
                await message.reply_text("⚠️ غير محظور",
                                         reply_markup=dev_keyboard())
                dev_waiting.pop(user_id, None)
                return True
            await db.ban_user(uid, False)
            await audit_log(db.pool, user_id, "unban", f"target={uid}")
            await message.reply_text(
                f"✅ تم إلغاء حظر {_user_mention(uid)}",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=dev_keyboard()
            )
            dev_waiting.pop(user_id, None)
            return True

        # ═══ 🧊 تجميد ═══
        if action == "freeze_number":
            text = (message.text or "").strip()
            phone = text if text.startswith('+') else '+' + text
            if not phone[1:].isdigit() or len(phone) < 11:
                await message.reply_text("❌ رقم غير صالح")
                return True
            number = await db.get_number(phone)
            if not number:
                await message.reply_text(f"❌ الرقم `{phone}` غير موجود",
                                         parse_mode=ParseMode.MARKDOWN,
                                         reply_markup=dev_keyboard())
                dev_waiting.pop(user_id, None)
                return True
            if await db.is_number_frozen(phone):
                await message.reply_text("⚠️ مجمد مسبقاً",
                                         reply_markup=dev_keyboard())
                dev_waiting.pop(user_id, None)
                return True
            ok = await db.freeze_number(phone, user_id, "تجميد")
            if ok:
                await audit_log(db.pool, user_id, "freeze_number", phone)
                await message.reply_text(
                    f"🧊 *تم التجميد*\n\n📱 `{phone}`",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=dev_keyboard()
                )
            dev_waiting.pop(user_id, None)
            return True

        if action == "unfreeze_number":
            text = (message.text or "").strip()
            phone = text if text.startswith('+') else '+' + text
            if not phone[1:].isdigit() or len(phone) < 11:
                await message.reply_text("❌ رقم غير صالح")
                return True
            if not await db.is_number_frozen(phone):
                await message.reply_text("⚠️ غير مجمد",
                                         reply_markup=dev_keyboard())
                dev_waiting.pop(user_id, None)
                return True
            ok = await db.unfreeze_number(phone)
            if ok:
                await audit_log(db.pool, user_id, "unfreeze_number", phone)
                await message.reply_text(
                    f"🔥 *تم فك التجميد*\n\n📱 `{phone}`",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=dev_keyboard()
                )
            dev_waiting.pop(user_id, None)
            return True

        # ═══ 👤 رفع ادمن ═══
        if action == "add_admin":
            text = (message.text or "").strip()
            if user_id != OWNER_ID:
                dev_waiting.pop(user_id, None)
                return True
            uid = await resolve_user_id(client, text)
            if not uid:
                await message.reply_text("❌ معرف غير صالح")
                return True
            if uid == OWNER_ID:
                await message.reply_text("⚠️ هو المالك",
                                         reply_markup=dev_keyboard())
                dev_waiting.pop(user_id, None)
                return True
            if uid in ADMINS:
                await message.reply_text("⚠️ مشرف مسبقاً",
                                         reply_markup=dev_keyboard())
                dev_waiting.pop(user_id, None)
                return True
            ok = await db.add_admin(uid, user_id)
            if ok:
                ADMINS.add(uid)
                await audit_log(db.pool, user_id, "add_admin", f"target={uid}")
                await message.reply_text(
                    f"✅ *تم رفع ادمن*\n\n👤 {_user_mention(uid)}",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=dev_keyboard()
                )
                try:
                    await safe_send(client, uid,
                        "👑 **تم ترقيتك لمشرف!**\n📝 أرسل /start",
                        parse_mode=ParseMode.MARKDOWN)
                except Exception:
                    pass
            dev_waiting.pop(user_id, None)
            return True

        if action == "del_admin":
            text = (message.text or "").strip()
            if user_id != OWNER_ID:
                dev_waiting.pop(user_id, None)
                return True
            uid = await resolve_user_id(client, text)
            if not uid:
                await message.reply_text("❌ معرف غير صالح")
                return True
            if uid not in ADMINS:
                await message.reply_text("⚠️ ليس مشرفاً",
                                         reply_markup=dev_keyboard())
                dev_waiting.pop(user_id, None)
                return True
            ok = await db.remove_admin(uid)
            if ok:
                ADMINS.discard(uid)
                await audit_log(db.pool, user_id, "del_admin", f"target={uid}")
                await message.reply_text(
                    f"✅ *تم تنزيل ادمن*\n\n👤 {_user_mention(uid)}",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=dev_keyboard()
                )
                try:
                    await safe_send(client, uid,
                        "⚠️ **تم سحب صلاحيات المشرف منك**",
                        parse_mode=ParseMode.MARKDOWN)
                except Exception:
                    pass
            dev_waiting.pop(user_id, None)
            return True

        # ═══ 💰 رصيد ═══
        if action == "add_balance_user":
            text = (message.text or "").strip()
            uid = await resolve_user_id(client, text)
            if not uid:
                await message.reply_text("❌ معرف غير صالح")
                return True
            dev_waiting[user_id] = {"action": "add_balance_amount", "target_uid": uid}
            await message.reply_text(
                f"💰 *إضافة رصيد*\n\n👤 {_user_mention(uid)}\n\n📝 أرسل المبلغ:",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=dev_cancel_keyboard()
            )
            return True

        if action == "add_balance_amount":
            text = (message.text or "").strip()
            try:
                amt = float(text.replace('$', '').strip())
                if amt <= 0:
                    raise ValueError
            except ValueError:
                await message.reply_text("❌ مبلغ غير صالح")
                return True
            uid = data["target_uid"]
            await db.update_balance(uid, amt)
            await db.add_transaction(generate_transaction_id(), uid,
                                     "topup", amt, None, "شحن من الإدارة")
            await audit_log(db.pool, user_id, "add_balance",
                            f"to={uid} amount={amt}")
            await message.reply_text(
                f"✅ تم إضافة **${amt:.2f}** لـ {_user_mention(uid)}",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=dev_keyboard()
            )
            dev_waiting.pop(user_id, None)
            try:
                await client.send_message(uid,
                    f"🎁 *تم شحن محفظتك!*\n💵 **${amt:.2f}**",
                    parse_mode=ParseMode.MARKDOWN)
            except Exception:
                pass
            return True

        if action == "remove_balance_user":
            text = (message.text or "").strip()
            uid = await resolve_user_id(client, text)
            if not uid:
                await message.reply_text("❌ معرف غير صالح")
                return True
            bal = await db.get_balance(uid)
            dev_waiting[user_id] = {"action": "remove_balance_amount", "target_uid": uid}
            await message.reply_text(
                f"💸 *خصم رصيد*\n\n👤 {_user_mention(uid)}\n"
                f"💰 رصيده: **${bal:.2f}**\n\n📝 أرسل المبلغ:",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=dev_cancel_keyboard()
            )
            return True

        if action == "remove_balance_amount":
            text = (message.text or "").strip()
            try:
                amt = float(text.replace('$', '').strip())
                if amt <= 0:
                    raise ValueError
            except ValueError:
                await message.reply_text("❌ مبلغ غير صالح")
                return True
            uid = data["target_uid"]
            await db.update_balance(uid, -amt)
            await db.add_transaction(generate_transaction_id(), uid,
                                     "withdrawal", -amt, None, "خصم من الإدارة")
            await audit_log(db.pool, user_id, "remove_balance",
                            f"from={uid} amount={amt}")
            await message.reply_text(
                f"✅ تم خصم **${amt:.2f}** من {_user_mention(uid)}",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=dev_keyboard()
            )
            dev_waiting.pop(user_id, None)
            try:
                await client.send_message(uid,
                    f"⚠️ *تم خصم من محفظتك*\n💵 **-${amt:.2f}**",
                    parse_mode=ParseMode.MARKDOWN)
            except Exception:
                pass
            return True

        if action == "reset_balance_user":
            text = (message.text or "").strip()
            uid = await resolve_user_id(client, text)
            if not uid:
                await message.reply_text("❌ معرف غير صالح")
                return True
            if uid == OWNER_ID:
                await message.reply_text("⚠️ لا يمكن تصفير المالك",
                                         reply_markup=dev_keyboard())
                dev_waiting.pop(user_id, None)
                return True
            bal = await db.get_balance(uid)
            await db.update_balance(uid, -bal)
            await db.add_transaction(generate_transaction_id(), uid,
                                     "reset", -bal, None, "تصفير الرصيد")
            await audit_log(db.pool, user_id, "reset_balance",
                            f"target={uid} amount={bal}")
            await message.reply_text(
                f"💵 *تم التصفير*\n\n👤 {_user_mention(uid)}\n💰 كان: **${bal:.2f}**",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=dev_keyboard()
            )
            dev_waiting.pop(user_id, None)
            return True

        # ═══ 📢 الإذاعة (للمستخدمين) ═══
        if action == "broadcast":
            mode = data.get("mode", "normal")
            dev_waiting.pop(user_id, None)

            users = await db.get_all_users()
            if not users:
                await message.reply_text("❌ لا يوجد مستخدمون",
                                         reply_markup=dev_keyboard())
                return True

            status = await message.reply_text(
                f"📢 جاري الإذاعة...\n"
                f"👥 العدد: `{len(users)}`\n"
                f"🎯 الوضع: `{mode}`"
            )

            success, failed = await run_broadcast(
                client, message, mode, users, status
            )

            mode_names = {
                "normal": "العادية",
                "forward": "بالتوجيه",
                "pin": "بالتثبيت",
            }

            await status.edit_text(
                f"✅ **اكتملت الإذاعة {mode_names.get(mode, '')}**\n"
                f"━━━━━━━━━━━━━━━\n\n"
                f"👥 الإجمالي: `{len(users)}`\n"
                f"✔️ نجح: `{success}`\n"
                f"❌ فشل: `{failed}`",
                reply_markup=dev_keyboard()
            )
            return True

        # ═══ 📱 إذاعة للأرقام ═══
        if action == "nums_broadcast":
            mode = data.get("mode", "normal")
            target = data.get("target", "private")
            dev_waiting.pop(user_id, None)

            try:
                numbers = await db.get_all_numbers(limit=5000)
            except Exception as e:
                logger.error(f"get_all_numbers: {e}")
                await message.reply_text(
                    "❌ فشل جلب الأرقام",
                    reply_markup=dev_keyboard()
                )
                return True

            available_numbers = [
                n for n in numbers
                if n.get('session_enc')
            ]

            if not available_numbers:
                await message.reply_text(
                    "❌ لا توجد أرقام مسجلة بجلسات",
                    reply_markup=dev_keyboard()
                )
                return True

            status = await message.reply_text(
                f"📱 جاري الإذاعة للأرقام...\n"
                f"📊 الأرقام: `{len(available_numbers)}`\n"
                f"🎯 الهدف: `{target}`\n"
                f"📤 الوضع: `{mode}`"
            )

            from Database import decrypt as _decrypt
            from config import API_ID as _API_ID, API_HASH as _API_HASH
            from pyrogram.enums import ChatType

            success = failed = 0
            numbers_sent = 0

            for i, num in enumerate(available_numbers):
                phone = num.get('phone')
                session_enc = num.get('session_enc')
                if not session_enc:
                    failed += 1
                    continue

                lc = None
                try:
                    session_string = _decrypt(session_enc)
                    if not session_string:
                        failed += 1
                        continue

                    lc = Client(
                        f"bc_{i}_{phone[-4:] if phone else '0000'}",
                        api_id=_API_ID,
                        api_hash=_API_HASH,
                        session_string=session_string,
                        in_memory=True
                    )
                    await lc.connect()
                    await asyncio.sleep(0.5)

                    if target in ("private", "both"):
                        try:
                            me = await lc.get_me()
                            ok_send = await send_broadcast_to(
                                lc, me.id, message, mode
                            )
                            if ok_send:
                                numbers_sent += 1
                        except Exception as e:
                            logger.debug(f"private send {phone}: {e}")

                    if target in ("groups", "both"):
                        try:
                            async for dialog in lc.get_dialogs():
                                try:
                                    chat = dialog.chat
                                    if chat.type in (
                                        ChatType.GROUP,
                                        ChatType.SUPERGROUP,
                                    ):
                                        ok_send = await send_broadcast_to(
                                            lc, chat.id, message, mode
                                        )
                                        if ok_send:
                                            numbers_sent += 1
                                        await asyncio.sleep(0.3)
                                except Exception:
                                    continue
                        except Exception as e:
                            logger.debug(f"groups {phone}: {e}")

                    success += 1

                except Exception as e:
                    logger.debug(f"num broadcast {phone}: {e}")
                    failed += 1
                finally:
                    try:
                        if lc and lc.is_connected:
                            await lc.disconnect()
                    except Exception:
                        pass

                if i % 10 == 0:
                    try:
                        await status.edit_text(
                            f"📱 جاري الإذاعة للأرقام...\n"
                            f"📊 التقدم: `{i+1}`/{len(available_numbers)}\n"
                            f"✔️ نجح: `{success}`\n"
                            f"❌ فشل: `{failed}`\n"
                            f"📨 رسائل: `{numbers_sent}`"
                        )
                    except Exception:
                        pass

                await asyncio.sleep(1)

            await status.edit_text(
                f"✅ **اكتملت إذاعة الأرقام**\n"
                f"━━━━━━━━━━━━━━━\n\n"
                f"📊 الإجمالي: `{len(available_numbers)}`\n"
                f"✔️ نجح: `{success}`\n"
                f"❌ فشل: `{failed}`\n"
                f"📨 رسائل مرسلة: `{numbers_sent}`",
                reply_markup=dev_keyboard()
            )
            return True

        # ═══ 🎟️ كوبون ═══
        if action == "coupon":
            text = (message.text or "").strip()
            dev_waiting.pop(user_id, None)
            parts = text.split()
            if len(parts) < 2:
                await message.reply_text("❌ صيغة: `CODE discount [max_uses]`",
                                         parse_mode=ParseMode.MARKDOWN,
                                         reply_markup=dev_keyboard())
                return True
            code = parts[0].upper()
            try:
                discount = int(parts[1])
                max_uses = int(parts[2]) if len(parts) > 2 else 100
            except ValueError:
                await message.reply_text("❌ قيم غير صالحة",
                                         reply_markup=dev_keyboard())
                return True
            await db.add_coupon(code, discount, max_uses)
            await message.reply_text(
                f"✅ كوبون `{code}` — خصم {discount}%",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=dev_keyboard()
            )
            return True

    except Exception as e:
        logger.exception(f"process_dev_text: {e}")
        try:
            await message.reply_text(f"❌ خطأ: {e}")
        except Exception:
            pass
        dev_waiting.pop(user_id, None)
        return True

    return False


# ═══════════════════════════════════════════════════════════
# 🎯 Callbacks لإعداد إذاعة الأرقام
# ═══════════════════════════════════════════════════════════
def register_num_broadcast_callbacks(app: Client):

    @app.on_callback_query(filters.regex(r"^nums_bc_"))
    async def nums_bc_cb(client, cb):
        data = cb.data
        user_id = cb.from_user.id

        if not is_owner_or_admin(user_id):
            await cb.answer("🚫 للمشرفين فقط", show_alert=True)
            return

        if data in (
            "nums_bc_target_private",
            "nums_bc_target_groups",
            "nums_bc_target_both",
        ):
            target_map = {
                "nums_bc_target_private": "private",
                "nums_bc_target_groups": "groups",
                "nums_bc_target_both": "both",
            }
            target = target_map[data]

            dev_waiting[user_id] = {
                "action": "_pending_nums_bc",
                "target": target,
            }

            target_names = {
                "private": "👤 خاص فقط",
                "groups": "👥 مجموعات فقط",
                "both": "🌍 خاص + مجموعات",
            }

            await cb.message.edit_text(
                f"📱 *إذاعة للأرقام*\n"
                f"━━━━━━━━━━━━━━━\n\n"
                f"🎯 الهدف: **{target_names[target]}**\n\n"
                f"📤 اختر نوع الإذاعة:",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(
                        "📢 عادية", callback_data=f"nums_bc_mode_{target}_normal"
                    )],
                    [InlineKeyboardButton(
                        "📤 بالتوجيه", callback_data=f"nums_bc_mode_{target}_forward"
                    )],
                    [InlineKeyboardButton(
                        "📌 بالتثبيت", callback_data=f"nums_bc_mode_{target}_pin"
                    )],
                    [InlineKeyboardButton("❌ إلغاء", callback_data="nums_bc_cancel")],
                ])
            )
            await cb.answer()
            return

        if data.startswith("nums_bc_mode_"):
            parts = data.replace("nums_bc_mode_", "").split("_", 1)
            if len(parts) != 2:
                await cb.answer("❌ خطأ", show_alert=True)
                return
            target, mode = parts
            dev_waiting[user_id] = {
                "action": "nums_broadcast",
                "mode": mode,
                "target": target,
            }

            mode_names = {"normal": "📢 عادية", "forward": "📤 بالتوجيه", "pin": "📌 بالتثبيت"}
            target_names = {
                "private": "👤 خاص فقط",
                "groups": "👥 مجموعات فقط",
                "both": "🌍 خاص + مجموعات",
            }

            await cb.message.edit_text(
                f"📱 *إذاعة للأرقام*\n"
                f"━━━━━━━━━━━━━━━\n\n"
                f"🎯 الهدف: **{target_names.get(target, target)}**\n"
                f"📤 الوضع: **{mode_names.get(mode, mode)}**\n\n"
                f"📝 أرسل الآن الرسالة (نص/صورة/فيديو/ملف/ستيكر...):",
                parse_mode=ParseMode.MARKDOWN
            )
            await cb.answer("✅ أرسل الرسالة الآن")
            return

        if data == "nums_bc_cancel":
            dev_waiting.pop(user_id, None)
            await cb.message.edit_text("❌ تم الإلغاء")
            await cb.answer()
            return


# ═══════════════════════════════════════════════════════════
# 💾 أوامر النسخ الاحتياطي
# ═══════════════════════════════════════════════════════════
def register(app: Client):

    register_num_broadcast_callbacks(app)

    @app.on_message(filters.command("backup_numbers") & dev_filter)
    async def backup_numbers_cmd(client, message: Message):
        msg = await message.reply_text("💾 جاري تجهيز النسخة...")
        try:
            data = await db.export_numbers_backup()
            lines = []
            for item in data:
                line = "|".join([
                    str(item.get("phone", "")),
                    str(item.get("session_enc", "")),
                    str(item.get("seller_id", "")),
                    str(item.get("country", "")),
                    str(item.get("password_2fa_enc", "")),
                    str(item.get("price", "")),
                    str(item.get("status", "")),
                ])
                lines.append(line)
            content = "\n".join(lines)
            file_path = "backup_numbers.txt"
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            await client.send_document(
                message.chat.id, file_path,
                caption=f"💾 نسخة احتياطية للأرقام ({len(data)} رقم)"
            )
            await msg.delete()
        except Exception as e:
            await msg.edit_text(f"❌ فشل: {e}")

    @app.on_message(filters.command("backup_users") & dev_filter)
    async def backup_users_cmd(client, message: Message):
        msg = await message.reply_text("💾 جاري تجهيز نسخة المستخدمين...")
        try:
            users = await db.export_users_txt()
            lines = [
                "=" * 70,
                f"📊 تقرير المستخدمين — {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                f"👥 الإجمالي: {len(users)} مستخدم",
                "=" * 70,
                "",
            ]
            for u in users:
                name = (u.get('first_name') or '؟')
                username = (u.get('username') or '—')
                balance = f"${float(u.get('balance', 0)):.2f}"
                level = u.get('level') or 'normal'
                banned = "🚫" if u.get('is_banned') else "✅"
                lines.append(
                    f"{banned} {u['id']} | {name} | @{username} | {balance} | {level}"
                )
            total_balance = sum(float(u.get('balance', 0)) for u in users)
            banned_count = sum(1 for u in users if u.get('is_banned'))
            lines.extend([
                "",
                "=" * 70,
                f"💰 إجمالي الأرصدة: ${total_balance:.2f}",
                f"🚫 المحظورون: {banned_count}",
                "=" * 70,
            ])
            content = "\n".join(lines)
            file_path = "backup_users.txt"
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            await client.send_document(
                message.chat.id, file_path,
                caption=(
                    f"👥 **نسخة المستخدمين**\n"
                    f"👥 الإجمالي: `{len(users)}`\n"
                    f"💰 الأرصدة: `${total_balance:.2f}`\n"
                    f"🚫 محظورون: `{banned_count}`"
                ),
                parse_mode=ParseMode.MARKDOWN
            )
            await msg.delete()
        except Exception as e:
            logger.exception(f"backup_users: {e}")
            await msg.edit_text(f"❌ فشل: {e}")

    @app.on_message(filters.command("backup_transactions") & dev_filter)
    async def backup_transactions_cmd(client, message: Message):
        msg = await message.reply_text("💾 جاري تجهيز نسخة المعاملات...")
        try:
            txs = await db.get_all_transactions(limit=100000)
            lines = [
                "=" * 70,
                f"📊 تقرير المعاملات — {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                f"📜 الإجمالي: {len(txs)} معاملة",
                "=" * 70,
                "",
            ]
            for tx in txs:
                lines.append(
                    f"{tx.get('id', '')} | {tx.get('user_id', '')} | "
                    f"{tx.get('type', '')} | ${float(tx.get('amount', 0)):.2f} | "
                    f"{tx.get('created_at', '')}"
                )
            content = "\n".join(lines)
            file_path = "backup_transactions.txt"
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            await client.send_document(
                message.chat.id, file_path,
                caption=f"📊 نسخة المعاملات ({len(txs)} معاملة)"
            )
            await msg.delete()
        except Exception as e:
            logger.exception(f"backup_transactions: {e}")
            await msg.edit_text(f"❌ فشل: {e}")

    @app.on_message(filters.command("backup_sessions") & dev_filter)
    async def backup_sessions_cmd(client, message: Message):
        msg = await message.reply_text("💾 جاري تجهيز نسخة الجلسات...")
        try:
            data = await db.export_sessions_backup()
            lines = []
            for item in data:
                line = "|".join([
                    str(item.get("phone", "")),
                    str(item.get("session_enc", "")),
                    str(item.get("password_2fa_enc", "")),
                    str(item.get("country", "")),
                ])
                lines.append(line)
            content = "\n".join(lines)
            file_path = "backup_sessions.txt"
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            await client.send_document(
                message.chat.id, file_path,
                caption=f"💾 نسخة احتياطية للجلسات ({len(data)} جلسة)"
            )
            await msg.delete()
        except Exception as e:
            await msg.edit_text(f"❌ فشل: {e}")

    @app.on_message(filters.command("restore_numbers") & dev_filter)
    async def restore_numbers_cmd(client, message: Message):
        if not message.reply_to_message or not message.reply_to_message.document:
            return await message.reply_text("❌ قم بالرد على ملف txt")
        msg = await message.reply_text("📥 جاري الاستيراد...")
        try:
            path = await message.reply_to_message.download()
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            data = []
            for line in content.strip().split("\n"):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split("|")
                if len(parts) < 7:
                    continue
                data.append({
                    "phone": parts[0],
                    "session_enc": parts[1],
                    "seller_id": int(parts[2]) if parts[2].isdigit() else 0,
                    "country": parts[3] or "غير محدد",
                    "password_2fa_enc": parts[4],
                    "price": float(parts[5]) if parts[5] else 5.0,
                    "status": parts[6] or "available",
                })
            count = await db.import_numbers_backup(data)
            await msg.edit_text(f"✅ تم استيراد {count} رقم من أصل {len(data)}")
        except Exception as e:
            await msg.edit_text(f"❌ فشل: {e}")

    @app.on_message(filters.command("restore_sessions") & dev_filter)
    async def restore_sessions_cmd(client, message: Message):
        if not message.reply_to_message or not message.reply_to_message.document:
            return await message.reply_text("❌ قم بالرد على ملف txt")
        msg = await message.reply_text("📥 جاري الاستيراد...")
        try:
            path = await message.reply_to_message.download()
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            data = []
            for line in content.strip().split("\n"):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split("|")
                if len(parts) < 4:
                    continue
                data.append({
                    "phone": parts[0],
                    "session_enc": parts[1],
                    "password_2fa_enc": parts[2],
                    "country": parts[3] or "غير محدد",
                })
            count = await db.import_sessions_backup(data)
            await msg.edit_text(f"✅ تم استيراد {count} جلسة من أصل {len(data)}")
        except Exception as e:
            await msg.edit_text(f"❌ فشل: {e}")