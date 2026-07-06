"""
SupplyLink — models.py
All SQLAlchemy models in a single file (matches Knowledge Repo convention).
"""

from datetime import datetime, date

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from extensions import db


# ---------------------------------------------------------------------------
# Choice constants (used for validation + template dropdowns / badges)
# ---------------------------------------------------------------------------

class Role:
    ADMIN = "admin"
    SUPPLY_OFFICER = "supply_officer"
    STAFF = "staff"

    CHOICES = [ADMIN, SUPPLY_OFFICER, STAFF]


class MovementType:
    IN = "in"
    OUT = "out"
    ADJUSTMENT = "adjustment"

    CHOICES = [IN, OUT, ADJUSTMENT]


class POStatus:
    DRAFT = "Draft"
    SENT = "Sent"
    RECEIVED = "Received"
    CANCELLED = "Cancelled"

    CHOICES = [DRAFT, SENT, RECEIVED, CANCELLED]


class RequisitionStatus:
    PENDING = "Pending"
    APPROVED = "Approved"
    REJECTED = "Rejected"
    FULFILLED = "Fulfilled"

    CHOICES = [PENDING, APPROVED, REJECTED, FULFILLED]


# ---------------------------------------------------------------------------
# Department
# ---------------------------------------------------------------------------

class Department(db.Model):
    __tablename__ = "departments"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    is_supply_chain = db.Column(db.Boolean, nullable=False, default=False)

    users = db.relationship("User", back_populates="department")
    requisitions = db.relationship("Requisition", back_populates="department")

    def __repr__(self):
        return f"<Department {self.name}>"


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------

class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), nullable=False, unique=True, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default=Role.STAFF)
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    department = db.relationship("Department", back_populates="users")

    stock_movements = db.relationship(
        "StockMovement", back_populates="created_by", foreign_keys="StockMovement.created_by_id"
    )
    requisitions_submitted = db.relationship(
        "Requisition", back_populates="requested_by", foreign_keys="Requisition.requested_by_id"
    )
    requisitions_decided = db.relationship(
        "Requisition", back_populates="decided_by", foreign_keys="Requisition.decided_by_id"
    )

    def set_password(self, raw_password):
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        return check_password_hash(self.password_hash, raw_password)

    @property
    def is_admin(self):
        return self.role == Role.ADMIN

    @property
    def is_supply_officer(self):
        return self.role == Role.SUPPLY_OFFICER

    @property
    def can_approve_requisitions(self):
        return self.role in (Role.ADMIN, Role.SUPPLY_OFFICER) and self.department.is_supply_chain

    def __repr__(self):
        return f"<User {self.email}>"


# ---------------------------------------------------------------------------
# Category
# ---------------------------------------------------------------------------

class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)

    items = db.relationship("Item", back_populates="category")

    def __repr__(self):
        return f"<Category {self.name}>"


# ---------------------------------------------------------------------------
# Supplier
# ---------------------------------------------------------------------------

class Supplier(db.Model):
    __tablename__ = "suppliers"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(180), nullable=False)
    contact_person = db.Column(db.String(120))
    phone = db.Column(db.String(30))
    email = db.Column(db.String(255))
    address = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    items = db.relationship("Item", back_populates="supplier")
    purchase_orders = db.relationship("PurchaseOrder", back_populates="supplier")

    def __repr__(self):
        return f"<Supplier {self.name}>"


# ---------------------------------------------------------------------------
# Item
# ---------------------------------------------------------------------------

class Item(db.Model):
    __tablename__ = "items"

    id = db.Column(db.Integer, primary_key=True)
    sku = db.Column(db.String(60), nullable=False, unique=True, index=True)
    name = db.Column(db.String(180), nullable=False)
    unit_of_measure = db.Column(db.String(30), nullable=False, default="unit")
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"), nullable=True)

    quantity_on_hand = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    reorder_level = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    unit_cost = db.Column(db.Numeric(12, 2), nullable=False, default=0)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    category = db.relationship("Category", back_populates="items")
    supplier = db.relationship("Supplier", back_populates="items")
    stock_movements = db.relationship("StockMovement", back_populates="item")
    po_lines = db.relationship("PurchaseOrderLine", back_populates="item")
    requisition_lines = db.relationship("RequisitionLine", back_populates="item")

    @property
    def is_low_stock(self):
        return self.quantity_on_hand <= self.reorder_level

    @property
    def stock_value(self):
        return (self.quantity_on_hand or 0) * (self.unit_cost or 0)

    def __repr__(self):
        return f"<Item {self.sku} - {self.name}>"


# ---------------------------------------------------------------------------
# Stock Movement
# ---------------------------------------------------------------------------

class StockMovement(db.Model):
    __tablename__ = "stock_movements"

    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey("items.id"), nullable=False)
    movement_type = db.Column(db.String(20), nullable=False)  # in / out / adjustment
    quantity = db.Column(db.Numeric(12, 2), nullable=False)
    reference = db.Column(db.String(60))  # related PO number or requisition number
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    item = db.relationship("Item", back_populates="stock_movements")
    created_by = db.relationship(
        "User", back_populates="stock_movements", foreign_keys=[created_by_id]
    )

    def __repr__(self):
        return f"<StockMovement {self.movement_type} {self.quantity} of item {self.item_id}>"


# ---------------------------------------------------------------------------
# Purchase Order + line items
# ---------------------------------------------------------------------------

class PurchaseOrder(db.Model):
    __tablename__ = "purchase_orders"

    id = db.Column(db.Integer, primary_key=True)
    po_number = db.Column(db.String(30), nullable=False, unique=True, index=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"), nullable=False)
    status = db.Column(db.String(20), nullable=False, default=POStatus.DRAFT)
    order_date = db.Column(db.Date, default=date.today)
    expected_date = db.Column(db.Date, nullable=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    supplier = db.relationship("Supplier", back_populates="purchase_orders")
    created_by = db.relationship("User", foreign_keys=[created_by_id])
    lines = db.relationship(
        "PurchaseOrderLine", back_populates="purchase_order", cascade="all, delete-orphan"
    )

    @property
    def total_value(self):
        return sum((line.line_total for line in self.lines), 0)

    @staticmethod
    def generate_po_number():
        """e.g. PO-202607-0001"""
        prefix = f"PO-{datetime.utcnow().strftime('%Y%m')}-"
        count_this_month = PurchaseOrder.query.filter(
            PurchaseOrder.po_number.like(f"{prefix}%")
        ).count()
        return f"{prefix}{count_this_month + 1:04d}"

    def __repr__(self):
        return f"<PurchaseOrder {self.po_number} [{self.status}]>"


class PurchaseOrderLine(db.Model):
    __tablename__ = "purchase_order_lines"

    id = db.Column(db.Integer, primary_key=True)
    purchase_order_id = db.Column(db.Integer, db.ForeignKey("purchase_orders.id"), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey("items.id"), nullable=False)
    quantity = db.Column(db.Numeric(12, 2), nullable=False)
    unit_cost = db.Column(db.Numeric(12, 2), nullable=False)

    purchase_order = db.relationship("PurchaseOrder", back_populates="lines")
    item = db.relationship("Item", back_populates="po_lines")

    @property
    def line_total(self):
        return (self.quantity or 0) * (self.unit_cost or 0)

    def __repr__(self):
        return f"<PurchaseOrderLine item={self.item_id} qty={self.quantity}>"


# ---------------------------------------------------------------------------
# Requisition + line items
# ---------------------------------------------------------------------------

class Requisition(db.Model):
    __tablename__ = "requisitions"

    id = db.Column(db.Integer, primary_key=True)
    req_number = db.Column(db.String(30), nullable=False, unique=True, index=True)
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"), nullable=False)
    requested_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    status = db.Column(db.String(20), nullable=False, default=RequisitionStatus.PENDING)
    decided_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    decided_at = db.Column(db.DateTime, nullable=True)
    fulfilled_at = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.Text, nullable=True)

    department = db.relationship("Department", back_populates="requisitions")
    requested_by = db.relationship(
        "User", back_populates="requisitions_submitted", foreign_keys=[requested_by_id]
    )
    decided_by = db.relationship(
        "User", back_populates="requisitions_decided", foreign_keys=[decided_by_id]
    )
    lines = db.relationship(
        "RequisitionLine", back_populates="requisition", cascade="all, delete-orphan"
    )

    @staticmethod
    def generate_req_number():
        """e.g. REQ-202607-0001"""
        prefix = f"REQ-{datetime.utcnow().strftime('%Y%m')}-"
        count_this_month = Requisition.query.filter(
            Requisition.req_number.like(f"{prefix}%")
        ).count()
        return f"{prefix}{count_this_month + 1:04d}"

    def __repr__(self):
        return f"<Requisition {self.req_number} [{self.status}]>"


class RequisitionLine(db.Model):
    __tablename__ = "requisition_lines"

    id = db.Column(db.Integer, primary_key=True)
    requisition_id = db.Column(db.Integer, db.ForeignKey("requisitions.id"), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey("items.id"), nullable=False)
    quantity_requested = db.Column(db.Numeric(12, 2), nullable=False)
    quantity_fulfilled = db.Column(db.Numeric(12, 2), nullable=True)

    requisition = db.relationship("Requisition", back_populates="lines")
    item = db.relationship("Item", back_populates="requisition_lines")

    def __repr__(self):
        return f"<RequisitionLine item={self.item_id} qty={self.quantity_requested}>"