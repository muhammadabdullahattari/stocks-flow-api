from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from uuid import UUID
from app.database import get_db
from app.models.users import User
from app.dependencies.auth import get_current_business_user
from app.schemas.supplier import SupplierCreate,SupplierUpdate,SupplierResponse,SupplierListResponse
from app.services.supplier_service import create_supplier,get_supplier_by_id,get_all_suppliers,update_supplier,deactivate_supplier
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/suppliers", tags=["Suppliers"])

@router.post("",response_model=SupplierResponse,status_code=status.HTTP_201_CREATED,summary="Create Supplier",description="Create a new supplier (BUSINESS only)")
def create_new_supplier(supplier_data: SupplierCreate,current_user: User = Depends(get_current_business_user),db: Session = Depends(get_db)):
    return create_supplier(db, supplier_data, current_user.id)

@router.get("",response_model=dict,summary="List Suppliers",description="Get all suppliers with pagination (BUSINESS only)")
def list_suppliers(skip: int = Query(0, ge=0),limit: int = Query(100, ge=1, le=1000),is_active: bool = Query(None),
    current_user: User = Depends(get_current_business_user),db: Session = Depends(get_db)):
    
    result = get_all_suppliers(db, skip=skip, limit=limit, is_active=is_active)
    return {
        "total": result["total"],
        "items": [SupplierListResponse.model_validate(sup) for sup in result["items"]],
        "skip": result["skip"],
        "limit": result["limit"]
    }

@router.get("/{supplier_id}",response_model=SupplierResponse,summary="Get Supplier",description="Get a specific supplier by ID (BUSINESS only)")
def get_supplier(supplier_id: UUID,current_user: User = Depends(get_current_business_user),db: Session = Depends(get_db)):
    supplier = get_supplier_by_id(db, supplier_id)
    return SupplierResponse.model_validate(supplier)

@router.put("/{supplier_id}",response_model=SupplierResponse,summary="Update Supplier",description="Update an existing supplier (BUSINESS only)")
def update_existing_supplier(supplier_id: UUID,supplier_data: SupplierUpdate,current_user: User = Depends(get_current_business_user),db: Session = Depends(get_db)):
    supplier = update_supplier(db, supplier_id, supplier_data)
    return SupplierResponse.model_validate(supplier)

@router.patch("/{supplier_id}/deactivate",response_model=SupplierResponse,summary="Deactivate Supplier",description="Deactivate a supplier (BUSINESS only)")
def deactivate_existing_supplier(supplier_id: UUID,current_user: User = Depends(get_current_business_user),db: Session = Depends(get_db)):
    supplier = deactivate_supplier(db, supplier_id)
    return SupplierResponse.model_validate(supplier)