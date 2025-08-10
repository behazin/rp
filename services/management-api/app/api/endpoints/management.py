# FILE: ./services/management-api/app/api/endpoints/management.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import json
from common.rabbit import RabbitMQClient
from common.database import get_db
from app.models import management as models
from app.schemas import management as schemas

router = APIRouter()

# --- مدیریت منابع (Sources) ---
@router.get("/sources", response_model=List[schemas.SourceInDB])
def get_all_sources(db: Session = Depends(get_db)):
    """لیست تمام منابع ثبت شده را برمی‌گرداند."""
    return db.query(models.Source).all()

@router.post("/sources", response_model=schemas.SourceInDB, status_code=201)
def create_source(source: schemas.SourceCreate, db: Session = Depends(get_db)):
    db_source = db.query(models.Source).filter(models.Source.url == str(source.url)).first()
    if db_source:
        raise HTTPException(status_code=400, detail="Source URL already registered")
    
    new_source = models.Source(name=source.name, url=str(source.url))
    db.add(new_source)
    db.commit()
    db.refresh(new_source)
    return new_source

@router.delete("/sources/{source_id}", status_code=204)
def delete_source(source_id: int, db: Session = Depends(get_db)):
    db_source = db.query(models.Source).filter(models.Source.id == source_id).first()
    if not db_source:
        raise HTTPException(status_code=404, detail="Source not found")
    
    db.delete(db_source)
    db.commit()
    return

# --- مدیریت مقصدها (Destinations) ---
@router.get("/destinations", response_model=List[schemas.DestinationInDB])
def get_all_destinations(db: Session = Depends(get_db)):
    """لیست تمام مقصدهای ثبت شده را برمی‌گرداند."""
    return db.query(models.Destination).all()

@router.post("/destinations", response_model=schemas.DestinationInDB, status_code=201)
def create_destination(dest: schemas.DestinationCreate, db: Session = Depends(get_db)):
    db_dest = db.query(models.Destination).filter(models.Destination.name == dest.name).first()
    if db_dest:
        raise HTTPException(status_code=400, detail="Destination name already exists")
        
    new_dest = models.Destination(**dest.model_dump())
    db.add(new_dest)
    db.commit()
    db.refresh(new_dest)
    return new_dest

@router.delete("/destinations/{destination_id}", status_code=204)
def delete_destination(destination_id: int, db: Session = Depends(get_db)):
    db_dest = db.query(models.Destination).filter(models.Destination.id == destination_id).first()
    if not db_dest:
        raise HTTPException(status_code=404, detail="Destination not found")
        
    db.delete(db_dest)
    db.commit()
    return

# --- مدیریت ارتباط بین منابع و مقصدها ---
@router.post("/sources/{source_id}/link/{destination_id}", response_model=schemas.SourceInDB)
def link_source_to_destination(source_id: int, destination_id: int, db: Session = Depends(get_db)):
    db_source = db.query(models.Source).filter(models.Source.id == source_id).first()
    if not db_source:
        raise HTTPException(status_code=404, detail="Source not found")

    db_dest = db.query(models.Destination).filter(models.Destination.id == destination_id).first()
    if not db_dest:
        raise HTTPException(status_code=404, detail="Destination not found")

    if db_dest not in db_source.destinations:
        db_source.destinations.append(db_dest)
        db.commit()
        db.refresh(db_source)
    return db_source

# --- مدیریت پست‌ها (Posts) ---
@router.post("/posts", response_model=schemas.PostInDB, status_code=201)
def create_post(post: schemas.PostCreate, db: Session = Depends(get_db)):
    """این API توسط fetcher-service برای ایجاد پست جدید استفاده می‌شود."""
    post_data = post.model_dump(exclude_unset=True) # فقط فیلدهای ارسال شده را می‌گیرد
    
    # اطمینان از اینکه آبجکت‌های URL به رشته تبدیل شده‌اند
    if 'url_original' in post_data and post_data['url_original'] is not None:
        post_data['url_original'] = str(post_data['url_original'])
    if 'image_urls_original' in post_data and post_data.get('image_urls_original'):
        post_data['image_urls_original'] = [str(url) for url in post_data['image_urls_original']]
    
    new_post = models.Post(**post_data)
    db.add(new_post)
    db.commit()
    db.refresh(new_post)
    return new_post

@router.get("/posts/exists")
def post_exists(url_original: str, db: Session = Depends(get_db)):
    """بررسی می‌کند آیا پستی با URL مشخص شده وجود دارد یا خیر."""
    db_post = db.query(models.Post).filter(models.Post.url_original == url_original).first()
    return {"exists": db_post is not None}

@router.get("/posts/pending", response_model=List[schemas.PostInDB])
def get_pending_posts(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """لیست پست‌های در انتظار تایید را برمی‌گرداند."""
    posts = db.query(models.Post).filter(models.Post.status == models.PostStatus.PENDING_APPROVAL).offset(skip).limit(limit).all()
    return posts

@router.post("/posts/{post_id}/approve", response_model=schemas.PostInDB)
def approve_post(post_id: int, db: Session = Depends(get_db)):
    """یک پست را تایید می‌کند، وضعیت آن را به 'approved' تغییر می‌دهد و پیامی به RabbitMQ ارسال می‌کند."""
    db_post = db.query(models.Post).filter(models.Post.id == post_id).first()
    if not db_post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    db_post.status = models.PostStatus.APPROVED
    db.commit()
    
    try:
        with RabbitMQClient() as client:
            message_body = json.dumps({"post_id": db_post.id})
            client.channel.queue_declare(queue='post_approval_queue', durable=True)
            client.publish(exchange_name="", routing_key="post_approval_queue", body=message_body)
            logger.info(f"Successfully sent approval message for post_id: {post_id} to RabbitMQ.")
    except Exception as e:
        logger.error(f"Failed to send message to RabbitMQ for post_id: {post_id}. Error: {e}")
    
    db.refresh(db_post)
    return db_post

@router.get("/posts/{post_id}", response_model=schemas.PostInDB)
def get_post(post_id: int, db: Session = Depends(get_db)):
    """اطلاعات یک پست مشخص را بر اساس شناسه آن برمی‌گرداند."""
    db_post = db.query(models.Post).filter(models.Post.id == post_id).first()
    if not db_post:
        raise HTTPException(status_code=404, detail="Post not found")
    return db_post

@router.post("/posts/{post_id}/translations", response_model=schemas.PostTranslationInDB, status_code=201)
def create_translation_for_post(post_id: int, translation: schemas.PostTranslationCreate, db: Session = Depends(get_db)):
    """یک ترجمه/پردازش جدید برای یک پست مشخص ایجاد می‌کند."""
    db_post = db.query(models.Post).filter(models.Post.id == post_id).first()
    if not db_post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    # model_dump() داده‌های اسکما را به دیکشنری تبدیل می‌کند
    translation_data = translation.model_dump()
    new_translation = models.PostTranslation(**translation_data, post_id=post_id)
    
    db.add(new_translation)
    db.commit()
    db.refresh(new_translation)
    return new_translation