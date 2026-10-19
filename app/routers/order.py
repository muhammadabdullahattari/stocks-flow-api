from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from uuid import UUID
from app.database import get_db
from app.models.users import User
from app.dependencies.auth import get_current_user,get_current_customer_user,get_current_business_user
from app.schemas.order import OrderCreate,OrderUpdate,OrderResponse,OrderListResponse,OrderItemResponse
from app.services.order_service import (place_order,get_order_by_id,get_customer_orders,get_all_orders,
                                        update_order_status,cancel_order,get_order_with_items,get_customer_order_total,get_order_items)
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/orders", tags=["Orders"])

@router.post("",response_model=OrderResponse,status_code=status.HTTP_201_CREATED,summary="Place Order",
             description="Create a new customer order (CUSTOMER only)")
def create_order(order_data: OrderCreate,current_user: User = Depends(get_current_customer_user),db: Session = Depends(get_db)):
    try:
        order = place_order(db, order_data, current_user.id) 
        db.refresh(order) 
        return OrderResponse.model_validate(order)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating order: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,detail="Failed to create order")

@router.get("/my-orders",response_model=dict,summary="List My Orders",description="Get customer's own order history (CUSTOMER only)")
def get_my_orders(skip: int = Query(0, ge=0, description="Skip N items"),
                  limit: int = Query(100, ge=1, le=1000, description="Limit to N items"),
                  status: str = Query(None,description="Filter by status: pending, confirmed, shipped, delivered, cancelled"),
                  current_user: User = Depends(get_current_customer_user),
                  db: Session = Depends(get_db)):

    result = get_customer_orders(db,customer_id=current_user.id,skip=skip,limit=limit,status=status)
    
    return {
        "total": result["total"],
        "items": [OrderListResponse.model_validate(order) for order in result["items"]],
        "skip": result["skip"],
        "limit": result["limit"]
    }


@router.get("/all",response_model=dict,summary="List All Orders",description="Get all orders with filters (BUSINESS only)")
def get_all_orders_endpoint(skip: int = Query(0, ge=0),limit: int = Query(100, ge=1, le=1000),
    status: str = Query(None, description="Filter by status"),
    customer_id: UUID = Query(None, description="Filter by customer"),
    current_user: User = Depends(get_current_business_user),db: Session = Depends(get_db)):

    result = get_all_orders(db,skip=skip,limit=limit,status=status,customer_id=customer_id)
    
    return {
        "total": result["total"],
        "items": [OrderListResponse.model_validate(order) for order in result["items"]],
        "skip": result["skip"],
        "limit": result["limit"]
    }


@router.get("/{order_id}",response_model=OrderResponse,summary="Get Order Details",description="Get a specific order with all items")
def get_order_details(order_id: UUID,current_user: User = Depends(get_current_user),db: Session = Depends(get_db)):
 
    order = get_order_with_items(db, order_id)
    
    if current_user.role == "CUSTOMER" and order.customer_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,detail="You can only view your own orders")
    
    return OrderResponse.model_validate(order)


@router.get("/{order_id}/items",response_model=dict,summary="Get Order Items",description="Get detailed list of items in an order")
def get_order_items_endpoint(order_id: UUID,current_user: User = Depends(get_current_user),db: Session = Depends(get_db)):

    order = get_order_by_id(db, order_id)
    
    if current_user.role == "CUSTOMER" and order.customer_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,detail="You can only view your own order items")
    
    items = get_order_items(db, order_id)
    
    return {"order_id": order_id,"items": items}


@router.put("/{order_id}/status",response_model=OrderResponse,summary="Update Order Status",description="Update order status (BUSINESS only)")
def update_order_status_endpoint(order_id: UUID,order_data: OrderUpdate,current_user: User = Depends(get_current_business_user),
    db: Session = Depends(get_db)):
    
    if not order_data.status:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail="Status is required")
    
    try:
        order = update_order_status(db, order_id, order_data.status)
        
        if order_data.notes:
            order.notes = order_data.notes
            db.commit()
            db.refresh(order)
        
        return OrderResponse.model_validate(order)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating order status: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,detail="Failed to update order status")


@router.patch("/{order_id}/cancel",response_model=OrderResponse,status_code=status.HTTP_200_OK,summary="Cancel Order",description="Cancel an order and release reserved inventory")
def cancel_order_endpoint(order_id: UUID,current_user: User = Depends(get_current_user),db: Session = Depends(get_db)):

    order = get_order_by_id(db, order_id)
    
    if current_user.role == "CUSTOMER" and order.customer_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,detail="You can only cancel your own orders")
    
    try:
        order = cancel_order(db, order_id)
        return OrderResponse.model_validate(order)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling order: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,detail="Failed to cancel order")


@router.get("/stats/my-orders",response_model=dict,summary="My Order Statistics",description="Get your order summary (CUSTOMER only)")
def get_my_order_stats(current_user: User = Depends(get_current_customer_user),db: Session = Depends(get_db)):
    stats = get_customer_order_total(db, current_user.id)
    return stats


@router.get("",response_model=dict,summary="List Orders (Smart Route)",description="List orders (redirects based on user role)",
    include_in_schema=False)
def get_orders_smart(current_user: User = Depends(get_current_user),db: Session = Depends(get_db),
                     skip: int = Query(0, ge=0),limit: int = Query(100, ge=1, le=1000),status: str = Query(None)):

    if current_user.role == "CUSTOMER":
        result = get_customer_orders(db, current_user.id, skip, limit, status)
    else:
        result = get_all_orders(db, skip, limit, status)
    
    return {
        "total": result["total"],
        "items": [OrderListResponse.model_validate(order) for order in result["items"]],
        "skip": result["skip"],
        "limit": result["limit"]
    }