from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from uuid import UUID
from app.models.product import Product
from app.models.category import Category
from app.models.inventory import Inventory
from app.schemas.product import ProductCreate, ProductUpdate
from app.services.category_service import get_category_by_id
from fastapi import HTTPException, status
from decimal import Decimal
import logging
import random
import string

logger = logging.getLogger(__name__)

def generate_sku(category: Category, name: str) -> str:
    category_part = "".join(c for c in category.name.upper() if c.isalnum())[:3]
    name_part = "".join(c for c in name.upper() if c.isalnum())[:3]
    random_part = "".join(random.choices(string.digits, k=5))
    return f"{category_part}-{name_part}-{random_part}"

def create_product(db: Session,product_data: ProductCreate,user_id: UUID) -> Product:
    try:
        category = get_category_by_id(db, product_data.category_id)
        
        if product_data.price <= product_data.cost:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail="Selling price must be greater than cost price")
        
        sku = generate_sku(category, product_data.name)
        while db.query(Product).filter(Product.sku == sku).first():
            sku = generate_sku(category, product_data.name)
        
        product = Product(**product_data.model_dump(),sku=sku,created_by=user_id)
        db.add(product)
        db.flush()
        
        inventory = Inventory(product_id=product.id)
        db.add(inventory)
        
        db.commit()
        db.refresh(product)
        
        logger.info(f"Product created: {product.id}")
        return product
        
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error creating product: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create product"
        )


def get_product_by_id(db: Session, product_id: UUID, check_active: bool = False) -> Product:
    product = db.query(Product).filter(Product.id == product_id).first()
    
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="Product not found")
    
    if check_active and not product.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="Product not available")
    
    return product


def get_all_products(db: Session,skip: int = 0,limit: int = 100,category_id: UUID = None,is_active: bool = None,status: str = None):
    query = db.query(Product)
    
    if category_id:
        query = query.filter(Product.category_id == category_id)
    
    if is_active is not None:
        query = query.filter(Product.is_active == is_active)
    
    if status:
        query = query.filter(Product.status == status)
    
    total = query.count()
    products = query.offset(skip).limit(limit).all()
    
    return {"total": total, "items": products, "skip": skip, "limit": limit}


def get_available_products(db: Session, skip: int = 0, limit: int = 100):
    query = db.query(Product).join(Inventory).filter(
        Product.is_active == True,
        Product.status == "active",
        Inventory.quantity_available > 0
    )
    
    total = query.count()
    products = query.offset(skip).limit(limit).all()
    
    return {"total": total, "items": products, "skip": skip, "limit": limit}


def update_product(db: Session,product_id: UUID,product_data: ProductUpdate,user_id: UUID) -> Product:
    try:
        product = get_product_by_id(db, product_id)
        
        if product_data.category_id:
            get_category_by_id(db, product_data.category_id)
        
        if product_data.sku and product_data.sku != product.sku:
            existing = db.query(Product).filter(
                Product.sku == product_data.sku,
                Product.id != product_id
            ).first()
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"SKU '{product_data.sku}' already in use"
                )
        
        price = product_data.price if product_data.price else product.price
        cost = product_data.cost if product_data.cost else product.cost
        if price and cost and price <= cost:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Selling price must be greater than cost price"
            )
        
        update_data = product_data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(product, key, value)
        
        db.commit()
        db.refresh(product)
        
        logger.info(f"Product updated: {product.id}")
        return product
        
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error updating product: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update product"
        )


def deactivate_product(db: Session, product_id: UUID) -> Product:
    try:
        product = get_product_by_id(db, product_id)
        
        product.is_active = False
        product.status = "inactive"
        
        db.commit()
        db.refresh(product)
        
        logger.info(f"Product deactivated: {product.id}")
        return product
        
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error deactivating product: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to deactivate product"
        )