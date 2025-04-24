from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.ext.declarative import declarative_base
import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(Integer, unique=True, index=True)
    username = Column(String, nullable=True)
    session_data = Column(String, nullable=True)
    two_factor_enabled = Column(Boolean, default=False)


class ScheduledPost(Base):
    __tablename__ = "scheduled_posts"

    id = Column(Integer, primary_key=True)
    chat_id = Column(Integer)
    message_text = Column(String)
    scheduled_time = Column(DateTime, default=datetime.datetime.utcnow) # час створення
    photo_path = Column(String, nullable=True) # Шлях до фото, якщо є

    def __repr__(self):
        return f"<ScheduledPost(message_text='{self.message_text}', scheduled_time='{self.scheduled_time}')>"
