# models.py
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Text, DateTime, func, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

class Review(Base):
    __tablename__ = 'reviews'
    id = Column(String, primary_key=True)
    sku = Column(Integer)
    text = Column(Text)
    rating = Column(Integer)
    status = Column(String)
    published_at = Column(DateTime(timezone=True))
    order_status = Column(String)
    is_rating_participant = Column(Boolean)
    client_id = Column(String)  # Новая колонка для client_id

    product_info = relationship("ProductInfo", back_populates="review", uselist=False)
    photos = relationship("Photo", back_populates="review")
    videos = relationship("Video", back_populates="review")
    neural_response = relationship("NeuralResponse", back_populates="review", uselist=False)

class Comment(Base):
    __tablename__ = 'comments'
    id = Column(String, primary_key=True)
    review_id = Column(String, ForeignKey('reviews.id'))
    text = Column(Text)
    parent_comment_id = Column(String)
    is_owner = Column(Boolean)
    is_official = Column(Boolean)
    published_at = Column(String)

class Photo(Base):
    __tablename__ = 'photos'
    id = Column(Integer, primary_key=True, autoincrement=True)
    review_id = Column(String, ForeignKey('reviews.id'))
    url = Column(String)
    width = Column(Integer)
    height = Column(Integer)

    review = relationship("Review", back_populates="photos")

class Video(Base):
    __tablename__ = 'videos'
    id = Column(Integer, primary_key=True, autoincrement=True)
    review_id = Column(String, ForeignKey('reviews.id'))
    url = Column(String)
    preview_url = Column(String)
    short_video_preview_url = Column(String)
    width = Column(Integer)
    height = Column(Integer)

    review = relationship("Review", back_populates="videos")

class Log(Base):
    __tablename__ = 'logs'
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(String)
    status = Column(String)
    message = Column(String)

class NeuralResponse(Base):
    __tablename__ = 'neural_responses'
    __table_args__ = (
        UniqueConstraint('review_id', name='uq_neural_response_review_id'),
    )
    id = Column(Integer, primary_key=True, autoincrement=True)
    review_id = Column(String, ForeignKey('reviews.id'))
    response_text = Column(Text)
    created_at = Column(String)  # Время создания ответа

    review = relationship("Review", back_populates="neural_response")

class LogsNeuro(Base):
    __tablename__ = 'logs_neuro'
    id = Column(Integer, primary_key=True, autoincrement=True)
    review_text = Column(Text, nullable=False)
    response_text = Column(Text, nullable=True)
    status = Column(String, nullable=False)
    created_at = Column(String)


class ProductInfo(Base):
    __tablename__ = 'product_info'
    review_id = Column(String, ForeignKey('reviews.id'), primary_key=True)
    sku = Column(Integer, nullable=False)
    product_name = Column(String, nullable=True)  # Будем заполнять позже

    review = relationship("Review", back_populates="product_info")


class Prompt(Base):
    __tablename__ = 'prompts'
    id = Column(String, primary_key=True, unique=True)
    content = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class ProductPrompt(Base):
    __tablename__ = 'product_prompts'
    sku = Column(Integer, primary_key=True)  # Уникальный SKU товара
    prompt = Column(Text, nullable=True)    # Кастомный промпт для этого товара
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class ApiKeys(Base):  # Обратите внимание на стиль именования (PascalCase)
    __tablename__ = 'api_keys'
    id = Column(String, primary_key=True, unique=True)
    yandex_gpt_folder = Column(Text, nullable=True)
    YANDEX_GPT_API_KEY = Column(Text, nullable=True)
    OZON_API_KEY = Column(Text, nullable=True)
    OZON_CLIENT_ID = Column(Text, nullable=True)
    LAST_ID = Column(Text, nullable=True)
    TIMESTUMP = Column(Text, nullable=True)
    IS_PREMIUM_PLUS = Column(Boolean, default=True)
    OZON_COOKIES = Column(Text, nullable=True)
    CUSTUMER_COOKIES = Column(Text, nullable=True)
    STATUS = Column(Boolean, default=True)

class ReviewFilter(Base):
    __tablename__ = 'review_filters'

    id = Column(String, primary_key=True, unique=True)  # Уникальный ID фильтра
    RATING = Column(Integer, nullable=True)  # Фильтр по рейтингу (1-5)
    HAS_TEXT = Column(Boolean, nullable=True)
    IS_ACTIVE = Column(Boolean, default=True)


class PredefinedResponse(Base):
    __tablename__ = 'predefined_responses'

    id = Column(Integer, primary_key=True)
    text = Column(String, nullable=False)
