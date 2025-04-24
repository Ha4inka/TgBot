from instagrapi import Client
import logging
import asyncio
import os
from instagrapi.exceptions import (
    LoginRequired,
    PleaseWaitFewMinutes,
    PrivateAccount,
    UserNotFound,
    ClientConnectionError,
    ClientForbiddenError,
    ClientThrottledError,
    TwoFactorRequired,
    ChallengeRequired
)
from telegram import Update
from telegram.ext import CallbackContext

from database.models import User #Використовується

logging.basicConfig(level=logging.INFO)

class InstagramAPI:
    def __init__(self, db_session):
        self.client = Client()
        self.db_session = db_session #Зберiгаємо сесiю
        self.is_logged_in = False
        self.username = None
        self._last_login_result = None
        self.user_id = None  # Зберігаємо user_id

    async def is_logged_in_check(self): #Метод для перевірки
        return self.is_logged_in

    async def load_session(self):
        """Завантаження сесії з БД."""
        if not self.user_id:
            logging.warning("User ID not set, cannot load session.")
            return False
        user = self.db_session.query(User).filter(User.telegram_id == self.user_id).first()
        if user and user.session_data:
            try:
                self.client.load_settings_from_json(user.session_data)  #Використовуєм json
                self.is_logged_in = True
                self.username = user.username
                logging.info(f"Сесія для {self.username} завантажена з БД.")
                return True
            except Exception as e:
                logging.error(f"Помилка завантаження сесії: {e}")
                return False
        return False

    async def save_session(self):
        """Збереження сесії в БД."""
        if not self.is_logged_in:
            return False

        user = self.db_session.query(User).filter(User.telegram_id == self.user_id).first()
        if user:
            try:
                user.session_data = self.client.dump_settings_json()
                self.db_session.commit()
                logging.info(f"Сесія для {self.username} збережена в БД.")
                return True
            except Exception as e:
                logging.error(f"Помилка збереження сесії: {e}")
                return False
        return False

    async def login(self, username, password):
        if os.environ.get("http_proxy"): #якщо треба проксі
                self.client.set_proxy(os.environ.get("http_proxy"))
        try:
            self.client.login(username, password)
            self.is_logged_in = True
            self.username = username
            logging.info(f"✅ Успішний вхід у Instagram як {username}")

            #Оновлюємо, або створюємо юзера
            user = self.db_session.query(User).filter(User.telegram_id == self.user_id).first()
            if not user: #Якщо юзер не існує
                user = User(telegram_id=self.user_id, username=username)
                self.db_session.add(user)
            else: #Якщо існує
                user.username = username #оновлюємо данні
            self.db_session.commit()
            await self.save_session() # Зберігаєм сесію в БД
            self._last_login_result = True
            return True

        except TwoFactorRequired:
            logging.warning("Потрібна двоетапна автентифікація.")
            self._last_login_result = None
            return False # Вказуємо що треба 2FA
        except ChallengeRequired:
            logging.warning("Потрібне підтвердження особи.")
            self._last_login_result = False
            return False # Без обробки
        except (LoginRequired, PleaseWaitFewMinutes, PrivateAccount, UserNotFound) as e:
            logging.warning(f"Помилка входу: {type(e).__name__} - {e}")
            self._last_login_result = False
            return False
        except (ClientConnectionError, ClientForbiddenError, ClientThrottledError) as e:
            logging.error(f"Помилка Instagram API: {type(e).__name__} - {e}")
            self._last_login_result = False
            return False
        except Exception as e:
            logging.error(f"❌ Неочікувана помилка входу: {e}")
            self._last_login_result = False
            return False

    async def request_2fa_code(self, context : CallbackContext, update: Update):
        """Запит коду 2FA (тепер з context)"""
        #Отримуємо об'єкт
        await context.bot.send_message(update.message.from_user.id, "Будь ласка, введіть код 2FA:")  # Надсилаємо запит 2FA

    async def complete_2fa_login(self, code : str):
        """Завершення входу з 2FA (змінено)"""
        try:
            self.client.two_factor_login(code) #Використовуємо метод two_factor_login
            self.is_logged_in = True
            logging.info("✅ Успішний вхід з 2FA!")
            await self.save_session() # Зберігаєм
            #Оновлюєм інфу про юзера
            user = self.db_session.query(User).filter(User.telegram_id == self.user_id).first()
            if user:
               user.two_factor_enabled = True #зберігаєм що увімкнено 2fa
               self.db_session.commit()
            return True
        except Exception as e:
                logging.warning(f"Помилка 2FA: {e}")
                return False


    async def logout(self):
        """Вихід з Instagram."""
        if self.is_logged_in:
            try:
                await asyncio.to_thread(self.client.logout)
               # Очищаємо дані сесії з БД
                user = self.db_session.query(User).filter(User.telegram_id == self.user_id).first()
                if user:
                    user.session_data = None  # Очищаємо дані сесії
                    user.two_factor_enabled = False
                    self.db_session.commit()  # Зберігаємо зміни

                self.is_logged_in = False
                self.username = None
                logging.info("Вихід з Instagram успішний.")
                return True
            except Exception as e:
                logging.error(f"Помилка виходу: {e}")
                return False
        return False

    async def get_user_stats(self):
        """Отримання статистики акаунта."""
        if not self.is_logged_in:
             return None

        try:
            user_id = await asyncio.to_thread(self.client.user_id_from_username, self.username)
            user_info = await asyncio.to_thread(self.client.user_info, user_id)

            total_likes = 0
            medias = await asyncio.to_thread(self.client.user_medias, user_id, amount=0)
            for media in medias:
                total_likes += media.like_count

            stats = {
                "Лайки (всього)": total_likes,
                "Підписники": user_info.follower_count,
                "Підписки": user_info.following_count,
                "Публікації" : user_info.media_count
            }
            return stats
        except Exception as e:
            logging.error(f"❌ Помилка отримання статистики: {e}")
            return None

    async def get_last_post_stats(self):
        """Отримання статистики останнього поста."""
        if not self.is_logged_in:
            return None

        try:
            user_id = await asyncio.to_thread(self.client.user_id_from_username, self.username)
            posts = await asyncio.to_thread(self.client.user_medias, user_id, amount=1)

            if not posts:
                return {"likes": 0, "comments": 0, "views": 0}

            last_post = posts[0]
            return {
                "Лайки": last_post.like_count,
                "Коментарі": last_post.comment_count,
                "Перегляди": last_post.view_count if hasattr(last_post, 'view_count') else 0
            }
        except Exception as e:
            logging.error(f"❌ Помилка отримання статистики останнього поста: {e}")
            return None

    async def post_photo(self, photo_path, caption):
        """Публікація фото з підписом."""
        if not self.is_logged_in:
            raise Exception("Користувач не авторизований")
        try:
            await asyncio.to_thread(self.client.photo_upload, photo_path, caption)
            logging.info("Фото успішно опубліковано")

        except Exception as e:
            logging.error(f"Помилка публікації фото: {e}")
            raise

    async def post_story(self, photo_path):
        """Публікація історії з фотографією."""
        if not self.is_logged_in:
              raise Exception("Користувач не авторизований.")
        try:
            await asyncio.to_thread(self.client.photo_upload_to_story, photo_path)
            logging.info("Сторіс успішно опубліковано.")
        except Exception as e:
            logging.error(f"Помилка при публікації сторіс: {e}")
            raise
