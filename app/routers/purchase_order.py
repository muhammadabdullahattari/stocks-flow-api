from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from uuid import UUID
from pydantic import BaseModel, Field
from app.database import get_db
from app.models.users import User
from app.dependencies.auth import get_current_business_user
from app.schemas.purchase_order import (
    PurchaseOrderCreate,
    PurchaseOrderUpdate,
    PurchaseOrderResponse,
    PurchaseOrderListResponse,
    PurchaseOrderItemResponse,
    ReceiveStockRequest,
    ReceiveStockResponse
)
from app.services.purchase_order_service import (
    create_purchase_order,
    get_purchase_order_by_id,
    get_all_purchase_orders,
    update_purchase_order,
    update_po_status,
    receive_po_item,
    cancel_purchase_order,
    get_po_items,
    get_pending_shipments,)
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/purchase-orders", tags=["Purchase Orders"])

@router.post("",response_model=PurchaseOrderResponse,status_code=status.HTTP_201_CREATED,
    summary="Create Purchase Order",description="Create a new purchase order (BUSINESS only)")
def create_new_purchase_order(po_data: PurchaseOrderCreate,current_user: User = Depends(get_current_business_user),
    db: Session = Depends(get_db)):

    try:
        po = create_purchase_order(db, po_data, current_user.id)
        db.refresh(po)
        return PurchaseOrderResponse.model_validate(po)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating purchase order: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,detail="Failed to create purchase order")


@router.get("",response_model=dict,summary="List Purchase Orders",
            description="Get all purchase orders with filters (BUSINESS only)")
def list_purchase_orders(
    skip: int = Query(0, ge=0, description="Skip N items"),
    limit: int = Query(100, ge=1, le=1000, description="Limit to N items"),
    status: str = Query(None,description="Filter by status: draft, pending, confirmed, received, cancelled"),
    supplier_id: UUID = Query(None, description="Filter by supplier"),
    current_user: User = Depends(get_current_business_user),db: Session = Depends(get_db)):

    result = get_all_purchase_orders(db,skip=skip,limit=limit,status=status,supplier_id=supplier_id)
    
    return {"total": result["total"],"items": [PurchaseOrderListResponse.model_validate(po) for po in result["items"]],
        "skip": result["skip"],"limit": result["limit"]}


@router.get("/{po_id}",response_model=PurchaseOrderResponse,summary="Get Purchase Order",description="Get PO details with all items (BUSINESS only)")
def get_purchase_order(po_id: UUID,current_user: User = Depends(get_current_business_user),db: Session = Depends(get_db)):
    po = get_purchase_order_by_id(db, po_id)
    return PurchaseOrderResponse.model_validate(po)


@router.get("/{po_id}/items",response_model=dict,summary="Get PO Items",
    description="Get detailed list of items in a purchase order (BUSINESS only)")
def get_po_items_endpoint(po_id: UUID,current_user: User = Depends(get_current_business_user),db: Session = Depends(get_db)):
    items = get_po_items(db, po_id)
    return {"po_id": po_id,"items": items}


@router.put("/{po_id}",response_model=PurchaseOrderResponse,summary="Update Purchase Order",
            description="Update PO details (BUSINESS only, draft only)")
def update_existing_po(po_id: UUID,po_data: PurchaseOrderUpdate,current_user: User = Depends(get_current_business_user),
    db: Session = Depends(get_db)):

    try:
        po = update_purchase_order(db, po_id, po_data)
        return PurchaseOrderResponse.model_validate(po)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating PO: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,detail="Failed to update purchase order")


@router.put("/{po_id}/status",response_model=PurchaseOrderResponse,summary="Update PO Status",description="Update purchase order status through workflow (BUSINESS only)")
def update_po_status_endpoint(po_id: UUID,status_update: dict = {"status": ""},
                              current_user: User = Depends(get_current_business_user),db: Session = Depends(get_db)):

    new_status = status_update.get("status")
    if not new_status:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail="Status is required")
    
    try:
        po = update_po_status(db, po_id, new_status)
        return PurchaseOrderResponse.model_validate(po)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating PO status: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,detail="Failed to update PO status")

@router.post("/{po_id}/items/{po_item_id}/receive",response_model=dict,summary="Receive Stock",
             description="Receive stock for a PO item (BUSINESS only)")
def receive_stock_endpoint(po_id: UUID,po_item_id: UUID,request: ReceiveStockRequest,
    current_user: User = Depends(get_current_business_user),db: Session = Depends(get_db)):

    try:
        po_item = receive_po_item(db, po_id, po_item_id, request.quantity_received)
        po = get_purchase_order_by_id(db, po_id)
        
        return {
            "message": "Stock received successfully",
            "po_item": {
                "id": str(po_item.id),
                "product_name": po_item.product.name,
                "quantity_ordered": po_item.quantity_ordered,
                "quantity_received": po_item.quantity_received,
                "quantity_pending": po_item.quantity_ordered - po_item.quantity_received,
                "received_at": po_item.received_at.isoformat() if po_item.received_at else None
            },
            "po_status": po.status,
            "note": "PO marked as 'received' (all items fully received)" if po.status == "received" else "Partial shipment received"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error receiving stock: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,detail="Failed to receive stock")


@router.patch("/{po_id}/cancel",response_model=PurchaseOrderResponse,summary="Cancel Purchase Order",description="Cancel a purchase order (BUSINESS only)")
def cancel_po_endpoint(po_id: UUID,current_user: User = Depends(get_current_business_user),db: Session = Depends(get_db)):
    try:
        po = cancel_purchase_order(db, po_id)
        return PurchaseOrderResponse.model_validate(po)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling PO: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,detail="Failed to cancel purchase order")


@router.get("/dashboard/pending",response_model=dict,summary="Pending Shipments",
    description="Get all POs with pending/partial shipments (BUSINESS only)")
def get_pending_shipments_endpoint(current_user: User = Depends(get_current_business_user),db: Session = Depends(get_db)):
    return get_pending_shipments(db)