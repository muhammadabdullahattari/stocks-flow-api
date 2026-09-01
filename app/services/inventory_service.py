from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from uuid import UUID
from app.models.inventory import Inventory
from app.schemas.inventory import InventoryUpdate
from fastapi import HTTPException, status
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

def get_inventory_by_product_id(db: Session, product_id: UUID) -> Inventory:
    inventory = db.query(Inventory).filter(Inventory.product_id == product_id).first()
    
    if not inventory:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inventory not found"
        )
    
    return inventory


def check_availability(db: Session, product_id: UUID, quantity: int) -> bool:
    try:
        inventory = get_inventory_by_product_id(db, product_id)
        return inventory.quantity_available >= quantity
    except HTTPException:
        raise


def reserve_inventory(db: Session,product_id: UUID,quantity: int) -> Inventory:
    try:
        inventory = get_inventory_by_product_id(db, product_id)
        
        if inventory.quantity_available < quantity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Insufficient inventory. Available: {inventory.quantity_available}"
            )
        
        inventory.quantity_reserved += quantity
        db.commit()
        db.refresh(inventory)
        
        logger.info(f"Inventory reserved: product_id={product_id}, quantity={quantity}")
        return inventory
        
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Error reserving inventory: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reserve inventory"
        )


def release_reserved_inventory(db: Session,product_id: UUID,quantity: int) -> Inventory:
    try:
        inventory = get_inventory_by_product_id(db, product_id)        
        inventory.quantity_reserved = max(0, inventory.quantity_reserved - quantity)
        
        db.commit()
        db.refresh(inventory)
        
        logger.info(f"Inventory released: product_id={product_id}, quantity={quantity}")
        return inventory
        
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Error releasing inventory: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to release inventory"
        )


def update_inventory(db: Session,product_id: UUID,inventory_data: InventoryUpdate) -> Inventory:
    try:
        inventory = get_inventory_by_product_id(db, product_id)
        
        update_data = inventory_data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(inventory, key, value)
        
        if "quantity_on_hand" in update_data or "quantity_reserved" in update_data:
            inventory.quantity_available = max(0,inventory.quantity_on_hand - inventory.quantity_reserved)
        
        db.commit()
        db.refresh(inventory)
        
        logger.info(f"Inventory updated: product_id={product_id}")
        return inventory
        
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Error updating inventory: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update inventory"
        )


def add_stock(db: Session,product_id: UUID,quantity: int) -> Inventory:
    try:
        if quantity <= 0:
            raise ValueError("Quantity must be positive")
        
        inventory = get_inventory_by_product_id(db, product_id)
        inventory.quantity_on_hand += quantity
        inventory.quantity_available = max(0,inventory.quantity_on_hand - inventory.quantity_reserved)
        inventory.last_restock_at = datetime.now(timezone.utc)
        
        db.commit()
        db.refresh(inventory)
        
        logger.info(f"Stock added: product_id={product_id}, quantity={quantity}")
        return inventory
        
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Error adding stock: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add stock"
        )