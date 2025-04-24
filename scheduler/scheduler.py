from apscheduler.schedulers.asyncio import AsyncIOScheduler
from instagrapi import Client
from database.models import ScheduledPost
from database.crud import get_scheduled_posts
from datetime import datetime
from database.models import ScheduledPost, User  # Додано User
import asyncio

class PostScheduler:
    def __init__(self, db_session, telegram_bot):
        self.scheduler = AsyncIOScheduler()
        self.db_session = db_session
        self.bot = telegram_bot
        self.instagram_client = Client()

    async def check_posts(self):
        """Перевірка запланованих постів"""
        posts = get_scheduled_posts(self.db_session)
        for post in posts:
            if post.scheduled_time <= datetime.now() and not post.posted:
                await self.publish_post(post)

    async def publish_post(self, post):
        """Публікація поста"""
        try:
            # Виконання синхронного коду в окремому потоці
            await asyncio.to_thread(
                self.instagram_client.login,
                post.user.instagram_username,
                post.user.session_data
            )
            await asyncio.to_thread(
                self.instagram_client.photo_upload,
                post.image_path,
                post.caption
            )
            post.posted = True
            self.db_session.commit()
            await self.bot.send_message(post.user.telegram_id, "✅ Пост успішно опубліковано!")
        except Exception as e:
            await self.bot.send_message(post.user.telegram_id, f"❌ Помилка публікації: {e}")

    def start(self):
        self.scheduler.add_job(self.check_posts, 'interval', minutes=5)
        self.scheduler.start()