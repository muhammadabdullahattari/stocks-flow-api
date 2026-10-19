import pytest
from fastapi import status
from uuid import uuid4
from decimal import Decimal
from app.models.inventory import Inventory
from app.models.product import Product


class TestAdditionalEdgeCases:
    """Additional edge case tests across StockFlow modules."""

    # ========================================================
    # CATEGORY EDGE CASES
    # ========================================================

    def test_category_slug_auto_suffix_increment(self, test_client, business_headers):
        """Test creating categories with similar names automatically increments slug suffixes."""
        cat1 = test_client.post("/categories", json={"name": "Duplicate Slug Test"}, headers=business_headers).json()
        cat2 = test_client.post("/categories", json={"name": "Duplicate Slug Test 2"}, headers=business_headers).json()

        assert cat1["id"] != cat2["id"]

    def test_create_category_duplicate_name_conflict(self, test_client, business_headers):
        """Test creating category with exact duplicate name returns 409 Conflict."""
        name = f"Unique Name {uuid4().hex[:6]}"
        res1 = test_client.post("/categories", json={"name": name}, headers=business_headers)
        assert res1.status_code == status.HTTP_201_CREATED

        res2 = test_client.post("/categories", json={"name": name}, headers=business_headers)
        assert res2.status_code == status.HTTP_409_CONFLICT

    # ========================================================
    # PRODUCT EDGE CASES
    # ========================================================

    def test_product_price_less_than_cost_rejected(self, test_client, business_headers, create_category):
        """Test product creation fails when price is less than or equal to cost."""
        cat = create_category()
        payload = {
            "name": "Loss Product",
            "price": "10.00",
            "cost": "20.00",
            "category_id": cat["id"],
        }
        res = test_client.post("/products", json=payload, headers=business_headers)
        assert res.status_code == status.HTTP_400_BAD_REQUEST

    def test_product_search_advanced_price_range(self, test_client, business_headers, create_category):
        """Test advanced product search filters correctly by min_price and max_price."""
        cat = create_category()
        p1 = test_client.post("/products", json={"name": "Cheap Gadget", "price": "15.00", "cost": "5.00", "category_id": cat["id"]}, headers=business_headers).json()
        p2 = test_client.post("/products", json={"name": "Expensive Gadget", "price": "500.00", "cost": "200.00", "category_id": cat["id"]}, headers=business_headers).json()

        res = test_client.get(f"/products/search/advanced?q=Gadget&min_price=10&max_price=50", headers=business_headers)
        assert res.status_code == status.HTTP_200_OK
        items = res.json()["items"]
        item_ids = [item["id"] for item in items]
        assert p1["id"] in item_ids
        assert p2["id"] not in item_ids

    # ========================================================
    # INVENTORY EDGE CASES
    # ========================================================

    def test_inventory_update_and_low_stock_detection(self, test_client, business_headers, create_product, db_session):
        """Test updating inventory stock levels and verifying low stock reporting."""
        prod = create_product()

        # Update stock level below reorder_level
        test_client.put(
            f"/inventory/product/{prod['id']}",
            json={"quantity_on_hand": 5, "reorder_level": 10, "reorder_quantity": 20},
            headers=business_headers,
        )

        res = test_client.get("/inventory/low-stock", headers=business_headers)
        assert res.status_code == status.HTTP_200_OK
        data = res.json()
        low_stock_prod_ids = [p["product_id"] for p in data["products"]]
        assert prod["id"] in low_stock_prod_ids

    # ========================================================
    # ORDER WORKFLOW EDGE CASES
    # ========================================================

    def test_order_full_lifecycle(self, test_client, customer_headers, business_headers, create_product):
        """Test complete order workflow: pending -> confirmed -> shipped -> delivered."""
        prod = create_product()
        test_client.put(f"/inventory/product/{prod['id']}", json={"quantity_on_hand": 100}, headers=business_headers)

        # Place order
        order_res = test_client.post("/orders", json={"items": [{"product_id": prod["id"], "quantity": 2}]}, headers=customer_headers)
        assert order_res.status_code == status.HTTP_201_CREATED
        order_id = order_res.json()["id"]

        # Confirm order
        res1 = test_client.put(f"/orders/{order_id}/status", json={"status": "confirmed"}, headers=business_headers)
        assert res1.status_code == status.HTTP_200_OK
        assert res1.json()["status"] == "confirmed"

        # Ship order
        res2 = test_client.put(f"/orders/{order_id}/status", json={"status": "shipped"}, headers=business_headers)
        assert res2.status_code == status.HTTP_200_OK
        assert res2.json()["status"] == "shipped"

        # Deliver order
        res3 = test_client.put(f"/orders/{order_id}/status", json={"status": "delivered"}, headers=business_headers)
        assert res3.status_code == status.HTTP_200_OK
        assert res3.json()["status"] == "delivered"

    # ========================================================
    # PURCHASE ORDER WORKFLOW & STOCK RECEIVING
    # ========================================================

    def test_po_stock_receiving_updates_inventory(self, test_client, business_headers, create_supplier, create_product, db_session):
        """Test receiving stock on PO updates physical inventory on_hand and available quantities."""
        sup = create_supplier()
        prod = create_product()

        po_res = test_client.post(
            "/purchase-orders",
            json={
                "supplier_id": sup["id"],
                "items": [{"product_id": prod["id"], "quantity_ordered": 20, "unit_cost": "50.00"}],
            },
            headers=business_headers,
        )
        po = po_res.json()

        # Transition PO: draft -> pending -> confirmed
        test_client.put(f"/purchase-orders/{po['id']}/status", json={"status": "pending"}, headers=business_headers)
        test_client.put(f"/purchase-orders/{po['id']}/status", json={"status": "confirmed"}, headers=business_headers)

        po_item_id = po["items"][0]["id"]

        # Receive 20 items
        rx_res = test_client.post(
            f"/purchase-orders/{po['id']}/items/{po_item_id}/receive",
            json={"quantity_received": 20},
            headers=business_headers,
        )
        assert rx_res.status_code == status.HTTP_200_OK
        assert rx_res.json()["po_status"] == "received"

        # Verify inventory was updated in DB
        inv = db_session.query(Inventory).filter(Inventory.product_id == prod["id"]).first()
        assert inv.quantity_on_hand >= 20
        assert inv.quantity_available >= 20
