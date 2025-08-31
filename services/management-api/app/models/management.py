# FILE: ./services/management-api/app/models/management.py

from sqlalchemy import Column, Integer, String, JSON, Table, ForeignKey, Text, Enum, DateTime, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from common.database import Base
import enum


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

class PostStatus(str, enum.Enum):
    FETCHED = "fetched"
    PREPROCESSED = "preprocessed"
    PENDING_APPROVAL = "pending_approval"
    PROCESSING_CONTENT = "processing_content"
    READY_FOR_FINAL_APPROVAL = "ready_for_final_approval"
    APPROVED = "approved"
    PUBLISHED = "published"
    REJECTED = "rejected"

class PostImage(Base):
    __tablename__ = "post_images"
    id = Column(Integer, primary_key=True, index=True)
    url = Column(String(2048), nullable=False)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False)

    post = relationship("Post", back_populates="images")   

class Post(Base):
    __tablename__ = "posts"
    id = Column(Integer, primary_key=True, index=True)
    url_original = Column(String(767), unique=True, index=True)
    source_id = Column(Integer, ForeignKey("sources.id"))
    status = Column(String(50), default=PostStatus.FETCHED.value, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now()) # تاریخ ایجاد خودکار
    admin_chat_id = Column(String(255)) # شناسه چت مدیر
    admin_message_id = Column(String(255)) # شناسه پیام مدیریتی
    title_original = Column(String(512))
    content_original = Column(Text)
    source = relationship("Source", back_populates="posts")
    translations = relationship("PostTranslation", back_populates="post", cascade="all, delete-orphan")
    images = relationship("PostImage", back_populates="post", cascade="all, delete-orphan")

class PostTranslation(Base):
    __tablename__ = "post_translations"
    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False)
    language = Column(String(5), nullable=False) # e.g., "fa", "ar", "tr"
    score = Column(Float) # امتیاز هوش مصنوعی
    title_translated = Column(Text)
    content_translated = Column(Text)
    featured_image_url = Column(Text)
    content_telegram = Column(Text)
    content_instagram = Column(Text)
    content_twitter = Column(Text)
    post = relationship("Post", back_populates="translations")