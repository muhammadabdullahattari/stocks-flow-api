from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID
from app.database import get_db
from app.models.users import User
from app.dependencies.auth import get_current_user, get_current_business_user
from app.schemas.inventory import InventoryUpdate,InventoryResponse,InventorySimpleResponse
from app.services.inventory_service import get_inventory_by_product_id,check_availability,update_inventory
import logging
from app.models.inventory import Inventory
from app.models.product import Product

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/inventory", tags=["Inventory"])

@router.get("/product/{product_id}",response_model=InventoryResponse,summary="Get Product Inventory",description="Get inventory details for a product (BUSINESS only)")
def get_product_inventory(product_id: UUID,current_user: User = Depends(get_current_business_user),db: Session = Depends(get_db)):
    inventory = get_inventory_by_product_id(db, product_id)
    return InventoryResponse.model_validate(inventory)

@router.get("/product/{product_id}/availability",response_model=InventorySimpleResponse,summary="Check Product Availability",description="Check if product is available (simplified view)")
def check_product_availability(product_id: UUID,current_user: User = Depends(get_current_user),db: Session = Depends(get_db)):
    inventory = get_inventory_by_product_id(db, product_id)
    return InventorySimpleResponse(quantity_available=inventory.quantity_available,quantity_on_hand=inventory.quantity_on_hand)

@router.put("/product/{product_id}",response_model=InventoryResponse,summary="Update Inventory",description="Update inventory levels (BUSINESS only)")
def update_product_inventory(product_id: UUID,inventory_data: InventoryUpdate,current_user: User = Depends(get_current_business_user),db: Session = Depends(get_db)):
    inventory = update_inventory(db, product_id, inventory_data)
    return InventoryResponse.model_validate(inventory)

@router.get("/low-stock",response_model=dict,summary="Low Stock Products",description="Get products below reorder level (BUSINESS only)")
def get_low_stock_products(current_user: User = Depends(get_current_business_user),db: Session = Depends(get_db)):
    low_stock = db.query(Inventory).filter(Inventory.quantity_available <= Inventory.reorder_level).join(Product).all()
    
    return {
        "count": len(low_stock),
        "products": [
            {
                "product_id": inv.product_id,
                "product_name": inv.product.name,
                "current_stock": inv.quantity_available,
                "reorder_level": inv.reorder_level,
                "reorder_quantity": inv.reorder_quantity
            }
            for inv in low_stock
        ]
    }