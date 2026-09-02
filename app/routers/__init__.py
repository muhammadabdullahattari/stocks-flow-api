from .auth import router as auth_router
from .category import router as category_router
from .product import router as product_router
from .inventory import router as inventory_router
from .supplier import router as supplier_router
from .order import router as order_router
from .purchase_order import router as purchase_order_router

__all__ = [
    "auth_router",
    "category_router",
    "product_router",
    "inventory_router",
    "supplier_router",
    "order_router",
    "purchase_order_router"
]