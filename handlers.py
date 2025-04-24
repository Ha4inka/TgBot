import json
import logging
import os

import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext

from api.api import InstagramAPI
from config import DEEPSEEK_API_KEY, DEEPSEEK_API_URL

# Налаштування логування
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Глобальний кеш для збереження станів користувачів
user_state = {}

# Функція для взаємодії з DeepSeek API
async def get_deepseek_response(user_message):
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "deepseek/deepseek-r1:free",
        "messages": [
            {"role": "system", "content": "Ти AI-асистент для Telegram бота, який допомагає керувати Instagram. Відповідаєш чітко коротко та без зайвого."},
            {"role": "user", "content": user_message}
        ],
        "max_tokens": 500,
        "temperature": 0.7
    }

    try:
        response = requests.post(DEEPSEEK_API_URL, headers=headers, data=json.dumps(data))
        response.raise_for_status()
        response_data = response.json()
        logger.info(f"Відповідь DeepSeek API: {response_data}")
        return response_data['choices'][0]['message']['content']

    except requests.exceptions.RequestException as e:
        logger.error(f"Помилка запиту до DeepSeek API: {e}")
        return "❌ Помилка при обробці вашого запиту. Спробуйте ще раз."
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        logger.error(f"Помилка обробки відповіді DeepSeek API: {e}")
        return "❌ Не вдалося отримати відповідь від AI. Спробуйте ще раз."


# /start - Початок роботи з ботом
async def start(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id #Отримуємо id
    #Перевіряємо, чи є вже інстанція
    if user_id not in context.bot_data['instagram_api']:
        context.bot_data['instagram_api'][user_id] = InstagramAPI(context.bot_data['db_session']) # Ініціалізуємо
        # Якщо потрiбна попередня iнiцiалзацiя, робимо це тут.
        await context.bot_data['instagram_api'][user_id].load_session() # Спробуємо завантажити
    print("-->>Start function")
    keyboard = [
        [InlineKeyboardButton("Увійти в Instagram", callback_data="login")],
        [InlineKeyboardButton("Вийти з Instagram", callback_data="logout")],
        [InlineKeyboardButton("Отримати статистику", callback_data="get_stats")],
        [InlineKeyboardButton("Запостити фото", callback_data="post_photo")],
        [InlineKeyboardButton("Запостити сторіс", callback_data="post_story")],
        [InlineKeyboardButton("Допомога", callback_data="help")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Привіт! Я бот для керування твоїм Instagram. Що ти хочеш зробити?",
        reply_markup=reply_markup
    )

# /help - Допомога
async def help_command(update: Update, context: CallbackContext):
    await update.message.reply_text(
        "Список доступних команд:\n"
        "/start - Початок роботи\n"
        "/help - Допомога\n"
        "/stats - Отримати статистику\n"
        "/login - Увійти в Instagram (використовуйте /login user:<username> password:<password>)\n"
        "/logout - Вийти з Instagram"
    )


async def login_command(update: Update, context: CallbackContext):
    """Обробник команди /login."""
    user_id = update.message.from_user.id

    # Перевіряємо, чи є вже інстанція InstagramAPI для цього користувача
    if user_id not in context.bot_data['instagram_api']:
        context.bot_data['instagram_api'][user_id] = InstagramAPI(context.bot_data['db_session'])

    insta_api = context.bot_data['instagram_api'][user_id]
    insta_api.user_id = user_id # Додано

    # Перевірка, чи користувач уже в процесі очікування коду 2FA
    if user_id in user_state and user_state[user_id] == "waiting_for_2fa_code":
        # Обробка вводу коду 2FA
        code = update.message.text.strip()
        login_success = await insta_api.complete_2fa_login(code)
        if login_success:
            await update.message.reply_text("✅ Успішний вхід з 2FA!")
            del user_state[user_id]  # Очищаємо стан
        else:
            await update.message.reply_text("❌ Невірний код 2FA. Почніть вхід знову з /login.")
            del user_state[user_id]  # Очищаємо стан у разі невдачі
        return #Завершуємо виконання щоб не оброблялось далі.

    # Обробка звичайного логіну (вхідні дані з команди)
    parts = update.message.text.split()
    if len(parts) >= 3 and parts[0] == '/login':
        try:
            login_part = parts[1].split(":")
            password_part = parts[2].split(":")

            if len(login_part) == 2 and login_part[0] == "user" and len(password_part) == 2 and password_part[0] == "password":
                username = login_part[1].strip()
                password = password_part[1].strip()

                login_success = await insta_api.login(username, password)
                if login_success:
                    await update.message.reply_text("✅ Успішний логін!")
                elif insta_api._last_login_result is False:
                    await update.message.reply_text("❌ Невірний логін або пароль. Спробуйте ще раз.")
                elif insta_api._last_login_result is None:
                    await insta_api.request_2fa_code(context, update)
                    user_state[user_id] = "waiting_for_2fa_code"  # Встановлюємо стан
                else:
                    await update.message.reply_text("Не вдалося увійти. Перевірте дані і спробуйте ще раз.")

            else:
                await update.message.reply_text("Невірний формат. Використовуйте: /login user:<username> password:<password>")
        except Exception as e:
            await update.message.reply_text(f"Сталася помилка: {e}")
            logger.error(f"Помилка при обробці /login: {e}")


    else:
        await update.message.reply_text("Для входу використовуйте команду у форматі: /login user:<username> password:<password>")

# /logout - Обробник команди виходу (НОВИЙ)
async def logout_command(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    # Перевіряємо, чи є вже інстанція InstagramAPI для цього користувача
    if user_id not in context.bot_data['instagram_api']:
        context.bot_data['instagram_api'][user_id] = InstagramAPI(context.bot_data['db_session'])
    insta_api = context.bot_data['instagram_api'][user_id]
    insta_api.user_id = user_id

    if await insta_api.logout():
        await update.message.reply_text("✅ Ви вийшли з Instagram.")
        del context.bot_data['instagram_api'][user_id] #Remove API instance

    else:
        await update.message.reply_text("Ви не авторизовані.")


# Обробник натискань на inline-кнопки
async def button_click(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()  # Завжди викликайте query.answer()
    user_id = query.from_user.id

    # Перевіряємо, чи є вже інстанція InstagramAPI для цього користувача
    if user_id not in context.bot_data['instagram_api']:
        context.bot_data['instagram_api'][user_id] = InstagramAPI(context.bot_data['db_session']) # Ініціалізуємо, якщо потрібно
    insta_api = context.bot_data['instagram_api'][user_id]
    insta_api.user_id = user_id

    if query.data == "login":
        await query.message.reply_text("Введіть команду /login, ваш логін та пароль у форматі: /login user:<username> password:<password>")
    elif query.data == "logout":
        await logout_command(update, context)  # Викликаємо функцію, що оброблює команду
    elif query.data == "get_stats":
        if insta_api.is_logged_in:  # Перевіряємо чи залогінені
            stats = await insta_api.get_user_stats()
            if stats:
                stats_message = "\n".join([f"{key}: {value}" for key, value in stats.items()])
                await query.message.reply_text(f"📊 Ваша статистика:\n{stats_message}")
            else:
                await query.message.reply_text("Не вдалося отримати статистику.")
        else:
            await query.message.reply_text("Спочатку увійдіть в Instagram (/start -> Увійти в Instagram (/login)).")

    elif query.data == "post_photo":

            if insta_api.is_logged_in:
                await query.message.reply_text("Надішліть фото для публікації:")
                user_state[user_id] = "waiting_for_photo"
            else:
                await query.message.reply_text("Спочатку увійдіть в Instagram (/start -> Увійти в Instagram (/login)).")
    elif query.data == "post_story":
          if insta_api.is_logged_in:
            await query.message.reply_text("Надішліть фото для публікації в сторіс:")
            user_state[user_id] = "waiting_for_story_photo"
          else:
            await query.message.reply_text("Спочатку увійдіть в Instagram (/start -> Увійти в Instagram (/login)).")
    elif query.data == "help":
        await help_command(update, context)


# Обробник текстових повідомлень
async def handle_text(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    text = update.message.text

    # Перевіряємо, чи є вже інстанція InstagramAPI для цього користувача
    if user_id not in context.bot_data['instagram_api']:
        context.bot_data['instagram_api'][user_id] = InstagramAPI(context.bot_data['db_session'])

    insta_api = context.bot_data['instagram_api'][user_id]
    insta_api.user_id = user_id

    if user_id in user_state:
        if user_state[user_id] == "waiting_for_caption":
            photo_path = user_state.get(f"{user_id}_photo_path")
            if photo_path:
                if insta_api.is_logged_in:
                    try:
                        await insta_api.post_photo(photo_path, text)  # Використовуємо збережений шлях
                        await update.message.reply_text("✅ Фото опубліковано!")
                    except Exception as e:
                        await update.message.reply_text(f"❌ Помилка при публікації: {e}")
                    finally:
                        # Видаляємо тимчаовий файл
                        try:

                            os.remove(photo_path)
                        except FileNotFoundError:
                            pass

                else:
                    await update.message.reply_text("Спочатку увійдіть в Instagram (/start -> Увійти в Instagram (/login)).")
            else:
                await update.message.reply_text("Сталася помилка з фото. Спробуйте ще раз.")
            # Очищаємо стани
            del user_state[user_id]
            del user_state[f"{user_id}_photo_path"]

        elif user_state[user_id] == "waiting_for_story_caption":
            photo_path = user_state.get(f"{user_id}_story_photo_path")  # виправлено
            if photo_path:
                if insta_api.is_logged_in:
                    try:
                        await insta_api.post_story(photo_path)
                        await update.message.reply_text("✅ Сторіс опубліковано!")
                    except Exception as e:
                        await update.message.reply_text(f"❌ Помилка при публікації сторіс: {e}")
                    finally:
                         # Видаляємо тимчаовий файл
                        try:

                            os.remove(photo_path)
                        except FileNotFoundError:
                            pass

            else:
                await update.message.reply_text("Сталася помилка з фото для сторіс. Спробуйте ще раз.")

             # Очищаємо стани
            del user_state[user_id]
            del user_state[f"{user_id}_story_photo_path"]
        elif user_state[user_id] == "waiting_for_2fa_code":
          await login_command(update,context) #Передаємо обробку назад в login_command
    else:
        response = await get_deepseek_response(text)  # AI, якщо потрібно і команда не розпізнана
        await update.message.reply_text(response)

async def handle_photo(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id

    # Перевіряємо, чи є вже інстанція InstagramAPI для цього користувача
    if user_id not in context.bot_data['instagram_api']:
        context.bot_data['instagram_api'][user_id] = InstagramAPI(context.bot_data['db_session'])

    insta_api = context.bot_data['instagram_api'][user_id]
    insta_api.user_id = user_id


    if user_id in user_state:
        if user_state[user_id] == "waiting_for_photo":
            photo_file = await update.message.photo[-1].get_file()
            photo_path = f"{photo_file.file_unique_id}.jpg"  # Унікальне ім'я
            await photo_file.download_to_drive(photo_path)
            user_state[f"{user_id}_photo_path"] = photo_path  # Зберігаємо шлях
            await update.message.reply_text("Введіть опис для фото:")
            user_state[user_id] = "waiting_for_caption"
            return

        elif user_state[user_id] == "waiting_for_story_photo":
            photo_file = await update.message.photo[-1].get_file()
            photo_path = f"story_{photo_file.file_unique_id}.jpg"
            await photo_file.download_to_drive(photo_path)

            user_state[f"{user_id}_story_photo_path"] = photo_path  # Corrected path
            await update.message.reply_text("Публікую сторіс...")
            if insta_api.is_logged_in:
                try:
                    await insta_api.post_story(photo_path)
                    await update.message.reply_text("✅ Сторіс опубліковано!")
                except Exception as e:
                    await update.message.reply_text(f"❌ Помилка при публікації сторіс: {e}")
                finally:
                     # Видаляємо тимчаовий файл
                    try:

                        os.remove(photo_path)
                    except FileNotFoundError:
                        pass
            else:
                await update.message.reply_text("Спочатку увійдіть в Instagram (/start -> Увійти в Instagram (/login)).")

            # Очищення стану
            del user_state[user_id]
            del user_state[f"{user_id}_story_photo_path"] #Удаляем story_photo_path
            return

    await update.message.reply_text("Я очікую від вас інші дії. Скористайтеся меню /start.")
