from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from uuid import UUID
from app.database import get_db
from app.models.users import User
from app.dependencies.auth import get_current_business_user
from app.schemas.category import CategoryCreate,CategoryUpdate,CategoryResponse,CategoryListResponse
from app.services.category_service import create_category,get_category_by_id,get_all_categories,update_category,delete_category
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/categories", tags=["Categories"])

@router.post("",response_model=CategoryResponse,status_code=status.HTTP_201_CREATED,summary="Create Category",description="Create a new product category (BUSINESS only)")
def create_new_category(category_data: CategoryCreate,current_user: User = Depends(get_current_business_user),db: Session = Depends(get_db)):
    return create_category(db, category_data)


@router.get("",response_model=dict,summary="List Categories",description="Get all categories with pagination")
def list_categories(skip: int = Query(0, ge=0, description="Skip N items"),
    limit: int = Query(100, ge=1, le=1000, description="Limit to N items"),
    is_active: bool = Query(None, description="Filter by active status"),
    db: Session = Depends(get_db)):
    
    result = get_all_categories(db, skip=skip, limit=limit, is_active=is_active)
    return {
        "total": result["total"],
        "items": [CategoryListResponse.model_validate(cat) for cat in result["items"]],
        "skip": result["skip"],
        "limit": result["limit"]
    }

@router.get("/{category_id}",response_model=CategoryResponse,summary="Get Category",description="Get a specific category by ID")
def get_category(category_id: UUID,db: Session = Depends(get_db)):
    category = get_category_by_id(db, category_id)
    return CategoryResponse.model_validate(category)

@router.put("/{category_id}",response_model=CategoryResponse,summary="Update Category",description="Update an existing category (BUSINESS only)")
def update_existing_category(category_id: UUID,category_data: CategoryUpdate,current_user: User = Depends(get_current_business_user),
    db: Session = Depends(get_db)):
    
    category = update_category(db, category_id, category_data)
    return CategoryResponse.model_validate(category)


@router.delete("/{category_id}",status_code=status.HTTP_204_NO_CONTENT,summary="Delete Category",description="Delete a category (BUSINESS only)")
def delete_existing_category(category_id: UUID,current_user: User = Depends(get_current_business_user),db: Session = Depends(get_db)):

    delete_category(db, category_id)
    return None