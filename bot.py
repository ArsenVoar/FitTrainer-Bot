import sqlite3
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters, CallbackContext
from datetime import datetime, timedelta
import time
import schedule
import threading

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

def create_database():
    conn = sqlite3.connect('fitness_bot.db')
    c = conn.cursor()

    # Создание таблицы users с добавленным столбцом weight
    c.execute('''
              CREATE TABLE IF NOT EXISTS users (
                 user_id INTEGER PRIMARY KEY,
                 first_name TEXT,
                 last_name TEXT,
                 username TEXT,
                 weight REAL
              )
    ''')

    # Создание таблицы weight_history
    c.execute('''
              CREATE TABLE IF NOT EXISTS weight_history (
                 user_id INTEGER,
                 date TEXT,
                 weight REAL,
                 FOREIGN KEY(user_id) REFERENCES users(user_id)
              )
    ''')

    # Проверка наличия столбца weight в таблице users
    c.execute("PRAGMA table_info(users);")
    columns = [column[1] for column in c.fetchall()]
    if 'weight' not in columns:
        c.execute("ALTER TABLE users ADD COLUMN weight REAL;")

    conn.commit()
    conn.close()

# Вызов функции создания базы данных
create_database()

""""
# Функция для проверки содержимого базы данных
def check_database():
    conn = sqlite3.connect('fitness_bot.db')
    c = conn.cursor()

    # Печатаем список таблиц
    c.execute("SELECT name FROM sqlite_master WHERE type='table';")
    print("Tables:", c.fetchall())

    # Печатаем содержимое таблицы users
    c.execute("SELECT * FROM users")
    print("Users Table Content:", c.fetchall())

    # Печатаем содержимое таблицы progress
    c.execute("SELECT * FROM progress")
    print("Progress Table Content:", c.fetchall())

    conn.close()
"""

# Функция регистрации пользователя
async def register(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.message.from_user
    user_id = user.id
    first_name = user.first_name
    last_name = user.last_name if user.last_name else ""
    username = user.username if user.username else ""

    conn = sqlite3.connect('fitness_bot.db')
    c = conn.cursor()
    c.execute('''
              INSERT OR IGNORE INTO users (user_id, first_name, last_name, username, weight)
              VALUES (?, ?, ?, ?, ?)
    ''', (user_id, first_name, last_name, username, None))
    conn.commit()
    conn.close()

    await update.message.reply_text(f"Вы успешно зарегистрированы! Привет, {first_name}!")

# Функция проверки статуса регистрации
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    
    conn = sqlite3.connect('fitness_bot.db')
    c = conn.cursor()
    c.execute("SELECT first_name, last_name, username, weight FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    
    if row:
        first_name, last_name, username, weight = row
        last_name = last_name if last_name else "Не указана"
        username = username if username else "Не указан"
        weight = weight if weight else "Не указан"
        await update.message.reply_text(f"Вы зарегистрированы!\nИмя: {first_name}\nФамилия: {last_name}\nИмя пользователя: {username}\nТекущий вес: {weight} кг")
    else:
        await update.message.reply_text("Вы не зарегистрированы. Пожалуйста, начните с команды /start для регистрации.")

# Функция для отображения профиля
async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user_id = query.from_user.id

    conn = sqlite3.connect('fitness_bot.db')
    c = conn.cursor()
    c.execute("SELECT first_name, last_name, username, weight FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()

    if row:
        first_name, last_name, username, weight = row
        last_name = last_name if last_name else "Не указана"
        username = username if username else "Не указан"
        weight = weight if weight else "Не указан"
        profile_message = (
            f"Ваш профиль:\n\n"
            f"Имя: {first_name}\n"
            f"Фамилия: {last_name}\n"
            f"Имя пользователя: {username}\n"
            f"Текущий вес: {weight} кг\n\n"
            "Вы можете использовать следующие команды:\n"
            "/status - Проверить регистрацию\n"
            "/delete - Удалить аккаунт и данные\n"
        )
    else:
        profile_message = "Ваша регистрация не найдена. Пожалуйста, начните с команды /start для регистрации."

    logger.info(f"Profile message: {profile_message}")
    await query.message.reply_text(profile_message)

# Функция для обновления веса каждую неделю
def update_weekly_weight():
    conn = sqlite3.connect('fitness_bot.db')
    c = conn.cursor()
    c.execute("SELECT user_id, weight FROM users")
    users = c.fetchall()

    for user in users:
        user_id, weight = user
        if weight:
            date = datetime.now().strftime('%Y-%m-%d')
            c.execute("INSERT INTO weight_history (user_id, date, weight) VALUES (?, ?, ?)",
                      (user_id, date, weight))

    conn.commit()
    conn.close()
    logger.info("Weekly weight updated.")

def start_scheduler():
    schedule.every().monday.at("00:00").do(update_weekly_weight)
    while True:
        schedule.run_pending()
        time.sleep(1)   

async def delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id

    conn = sqlite3.connect('fitness_bot.db')
    c = conn.cursor()
    c.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
    c.execute("DELETE FROM weight_history WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

    await update.message.reply_text("Ваш аккаунт и данные успешно удалены!")

# Обработка команд для записи веса
async def log_weight(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        weight = float(update.message.text)

        user_id = update.message.from_user.id
        date = datetime.now().strftime('%Y-%m-%d')

        conn = sqlite3.connect('fitness_bot.db')
        c = conn.cursor()
        c.execute("INSERT INTO weight_history (user_id, date, weight) VALUES (?, ?, ?)",
                  (user_id, date, weight))
        c.execute("UPDATE users SET weight = ? WHERE user_id = ?", (weight, user_id))
        conn.commit()
        conn.close()

        await update.message.reply_text("Вес записан!")
    except ValueError:
        await update.message.reply_text("Пожалуйста, отправьте числовое значение веса.")

        # Просмотр истории веса
async def view_weight_history(update: Update, context: CallbackContext):
    # Используем update.callback_query вместо update.message
    user_id = update.callback_query.from_user.id
    
    conn = sqlite3.connect('fitness_bot.db')
    c = conn.cursor()
    
    c.execute('''
              SELECT date, weight FROM weight_history WHERE user_id = ?
              ORDER BY date DESC
              ''', (user_id,))
    
    rows = c.fetchall()
    conn.close()

    if rows:
        history = "\n".join([f"{date}: {weight} кг" for date, weight in rows])
    else:
        history = "История веса пуста."

    await update.callback_query.message.reply_text(f"История веса:\n{history}")

    # Убедитесь, что мы обрабатываем callback_query
    await update.callback_query.answer()

# Функция, которая будет обрабатывать нажатие кнопок меню
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    logger.info(f"Button pressed with data: {query.data}")
    if query.data == '1':
        await query.edit_message_text(text="Видео для тренировки 1: [Ссылка на видео]")
    elif query.data == '2':
        await query.edit_message_text(text="Видео для тренировки 2: [Ссылка на видео]")
    elif query.data == '3':
        await query.edit_message_text(text="Видео для тренировки 3: [Ссылка на видео]")
    if query.data == 'log_weight':
        await query.message.reply_text("Пожалуйста, отправьте свой текущий вес в килограммах.")
    elif query.data == 'view_weight_history':
        await view_weight_history(update, context)
    elif query.data == 'profile':
        await profile(update, context) 

## Функция, которая будет отправлять приветствие
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.message.from_user  # Получаем пользователя из сообщения
    await register(update, context)  # Добавляем вызов функции регистрации
    welcome_message = "Добро пожаловать в фитнес-бот. Пожалуйста, выберите интересующий вас раздел:"
    # Создаем меню с кнопками
    keyboard = [
        [InlineKeyboardButton("Тренировка 1", callback_data='1')],
        [InlineKeyboardButton("Тренировка 2", callback_data='2')],
        [InlineKeyboardButton("Тренировка 3", callback_data='3')],
        [InlineKeyboardButton("Записать вес", callback_data='log_weight')],
        [InlineKeyboardButton("Посмотреть историю веса", callback_data='view_weight_history')],
        [InlineKeyboardButton("Профиль", callback_data='profile')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(welcome_message, reply_markup=reply_markup)


# Основная функция
def main() -> None:
    # Вставьте сюда ваш токен
    application = Application.builder().token(YOUR TG TOKEN).build()

    threading.Thread(target=start_scheduler).start() 

    # Регистрация обработчиков команд
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('status', status))  # Обработка команды /status
    application.add_handler(CommandHandler('delete', delete))  # Обработка команды /delete
    
    # Регистрация обработчиков кнопок и сообщений
    application.add_handler(CallbackQueryHandler(button))  # Обработка нажатий кнопок
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, log_weight))  # Обработка логирования результатов

    #check_database()

    # Запуск бота
    application.run_polling()

if __name__ == '__main__':
    main()
