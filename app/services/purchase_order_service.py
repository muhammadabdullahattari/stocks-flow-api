from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from uuid import UUID
from decimal import Decimal
from datetime import datetime, timezone
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_order_item import PurchaseOrderItem
from app.models.product import Product
from app.schemas.purchase_order import PurchaseOrderCreate, PurchaseOrderUpdate
from app.services.product_service import get_product_by_id
from app.services.inventory_service import add_stock, get_inventory_by_product_id
from fastapi import HTTPException, status
import logging
import random
import string

logger = logging.getLogger(__name__)


def generate_po_number() -> str:
    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
    return f"PO-{date_str}-{random_str}"

def create_purchase_order(db: Session,po_data: PurchaseOrderCreate,user_id: UUID) -> PurchaseOrder:
   
    try:
        from app.services.supplier_service import get_supplier_by_id
        
        supplier = get_supplier_by_id(db, po_data.supplier_id)
        if not supplier.is_active:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail="Cannot create PO with inactive supplier")
        
        products_data = {}
        for item in po_data.items:
            product = get_product_by_id(db, item.product_id)
            products_data[item.product_id] = product
        
        total_amount = Decimal("0.00")
        po_items_data = []
        
        for item in po_data.items:
            subtotal = item.unit_cost * item.quantity_ordered
            total_amount += subtotal
            
            po_items_data.append({
                "product_id": item.product_id,
                "quantity_ordered": item.quantity_ordered,
                "unit_cost": item.unit_cost,
                "subtotal": subtotal,
                "quantity_received": 0
            })
        
        purchase_order = PurchaseOrder(
            po_number=generate_po_number(),
            supplier_id=po_data.supplier_id,
            created_by=user_id,
            status="draft",
            total_amount=total_amount,
            expected_delivery_date=po_data.expected_delivery_date,
            notes=po_data.notes
        )
        db.add(purchase_order)
        db.flush()
        
        for item_data in po_items_data:
            po_item = PurchaseOrderItem(**item_data, purchase_order_id=purchase_order.id)
            db.add(po_item)
        
        db.commit()
        db.refresh(purchase_order)
        
        logger.info(f"Purchase order created: {purchase_order.id}")
        return purchase_order
        
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error creating purchase order: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create purchase order"
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating purchase order: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create purchase order"
        )


def get_purchase_order_by_id(db: Session, po_id: UUID) -> PurchaseOrder:
    """Get purchase order by ID"""
    po = db.query(PurchaseOrder).filter(PurchaseOrder.id == po_id).first()
    
    if not po:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Purchase order not found"
        )
    
    return po


def get_all_purchase_orders(db: Session,skip: int = 0,limit: int = 100,status: str = None,supplier_id: UUID = None):
    
    query = db.query(PurchaseOrder)
    
    if status:
        query = query.filter(PurchaseOrder.status == status)
    
    if supplier_id:
        query = query.filter(PurchaseOrder.supplier_id == supplier_id)
    
    total = query.count()
    pos = query.order_by(PurchaseOrder.created_at.desc()).offset(skip).limit(limit).all()
    
    return {"total": total, "items": pos, "skip": skip, "limit": limit}


def update_purchase_order(db: Session,po_id: UUID,po_data: PurchaseOrderUpdate) -> PurchaseOrder:
    
    try:
        po = get_purchase_order_by_id(db, po_id)
        
        if po.status != "draft":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot update purchase order with status '{po.status}'. Only 'draft' POs can be updated."
            )
        
        update_data = po_data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(po, key, value)
        
        db.commit()
        db.refresh(po)
        
        logger.info(f"Purchase order updated: {po.id}")
        return po
        
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error updating purchase order: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update purchase order"
        )


def update_po_status(db: Session,po_id: UUID,new_status: str) -> PurchaseOrder:

    try:
        po = get_purchase_order_by_id(db, po_id)
        
        valid_statuses = ["draft", "pending", "confirmed", "received", "cancelled"]
        if new_status not in valid_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status. Must be one of {valid_statuses}"
            )
        
        transitions = {
            "draft": ["pending", "cancelled"],
            "pending": ["confirmed", "cancelled"],
            "confirmed": ["received", "cancelled"],
            "received": [],
            "cancelled": []
        }
        
        if new_status not in transitions.get(po.status, []):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot transition from '{po.status}' to '{new_status}'"
            )
        
        po.status = new_status
        db.commit()
        db.refresh(po)
        
        logger.info(f"Purchase order status updated: {po.id} → {new_status}")
        return po
        
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error updating PO status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update purchase order status"
        )


def receive_po_item(db: Session,po_id: UUID,po_item_id: UUID,quantity_received: int) -> PurchaseOrderItem:
    
    try:
        po = get_purchase_order_by_id(db, po_id)
        
        if po.status not in ["confirmed", "received"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Can only receive stock from 'confirmed' or 'received' POs. Current status: '{po.status}'"
            )
        
        po_item = db.query(PurchaseOrderItem).filter(
            PurchaseOrderItem.id == po_item_id,
            PurchaseOrderItem.purchase_order_id == po_id
        ).first()
        
        if not po_item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Purchase order item not found"
            )
        
        if quantity_received <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Quantity received must be greater than 0"
            )
        
        total_received = po_item.quantity_received + quantity_received
        if total_received > po_item.quantity_ordered:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot receive {quantity_received}. Already received {po_item.quantity_received}, ordered {po_item.quantity_ordered}"
            )
        
        po_item.quantity_received = total_received
        po_item.received_at = datetime.now(timezone.utc)
        
        inventory = add_stock(db, po_item.product_id, quantity_received)
        
        all_items = db.query(PurchaseOrderItem).filter(PurchaseOrderItem.purchase_order_id == po_id).all()
        
        all_fully_received = all(item.quantity_received == item.quantity_ordered for item in all_items)
        
        if all_fully_received and po.status != "received":
            po.status = "received"
            po.actual_delivery_date = datetime.now(timezone.utc)
        
        db.commit()
        db.refresh(po_item)
        
        logger.info(f"PO item received: po_id={po_id}, quantity={quantity_received}")
        return po_item
        
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error receiving PO item: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to receive purchase order item"
        )


def cancel_purchase_order(db: Session, po_id: UUID) -> PurchaseOrder:

    try:
        po = get_purchase_order_by_id(db, po_id)
        
        if po.status not in ["draft", "pending", "confirmed"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot cancel PO with status '{po.status}'. Only draft/pending/confirmed can be cancelled."
            )
        
        po.status = "cancelled"
        db.commit()
        db.refresh(po)
        
        logger.info(f"Purchase order cancelled: {po.id}")
        return po
        
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error cancelling PO: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel purchase order"
        )


def get_po_items(db: Session, po_id: UUID):
    po = get_purchase_order_by_id(db, po_id)
    
    items_with_details = []
    for item in po.purchase_order_items:
        items_with_details.append({
            "id": item.id,
            "product_id": item.product_id,
            "product_name": item.product.name,
            "product_sku": item.product.sku,
            "quantity_ordered": item.quantity_ordered,
            "quantity_received": item.quantity_received,
            "quantity_pending": item.quantity_ordered - item.quantity_received,
            "unit_cost": float(item.unit_cost),
            "subtotal": float(item.subtotal),
            "received_at": item.received_at
        })
    
    return items_with_details


def get_pending_shipments(db: Session) -> dict:
    pos = db.query(PurchaseOrder).filter(PurchaseOrder.status.in_(["confirmed", "received"])).all()
    
    pending_pos = []
    for po in pos:
        pending_items = [item for item in po.purchase_order_items if item.quantity_received < item.quantity_ordered]
        
        if pending_items:
            pending_po = {
                "po_id": po.id,
                "po_number": po.po_number,
                "supplier_id": po.supplier_id,
                "supplier_name": po.supplier.name,
                "status": po.status,
                "expected_delivery_date": po.expected_delivery_date,
                "pending_items_count": len(pending_items),
                "pending_items": [
                    {
                        "product_name": item.product.name,
                        "quantity_ordered": item.quantity_ordered,
                        "quantity_received": item.quantity_received,
                        "quantity_pending": item.quantity_ordered - item.quantity_received
                    }
                    for item in pending_items
                ]
            }
            pending_pos.append(pending_po)
    
    return {"count": len(pending_pos),"purchase_orders": pending_pos}
    