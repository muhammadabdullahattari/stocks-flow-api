from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import select
from uuid import UUID
from app.models.category import Category
from app.schemas.category import CategoryCreate, CategoryUpdate
from fastapi import HTTPException, status
import logging
import re

from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

# In-memory category cache for heavy read load (TTL: 60s)
_CATEGORY_CACHE = {}

def invalidate_category_cache():
    global _CATEGORY_CACHE
    _CATEGORY_CACHE.clear()

def generate_slug(name: str) -> str:
    slug = name.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug


def create_category(db: Session, category_data: CategoryCreate) -> Category:
    try:
        
        existing_name = db.query(Category).filter(Category.name == category_data.name).first()
        if existing_name:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT,detail=f"Category with name '{category_data.name}' already exists")
        
        base_slug = generate_slug(category_data.name)
        slug = base_slug
        suffix = 1

        while db.query(Category).filter(Category.slug == slug).first():
            suffix += 1
            slug = f"{base_slug}-{suffix}"

        category = Category(**category_data.model_dump(), slug=slug)
        db.add(category)
        db.commit()
        db.refresh(category)
        
        invalidate_category_cache()
        logger.info(f"Category created: {category.id}")
        return category
        
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error creating category: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,detail="Failed to create category")

def get_category_by_id(db: Session, category_id: UUID) -> Category:
    category = db.query(Category).filter(Category.id == category_id).first()
    
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="Category not found")
    
    return category


def get_all_categories(db: Session, skip: int = 0, limit: int = 100, is_active: bool = None):
    cache_key = (skip, limit, is_active)
    now = datetime.now(timezone.utc)
    if cache_key in _CATEGORY_CACHE:
        cached_time, cached_result = _CATEGORY_CACHE[cache_key]
        if now - cached_time < timedelta(seconds=60):
            return cached_result

    query = db.query(Category)
    
    if is_active is not None:
        query = query.filter(Category.is_active == is_active)
    
    total = query.count()
    categories = query.offset(skip).limit(limit).all()
    
    result = {"total": total, "items": categories, "skip": skip, "limit": limit}
    _CATEGORY_CACHE[cache_key] = (now, result)
    return result


def update_category(db: Session,category_id: UUID,category_data: CategoryUpdate) -> Category:
    try:
        category = get_category_by_id(db, category_id)
        
        update_data = category_data.model_dump(exclude_unset=True)

        if "name" in update_data and update_data["name"] != category.name:
            
            existing_name = db.query(Category).filter(Category.name == update_data["name"],Category.id != category_id).first()
            if existing_name:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Category with name '{update_data['name']}' already exists"
                )
            
            base_slug = generate_slug(update_data["name"])
            slug = base_slug
            suffix = 1

            while db.query(Category).filter(Category.slug == slug,Category.id != category_id).first():
                suffix += 1
                slug = f"{base_slug}-{suffix}"

        if "slug" in update_data:
            existing_slug = db.query(Category).filter(Category.slug == update_data["slug"], Category.id != category_id).first()
            if existing_slug:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Category with slug '{update_data['slug']}' already exists"
                )

        for key, value in update_data.items():
            setattr(category, key, value)
        
        db.commit()
        db.refresh(category)
    
        invalidate_category_cache()
        logger.info(f"Category updated: {category.id}")
        return category
        
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error updating category: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update category"
        )


def delete_category(db: Session, category_id: UUID) -> bool:
    try:
        category = get_category_by_id(db, category_id)
        
        if category.products:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete category with products. Deactivate products first."
            )
        
        db.delete(category)
        db.commit()
        
        invalidate_category_cache()
        logger.info(f"Category deleted: {category_id}")
        return True
        
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error deleting category: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete category"
        )