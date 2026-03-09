import asyncio
import sqlite3
import requests
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from apscheduler.schedulers.asyncio import AsyncIOScheduler

BOT_TOKEN = "8365107740:AAEaOHxvWIXRxv_EExuUEH9kafedBQaPOV0"
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ------------------ База данных ------------------
db = sqlite3.connect("bot.db")
cursor = db.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users(
    id INTEGER PRIMARY KEY
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS versions(
    app TEXT PRIMARY KEY,
    android TEXT,
    ios TEXT
)
""")
db.commit()

# ------------------ Приложения ------------------
APPS = {
    "instagram": {"ios": "389801252"},
    "tiktok": {"ios": "835599320"},
    "youtube": {"ios": "544007664"}
}

# ------------------ Получение версий ------------------
def get_ios_version(app_id):
    try:
        r = requests.get(f"https://itunes.apple.com/lookup?id={app_id}", timeout=10)
        data = r.json()
        if data.get("resultCount", 0) > 0:
            return data["results"][0]["version"]
    except:
        return None

def get_android_version(name):
    # Пока фейковые версии
    return {
        "instagram": "Varies with device",
        "tiktok": "Varies with device",
        "youtube": "Varies with device"
    }.get(name)

# ------------------ Проверка обновлений ------------------
async def check_updates():
    for platform in ["android", "ios"]:
        for name, ids in APPS.items():
            if platform == "android":
                current_version = get_android_version(name)
                cursor.execute("SELECT android FROM versions WHERE app=?", (name,))
                row = cursor.fetchone()
                old_version = row[0] if row else None
            else:
                current_version = get_ios_version(ids["ios"])
                cursor.execute("SELECT ios FROM versions WHERE app=?", (name,))
                row = cursor.fetchone()
                old_version = row[0] if row else None

            if old_version != current_version:
                # Обновляем базу
                cursor.execute(
                    "INSERT OR REPLACE INTO versions(app, android, ios) VALUES(?,?,?)",
                    (name,
                     get_android_version(name),
                     get_ios_version(ids["ios"]))
                )
                db.commit()

                # Отправляем уведомления подписчикам
                cursor.execute("SELECT id FROM users")
                users = cursor.fetchall()
                for user in users:
                    try:
                        emoji = "🤖" if platform == "android" else "🍎"
                        msg = f"🚀 Новое обновление {name.capitalize()} для {platform.upper()}!\n{emoji} Версия: {current_version}"
                        await bot.send_message(user[0], msg)
                    except:
                        pass

# ------------------ Кнопки ------------------
def platform_keyboard():
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🤖 Android", callback_data="android"),
                InlineKeyboardButton(text="🍎 iOS", callback_data="ios")
            ],
            [
                InlineKeyboardButton(text="🔄 Проверить обновления", callback_data="check_now"),
                InlineKeyboardButton(text="❌ Отписаться", callback_data="unsubscribe")
            ]
        ]
    )
    return keyboard

# ------------------ Форматирование текста ------------------
async def get_versions_text(platform):
    text = f"📊 Текущие версии приложений ({platform.upper()}):\n\n"
    for name, ids in APPS.items():
        if platform == "android":
            version = get_android_version(name)
            cursor.execute("SELECT android FROM versions WHERE app=?", (name,))
            row = cursor.fetchone()
            old_version = row[0] if row else version
        else:
            version = get_ios_version(ids["ios"])
            cursor.execute("SELECT ios FROM versions WHERE app=?", (name,))
            row = cursor.fetchone()
            old_version = row[0] if row else version

        status = "🚀 Нужно обновление" if version != old_version else "✅ Уже актуально"
        emoji = "🤖" if platform == "android" else "🍎"
        text += f"{name.capitalize()}: {emoji} {version} — {status}\n"
    cursor.execute("SELECT COUNT(*) FROM users")
    return text

# ------------------ Обработчики ------------------
@dp.message(Command("start"))
async def start(msg: types.Message):
    cursor.execute("SELECT id FROM users WHERE id=?", (msg.from_user.id,))
    if cursor.fetchone():
        await msg.answer(
            "👋 Добро пожаловать обратно! Вы уже подписаны.\n"
            "Выберите платформу:",
            reply_markup=platform_keyboard()
        )
    else:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="✅ Подписаться", callback_data="subscribe")]
            ]
        )
        await msg.answer(
            "👋 Добро пожаловать! Нажми кнопку, чтобы подписаться на уведомления об обновлениях приложений.",
            reply_markup=keyboard
        )

@dp.callback_query(lambda c: c.data == "subscribe")
async def subscribe(cb: types.CallbackQuery):
    cursor.execute("INSERT OR IGNORE INTO users VALUES(?)", (cb.from_user.id,))
    db.commit()
    await cb.answer("✅ Вы подписались на уведомления", show_alert=True)
    await cb.message.answer("Выберите платформу:", reply_markup=platform_keyboard())

@dp.callback_query(lambda c: c.data in ["android", "ios"])
async def show_versions(cb: types.CallbackQuery):
    text = await get_versions_text(cb.data)
    await cb.message.answer(text)

@dp.callback_query(lambda c: c.data == "check_now")
async def check_now(cb: types.CallbackQuery):
    await cb.answer("🔍 Проверяю обновления...", show_alert=True)
    
    messages = []
    for platform in ["android", "ios"]:
        results = {}
        for name, ids in APPS.items():
            if platform == "android":
                current = get_android_version(name)
                cursor.execute("SELECT android FROM versions WHERE app=?", (name,))
                row = cursor.fetchone()
                old_version = row[0] if row else current
            else:
                current = get_ios_version(ids["ios"])
                cursor.execute("SELECT ios FROM versions WHERE app=?", (name,))
                row = cursor.fetchone()
                old_version = row[0] if row else current

            # Проверяем нужна ли замена версии
            if current != old_version:
                status = f"🚀 Доступно обновление: {current}"
                cursor.execute(
                    "UPDATE versions SET android=?, ios=? WHERE app=?",
                    (get_android_version(name), get_ios_version(ids["ios"]), name)
                )
                db.commit()
            else:
                status = f"🔹 Обновление не требуется, текущая версия: {current}"

            results[name] = status

        # Формируем текст для платформы
        text = f"📊 {platform.upper()} версии приложений:\n"
        for app, status in results.items():
            text += f"{app.capitalize()}: {status}\n"
        messages.append(text)
    
    await cb.message.answer("\n\n".join(messages))

@dp.callback_query(lambda c: c.data == "unsubscribe")
async def unsubscribe(cb: types.CallbackQuery):
    cursor.execute("DELETE FROM users WHERE id=?", (cb.from_user.id,))
    db.commit()
    await cb.answer("❌ Вы отписались от уведомлений", show_alert=True)
    await cb.message.answer("Вы больше не получаете уведомления. Чтобы подписаться снова, используйте /start.")

# ------------------ Запуск бота ------------------
async def main():
    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_updates, "interval", minutes=15)  # авто проверка каждые 15 минут
    scheduler.start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())