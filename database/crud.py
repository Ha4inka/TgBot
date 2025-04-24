# database/crud.py
from sqlalchemy.orm import Session
from database.models import User
from database.models import ScheduledPost
# Імпортуємо ScheduledPost


def get_or_create_user(session: Session, telegram_id: int, username: str):
    user = session.query(User).filter_by(telegram_id=telegram_id).first()
    if not user:
        user = User(telegram_id=telegram_id, username=username)  # Виправляємо
        session.add(user)
        session.commit()
        session.refresh(user)  # Оновлюємо об'єкт user, щоб отримати id
    return user


def get_scheduled_posts(db_session: Session):
    return db_session.query(ScheduledPost).filter(ScheduledPost.posted == False).all()


def add_scheduled_post(session: Session, user_id: int, image_path: str, caption: str, scheduled_time):
    post = ScheduledPost(
        user_id=user_id,
        image_path=image_path,
        caption=caption,
        scheduled_time=scheduled_time
    )
    session.add(post)
    session.commit()
    session.refresh(post)  # Оновлюємо об'єкт post, щоб згенерувати id
    return post
