# FILE: ./services/management-api/app/schemas/management.py

from pydantic import BaseModel, HttpUrl, ConfigDict
from typing import Dict, Any, List, Optional
from datetime import datetime
from app.models.management import PostStatus

# --- Base Schemas ---
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
    
# --- Post Translation Schemas ---
class PostTranslationBase(BaseModel):
    language: str
    title_translated: Optional[str] = None
    content_translated: Optional[str] = None
    featured_image_url: Optional[HttpUrl] = None
    content_telegram: Optional[str] = None
    content_instagram: Optional[str] = None
    content_twitter: Optional[str] = None
    score: Optional[float] = None #

class PostTranslationInDB(PostTranslationBase):
    id: int
    post_id: int
    model_config = ConfigDict(from_attributes=True)

# --- Post Schemas ---
class PostBase(BaseModel):
    title_original: Optional[str] = None
    content_original: Optional[str] = None
    # --- START: این خط فراموش شده بود ---
    url_original: Optional[HttpUrl] = None
    # --- END: بخش اضافه شده ---
    image_urls_original: Optional[List[HttpUrl]] = []

class PostCreate(PostBase):
    source_id: int

class PostInDB(PostBase):
    id: int
    source_id: int
    status: PostStatus
    created_at: datetime
    translations: List[PostTranslationInDB] = []
    model_config = ConfigDict(from_attributes=True)

# --- اسکماهای نهایی برای نمایش روابط ---
class SourceInDB(SourceInDBBase):
    destinations: List[DestinationInDBBase] = []

class DestinationInDB(DestinationInDBBase):
    sources: List[SourceInDBBase] = []

class PostTranslationBase(BaseModel):
    language: str
    title_translated: Optional[str] = None
    content_translated: Optional[str] = None
    featured_image_url: Optional[HttpUrl] = None
    content_telegram: Optional[str] = None
    content_instagram: Optional[str] = None
    content_twitter: Optional[str] = None

# --- START: این کلاس جدید را اضافه کنید ---
class PostTranslationCreate(PostTranslationBase):
    pass
# --- END: بخش اضافه شده ---

class PostTranslationInDB(PostTranslationBase):
    id: int
    post_id: int
    model_config = ConfigDict(from_attributes=True)