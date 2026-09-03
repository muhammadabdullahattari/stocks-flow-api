from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from uuid import UUID
from decimal import Decimal
from datetime import datetime, timezone
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.product import Product
from app.schemas.order import OrderCreate, OrderUpdate
from app.services.inventory_service import check_availability,reserve_inventory,release_reserved_inventory
from app.services.product_service import get_product_by_id
from fastapi import HTTPException, status
import logging
import random
import string

logger = logging.getLogger(__name__)

def generate_order_number() -> str:
    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
    return f"ORD-{date_str}-{random_str}"

def place_order(db: Session,order_data: OrderCreate,customer_id: UUID) -> Order:
    
    try:
        products_data = {}
        for item in order_data.items:
            product = get_product_by_id(db, item.product_id, check_active=True)
            products_data[item.product_id] = product
        
        for item in order_data.items:
            if not check_availability(db, item.product_id, item.quantity):
                product = products_data[item.product_id]
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Insufficient stock for '{product.name}'. Requested: {item.quantity}")
        
        total_amount = Decimal("0.00")
        order_items_data = []
        
        for item in order_data.items:
            product = products_data[item.product_id]
            unit_price = product.price
            subtotal = unit_price * item.quantity
            total_amount += subtotal
            
            order_items_data.append({"product_id": item.product_id,"quantity": item.quantity,"unit_price": unit_price,"subtotal": subtotal})
        
        order = Order(order_number=generate_order_number(),customer_id=customer_id,status="pending",total_amount=total_amount,
            notes=order_data.notes)
        db.add(order)
        db.flush()  
        
        for item_data in order_items_data:
            order_item = OrderItem(order_id=order.id,**item_data)
            db.add(order_item)
        
        db.flush()
        
        for item in order_data.items:
            reserve_inventory(db, item.product_id, item.quantity)
        
        db.commit()
        db.refresh(order)
        
        logger.info(f"Order placed: {order.id} for customer: {customer_id}")
        return order
        
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error placing order: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,detail="Failed to place order")
    except Exception as e:
        db.rollback()
        logger.error(f"Error placing order: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,detail="Failed to place order")

def get_order_by_id(db: Session, order_id: UUID) -> Order:
    order = db.query(Order).filter(Order.id == order_id).first()
    
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="Order not found")
    
    return order

def get_customer_orders(db: Session,customer_id: UUID,skip: int = 0,limit: int = 100,status: str = None):
    query = db.query(Order).filter(Order.customer_id == customer_id)
    
    if status:
        query = query.filter(Order.status == status)
    
    total = query.count()
    orders = query.order_by(Order.created_at.desc()).offset(skip).limit(limit).all()
    
    return {"total": total, "items": orders, "skip": skip, "limit": limit}


def get_all_orders(db: Session,skip: int = 0,limit: int = 100,status: str = None,customer_id: UUID = None):
    query = db.query(Order)
    
    if status:
        query = query.filter(Order.status == status)
    
    if customer_id:
        query = query.filter(Order.customer_id == customer_id)
    
    total = query.count()
    orders = query.order_by(Order.created_at.desc()).offset(skip).limit(limit).all()
    
    return {"total": total, "items": orders, "skip": skip, "limit": limit}

def update_order_status(db: Session,order_id: UUID,new_status: str) -> Order:
    
    try:
        order = get_order_by_id(db, order_id)
        valid_statuses = ["pending", "confirmed", "shipped", "delivered", "cancelled"]
        
        if new_status not in valid_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status. Must be one of {valid_statuses}"
            )
        
        transitions = {"pending": ["confirmed", "cancelled"],"confirmed": ["shipped", "cancelled"],"shipped": ["delivered"],
            "delivered": [],"cancelled": []}
        
        if new_status not in transitions.get(order.status, []):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail=f"Cannot transition from '{order.status}' to '{new_status}'")
        
        if new_status == "cancelled" and order.status != "cancelled":
            order.cancelled_at = datetime.now(timezone.utc)
            for item in order.order_items:
                release_reserved_inventory(db, item.product_id, item.quantity)
        
        if new_status == "delivered":
            order.delivered_at = datetime.now(timezone.utc)
        
        order.status = new_status
        db.commit()
        db.refresh(order)
        
        logger.info(f"Order status updated: {order.id} → {new_status}")
        return order
        
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error updating order status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update order status"
        )

def cancel_order(db: Session, order_id: UUID) -> Order:
 
    try:
        order = get_order_by_id(db, order_id)
        
        if order.status not in ["pending", "confirmed"]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail=f"Cannot cancel order with status '{order.status}'")
        
        for item in order.order_items:
            release_reserved_inventory(db, item.product_id, item.quantity)
        
        order.status = "cancelled"
        order.cancelled_at = datetime.now(timezone.utc)
        
        db.commit()
        db.refresh(order)
        
        logger.info(f"Order cancelled: {order.id}")
        return order
        
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error cancelling order: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel order"
        )


def get_order_with_items(db: Session, order_id: UUID) -> Order:
    order = get_order_by_id(db, order_id)
    
    if not order.order_items:
        db.refresh(order)
    
    return order


def get_customer_order_total(db: Session,customer_id: UUID) -> dict:
    orders = db.query(Order).filter(Order.customer_id == customer_id).all()    
    total_spent = Decimal("0.00")
    total_orders = len(orders)
    pending_orders = 0
    delivered_orders = 0
    cancelled_orders = 0
    
    for order in orders:
        
        status = order.status
    
        if status == "pending":
            pending_orders += 1
        elif status == "delivered":
            delivered_orders += 1
        elif status == "cancelled":
            cancelled_orders += 1
            
        if status != "cancelled":
            total_spent += order.total_amount

    
    return {"total_orders": total_orders,"total_spent": float(total_spent),"pending_orders": pending_orders,"delivered_orders": delivered_orders , "cancelled_orders" : cancelled_orders}


def get_order_items(db: Session, order_id: UUID):
    order = get_order_by_id(db, order_id)    
    items_with_details = []
    for item in order.order_items:
        items_with_details.append({
            "id": item.id,
            "product_id": item.product_id,
            "product_name": item.product.name,
            "product_sku": item.product.sku,
            "quantity": item.quantity,
            "unit_price": float(item.unit_price),
            "subtotal": float(item.subtotal)
        })
    
    return items_with_details