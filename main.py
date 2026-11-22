#لوجيك | Logic وجهتك البرمجية الأولى  بالوطن العربي
#شروحات - أكواد - وأحدث تقنيات برمجية - وحلول تقنية
#بواسطه: t.me/Logii3

#الترخيص: @TopVeGa
#العلامة التجارية: VEGA & Logic
#حقوق الطبع والنشر: © 2015 - 2025

import asyncio
import logging
import signal
import threading
import time
import os
import sys
import json
import importlib.util
from datetime import datetime
from pyrogram import Client
from flask import Flask, jsonify, request, render_template_string
from config import (
    BOT_TOKEN, API_ID, API_HASH, OWNER_ID, BOT_NAME, WEB_PORT,
    WEB_SECRET_KEY, WEB_ADMIN_USER, WEB_ADMIN_PASSWORD
)
from Database import db
from logging.handlers import RotatingFileHandler

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        RotatingFileHandler('bot.log', maxBytes=10*1024*1024, backupCount=5,
                            encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

START_TIME = time.time()
shutdown_event = asyncio.Event()
background_tasks = []
flask_app = Flask(__name__)
flask_app.secret_key = WEB_SECRET_KEY



def _run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@flask_app.route('/')
def index():
    return jsonify({
        "status": "ok",
        "bot": BOT_NAME,
        "uptime_seconds": int(time.time() - START_TIME),
    })


@flask_app.route('/health')
def health():
    return jsonify({
        "status": "healthy",
        "timestamp": time.time(),
        "uptime": int(time.time() - START_TIME),
    })


@flask_app.route('/api/health/db')
def db_health():
    try:
        stats = _run_async(db.get_stats())
        return jsonify({"status": "ok", "db": "connected", "stats": stats})
    except Exception as e:
        return jsonify({"status": "error", "db": "disconnected", "error": str(e)}), 500


@flask_app.route('/api/stats')
def api_stats():
    try:
        stats = _run_async(db.get_stats())
        daily = _run_async(db.get_daily_stats())
        return jsonify({
            "general": stats,
            "today": daily,
            "uptime": int(time.time() - START_TIME),
            "timestamp": datetime.utcnow().isoformat(),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@flask_app.route('/api/top_sellers')
def api_top_sellers():
    try:
        limit = int(request.args.get("limit", 10))
        rows = _run_async(db.get_top_sellers(limit))
        return jsonify(rows)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@flask_app.route('/api/top_countries')
def api_top_countries():
    try:
        limit = int(request.args.get("limit", 10))
        rows = _run_async(db.get_top_countries(limit))
        return jsonify(rows)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@flask_app.route('/api/users/count')
def api_users_count():
    try:
        users = _run_async(db.get_all_users())
        return jsonify({"count": len(users)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@flask_app.route('/dashboard')
def dashboard():
    try:
        stats = _run_async(db.get_stats())
        daily = _run_async(db.get_daily_stats())
        sellers = _run_async(db.get_top_sellers(5))
        countries = _run_async(db.get_top_countries(5))

        sellers_html = "".join(
            f"<tr><td>{s.get('first_name') or s.get('username') or s['id']}</td>"
            f"<td>{s['total_sales']}</td>"
            f"<td>⭐{float(s['rating']):.2f}</td></tr>"
            for s in sellers
        ) or "<tr><td colspan='3'>لا يوجد</td></tr>"

        countries_html = "".join(
            f"<tr><td>{c['country']}</td><td>{c['cnt']}</td></tr>"
            for c in countries
        ) or "<tr><td colspan='2'>لا يوجد</td></tr>"

        return render_template_string("""
        <!DOCTYPE html>
        <html><head><meta charset="utf-8"><title>SIMBot Dashboard</title>
        <style>
            body{font-family:Arial;background:#0d1117;color:#eee;padding:30px;margin:0}
            h1{color:#58a6ff}
            .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:15px;margin:20px 0}
            .card{background:#161b22;padding:20px;border-radius:10px;border:1px solid #30363d}
            .card h3{margin:0 0 10px;color:#8b949e;font-size:13px}
            .card p{font-size:24px;margin:0;color:#58a6ff;font-weight:bold}
            table{width:100%;border-collapse:collapse;background:#161b22;border-radius:10px;overflow:hidden;margin-bottom:20px}
            th,td{padding:12px;text-align:right;border-bottom:1px solid #30363d}
            th{background:#21262d;color:#8b949e}
            .section{margin-top:20px}
            .section h2{color:#58a6ff;font-size:18px}
            .uptime{color:#3fb950}
        </style></head><body>
        <h1>📊 SIMBot Dashboard</h1>
        <p class="uptime">⏱️ Uptime: {{ uptime }}s</p>

        <div class="grid">
            <div class="card"><h3>👥 المستخدمون</h3><p>{{ stats.users }}</p></div>
            <div class="card"><h3>📦 أرقام متاحة</h3><p>{{ stats.available }}</p></div>
            <div class="card"><h3>💰 أرقام مباعة</h3><p>{{ stats.sold }}</p></div>
            <div class="card"><h3>💵 الإيرادات</h3><p>${{ "%.2f"|format(stats.revenue) }}</p></div>
        </div>

        <div class="section">
            <h2>📅 اليوم</h2>
            <div class="grid">
                <div class="card"><h3>👥 مستخدمون جدد</h3><p>{{ daily.new_users }}</p></div>
                <div class="card"><h3>💰 مبيعات</h3><p>{{ daily.sold }}</p></div>
                <div class="card"><h3>💵 إيرادات</h3><p>${{ "%.2f"|format(daily.revenue) }}</p></div>
            </div>
        </div>

        <div class="section">
            <h2>🏆 أفضل البائعين</h2>
            <table><tr><th>الاسم</th><th>المبيعات</th><th>التقييم</th></tr>{{ sellers|safe }}</table>
        </div>

        <div class="section">
            <h2>🌍 أكثر الدول</h2>
            <table><tr><th>الدولة</th><th>العدد</th></tr>{{ countries|safe }}</table>
        </div>

        </body></html>
        """, stats=stats, daily=daily, sellers=sellers_html,
             countries=countries_html, uptime=int(time.time() - START_TIME))
    except Exception as e:
        return f"<h1>Error</h1><pre>{e}</pre>", 500


def run_flask():
    flask_app.run(host='0.0.0.0', port=WEB_PORT, use_reloader=False)


app = Client(
    "SIMBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workers=8
)


# ============================================================
# ✅ Background Tasks
# ============================================================
async def auto_refund_scheduler():
    while not shutdown_event.is_set():
        try:
            await asyncio.wait_for(shutdown_event.wait(), timeout=120)
            break
        except asyncio.TimeoutError:
            pass
        try:
            logger.debug("🔍 refund scheduler tick")
        except Exception as e:
            logger.error(f"refund scheduler: {e}")
    logger.info("🛑 auto_refund_scheduler توقف")


async def reservation_cleaner():
    while not shutdown_event.is_set():
        try:
            await db.release_expired_reservations()
        except Exception as e:
            logger.error(f"reservation cleaner: {e}")
        try:
            await asyncio.wait_for(shutdown_event.wait(), timeout=60)
        except asyncio.TimeoutError:
            pass
    logger.info("🛑 reservation_cleaner توقف")


async def stale_numbers_cleaner():
    while not shutdown_event.is_set():
        try:
            await asyncio.wait_for(shutdown_event.wait(), timeout=3600)
            break
        except asyncio.TimeoutError:
            pass
        try:
            count = await db.expire_stale_numbers(days=30)
            if count:
                logger.info(f"🗑️ تم حذف {count} رقم قديم")
        except Exception as e:
            logger.error(f"stale cleaner: {e}")
    logger.info("🛑 stale_numbers_cleaner توقف")


def load_shop_module(filename: str):
    here = os.path.dirname(os.path.abspath(__file__))
    shop_dir = os.path.join(here, "shop")
    path = os.path.join(shop_dir, filename)

    if not os.path.exists(path):
        raise FileNotFoundError(f"❌ الملف غير موجود: {path}")

    mod_name = "shop_" + filename.replace(".py", "").replace(" ", "_")
    spec = importlib.util.spec_from_file_location(mod_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module
    spec.loader.exec_module(module)
    return module


def register_all_handlers():
    logger.info("📦 تحميل وحدات shop...")

    load_shop_module("inform.py")
    logger.info("  ✅ inform.py")

    runner = load_shop_module("play.py")
    runner.register(app)
    logger.info("  ✅ play.py")

    admin_mod = load_shop_module("Admin.py")
    admin_mod.register(app)
    logger.info("  ✅ Admin.py")

    payments = load_shop_module("Botpay.py")
    payments.register(app)
    logger.info("  ✅ Botpay.py")

    cb_mod = load_shop_module("callbacks.py")
    cb_mod.register(app)
    logger.info("  ✅ callbacks.py")

    logger.info("✅ تم تحميل كل الوحدات بنجاح")


async def graceful_shutdown():
    logger.info("🛑 جاري إيقاف البوت...")
    shutdown_event.set()

    for task in background_tasks:
        if not task.done():
            task.cancel()
    if background_tasks:
        try:
            await asyncio.wait(background_tasks, timeout=5)
        except Exception:
            pass

    try:
        runner = sys.modules.get("shop_play")
        if runner:
            for uid, cli in list(runner.temp_clients.items()):
                try:
                    await cli.disconnect()
                except Exception:
                    pass

            for uid, s in list(runner.buy_sessions.items()):
                cli = s.get("client")
                if cli:
                    try:
                        await cli.disconnect()
                    except Exception:
                        pass

            for phone, w in list(runner.active_code_watchers.items()):
                t = w.get("task")
                if t:
                    t.cancel()
    except Exception as e:
        logger.error(f"cleanup sessions: {e}")

    try:
        await app.stop()
    except Exception as e:
        logger.error(f"stop app: {e}")

    try:
        await db.close()
    except Exception as e:
        logger.error(f"close db: {e}")

    logger.info("✅ تم الإيقاف بنجاح")


def shutdown_handler(signum, frame):
    loop = asyncio.get_event_loop()
    if loop.is_running():
        asyncio.run_coroutine_threadsafe(graceful_shutdown(), loop)
    else:
        loop.run_until_complete(graceful_shutdown())


async def main_async():
    await db.connect()
    logger.info("✅ تم الاتصال بقاعدة البيانات")

    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info(f"✅ Dashboard على http://0.0.0.0:{WEB_PORT}/dashboard")
    logger.info(f"✅ API على http://0.0.0.0:{WEB_PORT}/api/stats")

    t1 = asyncio.create_task(reservation_cleaner())
    t2 = asyncio.create_task(stale_numbers_cleaner())
    t3 = asyncio.create_task(auto_refund_scheduler())
    background_tasks.extend([t1, t2, t3])

    register_all_handlers()

    # ✅ حمّل المشرفين من DB بعد تحميل Admin.py
    admin_mod = sys.modules.get("shop_Admin")
    if admin_mod and hasattr(admin_mod, "load_admins_from_db"):
        try:
            await admin_mod.load_admins_from_db()
        except Exception as e:
            logger.error(f"load_admins_from_db: {e}")

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    await app.start()
    logger.info("🚀 البوت يعمل الآن")

    await shutdown_event.wait()


if __name__ == "__main__":
    print("=" * 50)
    print(f"🤖 {BOT_NAME} — نسخة احترافية")
    print(f"👤 المالك: {OWNER_ID}")
    print("• ترخيص بواسطه : @TopVeGa")
    print("• علامة تجارية : VEGA & PyZone")
    print("• جميع الحقوق محفوظة © 2015")
    print("=" * 50)

    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        logger.info("⏹️ تم الإيقاف يدوياً")