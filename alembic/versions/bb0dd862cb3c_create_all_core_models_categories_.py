"""Create all core models: categories, products, inventory, suppliers, orders, purchase_orders

Revision ID: bb0dd862cb3c
Revises: 479954355e94
Create Date: 2026-09-01 15:17:10.181288

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'bb0dd862cb3c'
down_revision: Union[str, Sequence[str], None] = '479954355e94'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('categories',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('slug', sa.String(length=100), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_categories_is_active'), 'categories', ['is_active'], unique=False)
    op.create_index(op.f('ix_categories_name'), 'categories', ['name'], unique=True)
    op.create_index(op.f('ix_categories_slug'), 'categories', ['slug'], unique=True)
    op.create_table('orders',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('order_number', sa.String(length=50), nullable=False, comment='Auto-generated order number (e.g., ORD-20240115-001)'),
    sa.Column('customer_id', sa.Uuid(), nullable=False, comment='CUSTOMER user who placed the order'),
    sa.Column('status', sa.String(length=20), nullable=False, comment='pending, confirmed, shipped, delivered, cancelled'),
    sa.Column('total_amount', sa.Numeric(precision=12, scale=2), nullable=False, comment='Total order amount'),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint('total_amount >= 0', name='check_total_amount_non_negative'),
    sa.ForeignKeyConstraint(['customer_id'], ['users.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_orders_created_at'), 'orders', ['created_at'], unique=False)
    op.create_index(op.f('ix_orders_customer_id'), 'orders', ['customer_id'], unique=False)
    op.create_index(op.f('ix_orders_order_number'), 'orders', ['order_number'], unique=True)
    op.create_index(op.f('ix_orders_status'), 'orders', ['status'], unique=False)
    op.create_table('products',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('sku', sa.String(length=50), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('category_id', sa.Uuid(), nullable=False),
    sa.Column('price', sa.Numeric(precision=12, scale=2), nullable=False, comment='Selling price in decimal format'),
    sa.Column('cost', sa.Numeric(precision=12, scale=2), nullable=False, comment='Cost price for profit tracking'),
    sa.Column('created_by', sa.Uuid(), nullable=False, comment='BUSINESS user who created this product'),
    sa.Column('status', sa.String(length=20), nullable=False, comment='active, inactive, discontinued'),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint('cost >= 0', name='check_cost_non_negative'),
    sa.CheckConstraint('price > 0', name='check_price_positive'),
    sa.ForeignKeyConstraint(['category_id'], ['categories.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_products_category_id'), 'products', ['category_id'], unique=False)
    op.create_index(op.f('ix_products_created_by'), 'products', ['created_by'], unique=False)
    op.create_index(op.f('ix_products_is_active'), 'products', ['is_active'], unique=False)
    op.create_index(op.f('ix_products_name'), 'products', ['name'], unique=False)
    op.create_index(op.f('ix_products_sku'), 'products', ['sku'], unique=True)
    op.create_index(op.f('ix_products_status'), 'products', ['status'], unique=False)
    op.create_table('suppliers',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=True),
    sa.Column('phone', sa.String(length=20), nullable=True),
    sa.Column('contact_person', sa.String(length=100), nullable=True),
    sa.Column('address', sa.Text(), nullable=True),
    sa.Column('city', sa.String(length=100), nullable=True),
    sa.Column('state', sa.String(length=100), nullable=True),
    sa.Column('country', sa.String(length=100), nullable=True),
    sa.Column('postal_code', sa.String(length=20), nullable=True),
    sa.Column('payment_terms', sa.String(length=100), nullable=True),
    sa.Column('created_by', sa.Uuid(), nullable=False, comment='BUSINESS user who created this supplier'),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_suppliers_created_by'), 'suppliers', ['created_by'], unique=False)
    op.create_index(op.f('ix_suppliers_is_active'), 'suppliers', ['is_active'], unique=False)
    op.create_index(op.f('ix_suppliers_name'), 'suppliers', ['name'], unique=False)
    op.create_table('inventory',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('product_id', sa.Uuid(), nullable=False),
    sa.Column('quantity_on_hand', sa.Integer(), nullable=False, comment='Current available stock'),
    sa.Column('quantity_reserved', sa.Integer(), nullable=False, comment='Reserved for pending orders'),
    sa.Column('quantity_available', sa.Integer(), nullable=False, comment='on_hand - reserved'),
    sa.Column('reorder_level', sa.Integer(), nullable=False, comment='Minimum stock level before reordering'),
    sa.Column('reorder_quantity', sa.Integer(), nullable=False, comment='Quantity to order when below reorder_level'),
    sa.Column('last_restock_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint('quantity_available >= 0', name='check_available_non_negative'),
    sa.CheckConstraint('quantity_on_hand >= 0', name='check_on_hand_non_negative'),
    sa.CheckConstraint('quantity_reserved >= 0', name='check_reserved_non_negative'),
    sa.CheckConstraint('reorder_level >= 0', name='check_reorder_level_non_negative'),
    sa.CheckConstraint('reorder_quantity > 0', name='check_reorder_quantity_positive'),
    sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_inventory_product_id'), 'inventory', ['product_id'], unique=True)
    op.create_table('order_items',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('order_id', sa.Uuid(), nullable=False),
    sa.Column('product_id', sa.Uuid(), nullable=False),
    sa.Column('quantity', sa.Integer(), nullable=False, comment='Quantity ordered'),
    sa.Column('unit_price', sa.Numeric(precision=12, scale=2), nullable=False, comment='Price at time of order'),
    sa.Column('subtotal', sa.Numeric(precision=12, scale=2), nullable=False, comment='quantity * unit_price'),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint('quantity > 0', name='check_quantity_positive'),
    sa.CheckConstraint('subtotal > 0', name='check_subtotal_positive'),
    sa.CheckConstraint('unit_price > 0', name='check_unit_price_positive'),
    sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_order_items_order_id'), 'order_items', ['order_id'], unique=False)
    op.create_index(op.f('ix_order_items_product_id'), 'order_items', ['product_id'], unique=False)
    op.create_table('purchase_orders',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('po_number', sa.String(length=50), nullable=False, comment='Auto-generated PO number (e.g., PO-20240115-001)'),
    sa.Column('supplier_id', sa.Uuid(), nullable=False),
    sa.Column('created_by', sa.Uuid(), nullable=False, comment='BUSINESS user who created this PO'),
    sa.Column('status', sa.String(length=20), nullable=False, comment='draft, pending, confirmed, received, cancelled'),
    sa.Column('total_amount', sa.Numeric(precision=12, scale=2), nullable=False, comment='Total PO amount'),
    sa.Column('expected_delivery_date', sa.DateTime(timezone=True), nullable=True),
    sa.Column('actual_delivery_date', sa.DateTime(timezone=True), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint('total_amount >= 0', name='check_po_total_non_negative'),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['supplier_id'], ['suppliers.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_purchase_orders_created_at'), 'purchase_orders', ['created_at'], unique=False)
    op.create_index(op.f('ix_purchase_orders_created_by'), 'purchase_orders', ['created_by'], unique=False)
    op.create_index(op.f('ix_purchase_orders_po_number'), 'purchase_orders', ['po_number'], unique=True)
    op.create_index(op.f('ix_purchase_orders_status'), 'purchase_orders', ['status'], unique=False)
    op.create_index(op.f('ix_purchase_orders_supplier_id'), 'purchase_orders', ['supplier_id'], unique=False)
    op.create_table('purchase_order_items',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('purchase_order_id', sa.Uuid(), nullable=False),
    sa.Column('product_id', sa.Uuid(), nullable=False),
    sa.Column('quantity_ordered', sa.Integer(), nullable=False, comment='Quantity ordered from supplier'),
    sa.Column('unit_cost', sa.Numeric(precision=12, scale=2), nullable=False, comment='Cost per unit from supplier'),
    sa.Column('subtotal', sa.Numeric(precision=12, scale=2), nullable=False, comment='quantity_ordered * unit_cost'),
    sa.Column('quantity_received', sa.Integer(), nullable=False, comment='Actual quantity received'),
    sa.Column('received_at', sa.DateTime(timezone=True), nullable=True, comment='When stock was received and inventory updated'),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint('quantity_ordered > 0', name='check_po_quantity_positive'),
    sa.CheckConstraint('quantity_received >= 0', name='check_quantity_received_non_negative'),
    sa.CheckConstraint('subtotal > 0', name='check_po_subtotal_positive'),
    sa.CheckConstraint('unit_cost > 0', name='check_po_unit_cost_positive'),
    sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['purchase_order_id'], ['purchase_orders.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_purchase_order_items_product_id'), 'purchase_order_items', ['product_id'], unique=False)
    op.create_index(op.f('ix_purchase_order_items_purchase_order_id'), 'purchase_order_items', ['purchase_order_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_purchase_order_items_purchase_order_id'), table_name='purchase_order_items')
    op.drop_index(op.f('ix_purchase_order_items_product_id'), table_name='purchase_order_items')
    op.drop_table('purchase_order_items')
    op.drop_index(op.f('ix_purchase_orders_supplier_id'), table_name='purchase_orders')
    op.drop_index(op.f('ix_purchase_orders_status'), table_name='purchase_orders')
    op.drop_index(op.f('ix_purchase_orders_po_number'), table_name='purchase_orders')
    op.drop_index(op.f('ix_purchase_orders_created_by'), table_name='purchase_orders')
    op.drop_index(op.f('ix_purchase_orders_created_at'), table_name='purchase_orders')
    op.drop_table('purchase_orders')
    op.drop_index(op.f('ix_order_items_product_id'), table_name='order_items')
    op.drop_index(op.f('ix_order_items_order_id'), table_name='order_items')
    op.drop_table('order_items')
    op.drop_index(op.f('ix_inventory_product_id'), table_name='inventory')
    op.drop_table('inventory')
    op.drop_index(op.f('ix_suppliers_name'), table_name='suppliers')
    op.drop_index(op.f('ix_suppliers_is_active'), table_name='suppliers')
    op.drop_index(op.f('ix_suppliers_created_by'), table_name='suppliers')
    op.drop_table('suppliers')
    op.drop_index(op.f('ix_products_status'), table_name='products')
    op.drop_index(op.f('ix_products_sku'), table_name='products')
    op.drop_index(op.f('ix_products_name'), table_name='products')
    op.drop_index(op.f('ix_products_is_active'), table_name='products')
    op.drop_index(op.f('ix_products_created_by'), table_name='products')
    op.drop_index(op.f('ix_products_category_id'), table_name='products')
    op.drop_table('products')
    op.drop_index(op.f('ix_orders_status'), table_name='orders')
    op.drop_index(op.f('ix_orders_order_number'), table_name='orders')
    op.drop_index(op.f('ix_orders_customer_id'), table_name='orders')
    op.drop_index(op.f('ix_orders_created_at'), table_name='orders')
    op.drop_table('orders')
    op.drop_index(op.f('ix_categories_slug'), table_name='categories')
    op.drop_index(op.f('ix_categories_name'), table_name='categories')
    op.drop_index(op.f('ix_categories_is_active'), table_name='categories')
    op.drop_table('categories')
