#لوجيك | Logic وجهتك البرمجية الأولى  بالوطن العربي
#شروحات - أكواد - وأحدث تقنيات برمجية - وحلول تقنية
#بواسطه: t.me/Logii3

#الترخيص: @TopVeGa
#العلامة التجارية: VEGA & Logic
#حقوق الطبع والنشر: © 2015 - 2025

import asyncio
import re
import random
import logging

from pyrogram import Client, filters
from pyrogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardRemove
)
from pyrogram.enums import ParseMode
from pyrogram.errors import (
    SessionPasswordNeeded, PhoneCodeInvalid, PhoneCodeExpired,
    PasswordHashInvalid, FloodWait
)

from config import API_ID, API_HASH, OWNER_ID, FIXED_2FA_PASSWORD, DAILY_BONUS_AMOUNT
from Database import (
    db, encrypt, decrypt, generate_transaction_id,
    safe_send, safe_edit, format_datetime, rate_limited
)
from shop.inform import get_country_from_phone, get_default_price

from shop.play import (
    temp_clients, waiting_for, buy_sessions, active_code_watchers,
    buy_locks,
    change_2fa_password, complete_purchase,
    main_reply_keyboard, dev_reply_keyboard,
    cancel_all_user_operations, cancel_keyboard,
    count_other_sessions, list_other_sessions,
    _verify_2fa, _is_account_2fa_protected,
    watch_for_code, check_subscription,
    send_communication_notice,
)

logger = logging.getLogger(__name__)


def is_valid_phone(phone: str) -> bool:
    return bool(re.match(r'^\+\d{10,15}$', phone))


def rate_keyboard(phone: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⭐1", callback_data=f"rate_1_{phone}"),
            InlineKeyboardButton("⭐2", callback_data=f"rate_2_{phone}"),
            InlineKeyboardButton("⭐3", callback_data=f"rate_3_{phone}"),
            InlineKeyboardButton("⭐4", callback_data=f"rate_4_{phone}"),
            InlineKeyboardButton("⭐5", callback_data=f"rate_5_{phone}"),
        ],
    ])


async def _release_reservation(phone: str, user_id: int):
    try:
        await db.pool.execute(
            "UPDATE numbers SET status='available', buyer_id=NULL, "
            "reserved_until=NULL WHERE phone=$1 AND status='reserved' "
            "AND buyer_id=$2",
            phone, user_id
        )
        logger.info(f"♻️ تم إلغاء حجز {phone}")
    except Exception as e:
        logger.debug(f"release reservation: {e}")


async def start_buy(bot_app, cb, phone: str):
    user_id = cb.from_user.id
    if rate_limited(user_id, max_req=10, window=60):
        await cb.answer("⚠️ طلبات كثيرة، انتظر قليلاً", show_alert=True)
        return

    if phone in buy_locks:
        await cb.answer("⏳ جاري تجهيز الرقم...", show_alert=True)
        return
    buy_locks.add(phone)

    lc = None
    try:
        number = await db.get_number(phone)
        if not number or number['status'] != 'available':
            await cb.answer("❌ الرقم غير متاح", show_alert=True)
            return

        session_enc = number['session_enc']
        if not session_enc:
            await cb.answer("❌ لا توجد جلسة", show_alert=True)
            return

        base_price = float(number['price'])
        discount = await db.get_user_discount(user_id)
        final_price = base_price
        if discount > 0:
            final_price = base_price * (1 - discount / 100)

        balance = await db.get_balance(user_id)
        if balance < final_price:
            await cb.answer(
                f"❌ رصيدك غير كافٍ\n"
                f"تحتاج ${final_price:.2f} ورصيدك ${balance:.2f}",
                show_alert=True
            )
            return

        reserved = await db.reserve_number(phone, user_id, minutes=30)
        if not reserved:
            await cb.answer("❌ الرقم تم حجره", show_alert=True)
            return

        await safe_edit(cb.message, "⏳ *جاري تجهيز الحساب...*",
                        parse_mode=ParseMode.MARKDOWN)

        try:
            session_string = decrypt(session_enc)
            lc = Client(
                f"buy_{user_id}_{random.randint(1000, 9999)}",
                api_id=API_ID, api_hash=API_HASH,
                session_string=session_string, in_memory=True
            )
            await lc.connect()
            me = await lc.get_me()
        except Exception as e:
            logger.exception(f"connect: {e}")
            await _release_reservation(phone, user_id)
            await safe_edit(cb.message, f"❌ فشل الاتصال: {e}")
            if lc:
                try:
                    await lc.disconnect()
                except Exception:
                    pass
            return

        buy_sessions[user_id] = {
            "phone": phone,
            "client": lc,
            "step": "awaiting_login",
            "final_price": final_price,
            "seller_id": number['seller_id'],
        }

        task = asyncio.create_task(
            watch_for_code(bot_app, user_id, phone, lc)
        )
        active_code_watchers[phone] = {
            "client": lc, "buyer_id": user_id, "task": task
        }

        password_2fa_enc = number['password_2fa_enc']
        password_2fa = (
            decrypt(password_2fa_enc) if password_2fa_enc
            else FIXED_2FA_PASSWORD
        )
        if not password_2fa:
            password_2fa = FIXED_2FA_PASSWORD

        await safe_edit(
            cb.message,
            f"✅ **الرقم محجوز لك**\n"
            f"━━━━━━━━━━━━━━━\n\n"
            f"📱 الرقم: `{phone}`\n"
            f"🌍 الدولة: {number['country']}\n"
            f"💰 السعر: **${final_price:.2f}**\n\n"
            f"🔐 كلمة مرور 2FA: `{password_2fa}`\n\n"
            f"⚠️ **مهم جداً:**\n"
            f"1️⃣ افتح تطبيق تليجرام على هاتفك\n"
            f"2️⃣ سجّل دخول بالرقم: `{phone}`\n"
            f"3️⃣ هتستلم الكود هنا في البوت\n"
            f"4️⃣ أدخل كلمة مرور 2FA: `{password_2fa}`\n"
            f"5️⃣ بعدها اضغط **✅ تأكيد الشراء**\n\n"
            f"💰 **ملاحظة:** الفلوس مش هتتخصم غير لما تدخل بنجاح.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(
                    "✅ تأكيد الشراء",
                    callback_data=f"confirm_purchase_{phone}"
                )],
            ])
        )

        try:
            await safe_send(
                bot_app, user_id,
                f"✅ **الرقم محجوز لك**\n\n"
                f"📱 `{phone}`\n"
                f"🔐 2FA: `{password_2fa}`\n\n"
                f"🔑 سجّل دخول بالرقم، بعدها اضغط **✅ تأكيد الشراء**\n\n"
                f"💰 **الفلوس لسه ما اتخصمتش.**",
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception:
            pass

    except Exception as e:
        logger.exception(f"start_buy: {e}")
        if lc:
            try:
                await lc.disconnect()
            except Exception:
                pass
        await _release_reservation(phone, user_id)
        buy_sessions.pop(user_id, None)
        w = active_code_watchers.pop(phone, None)
        if w and w.get("task"):
            w["task"].cancel()
        try:
            await safe_edit(
                cb.message,
                f"❌ فشل تجهيز الحساب: {str(e)[:200]}"
            )
        except Exception:
            pass
    finally:
        buy_locks.discard(phone)


async def show_wallet(client, user_id: int, chat_id: int):
    user = await db.get_user(user_id)
    if not user:
        await safe_send(client, chat_id, "❌ استخدم /start أولاً")
        return
    text = (
        f"👛 *محفظتي*\n"
        f"━━━━━━━━━━━━━━━\n\n"
        f"💰 الرصيد: **${float(user['balance']):.2f}**\n"
        f"⭐ التقييم: {float(user['rating']):.2f}\n"
        f"🛒 المشتريات: {user['total_purchases']}\n"
        f"💰 المبيعات: {user['total_sales']}\n"
        f"🏅 المستوى: {user['level']}"
    )
    await safe_send(
        client, chat_id, text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📜 سجل المعاملات", callback_data="my_tx")],
        ])
    )


async def show_stats(client, user_id: int, chat_id: int):
    user = await db.get_user(user_id)
    if not user:
        await safe_send(client, chat_id, "❌ استخدم /start أولاً")
        return
    txs = await db.get_user_transactions(user_id, limit=1000)
    sales_income = sum(
        float(t['amount']) for t in txs
        if t['type'] == 'sale_income' and float(t['amount']) > 0
    )
    spent = sum(
        abs(float(t['amount'])) for t in txs if t['type'] == 'purchase'
    )
    text = (
        f"📊 *إحصائياتي*\n"
        f"━━━━━━━━━━━━━━━\n\n"
        f"💰 الرصيد: ${float(user['balance']):.2f}\n"
        f"📈 الأرباح: ${sales_income:.2f}\n"
        f"📉 المصروفات: ${spent:.2f}\n"
        f"🛒 المشتريات: {user['total_purchases']}\n"
        f"💰 المبيعات: {user['total_sales']}\n"
        f"⭐ التقييم: {float(user['rating']):.2f}\n"
        f"🏅 المستوى: {user['level']}"
    )
    await safe_send(client, chat_id, text, parse_mode=ParseMode.MARKDOWN)


async def show_history(client, user_id: int, chat_id: int, offset: int = 0):
    txs = await db.get_user_transactions(user_id, limit=15, offset=offset)
    if not txs and offset == 0:
        await safe_send(client, chat_id, "📭 لا توجد معاملات بعد")
        return
    type_emoji = {
        "purchase": "🛒", "sale_income": "💰", "sale_listing": "📤",
        "refund": "↩️", "topup": "📥", "coupon": "🎁", "deposit": "💳",
        "daily_bonus": "🎁",
    }
    lines = [
        f"📜 *آخر معاملاتك* (صفحة {offset//15 + 1})\n━━━━━━━━━━━━━━━\n"
    ]
    for tx in txs:
        emoji = type_emoji.get(tx['type'], "•")
        amount = float(tx['amount'])
        sign = "+" if amount >= 0 else ""
        lines.append(
            f"{emoji} `{sign}${amount:.2f}` — "
            f"{tx['description'] or tx['type']}\n"
            f"   🕐 {format_datetime(tx['created_at'])}\n"
        )
    buttons = []
    nav = []
    if offset > 0:
        nav.append(InlineKeyboardButton(
            "⬅️ السابق", callback_data=f"tx_page_{offset-15}"
        ))
    if len(txs) == 15:
        nav.append(InlineKeyboardButton(
            "➡️ التالي", callback_data=f"tx_page_{offset+15}"
        ))
    if nav:
        buttons.append(nav)
    await safe_send(
        client, chat_id, "\n".join(lines),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(buttons) if buttons else None
    )


def register(app: Client):

    @app.on_message(filters.private & filters.text & ~filters.command([
        "start", "cancel", "wallet", "stats", "history",
        "backup_numbers", "backup_sessions",
        "restore_numbers", "restore_sessions",
    ]))
    async def unified_text_handler(client, message: Message):
        user_id = message.from_user.id
        text = message.text.strip() if message.text else ""

        from shop import Admin as _admin_mod
        is_staff = (user_id == OWNER_ID or user_id in _admin_mod.ADMINS)

        # ═══════════════════════════════════════════════════════════
        # 🚨 0) أزرار التحكم الحرجة — قبل أي شيء
        # ═══════════════════════════════════════════════════════════

        # ❌ إلغاء العملية — أهم زر
        if text == "❌ إلغاء العملية":
            result = await cancel_all_user_operations(
                user_id, disconnect_clients=True
            )
            if is_staff:
                kb = dev_reply_keyboard()
            else:
                kb = main_reply_keyboard()

            cancelled_count = len(result.get("cancelled", []))
            disconnected = result.get("disconnected", 0)
            watchers = result.get("code_watchers_cancelled", 0)

            await message.reply_text(
                f"✅ **تم إلغاء جميع العمليات**\n\n"
                f"📋 العمليات: `{cancelled_count}`\n"
                f"🔌 الجلسات: `{disconnected}`\n"
                f"👁️ المراقبات: `{watchers}`",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=kb
            )
            return

        # ❌ إخفاء الكيبورد
        if text == "❌ إخفاء الكيبورد":
            await message.reply_text(
                "✅ تم إخفاء الكيبورد",
                reply_markup=ReplyKeyboardRemove()
            )
            return

        # 🏠 الرئيسية
        if text == "🏠 الرئيسية":
            from shop.play import send_home, send_dev_home
            if is_staff:
                await send_dev_home(client, message.chat.id)
            else:
                await send_home(client, user_id, message.chat.id)
            return

        # ═══════════════════════════════════════════════════════════
        # 1) محظور؟
        # ═══════════════════════════════════════════════════════════
        if await db.is_banned(user_id):
            await message.reply_text("🚫 أنت محظور")
            return

        # ═══════════════════════════════════════════════════════════
        # 2) تحقق الاشتراك (لغير المطورين)
        # ═══════════════════════════════════════════════════════════
        if not is_staff:
            try:
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
                        "🔒 **يجب الاشتراك في القنوات أولاً**\n"
                        "━━━━━━━━━━━━━━━\n\n"
                        + "\n".join(f"• {ch}" for ch in missing),
                        parse_mode=ParseMode.MARKDOWN,
                        reply_markup=InlineKeyboardMarkup(buttons)
                    )
                    return
            except Exception as e:
                logger.debug(f"check_sub mid: {e}")

        # ═══════════════════════════════════════════════════════════
        # 3) 🔥 نصوص المطور
        # ═══════════════════════════════════════════════════════════
        if user_id in _admin_mod.dev_waiting:
            handled = await _admin_mod.process_dev_text(client, message, user_id)
            if handled:
                return

        # ═══════════════════════════════════════════════════════════
        # 4) أزرار المطور
        # ═══════════════════════════════════════════════════════════
        if is_staff:
            from shop.Admin import process_dev_button
            handled = await process_dev_button(client, message, text)
            if handled:
                return

        # ═══════════════════════════════════════════════════════════
        # 5) 🔥 عمليات المستخدم (waiting_for)
        # ═══════════════════════════════════════════════════════════
        if user_id in waiting_for:
            data = waiting_for[user_id]
            action = data.get("action")

            # ═══ بيع رقم ═══
            if action == "sell_phone":
                phone = text if text.startswith('+') else '+' + text
                if not is_valid_phone(phone):
                    await message.reply_text(
                        "❌ رقم غير صالح\n\n"
                        "أرسل الرقم بصيغة دولية:\n`+20123456789`",
                        parse_mode=ParseMode.MARKDOWN
                    )
                    return

                if await db.get_number(phone):
                    await message.reply_text(
                        "❌ الرقم موجود مسبقاً في البوت",
                        reply_markup=main_reply_keyboard()
                    )
                    waiting_for.pop(user_id, None)
                    return

                msg = await message.reply_text("📤 جاري إرسال الكود...")
                try:
                    lc = Client(
                        f"login_{user_id}_{random.randint(1000, 9999)}",
                        api_id=API_ID, api_hash=API_HASH, in_memory=True
                    )
                    await lc.connect()
                    sent = await lc.send_code(phone)
                    temp_clients[user_id] = lc
                    waiting_for[user_id] = {
                        "action": "sell_code",
                        "phone": phone,
                        "phone_code_hash": sent.phone_code_hash,
                    }
                    await safe_edit(
                        msg,
                        f"✅ تم إرسال الكود\n\n📱 `{phone}`\n\n"
                        f"📝 أرسل الكود الذي وصلك",
                        parse_mode=ParseMode.MARKDOWN
                    )

                except FloodWait as e:
                    await safe_edit(
                        msg,
                        f"⏸️ **تليجرام طلب الانتظار**\n\n"
                        f"⏱️ انتظر `{e.value}` ثانية ثم حاول مرة أخرى.",
                        parse_mode=ParseMode.MARKDOWN
                    )
                    if user_id in temp_clients:
                        try:
                            await temp_clients[user_id].disconnect()
                        except Exception:
                            pass
                        temp_clients.pop(user_id, None)
                    waiting_for.pop(user_id, None)

                except Exception as e:
                    err = str(e).lower()
                    if "phone_number_invalid" in err:
                        friendly = (
                            "❌ **رقم الهاتف غير صحيح**\n"
                            "━━━━━━━━━━━━━━━\n\n"
                            "⚠️ **الأسباب المحتملة:**\n"
                            "• الرقم غير مسجّل في تليجرام\n"
                            "• الرقم وهمي أو تجريبي\n"
                            "• صيغة الرقم خاطئة\n\n"
                            "📝 **تأكد من:**\n"
                            "• الرقم بصيغة دولية: `+20123456789`\n"
                            "• كود الدولة صحيح\n"
                            "• الرقم حقيقي ومسجّل\n\n"
                            "💡 جرّب رقم آخر."
                        )
                    elif "phone_number_banned" in err:
                        friendly = (
                            "🚫 **الرقم محظور من تليجرام**\n\n"
                            "لا يمكن استخدام هذا الرقم."
                        )
                    elif "phone_number_flood" in err:
                        friendly = (
                            "⏸️ **محاولات كثيرة جداً**\n\n"
                            "انتظر 24 ساعة ثم حاول مجدداً."
                        )
                    else:
                        friendly = f"❌ **فشل إرسال الكود**\n\n`{str(e)[:150]}`"

                    await safe_edit(msg, friendly, parse_mode=ParseMode.MARKDOWN)
                    if user_id in temp_clients:
                        try:
                            await temp_clients[user_id].disconnect()
                        except Exception:
                            pass
                        temp_clients.pop(user_id, None)
                    waiting_for.pop(user_id, None)
                return

            # ═══ كود البيع ═══
            if action == "sell_code":
                code = re.sub(r'\D', '', text)
                if len(code) < 4:
                    await message.reply_text("❌ كود غير صالح")
                    return

                msg = await message.reply_text("🔐 جاري التحقق...")
                phone = data["phone"]
                pch = data["phone_code_hash"]
                lc = temp_clients.get(user_id)
                if not lc:
                    await safe_edit(msg, "❌ انتهت الجلسة")
                    waiting_for.pop(user_id, None)
                    return

                try:
                    await lc.sign_in(phone, pch, code)
                    me = await lc.get_me()
                    is_protected = await _is_account_2fa_protected(lc)
                    new_pass = FIXED_2FA_PASSWORD

                    if is_protected:
                        waiting_for[user_id] = {
                            "action": "sell_password",
                            "phone": phone,
                            "phone_code_hash": pch,
                        }
                        await safe_edit(
                            msg,
                            "🔐 **الحساب محمي بكلمة مرور (2FA)**\n\n"
                            "📝 أرسل كلمة المرور الحالية",
                            parse_mode=ParseMode.MARKDOWN
                        )
                        return

                    await safe_edit(msg, "🔐 جاري إعداد كلمة مرور الحساب...")
                    ok, msg2, new_pass_result = await change_2fa_password(lc)
                    if ok and new_pass_result:
                        new_pass = new_pass_result

                    try:
                        others = await count_other_sessions(lc)
                    except Exception as e:
                        logger.exception(f"sell_code count FAILED: {e}")
                        await safe_edit(msg, "❌ **فشل فحص الجلسات**")
                        waiting_for.pop(user_id, None)
                        if user_id in temp_clients:
                            try:
                                await temp_clients[user_id].disconnect()
                            except Exception:
                                pass
                            temp_clients.pop(user_id, None)
                        return

                    session_string = await lc.export_session_string()
                    country = get_country_from_phone(phone)
                    buy_price = get_default_price(country)

                    try:
                        if await db.is_number_premium(phone):
                            buy_price = 20.0
                    except Exception:
                        pass

                    waiting_for[user_id] = {
                        "action": "sell_confirm",
                        "phone": phone,
                        "session_enc": encrypt(session_string),
                        "two_fa_enc": encrypt(new_pass or ""),
                        "country": country,
                        "buy_price": buy_price,
                        "client": lc,
                    }

                    kb = InlineKeyboardMarkup([[
                        InlineKeyboardButton(
                            "✅ تأكيد عملية بيع",
                            callback_data=f"confirm_sell_{phone}"
                        )
                    ]])

                    warning = ""
                    if others > 0:
                        warning = (
                            f"\n\n⚠️ **تنبيه:** يوجد **{others}** جلسة.\n"
                            f"اخرج منها قبل التأكيد."
                        )

                    premium_tag = "💎 **رقم مميز**\n\n" if buy_price >= 20.0 else ""

                    await safe_edit(
                        msg,
                        f"{premium_tag}"
                        f"💰 *عرض شراء من البوت*\n"
                        f"━━━━━━━━━━━━━━━\n\n"
                        f"📱 الرقم: `{phone}`\n"
                        f"🌍 الدولة: {country}\n"
                        f"💵 السعر: **${buy_price:.2f}**\n\n"
                        f"⚠️ اخرج من كل الأجهزة" + warning,
                        parse_mode=ParseMode.MARKDOWN,
                        reply_markup=kb
                    )

                except SessionPasswordNeeded:
                    waiting_for[user_id] = {
                        "action": "sell_password",
                        "phone": phone,
                        "phone_code_hash": pch,
                    }
                    await safe_edit(
                        msg,
                        "🔐 **الحساب محمي (2FA)**\n\n📝 أرسل كلمة المرور",
                        parse_mode=ParseMode.MARKDOWN
                    )
                except PhoneCodeInvalid:
                    await safe_edit(msg, "❌ الكود غير صحيح\nحاول مرة أخرى:")
                except PhoneCodeExpired:
                    await safe_edit(msg, "❌ انتهت صلاحية الكود")
                    waiting_for.pop(user_id, None)
                    if user_id in temp_clients:
                        try:
                            await temp_clients[user_id].disconnect()
                        except Exception:
                            pass
                        temp_clients.pop(user_id, None)
                except Exception as e:
                    logger.exception(f"sell_code: {e}")
                    await safe_edit(msg, f"❌ خطأ: {e}")
                    waiting_for.pop(user_id, None)
                    if user_id in temp_clients:
                        try:
                            await temp_clients[user_id].disconnect()
                        except Exception:
                            pass
                        temp_clients.pop(user_id, None)
                return

            # ═══ كلمة المرور للبيع ═══
            if action == "sell_password":
                password = text.strip()
                msg = await message.reply_text("🔐 جاري التحقق...")
                phone = data["phone"]
                lc = temp_clients.get(user_id)
                if not lc:
                    await safe_edit(msg, "❌ انتهت الجلسة")
                    waiting_for.pop(user_id, None)
                    return

                try:
                    await lc.check_password(password)
                    await safe_edit(msg, "🔐 جاري تغيير كلمة المرور...")
                    ok, msg2, new_pass = await change_2fa_password(
                        lc, current_password=password
                    )
                    if not ok or not new_pass:
                        await safe_edit(msg, f"⚠️ **تحذير:** {msg2}")
                        waiting_for.pop(user_id, None)
                        if user_id in temp_clients:
                            try:
                                await temp_clients[user_id].disconnect()
                            except Exception:
                                pass
                            temp_clients.pop(user_id, None)
                        return

                    try:
                        others = await count_other_sessions(lc)
                    except Exception as e:
                        logger.exception(f"sell_password count FAILED: {e}")
                        await safe_edit(msg, "❌ **فشل فحص الجلسات**")
                        waiting_for.pop(user_id, None)
                        if user_id in temp_clients:
                            try:
                                await temp_clients[user_id].disconnect()
                            except Exception:
                                pass
                            temp_clients.pop(user_id, None)
                        return

                    session_string = await lc.export_session_string()
                    country = get_country_from_phone(phone)
                    buy_price = get_default_price(country)

                    try:
                        if await db.is_number_premium(phone):
                            buy_price = 20.0
                    except Exception:
                        pass

                    waiting_for[user_id] = {
                        "action": "sell_confirm",
                        "phone": phone,
                        "session_enc": encrypt(session_string),
                        "two_fa_enc": encrypt(new_pass or ""),
                        "country": country,
                        "buy_price": buy_price,
                        "client": lc,
                    }

                    kb = InlineKeyboardMarkup([[
                        InlineKeyboardButton(
                            "✅ تأكيد عملية بيع",
                            callback_data=f"confirm_sell_{phone}"
                        )
                    ]])

                    warning = ""
                    if others > 0:
                        warning = f"\n\n⚠️ **{others}** جلسة نشطة."

                    premium_tag = "💎 **رقم مميز**\n\n" if buy_price >= 20.0 else ""

                    await safe_edit(
                        msg,
                        f"{premium_tag}"
                        f"💰 *عرض شراء*\n"
                        f"━━━━━━━━━━━━━━━\n\n"
                        f"📱 `{phone}`\n"
                        f"🌍 {country}\n"
                        f"💵 **${buy_price:.2f}**"
                        + warning,
                        parse_mode=ParseMode.MARKDOWN,
                        reply_markup=kb
                    )
                except PasswordHashInvalid:
                    await safe_edit(
                        msg, "❌ كلمة المرور غير صحيحة\nحاول مرة أخرى:"
                    )
                except Exception as e:
                    logger.exception(f"sell_password: {e}")
                    await safe_edit(msg, f"❌ خطأ: {e}")
                return

            # ═══ طلب مخصص ═══
            if action == "custom_order_country":
                waiting_for[user_id] = {
                    "action": "custom_order_price",
                    "country": text,
                }
                await message.reply_text(
                    f"✅ الدولة: {text}\n\n💵 أرسل الحد الأقصى"
                )
                return

            if action == "custom_order_price":
                try:
                    max_price = float(text.replace('$', '').strip())
                except ValueError:
                    await message.reply_text("❌ سعر غير صالح")
                    return
                country = data["country"]
                await db.add_pending_request(user_id, country, max_price)
                waiting_for.pop(user_id, None)
                await message.reply_text(
                    f"✅ *تم تسجيل طلبك!*\n\n"
                    f"🌍 {country}\n💵 ${max_price:.2f}",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=main_reply_keyboard()
                )
                return

            # ═══ بحث ═══
            if action == "search_query":
                results = await db.search_numbers(text.strip(), limit=30)
                waiting_for.pop(user_id, None)
                if not results:
                    await message.reply_text(
                        "❌ لا توجد نتائج",
                        reply_markup=main_reply_keyboard()
                    )
                    return
                lines = [f"🔍 *نتائج* ({len(results)})\n"]
                buttons = []
                for n in results[:20]:
                    lines.append(
                        f"📱 `{n['phone']}` — ${float(n['price']):.2f}"
                    )
                    buttons.append([InlineKeyboardButton(
                        f"📱 {n['phone']}",
                        callback_data=f"view_number_{n['phone']}"
                    )])
                await message.reply_text(
                    "\n".join(lines),
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=InlineKeyboardMarkup(buttons)
                )
                return

            # ═══ مراقبة ═══
            if action == "watch_pattern":
                pattern = text.strip()
                if not pattern.startswith('+'):
                    pattern = '+' + pattern
                await db.add_to_watchlist(user_id, pattern)
                waiting_for.pop(user_id, None)
                await message.reply_text(
                    f"👁️ تم إضافة {pattern}",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=main_reply_keyboard()
                )
                return

            # ═══ تذكرة ═══
            if action == "ticket_subject":
                ticket_id = await db.create_ticket(user_id, text.strip())
                await db.add_ticket_message(ticket_id, user_id, text.strip())
                waiting_for.pop(user_id, None)
                await message.reply_text(
                    f"🎫 *تذكرة #{ticket_id}*",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=main_reply_keyboard()
                )
                return

        # ═══════════════════════════════════════════════════════════
        # 6) أزرار المستخدم العادية
        # ═══════════════════════════════════════════════════════════
        if text == "🛒 شراء رقم":
            from shop.callbacks import show_countries
            await show_countries(client, message.chat.id)
            return

        if text == "💰 بيع رقم":
            waiting_for[user_id] = {"action": "sell_phone"}
            await message.reply_text(
                "💰 *بيع رقم*\n\n"
                "📱 أرسل رقم الهاتف:\n"
                "مثال: `+20123456789`\n\n"
                "❌ للإلغاء: زر **❌ إلغاء العملية**",
                parse_mode=ParseMode.MARKDOWN
            )
            return

        if text == "👛 محفظتي":
            await show_wallet(client, user_id, message.chat.id)
            return

        if text == "📊 إحصائياتي":
            await show_stats(client, user_id, message.chat.id)
            return

        if text == "📜 سجل معاملاتي":
            await show_history(client, user_id, message.chat.id)
            return

        if text == "🔔 طلب مخصص":
            waiting_for[user_id] = {"action": "custom_order_country"}
            await message.reply_text("🔔 أرسل الدولة",
                                     parse_mode=ParseMode.MARKDOWN)
            return

        if text == "🔍 بحث":
            waiting_for[user_id] = {"action": "search_query"}
            await message.reply_text("🔍 أرسل جزءاً من الرقم",
                                     parse_mode=ParseMode.MARKDOWN)
            return

        if text == "👥 الإحالة":
            stats = await db.get_referral_stats(user_id)
            if not stats:
                await message.reply_text("❌ حدث خطأ")
                return
            me = await client.get_me()
            link = f"https://t.me/{me.username}?start=ref_{stats['code']}"
            await message.reply_text(
                f"👥 *الإحالة*\n\n"
                f"🔗 `{link}`\n\n"
                f"👤 {stats['count']}\n💰 ${stats['earnings']:.2f}",
                parse_mode=ParseMode.MARKDOWN
            )
            return

        if text == "👁️ مراقبة":
            waiting_for[user_id] = {"action": "watch_pattern"}
            await message.reply_text("👁️ أرسل البادئة",
                                     parse_mode=ParseMode.MARKDOWN)
            return

        if text == "🎁 مكافأة يومية":
            ok = await db.claim_daily_bonus(user_id, amount=DAILY_BONUS_AMOUNT)
            if ok:
                await message.reply_text(f"🎁 تم إضافة ${DAILY_BONUS_AMOUNT:.2f}")
            else:
                await message.reply_text("⏰ حصلت عليها اليوم")
            return

        if text == "🎫 الدعم":
            waiting_for[user_id] = {"action": "ticket_subject"}
            await message.reply_text("🎫 أرسل موضوع المشكلة",
                                     parse_mode=ParseMode.MARKDOWN)
            return

        if text == "💳 إيداع":
            await message.reply_text(
                "💳 اختر طريقة الإيداع:",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(
                        "💵 USDT (TRC20)", callback_data="deposit_usdt"
                    )],
                    [InlineKeyboardButton(
                        "📱 فودافون كاش", callback_data="deposit_vodafone"
                    )],
                    [InlineKeyboardButton(
                        "⭐ Telegram Stars", callback_data="deposit_stars"
                    )],
                ])
            )
            return

        if text == "📢 قنوات الاشتراك":
            channels = await db.get_required_channels()
            if not channels:
                await message.reply_text("📢 لا توجد قنوات")
                return
            buttons = []
            for ch in channels:
                uname = ch['channel_username'].lstrip('@')
                title = ch.get('channel_title') or uname
                buttons.append([InlineKeyboardButton(
                    f"📢 {title}",
                    url=f"https://t.me/{uname}"
                )])
            await message.reply_text(
                "📢 *القنوات*",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(buttons)
            )
            return

        if text == "👑 لوحة المطور":
            if is_staff:
                from shop.play import send_dev_home
                await send_dev_home(client, message.chat.id)
            return

        # ═══════════════════════════════════════════════════════════
        # 7) rate limit
        # ═══════════════════════════════════════════════════════════
        if rate_limited(user_id, max_req=20, window=60):
            await message.reply_text("⚠️ طلبات كثيرة")
            return

        # ═══════════════════════════════════════════════════════════
        # 8) 💬 التواصل — بدون فتح كيبورد
        # ═══════════════════════════════════════════════════════════
        if not is_staff and text and not text.startswith("/"):
            try:
                await send_communication_notice(
                    client, user_id, message=message
                )
                await message.reply_text(
                    "📩 **تم إرسال رسالتك للإدارة**\n\n"
                    "سيتم الرد عليك قريباً."
                )
                return
            except Exception as e:
                logger.debug(f"comm notice: {e}")

        # ═══════════════════════════════════════════════════════════
        # 9) أمر غير معروف — بدون فتح كيبورد
        # ═══════════════════════════════════════════════════════════
        if is_staff:
            await message.reply_text("❓ أمر غير معروف")
        else:
            await message.reply_text(
                "❓ أمر غير معروف\n\n"
                "💡 استخدم /start لعرض الأزرار."
            )

    # ═══════════════════════════════════════════════════════════
    # 📩 معالج رد المالك
    # ═══════════════════════════════════════════════════════════
    @app.on_message(
        filters.private & filters.user(OWNER_ID) & filters.reply,
        group=21
    )
    async def owner_reply_handler(client, message: Message):
        try:
            replied_id = message.reply_to_message.id
            record = await db.get_twasl_by_owner_msg(replied_id)
            if not record:
                return
            target_user = record['user_id']
            try:
                await client.copy_message(
                    chat_id=target_user,
                    from_chat_id=message.chat.id,
                    message_id=message.id
                )
                name = record.get('user_first_name') or "مستخدم"
                await message.reply(
                    f"✅ تم الإرسال إلى "
                    f"[{name}](tg://user?id={target_user})",
                    parse_mode=ParseMode.MARKDOWN
                )
            except Exception as e:
                await message.reply(f"❌ خطأ في الإرسال: {e}")
        except Exception as e:
            logger.debug(f"owner_reply_handler: {e}")

    # ═══════════════════════════════════════════════════════════
    # 💬 أوامر التواصل للمالك
    # ═══════════════════════════════════════════════════════════
    @app.on_message(
        filters.private & filters.user(OWNER_ID) &
        filters.text & filters.regex(r"^(تفعيل التواصل|تعطيل التواصل)$"),
        group=22
    )
    async def owner_comm_cmd(client, message: Message):
        text = message.text.strip()
        if text == "تفعيل التواصل":
            await db.enable_owner_comm(OWNER_ID)
            await message.reply("✅ تم تفعيل التواصل")
        elif text == "تعطيل التواصل":
            await db.disable_owner_comm(OWNER_ID)
            await message.reply("🔇 تم تعطيل التواصل")

    # ═══════════════════════════════════════════════════════════
    # 📋 أوامر مساعدة
    # ═══════════════════════════════════════════════════════════
    @app.on_message(filters.command("wallet"))
    async def wallet_cmd(client, message: Message):
        await show_wallet(client, message.from_user.id, message.chat.id)

    @app.on_message(filters.command("stats"))
    async def stats_cmd(client, message: Message):
        await show_stats(client, message.from_user.id, message.chat.id)

    @app.on_message(filters.command("history"))
    async def history_cmd(client, message: Message):
        await show_history(client, message.from_user.id, message.chat.id)