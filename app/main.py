from fastapi import FastAPI
from app.routers.auth import router as Authrouter
from app.routers.user import router as Userrouter
from app.routers.category import router as Categoryrouter
from app.routers.inventory import router as Inventoryrouter
from app.routers.product import router as Productrouter
from app.routers.supplier import router as Supplierrouter
from app.routers.order import router as Orderrouter
from app.routers.purchase_order import router as PurchaseOrderrouter
from app.database import Base,engine
import app.models
from fastapi.exceptions import RequestValidationError, HTTPException 
from app.exceptions.handlers import http_exception_handler, validation_exception_handler, general_exception_handler
from app.core.startup import startup_event

app = FastAPI(title="StockFlow API")

@app.on_event("startup")
async def on_startup():
    await startup_event()

app.add_exception_handler(HTTPException,http_exception_handler)
app.add_exception_handler(RequestValidationError,validation_exception_handler)
app.add_exception_handler(Exception,general_exception_handler)

app.include_router(Authrouter)
app.include_router(Userrouter)
app.include_router(Categoryrouter)
app.include_router(Inventoryrouter)
app.include_router(Productrouter)
app.include_router(Supplierrouter)
app.include_router(Orderrouter)
app.include_router(PurchaseOrderrouter)

@app.get("/")
def root():
    print("check yml")
    return {"message": "API is running"}
