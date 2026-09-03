from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from uuid import UUID
from app.models.supplier import Supplier
from app.schemas.supplier import SupplierCreate, SupplierUpdate
from fastapi import HTTPException, status
import logging

logger = logging.getLogger(__name__)
        
def create_supplier(db: Session, supplier_data: SupplierCreate, user_id: UUID) -> Supplier:
    try:
        existing = db.query(Supplier).filter(
            (Supplier.email == supplier_data.email) |
            (Supplier.phone == supplier_data.phone) |
            (Supplier.name == supplier_data.name)
        ).first()

        if existing:
            if existing.email == supplier_data.email:
                detail = f"Supplier with email '{supplier_data.email}' already exists"
            elif existing.phone == supplier_data.phone:
                detail = f"Supplier with phone '{supplier_data.phone}' already exists"
            else:
                detail = f"Supplier with name '{supplier_data.name}' already exists"
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)

        supplier = Supplier(**supplier_data.model_dump(), created_by=user_id)
        db.add(supplier)
        db.commit()
        db.refresh(supplier)

        logger.info(f"Supplier created: {supplier.id}")
        return supplier

    except HTTPException:
        raise
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error creating supplier: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create supplier"
        )

def get_supplier_by_id(db: Session, supplier_id: UUID) -> Supplier:
    supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    
    if not supplier:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="Supplier not found")
    
    return supplier


def get_all_suppliers(db: Session,skip: int = 0,limit: int = 100,is_active: bool = None):
    query = db.query(Supplier)
    
    if is_active is not None:
        query = query.filter(Supplier.is_active == is_active)
    
    total = query.count()
    suppliers = query.offset(skip).limit(limit).all()
    
    return {"total": total, "items": suppliers, "skip": skip, "limit": limit}


def update_supplier(db: Session,supplier_id: UUID,supplier_data: SupplierUpdate) -> Supplier:
    try:
        supplier = get_supplier_by_id(db, supplier_id)
        
        update_data = supplier_data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(supplier, key, value)
        
        db.commit()
        db.refresh(supplier)
        
        logger.info(f"Supplier updated: {supplier.id}")
        return supplier
        
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error updating supplier: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update supplier"
        )


def deactivate_supplier(db: Session, supplier_id: UUID) -> Supplier:
    try:
        supplier = get_supplier_by_id(db, supplier_id)
        
        supplier.is_active = False
        db.commit()
        db.refresh(supplier)
        
        logger.info(f"Supplier deactivated: {supplier.id}")
        return supplier
        
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error deactivating supplier: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to deactivate supplier"
        )