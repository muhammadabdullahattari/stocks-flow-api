from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from uuid import UUID
from app.database import get_db
from app.models.users import User
from app.dependencies.auth import get_current_user, get_current_business_user
from app.schemas.product import ProductCreate,ProductUpdate,ProductResponse,ProductListResponse,ProductSearchResponse
from app.services.product_service import ( create_product,get_product_by_id,get_all_products,
    get_available_products,update_product,deactivate_product,search_products_advanced,search_products_by_name)
import logging
from decimal import Decimal

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/products", tags=["Products"])

@router.post("",response_model=ProductResponse,status_code=status.HTTP_201_CREATED,summary="Create Product",description="Create a new product (BUSINESS only)")
def create_new_product(product_data: ProductCreate,current_user: User = Depends(get_current_business_user),db: Session = Depends(get_db)):
    return create_product(db, product_data, current_user.id)

@router.get("/available",response_model=dict,summary="List Available Products",description="Get products available for purchase (CUSTOMER view)")
def list_available_products(skip: int = Query(0, ge=0),limit: int = Query(100, ge=1, le=1000),db: Session = Depends(get_db)):

    result = get_available_products(db, skip=skip, limit=limit)
    return {
        "total": result["total"],
        "items": [ProductListResponse.model_validate(prod) for prod in result["items"]],
        "skip": result["skip"],
        "limit": result["limit"]
    }

@router.get("",response_model=dict,summary="List All Products",description="Get all products with filters (BUSINESS only)")
def list_all_products(skip: int = Query(0, ge=0),limit: int = Query(100, ge=1, le=1000),category_id: UUID = Query(None),
    status: str = Query(None),is_active: bool = Query(None),current_user: User = Depends(get_current_business_user),db: Session = Depends(get_db)):
    result = get_all_products(db,skip=skip,limit=limit,category_id=category_id,status=status,is_active=is_active)
    
    return {
        "total": result["total"],
        "items": [ProductListResponse.model_validate(prod) for prod in result["items"]],
        "skip": result["skip"],
        "limit": result["limit"]
    }

@router.get("/{product_id}",response_model=ProductResponse,summary="Get Product",description="Get a specific product by ID")
def get_product(product_id: UUID,current_user: User = Depends(get_current_user),db: Session = Depends(get_db)):
    product = get_product_by_id(db, product_id)
    
    if current_user.role == "CUSTOMER" and not product.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="Product not found")
    
    return ProductResponse.model_validate(product)

@router.put("/{product_id}",response_model=ProductResponse,summary="Update Product",description="Update an existing product (BUSINESS only)")
def update_existing_product(product_id: UUID,product_data: ProductUpdate,current_user: User = Depends(get_current_business_user),db: Session = Depends(get_db)):
    product = update_product(db, product_id, product_data, current_user.id)
    return ProductResponse.model_validate(product)

@router.patch("/{product_id}/deactivate",response_model=ProductResponse,summary="Deactivate Product",description="Deactivate a product (BUSINESS only)")
def deactivate_existing_product(product_id: UUID,current_user: User = Depends(get_current_business_user),db: Session = Depends(get_db)):
    product = deactivate_product(db, product_id)
    return ProductResponse.model_validate(product)

@router.get(
    "/search/by-name",
    response_model=dict,
    summary="Search Products by Name",
    description="Search products by name using partial matching"
)
def search_products_by_name_endpoint(
    q: str = Query(..., min_length=1, max_length=100, description="Search query (product name or part of it)"),
    skip: int = Query(0, ge=0, description="Skip N items"),
    limit: int = Query(100, ge=1, le=1000, description="Limit to N items"),
    db: Session = Depends(get_db)
):
    """
    Search for products by name.
    
    **Search is case-insensitive and matches anywhere in the product name.**
    
    **Examples:**
    - ?q=laptop → finds "Laptop Pro", "Gaming Laptop", "Budget Laptop"
    - ?q=pro → finds "Laptop Pro", "Pro Max", "Professional"
    - ?q=15 → finds "15 inch", "Pro 15", "Model 15"
    - ?q=gaming → finds "Gaming Laptop", "Gaming Mouse", "Gaming Monitor"
    
    **Query parameters:**
    - q: Search term (required, 1-100 chars)
    - skip: Number of results to skip (default: 0)
    - limit: Maximum results to return (default: 100, max: 1000)
    
    **Returns:** List of matching products with name, price, id
    
    **Note:** Only returns active products
    """
    result = search_products_by_name(db, q, skip=skip, limit=limit)
    
    return {
        "total": result["total"],
        "search_query": result["search_query"],
        "items": [ProductSearchResponse.model_validate(prod) for prod in result["items"]],
        "skip": result["skip"],
        "limit": result["limit"],
        "note": f"Found {result['total']} products matching '{q}'"
    }


@router.get("/search/advanced",response_model=dict,summary="Advanced Product Search",description="Search products with filters (name, category, price)")
def search_products_advanced_endpoint(
    q: str = Query(..., min_length=1, max_length=100, description="Search query"),
    category_id: UUID = Query(None, description="Filter by category (optional)"),
    min_price: Decimal = Query(None, ge=0, description="Minimum price (optional)"),
    max_price: Decimal = Query(None, ge=0, description="Maximum price (optional)"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)):
    
    result = search_products_advanced(db,q,category_id=category_id,min_price=min_price,max_price=max_price,skip=skip,
                                      limit=limit)
    
    return {
        "total": result["total"],
        "search_query": result["search_query"],
        "filters": {
            "category_id": category_id,
            "min_price": float(min_price) if min_price else None,
            "max_price": float(max_price) if max_price else None
        },
        "items": [ProductSearchResponse.model_validate(prod) for prod in result["items"]],
        "skip": result["skip"],
        "limit": result["limit"],
        "note": f"Found {result['total']} products matching filters"
    }