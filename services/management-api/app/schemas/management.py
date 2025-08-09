# FILE: ./services/management-api/app/schemas/management.py

from pydantic import BaseModel, HttpUrl, ConfigDict
from typing import Dict, Any, List, Optional
from datetime import datetime
from app.models.management import PostStatus

# --- Base Schemas ---
# این اسکماها برای جلوگیری از تکرار در اسکماهای دیگر استفاده می‌شوند
class SourceBase(BaseModel):
    name: str
    url: HttpUrl

class DestinationBase(BaseModel):
    name: str
    platform: str
    credentials: Dict[str, Any]

# --- Source Schemas ---
class SourceCreate(SourceBase):
    pass

class SourceInDBBase(SourceBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

# --- Destination Schemas ---
class DestinationCreate(DestinationBase):
    pass

class DestinationInDBBase(DestinationBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

# --- Post Translation Schemas (برای هر زبان) ---
class PostTranslationBase(BaseModel):
    language: str
    title_translated: Optional[str] = None
    content_translated: Optional[str] = None
    featured_image_url: Optional[HttpUrl] = None
    content_telegram: Optional[str] = None
    content_instagram: Optional[str] = None
    content_twitter: Optional[str] = None

class PostTranslationInDB(PostTranslationBase):
    id: int
    post_id: int
    model_config = ConfigDict(from_attributes=True)
    
# --- Post Schemas (پست اصلی) ---
class PostBase(BaseModel):
    title_original: Optional[str] = None
    content_original: Optional[str] = None
    image_urls_original: Optional[List[HttpUrl]] = None
    score: Optional[float] = None

class PostInDB(PostBase):
    id: int
    source_id: int
    status: PostStatus
    created_at: datetime
    translations: List[PostTranslationInDB] = [] # نمایش ترجمه‌های مرتبط
    model_config = ConfigDict(from_attributes=True)

# --- اسکماهای نهایی برای نمایش روابط ---
# این اسکماها به ما اجازه می‌دهند تا ببینیم هر منبع به کدام مقصدها متصل است و بالعکس
class SourceInDB(SourceInDBBase):
    destinations: List[DestinationInDBBase] = []

class DestinationInDB(DestinationInDBBase):
    sources: List[SourceInDBBase] = []