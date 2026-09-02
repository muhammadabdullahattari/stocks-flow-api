from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import select
from uuid import UUID
from app.models.category import Category
from app.schemas.category import CategoryCreate, CategoryUpdate
from fastapi import HTTPException, status
import logging
import re

logger = logging.getLogger(__name__)

def generate_slug(name: str) -> str:
    slug = name.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug


def create_category(db: Session, category_data: CategoryCreate) -> Category:
    try:
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


def get_all_categories(db: Session,skip: int = 0,limit: int = 100,is_active: bool = None):
    query = db.query(Category)
    
    if is_active is not None:
        query = query.filter(Category.is_active == is_active)
    
    total = query.count()
    categories = query.offset(skip).limit(limit).all()
    
    return {"total": total, "items": categories, "skip": skip, "limit": limit}


def update_category(db: Session,category_id: UUID,category_data: CategoryUpdate) -> Category:
    try:
        category = get_category_by_id(db, category_id)
        
        if category_data.slug and category_data.slug != category.slug:
            existing = db.query(Category).filter(
                Category.slug == category_data.slug,
                Category.id != category_id
            ).first()
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Slug '{category_data.slug}' already in use"
                )
        
        update_data = category_data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(category, key, value)
        
        db.commit()
        db.refresh(category)
        
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