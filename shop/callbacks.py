#لوجيك | Logic وجهتك البرمجية الأولى  بالوطن العربي
#شروحات - أكواد - وأحدث تقنيات برمجية - وحلول تقنية
#بواسطه: t.me/Logii3

#الترخيص: @TopVeGa
#العلامة التجارية: VEGA & Logic
#حقوق الطبع والنشر: © 2015 - 2025


import asyncio
import logging
import os
from datetime import datetime, timedelta
from pyrogram import Client
from pyrogram.types import (
    CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
)
from pyrogram.enums import ParseMode
from pyrogram.errors import MessageNotModified

from shop.play import (
    send_home, send_dev_home, waiting_for, buy_sessions,
    active_code_watchers, temp_clients,
    main_reply_keyboard, dev_reply_keyboard,
    get_otp_for_number, confirm_purchase_session,
    _verify_2fa, _is_account_2fa_protected, _is_bot_session,
    verify_buyer_login, decrypt, list_other_sessions,
    count_other_sessions, check_number_sessions_for_buy,
    _extract_code_from_text,
    terminate_bot_session, fetch_latest_otp, pre_delivery_check,
    check_subscription,
)
from config import (
    OWNER_ID, FIXED_2FA_PASSWORD, DAILY_BONUS_AMOUNT, API_ID, API_HASH,
    CHANNEL_BOT, BOT_NAME, NUMBER_NAME, NUMBER_BIO, NUMBER_PHOTO_PATH,
    BOT_USERNAME, GROUPS_TO_JOIN,
)
from Database import (
    db, safe_edit, safe_send, generate_transaction_id,
    rate_limited, audit_log,
)
from shop.Botpay import (
    start_buy, show_wallet, show_stats, show_history
)

logger = logging.getLogger(__name__)

TELEGRAM_SERVICE_IDS = [777000, 42777, 333000]


def _admin_mod_admins():
    try:
        from shop import Admin as _m
        return _m.ADMINS
    except Exception:
        return set()


def _is_staff(user_id: int) -> bool:
    return user_id == OWNER_ID or user_id in _admin_mod_admins()


async def _check_sub_or_alert(client, cb, user_id: int) -> bool:
    """يرجع True لو مسموح بالمرور، False لو تم حجبه"""
    if _is_staff(user_id):
        return True
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
            try:
                await cb.message.reply_text(
                    "🔒 **يجب الاشتراك في القنوات أولاً**\n"
                    "━━━━━━━━━━━━━━━\n\n"
                    + "\n".join(f"• {ch}" for ch in missing),
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=InlineKeyboardMarkup(buttons)
                )
            except Exception:
                pass
            await cb.answer("🔒 اشترك أولاً", show_alert=True)
            return False
    except Exception as e:
        logger.debug(f"_check_sub: {e}")
    return True


# ═══════════════════════════════════════════════════════════
# ✅ دالة تجهيز الحساب الجديد
# ═══════════════════════════════════════════════════════════
async def setup_new_number_account(client_obj: Client, phone: str) -> dict:
    result = {
        "name_changed": False,
        "bio_changed": False,
        "photo_changed": False,
        "joined_channels": [],
        "failed_channels": [],
        "errors": [],
    }
    
    try:
        if not client_obj.is_connected:
            await client_obj.connect()
            await asyncio.sleep(2)
    except Exception as e:
        result["errors"].append(f"connect: {e}")
        return result
    
    try:
        await client_obj.update_profile(first_name=NUMBER_NAME, last_name="")
        result["name_changed"] = True
        logger.info(f"✅ تم تغيير اسم {phone}")
    except Exception as e:
        result["errors"].append(f"name: {e}")
    
    await asyncio.sleep(1)
    
    try:
        await client_obj.update_profile(bio=NUMBER_BIO)
        result["bio_changed"] = True
        logger.info(f"✅ تم تغيير بايو {phone}")
    except Exception as e:
        result["errors"].append(f"bio: {e}")
    
    await asyncio.sleep(1)
    
    try:
        if os.path.exists(NUMBER_PHOTO_PATH):
            await client_obj.set_profile_photo(photo=NUMBER_PHOTO_PATH)
            result["photo_changed"] = True
            logger.info(f"✅ تم تغيير صورة {phone}")
    except Exception as e:
        result["errors"].append(f"photo: {e}")
    
    await asyncio.sleep(1)
    
    for channel in GROUPS_TO_JOIN:
        try:
            await client_obj.join_chat(channel)
            result["joined_channels"].append(channel)
            logger.info(f"✅ {phone} انضم لـ {channel}")
            await asyncio.sleep(2)
        except Exception as e:
            err = str(e).lower()
            if "already" in err or "participant" in err:
                result["joined_channels"].append(channel)
            else:
                result["failed_channels"].append(channel)
    
    return result


async def notify_channel(client, text: str, reply_markup=None):
    try:
        channel = CHANNEL_BOT
        if not channel.startswith("@") and not channel.startswith("-"):
            channel = "@" + channel
        await client.send_message(
            channel, text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup,
            disable_web_page_preview=True,
        )
        logger.info(f"✅ تم إرسال إشعار للقناة {channel}")
        return True
    except Exception as e:
        logger.error(f"❌ فشل إرسال للقناة: {e}")
        return False


async def show_countries(client, chat_id: int, message_to_edit=None):
    countries = await db.get_available_countries()
    if not countries:
        text = (
            "🛒 *شراء رقم*\n\n❌ لا توجد أرقام متاحة حالياً\n\n"
            "💡 يمكنك بيع رقمك أولاً"
        )
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("💰 بيع رقم", callback_data="sell_number")],
        ])
        if message_to_edit:
            await safe_edit(message_to_edit, text,
                            parse_mode=ParseMode.MARKDOWN, reply_markup=markup)
        else:
            await safe_send(client, chat_id, text,
                            parse_mode=ParseMode.MARKDOWN, reply_markup=markup)
        return

    total = sum(countries.values())
    text = (
        f"🛒 *اختر الدولة*\n━━━━━━━━━━━━━━━\n\n"
        f"📊 المتاح: {total} رقم\n\nاختر الدولة:"
    )
    buttons = [
        [InlineKeyboardButton(f"{c} ({n})", callback_data=f"country_{c}")]
        for c, n in sorted(countries.items(), key=lambda x: -x[1])
    ]
    if message_to_edit:
        await safe_edit(message_to_edit, text,
                        parse_mode=ParseMode.MARKDOWN,
                        reply_markup=InlineKeyboardMarkup(buttons))
    else:
        await safe_send(client, chat_id, text,
                        parse_mode=ParseMode.MARKDOWN,
                        reply_markup=InlineKeyboardMarkup(buttons))


async def show_country_numbers(client, cb: CallbackQuery, country: str):
    numbers = await db.get_numbers_by_country(country)
    if not numbers:
        await cb.answer("❌ لا توجد أرقام", show_alert=True)
        return
    text = (
        f"🌍 *{country}*\n━━━━━━━━━━━━━━━\n\n"
        f"📊 المتاح: {len(numbers)} رقم\n\nاختر رقماً:"
    )
    buttons = []
    for num in numbers[:25]:
        buttons.append([InlineKeyboardButton(
            f"📱 {num['phone']} — ${float(num['price']):.2f}",
            callback_data=f"view_number_{num['phone']}"
        )])
    buttons.append([InlineKeyboardButton("🔙 رجوع", callback_data="buy_number")])
    await safe_edit(cb.message, text, parse_mode=ParseMode.MARKDOWN,
                    reply_markup=InlineKeyboardMarkup(buttons))


async def show_number_details(client, cb: CallbackQuery, phone: str):
    number = await db.get_number(phone)
    if not number:
        await cb.answer("❌ الرقم غير موجود", show_alert=True)
        return
    if number['status'] != 'available':
        await cb.answer("❌ الرقم غير متاح", show_alert=True)
        return
    seller = await db.get_user(number['seller_id'])
    seller_rating = float(seller['rating']) if seller else 5.0
    text = (
        f"📱 *تفاصيل الرقم*\n━━━━━━━━━━━━━━━\n\n"
        f"📞 الرقم: `{phone}`\n"
        f"🌍 الدولة: {number['country']}\n"
        f"💰 السعر: **${float(number['price']):.2f}**\n"
        f"⭐ تقييم البائع: {seller_rating:.2f}\n"
        f"📌 الحالة: ✅ متاح"
    )
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ تأكيد الشراء",
                              callback_data=f"confirm_purchase_{phone}")],
        [InlineKeyboardButton("🔙 رجوع",
                              callback_data=f"country_{number['country']}")],
    ])
    await safe_edit(cb.message, text, parse_mode=ParseMode.MARKDOWN,
                    reply_markup=markup)


async def handle_rating(client, cb: CallbackQuery, phone: str, rating: int):
    user_id = cb.from_user.id
    number = await db.get_number(phone)

    if not number:
        completed = await db.get_completed_purchase(phone, user_id)
        if not completed:
            await cb.answer("❌ لا يمكنك تقييم هذا الرقم", show_alert=True)
            return
        if completed.get("rated"):
            await cb.answer("⚠️ قيّمت هذا الرقم من قبل", show_alert=True)
            return
        seller_id = completed['seller_id']
    else:
        if number['buyer_id'] != user_id:
            await cb.answer("❌ لا يمكنك تقييم هذا الرقم", show_alert=True)
            return
        seller_id = number['seller_id']

    try:
        await db.add_review(user_id, seller_id, phone, rating)
        try:
            await db.mark_purchase_rated(phone, user_id)
        except Exception:
            pass
    except Exception as e:
        logger.exception(f"add_review: {e}")
        await cb.answer("❌ فشل حفظ التقييم", show_alert=True)
        return

    await cb.answer(f"✅ شكراً لتقييمك {rating}⭐", show_alert=True)
    try:
        await safe_send(
            client, seller_id,
            f"⭐ *تقييم جديد!*\n\n📱 `{phone}`\n{'⭐' * rating}",
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception:
        pass
    try:
        await safe_edit(
            cb.message,
            f"✅ *شكراً لك!*\n\nتم تسجيل تقييمك {rating}⭐",
            parse_mode=ParseMode.MARKDOWN
        )
    except MessageNotModified:
        pass


async def _handle_confirm_sell(client, cb, phone: str, user_id: int):
    if rate_limited(user_id, max_req=5, window=60):
        await cb.answer("⚠️ طلبات كثيرة", show_alert=True)
        return

    w = waiting_for.get(user_id, {})
    if w.get("action") != "sell_confirm" or w.get("phone") != phone:
        await cb.answer("❌ لا توجد عملية بيع نشطة", show_alert=True)
        return

    session_enc = w.get("session_enc")
    two_fa_enc = w.get("two_fa_enc")
    buy_price = float(w.get("buy_price", 0))
    country = w.get("country", "غير محدد")
    lc = w.get("client")

    if not session_enc or not lc:
        await cb.answer("❌ بيانات الجلسة مفقودة", show_alert=True)
        waiting_for.pop(user_id, None)
        return

    await cb.answer("⏳ جاري الفحص...", show_alert=False)
    try:
        await safe_edit(
            cb.message,
            "⏳ *جاري فحص الجلسات لحظياً...*",
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception:
        pass

    try:
        if not lc.is_connected:
            await lc.connect()
            await asyncio.sleep(2)
    except Exception as e:
        logger.exception(f"reconnect: {e}")
        await cb.answer("❌ فشل الاتصال", show_alert=True)
        return

    new_pass = FIXED_2FA_PASSWORD
    if two_fa_enc:
        try:
            decrypted = decrypt(two_fa_enc)
            if decrypted and decrypted.strip():
                new_pass = decrypted
        except Exception:
            pass

    try:
        is_protected = await _is_account_2fa_protected(lc)
        if not is_protected:
            await cb.answer("❌ الحساب غير محمي بـ 2FA", show_alert=True)
            return
        ok_2fa = await _verify_2fa(lc, new_pass)
        if not ok_2fa:
            await cb.answer("❌ كلمة مرور 2FA غير صحيحة", show_alert=True)
            return
    except Exception as e:
        logger.exception(f"verify 2fa: {e}")
        await cb.answer("❌ فشل التحقق من 2FA", show_alert=True)
        return

    try:
        real_sessions = await list_other_sessions(lc)
        others = len(real_sessions)
        logger.info(f"🔎 فحص لحظي {phone}: {others} جلسة")
    except Exception as e:
        logger.exception(f"list_other_sessions FAILED: {e}")
        await cb.answer("❌ فشل فحص الجلسات", show_alert=True)
        return

    if others > 0:
        lines = []
        for i, s in enumerate(real_sessions[:10], 1):
            lines.append(
                f"*{i}.* 📱 `{s.get('device', '?')}`\n"
                f"   └ {s.get('app', '?')} — {s.get('system', '?')}"
            )

        warn_msg = (
            f"⚠️ **تنبيه: يوجد جلسات نشطة**\n"
            f"━━━━━━━━━━━━━━━\n\n"
            f"📞 الرقم: `{phone}`\n"
            f"🔢 عدد الجلسات: **{others}**\n\n"
            f"**الأجهزة:**\n" + "\n".join(lines) +
            f"\n\n🚪 **اخرج من كل الجلسات الأول**\n"
            f"ثم اضغط **🔄 إعادة الفحص**"
        )

        await cb.answer(f"⚠️ {others} جلسة نشطة", show_alert=True)
        try:
            await safe_send(client, user_id, warn_msg,
                            parse_mode=ParseMode.MARKDOWN)
        except Exception:
            pass

        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(
                "🔄 إعادة الفحص",
                callback_data=f"confirm_sell_{phone}"
            )],
            [InlineKeyboardButton(
                "❌ إلغاء البيع",
                callback_data="cancel_sell"
            )],
        ])
        try:
            await safe_edit(
                cb.message,
                f"⚠️ **{others} جلسة نشطة**\n\n🚪 اخرج منها ثم أعد الفحص",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=kb
            )
        except Exception:
            pass
        return

    sell_price = buy_price * 2

    try:
        await safe_edit(
            cb.message,
            "⚙️ *جاري تجهيز الحساب...*\n\n"
            "🖼️ الصورة\n📝 الاسم والبايو\n📢 القنوات\n\n"
            "⏳ قد يستغرق 30 ثانية...",
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception:
        pass

    setup_result = await setup_new_number_account(lc, phone)
    logger.info(f"🔧 تجهيز {phone}: {setup_result}")

    try:
        added = await db.add_number(
            phone, session_enc, user_id,
            country, two_fa_enc, sell_price
        )
        if not added:
            await cb.answer("❌ الرقم موجود", show_alert=True)
            waiting_for.pop(user_id, None)
            return
    except Exception as e:
        logger.exception(f"add_number: {e}")
        await cb.answer("❌ فشل الحفظ", show_alert=True)
        return

    try:
        await db.update_balance(user_id, buy_price)
        await db.increment_stat(user_id, "total_sales")
        await db.add_transaction(
            generate_transaction_id(), user_id,
            "sale_income", buy_price, phone,
            f"بيع رقم للبوت بـ ${buy_price:.2f}"
        )
    except Exception as e:
        logger.exception(f"balance: {e}")

    try:
        await safe_send(
            client, user_id,
            f"✅ **تم بيع الرقم بنجاح!**\n"
            f"━━━━━━━━━━━━━━━\n\n"
            f"📱 `{phone}`\n"
            f"🌍 {country}\n"
            f"💵 **+${buy_price:.2f}**\n\n"
            f"🔒 0 جلسات\n"
            f"⚙️ تم تجهيز الحساب",
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception:
        pass

    try:
        await notify_channel(
            client,
            f"🆕 **رقم جديد متاح للبيع!**\n"
            f"━━━━━━━━━━━━━━━\n\n"
            f"📱 الرقم: `{phone}`\n"
            f"🌍 الدولة: {country}\n"
            f"💰 السعر: **${sell_price:.2f}**\n\n"
            f"🛒 للشراء اضغط الزر 👇",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(
                    f"🛒 شراء من {BOT_NAME}",
                    url=BOT_USERNAME
                )],
            ])
        )
    except Exception as e:
        logger.error(f"notify_channel: {e}")

    try:
        seller = await db.get_user(user_id)
        seller_name = (seller['first_name'] if seller else None) or "غير معروف"
        seller_uname = (
            f"@{seller['username']}"
            if (seller and seller.get('username')) else "لا يوجد"
        )
        await safe_send(
            client, OWNER_ID,
            f"🔔 **رقم جديد للبيع**\n"
            f"━━━━━━━━━━━━━━━\n\n"
            f"📱 `{phone}`\n"
            f"🌍 {country}\n"
            f"💵 شراء: **${buy_price:.2f}**\n"
            f"💵 بيع: **${sell_price:.2f}**\n\n"
            f"👤 {seller_name} ({seller_uname})\n"
            f"🆔 `{user_id}`",
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception:
        pass

    waiting_for.pop(user_id, None)
    if user_id in temp_clients:
        try:
            await temp_clients[user_id].disconnect()
        except Exception:
            pass
        temp_clients.pop(user_id, None)

    try:
        await safe_edit(
            cb.message,
            f"✅ **تم البيع بنجاح!**\n\n"
            f"📱 `{phone}`\n"
            f"💵 **+${buy_price:.2f}**\n\n"
            f"⚙️ تم تجهيز الحساب\n"
            f"🎉 شكراً ليك!",
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception:
        pass

    await cb.answer(f"✅ تم البيع بـ ${buy_price:.2f}", show_alert=True)


def register(app: Client):

    @app.on_callback_query()
    async def cb_handler(client: Client, cb: CallbackQuery):
        user_id = cb.from_user.id
        data = cb.data

        if await db.is_banned(user_id):
            await cb.answer("🚫 أنت محظور", show_alert=True)
            return

        # ═══ تحقق الاشتراك — لكل الأزرار ما عدا check_sub و home ═══
        if data not in ("check_sub", "home") and not _is_staff(user_id):
            allowed = await _check_sub_or_alert(client, cb, user_id)
            if not allowed:
                return

        try:
            if data == "home":
                try:
                    await cb.answer()
                except Exception:
                    pass
                try:
                    await cb.message.delete()
                except Exception:
                    pass
                if _is_staff(user_id):
                    await send_dev_home(client, cb.message.chat.id)
                else:
                    await send_home(client, user_id, cb.message.chat.id)
                return

            if data == "sell_number":
                try:
                    await cb.answer()
                except Exception:
                    pass
                waiting_for[user_id] = {"action": "sell_phone"}
                await safe_edit(
                    cb.message,
                    "💰 *بيع رقم*\n\n"
                    "📱 أرسل رقم الهاتف:\n"
                    "مثال: `+20123456789`",
                    parse_mode=ParseMode.MARKDOWN
                )
                return

            if data.startswith("confirm_sell_"):
                phone = data.replace("confirm_sell_", "")
                await _handle_confirm_sell(client, cb, phone, user_id)
                return

            if data == "cancel_sell":
                await cb.answer("تم الإلغاء", show_alert=False)
                w = waiting_for.pop(user_id, None)
                if w and w.get("client"):
                    try:
                        await w["client"].disconnect()
                    except Exception:
                        pass
                if user_id in temp_clients:
                    try:
                        await temp_clients[user_id].disconnect()
                    except Exception:
                        pass
                    temp_clients.pop(user_id, None)
                try:
                    await safe_edit(
                        cb.message, "❌ تم إلغاء البيع",
                        parse_mode=ParseMode.MARKDOWN
                    )
                except Exception:
                    pass
                return

            if data == "buy_number":
                try:
                    await cb.answer()
                except Exception:
                    pass
                await show_countries(client, cb.message.chat.id, cb.message)
                return

            if data.startswith("country_"):
                try:
                    await cb.answer()
                except Exception:
                    pass
                country = data.replace("country_", "")
                await show_country_numbers(client, cb, country)
                return

            if data.startswith("view_number_"):
                try:
                    await cb.answer()
                except Exception:
                    pass
                phone = data.replace("view_number_", "")
                await show_number_details(client, cb, phone)
                return

            if data.startswith("buy_login_"):
                phone = data.replace("buy_login_", "")
                await start_buy(client, cb, phone)
                return

            if data.startswith("confirm_purchase_"):
                phone = data.replace("confirm_purchase_", "")

                number = await db.get_number(phone)
                if not number:
                    completed = await db.get_completed_purchase(phone, user_id)
                    if completed:
                        await cb.answer("✅ الرقم اتباع خلاص", show_alert=True)
                        return
                    await cb.answer("❌ الرقم غير موجود", show_alert=True)
                    return

                if number['status'] != 'available':
                    await cb.answer("❌ الرقم غير متاح", show_alert=True)
                    return

                base_price = float(number['price'])
                discount = await db.get_user_discount(user_id)
                final_price = base_price
                if discount > 0:
                    final_price = base_price * (1 - discount / 100)

                balance = await db.get_balance(user_id)
                if balance < final_price:
                    await cb.answer(
                        f"❌ رصيدك لا يكفي\n"
                        f"💰 ${balance:.2f} / ${final_price:.2f}",
                        show_alert=True
                    )
                    return

                await cb.answer("⏳ جاري الشراء...", show_alert=False)
                try:
                    await safe_edit(cb.message,
                                    "⏳ *جاري خصم الرصيد...*",
                                    parse_mode=ParseMode.MARKDOWN)
                except Exception:
                    pass

                seller_id = number['seller_id']
                lc = None
                try:
                    session_string = decrypt(number['session_enc'])
                    lc = Client(
                        f"deliver_{user_id}_{phone[-4:]}",
                        api_id=API_ID, api_hash=API_HASH,
                        session_string=session_string, in_memory=True
                    )
                    await lc.connect()
                    await asyncio.sleep(1)
                except Exception as e:
                    logger.exception(f"confirm_purchase connect: {e}")
                    await cb.answer("❌ فشل الاتصال", show_alert=True)
                    if lc:
                        try:
                            await lc.disconnect()
                        except Exception:
                            pass
                    return

                success = await db.atomic_purchase(
                    user_id, seller_id, phone, final_price
                )
                if not success:
                    await cb.answer("❌ فشل الخصم", show_alert=True)
                    try:
                        await lc.disconnect()
                    except Exception:
                        pass
                    return

                try:
                    await db.upgrade_user_level(user_id)
                    await db.check_and_upgrade_vip(user_id)
                except Exception:
                    pass

                code = None
                try:
                    code = await fetch_latest_otp(
                        lc, phone, user_id,
                        max_age_minutes=5,
                        force_resend=True
                    )
                except Exception as e:
                    logger.debug(f"fetch_otp: {e}")

                if not code:
                    try:
                        code = await db.get_last_code(phone, user_id)
                    except Exception:
                        code = None

                pwd_2fa = FIXED_2FA_PASSWORD
                if number.get("password_2fa_enc"):
                    try:
                        decrypted = decrypt(number["password_2fa_enc"])
                        if decrypted and decrypted.strip():
                            pwd_2fa = decrypted
                    except Exception:
                        pass

                try:
                    await db.save_completed_purchase(
                        phone, user_id, seller_id, final_price
                    )
                except Exception:
                    pass

                try:
                    await db.delete_number(phone)
                except Exception:
                    pass

                try:
                    await terminate_bot_session(lc)
                except Exception as e:
                    logger.debug(f"terminate: {e}")

                try:
                    await lc.disconnect()
                except Exception:
                    pass

                w = active_code_watchers.pop(phone, None)
                if w and w.get("task"):
                    w["task"].cancel()
                buy_sessions.pop(user_id, None)
                if user_id in waiting_for:
                    waiting_for.pop(user_id, None)

                try:
                    buyer = await db.get_user(user_id)
                    buyer_name = (buyer['first_name'] if buyer else None) or "مستخدم"
                    buyer_uname = (
                        f"@{buyer['username']}"
                        if (buyer and buyer.get('username')) else "لا يوجد"
                    )
                    await notify_channel(
                        client,
                        f"✅ **تم بيع رقم!**\n"
                        f"━━━━━━━━━━━━━━━\n\n"
                        f"📱 الرقم: `{phone}`\n"
                        f"🌍 الدولة: {number['country']}\n"
                        f"💰 السعر: **${final_price:.2f}**\n\n"
                        f"👤 **المشتري:**\n"
                        f"• الاسم: {buyer_name}\n"
                        f"• المعرف: {buyer_uname}\n"
                        f"• ID: `{user_id}`\n\n"
                        f"🎉 تم التسليم بنجاح",
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton(
                                f"🤖 بوت {BOT_NAME}",
                                url=BOT_USERNAME
                            )],
                        ])
                    )
                except Exception as e:
                    logger.error(f"notify_channel sold: {e}")

                delivery_text = (
                    f"🎉 **تم الشراء بنجاح!**\n"
                    f"━━━━━━━━━━━━━━━\n\n"
                    f"📱 الرقم: `{phone}`\n"
                    f"🌍 الدولة: {number['country']}\n"
                    f"💰 المبلغ: **${final_price:.2f}**\n\n"
                    f"━━━━━━━━━━━━━━━\n"
                    f"🔐 كود OTP: `{code or 'انتظر...'}`\n"
                    f"🔒 2FA: `{pwd_2fa}`\n"
                    f"━━━━━━━━━━━━━━━\n\n"
                    f"📲 **الخطوات:**\n"
                    f"1️⃣ افتح تطبيق تليجرام\n"
                    f"2️⃣ سجّل دخول بالرقم `{phone}`\n"
                    f"3️⃣ أدخل الكود: `{code or '....'}`\n"
                    f"4️⃣ أدخل 2FA: `{pwd_2fa}`\n\n"
                    f"✅ الرقم الآن ملكك!"
                )
                try:
                    await safe_send(client, user_id, delivery_text,
                                    parse_mode=ParseMode.MARKDOWN)
                except Exception as e:
                    logger.error(f"deliver: {e}")

                try:
                    seller_balance = await db.get_balance(seller_id)
                    await safe_send(
                        client, seller_id,
                        f"💰 **تم بيع رقمك!**\n"
                        f"📱 `{phone}`\n"
                        f"💵 **+${final_price:.2f}**\n"
                        f"💳 رصيدك: **${seller_balance:.2f}**",
                        parse_mode=ParseMode.MARKDOWN
                    )
                except Exception:
                    pass

                try:
                    await safe_send(
                        client, OWNER_ID,
                        f"🔔 **عملية شراء**\n"
                        f"📱 `{phone}`\n"
                        f"💵 **${final_price:.2f}**\n"
                        f"👤 `{user_id}`\n"
                        f"👛 `{seller_id}`",
                        parse_mode=ParseMode.MARKDOWN
                    )
                except Exception:
                    pass

                try:
                    await safe_edit(
                        cb.message,
                        f"✅ **تم الشراء!**\n\n"
                        f"📱 `{phone}`\n"
                        f"💰 **${final_price:.2f}**\n\n"
                        f"🔑 شوف الخاص",
                        parse_mode=ParseMode.MARKDOWN
                    )
                except Exception:
                    pass

                await cb.answer(f"✅ تم الشراء بـ ${final_price:.2f}",
                                show_alert=True)
                return

            # ═══ 🗑️ تأكيد تفريغ التخزين ═══
            if data == "dev_confirm_wipe":
                if user_id != OWNER_ID:
                    await cb.answer("🚫 للمطور فقط", show_alert=True)
                    return
                await cb.answer("⏳ جاري الحذف...", show_alert=False)
                try:
                    await safe_edit(
                        cb.message,
                        "⏳ *جاري تفريغ التخزين...*",
                        parse_mode=ParseMode.MARKDOWN
                    )
                except Exception:
                    pass

                try:
                    result = await db.clear_all_storage(keep_owner_id=OWNER_ID)
                    await audit_log(db.pool, user_id, "wipe_storage",
                                    str(result))
                    summary = (
                        f"✅ **تم تفريغ التخزين!**\n"
                        f"━━━━━━━━━━━━━━━\n\n"
                        f"📱 أرقام: `{result['numbers_deleted']}`\n"
                        f"📜 معاملات: `{result['transactions_deleted']}`\n"
                        f"⭐ تقييمات: `{result['reviews_deleted']}`\n"
                        f"💳 إيداعات: `{result['deposits_deleted']}`\n"
                        f"🎫 تذاكر: `{result['tickets_deleted']}`\n"
                        f"🔑 أكواد: `{result['saved_codes_deleted']}`\n"
                        f"📲 OTP: `{result['otp_deleted']}`\n"
                        f"🧊 مجمدة: `{result['frozen_deleted']}`\n"
                        f"🎁 هدايا: `{result['gifts_deleted']}`\n"
                        f"💰 أرصدة: `{result['users_balances_reset']}`\n\n"
                        f"✅ تم تخطي المطور"
                    )
                    await safe_edit(
                        cb.message, summary,
                        parse_mode=ParseMode.MARKDOWN
                    )
                except Exception as e:
                    logger.exception(f"wipe_storage: {e}")
                    await safe_edit(
                        cb.message,
                        f"❌ فشل: {str(e)[:200]}"
                    )
                return

            if data == "dev_cancel_wipe":
                await cb.answer("تم الإلغاء", show_alert=False)
                try:
                    await safe_edit(
                        cb.message,
                        "❌ تم إلغاء التفريغ",
                        parse_mode=ParseMode.MARKDOWN
                    )
                except Exception:
                    pass
                return

            # ═══ 💵 تأكيد تصفير الأرصدة ═══
            if data == "dev_confirm_reset_balances":
                if user_id != OWNER_ID:
                    await cb.answer("🚫 للمطور فقط", show_alert=True)
                    return
                await cb.answer("⏳ جاري التصفير...", show_alert=False)
                try:
                    await safe_edit(
                        cb.message,
                        "⏳ *جاري تصفير الأرصدة...*",
                        parse_mode=ParseMode.MARKDOWN
                    )
                except Exception:
                    pass

                try:
                    count = await db.reset_all_balances(keep_owner_id=OWNER_ID)
                    await audit_log(db.pool, user_id, "reset_all_balances",
                                    f"count={count}")
                    await safe_edit(
                        cb.message,
                        f"✅ **تم تصفير الأرصدة!**\n"
                        f"━━━━━━━━━━━━━━━\n\n"
                        f"💰 عدد المستخدمين: `{count}`\n"
                        f"✅ تم تخطي المطور",
                        parse_mode=ParseMode.MARKDOWN
                    )
                except Exception as e:
                    logger.exception(f"reset_balances: {e}")
                    await safe_edit(
                        cb.message,
                        f"❌ فشل: {str(e)[:200]}"
                    )
                return

            if data == "dev_cancel_reset_balances":
                await cb.answer("تم الإلغاء", show_alert=False)
                try:
                    await safe_edit(
                        cb.message,
                        "❌ تم إلغاء التصفير",
                        parse_mode=ParseMode.MARKDOWN
                    )
                except Exception:
                    pass
                return

            # ═══ 🔄 إعادة محاولة إضافة قناة ═══
            if data.startswith("retry_add_channel_"):
                if not _is_staff(user_id):
                    await cb.answer("🚫 للمشرفين فقط", show_alert=True)
                    return
                ch_raw = data.replace("retry_add_channel_", "")
                channel_username = "@" + ch_raw.lstrip("@")

                await cb.answer("🔄 جاري إعادة المحاولة...", show_alert=False)
                try:
                    await safe_edit(
                        cb.message,
                        "🔄 *جاري إعادة التحقق...*",
                        parse_mode=ParseMode.MARKDOWN
                    )
                except Exception:
                    pass

                chat = None
                try:
                    chat = await client.get_chat(channel_username)
                except Exception as e:
                    await safe_edit(
                        cb.message,
                        f"❌ **لم يتم العثور على القناة**\n\n"
                        f"`{channel_username}`\n\n`{str(e)[:100]}`",
                        parse_mode=ParseMode.MARKDOWN
                    )
                    return

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
                        else "⚠️ **البوت ليس أدمن بعد**\n"
                    )
                    await safe_edit(
                        cb.message,
                        f"{reason}"
                        f"━━━━━━━━━━━━━━━\n\n"
                        f"📢 `{channel_username}`\n"
                        f"📛 {chat.title}\n\n"
                        f"📝 ارفع البوت **@{me.username}** أدمن ثم أعد المحاولة.",
                        parse_mode=ParseMode.MARKDOWN,
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton(
                                "🔄 إعادة المحاولة",
                                callback_data=f"retry_add_channel_{ch_raw}"
                            )],
                        ])
                    )
                    return

                added = await db.add_required_channel(
                    channel_username, chat.title, user_id
                )
                if added:
                    await audit_log(db.pool, user_id, "add_channel",
                                    f"{channel_username} | {chat.title}")
                    await safe_edit(
                        cb.message,
                        f"✅ **تمت إضافة القناة بنجاح!**\n"
                        f"━━━━━━━━━━━━━━━\n\n"
                        f"📢 `{channel_username}`\n"
                        f"📛 {chat.title}",
                        parse_mode=ParseMode.MARKDOWN
                    )
                else:
                    await safe_edit(
                        cb.message,
                        "⚠️ القناة مضافة مسبقاً",
                        parse_mode=ParseMode.MARKDOWN
                    )
                return

            # ═══ 🧹 تأكيد مسح القنوات ═══
            if data == "dev_confirm_wipe_channels":
                if user_id != OWNER_ID:
                    await cb.answer("🚫 للمالك فقط", show_alert=True)
                    return
                await cb.answer("⏳ جاري المسح...", show_alert=False)
                try:
                    channels = await db.get_required_channels()
                    count = len(channels)
                    await db.clear_required_channels()
                    await audit_log(db.pool, user_id, "wipe_channels",
                                    f"count={count}")
                    await safe_edit(
                        cb.message,
                        f"✅ **تم مسح جميع القنوات**\n"
                        f"━━━━━━━━━━━━━━━\n\n"
                        f"🗑️ عدد القنوات المحذوفة: `{count}`",
                        parse_mode=ParseMode.MARKDOWN
                    )
                except Exception as e:
                    logger.exception(f"wipe_channels: {e}")
                    await safe_edit(
                        cb.message,
                        f"❌ فشل: {str(e)[:200]}"
                    )
                return

            if data == "dev_cancel_wipe_channels":
                await cb.answer("تم الإلغاء", show_alert=False)
                try:
                    await safe_edit(
                        cb.message,
                        "❌ تم إلغاء مسح القنوات",
                        parse_mode=ParseMode.MARKDOWN
                    )
                except Exception:
                    pass
                return

            # ═══ باقي الأزرار ═══
            if data == "wallet":
                try:
                    await cb.answer()
                except Exception:
                    pass
                await show_wallet(client, user_id, cb.message.chat.id)
                return

            if data == "my_stats":
                try:
                    await cb.answer()
                except Exception:
                    pass
                await show_stats(client, user_id, cb.message.chat.id)
                return

            if data == "my_tx":
                try:
                    await cb.answer()
                except Exception:
                    pass
                await show_history(client, user_id, cb.message.chat.id)
                return

            if data.startswith("tx_page_"):
                try:
                    await cb.answer()
                except Exception:
                    pass
                offset = int(data.replace("tx_page_", ""))
                await show_history(client, user_id, cb.message.chat.id, offset)
                return

            if data.startswith("rate_"):
                try:
                    await cb.answer()
                except Exception:
                    pass
                parts = data.split("_")
                rating = int(parts[1])
                phone = "_".join(parts[2:])
                await handle_rating(client, cb, phone, rating)
                return

            if data == "custom_order":
                try:
                    await cb.answer()
                except Exception:
                    pass
                waiting_for[user_id] = {"action": "custom_order_country"}
                await safe_edit(cb.message, "🔔 أرسل الدولة",
                                parse_mode=ParseMode.MARKDOWN)
                return

            if data == "referral":
                try:
                    await cb.answer()
                except Exception:
                    pass
                stats = await db.get_referral_stats(user_id)
                if not stats:
                    await cb.answer("❌ خطأ", show_alert=True)
                    return
                me = await client.get_me()
                link = f"https://t.me/{me.username}?start=ref_{stats['code']}"
                text = (
                    f"👥 *الإحالة*\n━━━━━━━━━━━━━━━\n\n"
                    f"🔗 `{link}`\n\n"
                    f"👤 {stats['count']}\n"
                    f"💰 ${stats['earnings']:.2f}"
                )
                await safe_edit(cb.message, text,
                                parse_mode=ParseMode.MARKDOWN)
                return

            if data == "daily_bonus":
                ok = await db.claim_daily_bonus(
                    user_id, amount=DAILY_BONUS_AMOUNT
                )
                if ok:
                    await cb.answer(f"🎁 +${DAILY_BONUS_AMOUNT:.2f}",
                                    show_alert=True)
                    await show_wallet(client, user_id, cb.message.chat.id)
                else:
                    await cb.answer("⏰ حصلت عليها اليوم", show_alert=True)
                return

            if data == "search":
                try:
                    await cb.answer()
                except Exception:
                    pass
                waiting_for[user_id] = {"action": "search_query"}
                await safe_edit(cb.message, "🔍 أرسل جزءاً من الرقم",
                                parse_mode=ParseMode.MARKDOWN)
                return

            if data.startswith("watch_prefix_"):
                phone = data.replace("watch_prefix_", "")
                prefix = phone[:6]
                await db.add_to_watchlist(user_id, prefix)
                await cb.answer(f"👁️ مراقبة {prefix}", show_alert=True)
                return

            if data == "watchlist":
                try:
                    await cb.answer()
                except Exception:
                    pass
                waiting_for[user_id] = {"action": "watch_pattern"}
                await safe_edit(cb.message, "👁️ أرسل البادئة",
                                parse_mode=ParseMode.MARKDOWN)
                return

            if data == "deposit_menu":
                try:
                    await cb.answer()
                except Exception:
                    pass
                await safe_edit(
                    cb.message,
                    "💳 اختر طريقة الإيداع:",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton(
                            "💵 USDT (TRC20)", callback_data="deposit_usdt"
                        )],
                        [InlineKeyboardButton(
                            "📱 فودافون كاش",
                            callback_data="deposit_vodafone"
                        )],
                        [InlineKeyboardButton(
                            "⭐ Telegram Stars",
                            callback_data="deposit_stars"
                        )],
                    ])
                )
                return

            if data.startswith("deposit_"):
                method = data.replace("deposit_", "")
                await cb.answer(
                    f"📩 تواصل مع الدعم للإيداع عبر {method}",
                    show_alert=True
                )
                return

            if data == "support":
                try:
                    await cb.answer()
                except Exception:
                    pass
                waiting_for[user_id] = {"action": "ticket_subject"}
                await safe_edit(cb.message, "🎫 أرسل موضوع المشكلة",
                                parse_mode=ParseMode.MARKDOWN)
                return

            if data == "check_sub":
                is_sub, missing = await check_subscription(client, user_id)
                if is_sub:
                    try:
                        await cb.message.delete()
                    except Exception:
                        pass
                    await send_home(client, user_id, cb.message.chat.id)
                else:
                    await cb.answer("❌ لم تشترك بعد", show_alert=True)
                return

            try:
                await cb.answer()
            except Exception:
                pass

        except MessageNotModified:
            pass
        except Exception as e:
            logger.exception(f"callback: {e}")
            try:
                await cb.answer("❌ حدث خطأ", show_alert=True)
            except Exception:
                pass