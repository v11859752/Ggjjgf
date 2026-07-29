import asyncio
import json
import os
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from mcstatus import JavaServer

# ========== КОНФИГ ==========
TOKEN = "E"
OWNER_ID = 5321474736

DATA_FILE = "minecraft_monitor.json"

default_data = {
    "servers": [],
    "statuses": {},
    "recipients": [OWNER_ID]
}

# ========== ЗАГРУЗКА/СОХРАНЕНИЕ ==========
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
            if "recipients" not in data:
                data["recipients"] = [OWNER_ID]
            return data
    return default_data.copy()

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

# ========== ПРОВЕРКА МАЙНКРАФТ-СЕРВЕРА ==========
async def check_minecraft_server(ip):
    print(f"🔄 Проверяю сервер: {ip}")
    try:
        server = JavaServer.lookup(ip)
        status = await server.async_status()
        print(f"✅ {ip} - ОНЛАЙН! Игроков: {status.players.online}")
        return True, status.players.online
    except Exception as e:
        print(f"❌ {ip} - ОФФЛАЙН! Ошибка: {e}")
        return False, 0

# ========== ОТПРАВКА УВЕДОМЛЕНИЙ ==========
async def send_notification(app, text, parse_mode="Markdown"):
    data = load_data()
    print(f"📨 Отправляю уведомление: {text[:50]}...")
    for recipient in data.get("recipients", [OWNER_ID]):
        try:
            await app.bot.send_message(
                chat_id=recipient,
                text=text,
                parse_mode=parse_mode
            )
            print(f"✅ Уведомление отправлено в {recipient}")
        except Exception as e:
            print(f"❌ Ошибка отправки в {recipient}: {e}")

# ========== ЗАДАЧА МОНИТОРИНГА ==========
async def monitor_servers(app):
    print("\n" + "="*50)
    print(f"🔍 ЗАПУСК МОНИТОРИНГА - {datetime.now().strftime('%H:%M:%S')}")
    print("="*50)
    
    data = load_data()
    
    if not data["servers"]:
        print("📭 Нет серверов для мониторинга")
        return
    
    for server in data["servers"]:
        ip = server["ip"]
        print(f"\n📡 Обработка сервера: {ip}")
        
        is_online, players = await check_minecraft_server(ip)
        
        prev_status = data["statuses"].get(ip, None)
        print(f"   Предыдущий статус: {prev_status}")
        print(f"   Текущий статус: {is_online}")
        
        if prev_status is None:
            print(f"   ℹ️ Первый опрос сервера {ip}, просто сохраняю статус")
            data["statuses"][ip] = is_online
            save_data(data)
        
        elif prev_status is False and is_online is True:
            print(f"   🟢 СЕРВЕР {ip} ВКЛЮЧИЛСЯ! Отправляю уведомление")
            await send_notification(
                app,
                f"🟢 **Сервер {ip} ВКЛЮЧИЛСЯ!**\n"
                f"👥 Игроков: {players}\n"
                f"🕐 {datetime.now().strftime('%H:%M:%S')}"
            )
            data["statuses"][ip] = is_online
            save_data(data)
        
        elif prev_status is True and is_online is False:
            print(f"   🔴 СЕРВЕР {ip} ВЫКЛЮЧИЛСЯ! Отправляю уведомление")
            await send_notification(
                app,
                f"🔴 **Сервер {ip} ВЫКЛЮЧИЛСЯ!**\n"
                f"🕐 {datetime.now().strftime('%H:%M:%S')}"
            )
            data["statuses"][ip] = is_online
            save_data(data)
        
        elif prev_status is True and is_online is True:
            print(f"   ℹ️ Сервер {ip} был и остаётся ОНЛАЙН (статус не менялся)")
        
        elif prev_status is False and is_online is False:
            print(f"   ℹ️ Сервер {ip} был и остаётся ОФФЛАЙН (статус не менялся)")
    
    print("\n" + "="*50)
    print(f"✅ МОНИТОРИНГ ЗАВЕРШЁН - {datetime.now().strftime('%H:%M:%S')}")
    print("="*50 + "\n")

# ========== ПРОВЕРКА ПРАВ ==========
def is_owner(update: Update):
    return update.effective_user.id == OWNER_ID

# ========== КОМАНДЫ ДЛЯ ВЛАДЕЛЬЦА ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"📩 Получена команда /start от пользователя {update.effective_user.id}")
    
    if not is_owner(update):
        await update.message.reply_text("❌ Доступ запрещён! Только владелец может управлять ботом.")
        print(f"⛔ Доступ запрещён для {update.effective_user.id}")
        return
    
    keyboard = [
        [InlineKeyboardButton("➕ Добавить сервер", callback_data="add")],
        [InlineKeyboardButton("❌ Удалить сервер", callback_data="remove")],
        [InlineKeyboardButton("📋 Список серверов", callback_data="list")],
        [InlineKeyboardButton("⏱ Интервал опроса", callback_data="interval")],
        [InlineKeyboardButton("📢 Управление получателями", callback_data="recipients")],
    ]
    await update.message.reply_text(
        "🏗 **Панель управления Minecraft-монитором**\n"
        "Все уведомления будут приходить тебе и в добавленные каналы/группы.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    print("✅ Отправлена панель управления")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    print(f"📩 Нажата кнопка: {query.data} от {update.effective_user.id}")
    
    if not is_owner(update):
        await query.edit_message_text("❌ Доступ запрещён! Только владелец.")
        print(f"⛔ Доступ запрещён для {update.effective_user.id}")
        return
    
    data = load_data()
    
    if query.data == "add":
        context.user_data["action"] = "add_server"
        await query.edit_message_text("📝 Введи IP сервера (например: play.mfcraft.ru или mc.example.com:25565)")
        print("⏳ Ожидание ввода IP сервера")
    
    elif query.data == "remove":
        if not data["servers"]:
            await query.edit_message_text("📭 Нет серверов для удаления")
            return
        keyboard = [
            [InlineKeyboardButton(s["ip"], callback_data=f"del_{s['ip']}")]
            for s in data["servers"]
        ]
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back")])
        await query.edit_message_text(
            "Выбери сервер для удаления:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif query.data.startswith("del_"):
        ip = query.data.replace("del_", "")
        data["servers"] = [s for s in data["servers"] if s["ip"] != ip]
        data["statuses"].pop(ip, None)
        save_data(data)
        await query.edit_message_text(f"✅ Сервер {ip} удалён!")
        print(f"🗑️ Сервер {ip} удалён")
    
    elif query.data == "list":
        if not data["servers"]:
            await query.edit_message_text("📭 Нет добавленных серверов")
            return
        text = "📋 **Список серверов:**\n\n"
        for s in data["servers"]:
            status = "🟢" if data["statuses"].get(s["ip"], False) else "🔴"
            text += f"{status} {s['ip']} (интервал: {s['interval']}с)\n"
        await query.edit_message_text(text)
        print("📋 Показан список серверов")
    
    elif query.data == "interval":
        context.user_data["action"] = "set_interval"
        await query.edit_message_text("⏱ Введи интервал в секундах (например: 60)")
        print("⏳ Ожидание ввода интервала")
    
    elif query.data == "recipients":
        keyboard = [
            [InlineKeyboardButton("➕ Добавить получателя", callback_data="add_recipient")],
            [InlineKeyboardButton("❌ Удалить получателя", callback_data="remove_recipient")],
            [InlineKeyboardButton("📋 Список получателей", callback_data="list_recipients")],
            [InlineKeyboardButton("🔙 Назад", callback_data="back")]
        ]
        await query.edit_message_text(
            "📢 **Управление получателями**\n"
            "Сюда будут приходить уведомления.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif query.data == "add_recipient":
        context.user_data["action"] = "add_recipient"
        await query.edit_message_text(
            "📝 Отправь ID чата/канала/группы.\n\n"
            "📌 Как получить ID:\n"
            "1. Добавь бота в канал/группу\n"
            "2. Напиши любое сообщение там\n"
            "3. Перешли его боту @userinfobot\n"
            "4. Скопируй ID (может быть отрицательным)"
        )
        print("⏳ Ожидание ввода ID получателя")
    
    elif query.data == "remove_recipient":
        recipients = data.get("recipients", [OWNER_ID])
        if len(recipients) <= 1:
            await query.edit_message_text("⚠️ Нельзя удалить последнего получателя (тебя)!")
            return
        keyboard = []
        for r in recipients:
            label = "👤 Ты" if r == OWNER_ID else f"📢 {r}"
            keyboard.append([InlineKeyboardButton(label, callback_data=f"del_rec_{r}")])
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="recipients")])
        await query.edit_message_text(
            "Выбери получателя для удаления:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif query.data.startswith("del_rec_"):
        recipient = int(query.data.replace("del_rec_", ""))
        if recipient == OWNER_ID:
            await query.edit_message_text("❌ Нельзя удалить себя!")
            return
        data["recipients"] = [r for r in data["recipients"] if r != recipient]
        save_data(data)
        await query.edit_message_text(f"✅ Получатель {recipient} удалён!")
        print(f"🗑️ Получатель {recipient} удалён")
    
    elif query.data == "list_recipients":
        recipients = data.get("recipients", [OWNER_ID])
        text = "📋 **Список получателей:**\n\n"
        for r in recipients:
            label = "👤 Ты (владелец)" if r == OWNER_ID else f"📢 {r}"
            text += f"• {label}\n"
        await query.edit_message_text(text)
        print("📋 Показан список получателей")
    
    elif query.data == "back":
        await start(update, context)

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"📩 Получено сообщение: {update.message.text} от {update.effective_user.id}")
    
    if not is_owner(update):
        await update.message.reply_text("❌ Доступ запрещён! Только владелец.")
        print(f"⛔ Доступ запрещён для {update.effective_user.id}")
        return
    
    data = load_data()
    action = context.user_data.get("action")
    text = update.message.text.strip()
    
    if action == "add_server":
        if any(s["ip"] == text for s in data["servers"]):
            await update.message.reply_text("⚠️ Такой сервер уже есть!")
            print(f"⚠️ Попытка добавить существующий сервер: {text}")
            return
        data["servers"].append({"ip": text, "interval": 60})
        data["statuses"][text] = None
        save_data(data)
        context.user_data["action"] = None
        await update.message.reply_text(f"✅ Сервер {text} добавлен! Интервал: 60с")
        print(f"➕ Добавлен сервер: {text}")
    
    elif action == "set_interval":
        try:
            interval = int(text)
            if interval < 10:
                await update.message.reply_text("⚠️ Минимальный интервал - 10 секунд")
                print(f"⚠️ Попытка установить интервал < 10: {interval}")
                return
            for s in data["servers"]:
                s["interval"] = interval
            save_data(data)
            context.user_data["action"] = None
            await update.message.reply_text(f"✅ Интервал обновлён: {interval}с")
            print(f"⏱ Интервал обновлён: {interval}с")
        except ValueError:
            await update.message.reply_text("❌ Введи число!")
            print(f"❌ Неверный формат интервала: {text}")
    
    elif action == "add_recipient":
        try:
            recipient_id = int(text)
            if recipient_id in data.get("recipients", []):
                await update.message.reply_text("⚠️ Этот получатель уже есть!")
                print(f"⚠️ Попытка добавить существующего получателя: {recipient_id}")
                return
            data.setdefault("recipients", [OWNER_ID]).append(recipient_id)
            save_data(data)
            context.user_data["action"] = None
            await update.message.reply_text(f"✅ Получатель {recipient_id} добавлен!")
            print(f"➕ Добавлен получатель: {recipient_id}")
        except ValueError:
            await update.message.reply_text("❌ Введи корректный ID (только цифры)!")
            print(f"❌ Неверный формат ID: {text}")

# ========== ЗАПУСК ==========
async def scheduler(app):
    interval = 60
    print("🔄 Планировщик запущен")
    while True:
        data = load_data()
        if data["servers"]:
            interval = data["servers"][0]["interval"]
            print(f"⏰ Следующий опрос через {interval} секунд")
            await monitor_servers(app)
        else:
            print("⏳ Нет серверов, ожидание...")
        await asyncio.sleep(interval)

def main():
    print("🚀 ЗАПУСК БОТА")
    print(f"📱 Владелец: {OWNER_ID}")
    print("="*50)
    
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    
    # Запускаем планировщик в фоне
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.create_task(scheduler(app))
    
    print("🤖 Бот запущен! Только владелец может управлять.")
    print("📝 Все действия логируются в консоль")
    print("="*50 + "\n")
    app.run_polling()

if __name__ == "__main__":
    main()
