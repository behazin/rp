# FILE: ./services/management-api/app/models/management.py

from sqlalchemy import Column, Integer, String, JSON, Table, ForeignKey, Text, Enum, DateTime, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from common.database import Base
import enum

# --- جدول واسط برای رابطه چند به چند Source و Destination ---
source_destination_association = Table(
    'source_destination_association', Base.metadata,
    Column('source_id', Integer, ForeignKey('sources.id'), primary_key=True),
    Column('destination_id', Integer, ForeignKey('destinations.id'), primary_key=True)
)

class Source(Base):
    __tablename__ = "sources"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, index=True, nullable=False)
    url = Column(String(767), unique=True, nullable=False)
    
    destinations = relationship(
        "Destination",
        secondary=source_destination_association,
        back_populates="sources"
    )
    posts = relationship("Post", back_populates="source", cascade="all, delete-orphan")

class Destination(Base):
    __tablename__ = "destinations"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False)
    platform = Column(String(50), nullable=False)
    language = Column(String(10), default="fa", nullable=False)
    credentials = Column(JSON, nullable=False)
    
    sources = relationship(
        "Source",
        secondary=source_destination_association,
        back_populates="destinations"
    )

# --- مدل‌های مربوط به پست و ترجمه‌ها ---
class PostStatus(str, enum.Enum):
    FETCHED = "fetched" 
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    PUBLISHED = "published"
    REJECTED = "rejected"

class Post(Base):
    __tablename__ = "posts"
    id = Column(Integer, primary_key=True, index=True)
    url_original = Column(String(767), unique=True, index=True)
    source_id = Column(Integer, ForeignKey("sources.id"))
    
    # ستون‌های مدیریتی و متادیتا
    status = Column(Enum(PostStatus), default=PostStatus.FETCHED, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now()) # تاریخ ایجاد خودکار
    admin_chat_id = Column(String(255)) # شناسه چت مدیر
    admin_message_id = Column(String(255)) # شناسه پیام مدیریتی

    # محتوای اصلی و خام
    title_original = Column(String(512))
    content_original = Column(Text)
    image_urls_original = Column(JSON)

    source = relationship("Source", back_populates="posts")
    translations = relationship("PostTranslation", back_populates="post", cascade="all, delete-orphan")

class PostTranslation(Base):
    __tablename__ = "post_translations"
    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False)
    language = Column(String(5), nullable=False) # e.g., "fa", "ar", "tr"
    score = Column(Float) # امتیاز هوش مصنوعی
    title_translated = Column(String(512))
    content_translated = Column(Text)
    featured_image_url = Column(String(2048))
    content_telegram = Column(String(1024))
    content_instagram = Column(Text)
    content_twitter = Column(String(280))
    post = relationship("Post", back_populates="translations")