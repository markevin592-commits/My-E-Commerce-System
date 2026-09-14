"""
models.py
---------
All the OOP building blocks for the Multi-User Web-Based Management System.

Demonstrates:
- Encapsulation  -> private-ish attributes (leading underscore) + getters/setters,
                    and the DataStore class hiding the raw Python lists behind methods.
- Inheritance    -> Admin, Staff and Customer all inherit from the abstract User class.
- Polymorphism   -> each role overrides dashboard_url() / permissions() / to_badge()
                    and the DataStore CRUD calls behave the same way no matter which
                    concrete class is stored inside the list.

NOTE: Per the project requirements there is NO DATABASE. Everything lives in
plain Python lists (self._users, self._products, self._orders) held in memory
for the lifetime of the running server process.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from itertools import count
from werkzeug.security import generate_password_hash, check_password_hash


# ---------------------------------------------------------------------------
# USER HIERARCHY  (Inheritance + Polymorphism + Encapsulation)
# ---------------------------------------------------------------------------

class User(ABC):
    """Abstract base class for every account in the system."""

    _id_counter = count(1)

    def __init__(self, username, password, full_name, email):
        self.id = next(User._id_counter)
        self.username = username.strip()
        self._password_hash = generate_password_hash(password)   # encapsulated
        self.full_name = full_name.strip()
        self.email = email.strip()
        self.created_at = datetime.now()
        self.active = True
        self.shipping_address = ""   # optional saved default, editable from Profile
        self.phone = ""

    # ---- encapsulation: password never exposed, only checked ----
    def check_password(self, password):
        return check_password_hash(self._password_hash, password)

    def set_password(self, new_password):
        self._password_hash = generate_password_hash(new_password)

    # ---- polymorphic hooks every subclass MUST provide ----
    @property
    @abstractmethod
    def role(self):
        """Short role code, e.g. 'admin' / 'staff' / 'customer'."""

    @abstractmethod
    def dashboard_url(self):
        """Which Flask endpoint this role lands on after login."""

    @abstractmethod
    def permissions(self):
        """List of human-readable permissions, used for display/admin table."""

    def role_label(self):
        return self.role.capitalize()

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "full_name": self.full_name,
            "email": self.email,
            "role": self.role,
            "active": self.active,
            "created_at": self.created_at.strftime("%b %d, %Y"),
        }

    def __repr__(self):
        return f"<{self.__class__.__name__} id={self.id} username={self.username!r}>"


class Admin(User):
    """Full control: manage users, manage products, view analytics & all orders."""

    @property
    def role(self):
        return "admin"

    def dashboard_url(self):
        return "admin_dashboard"

    def permissions(self):
        return [
            "Manage users (add / edit / deactivate / delete)",
            "Manage products (full CRUD)",
            "View & update all orders",
            "View store analytics",
        ]


class Staff(User):
    """Store staff: manage products and fulfil orders, no user management."""

    @property
    def role(self):
        return "staff"

    def dashboard_url(self):
        return "staff_dashboard"

    def permissions(self):
        return [
            "Manage products (full CRUD)",
            "View & update order status",
        ]


class Customer(User):
    """Regular shopper: browse the store, place orders, manage own profile."""

    @property
    def role(self):
        return "customer"

    def dashboard_url(self):
        return "customer_dashboard"

    def permissions(self):
        return [
            "Browse products",
            "Place orders",
            "View own order history",
            "Edit own profile / settings",
        ]


ROLE_CLASSES = {"admin": Admin, "staff": Staff, "customer": Customer}


# ---------------------------------------------------------------------------
# PRODUCT  &  ORDER
# ---------------------------------------------------------------------------

class Product:
    _id_counter = count(1)

    def __init__(self, name, description, price, stock, category, created_by):
        self.id = next(Product._id_counter)
        self.name = name.strip()
        self.description = description.strip()
        self.price = round(float(price), 2)
        self.stock = int(stock)
        self.category = category.strip() or "General"
        self.created_by = created_by          # username of admin/staff who added it
        self.created_at = datetime.now()

    def in_stock(self):
        return self.stock > 0

    def reduce_stock(self, qty):
        if qty > self.stock:
            raise ValueError("Not enough stock available.")
        self.stock -= qty

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "price": self.price,
            "stock": self.stock,
            "category": self.category,
            "created_by": self.created_by,
            "created_at": self.created_at.strftime("%b %d, %Y"),
        }


class OrderItem:
    """A single line inside an Order (product snapshot + quantity)."""

    def __init__(self, product, quantity):
        self.product_id = product.id
        self.product_name = product.name
        self.unit_price = product.price
        self.quantity = quantity

    @property
    def subtotal(self):
        return round(self.unit_price * self.quantity, 2)


class Order:
    _id_counter = count(1)
    VALID_STATUSES = ["Pending", "Processing", "Completed", "Cancelled"]

    def __init__(self, customer, items, shipping_address="", phone=""):
        self.id = next(Order._id_counter)
        self.customer_id = customer.id
        self.customer_name = customer.full_name
        self.items = items                 # list[OrderItem]
        self.status = "Pending"
        self.created_at = datetime.now()
        self.shipping_address = (shipping_address or "").strip()
        self.phone = (phone or "").strip()

    @property
    def total(self):
        return round(sum(item.subtotal for item in self.items), 2)

    def set_status(self, new_status):
        if new_status not in Order.VALID_STATUSES:
            raise ValueError(f"'{new_status}' is not a valid order status.")
        self.status = new_status

    def to_dict(self):
        return {
            "id": self.id,
            "customer_name": self.customer_name,
            "items": [
                {"name": i.product_name, "qty": i.quantity, "subtotal": i.subtotal}
                for i in self.items
            ],
            "total": self.total,
            "status": self.status,
            "created_at": self.created_at.strftime("%b %d, %Y %I:%M %p"),
            "shipping_address": self.shipping_address,
            "phone": self.phone,
        }


# ---------------------------------------------------------------------------
# DATASTORE  (Encapsulation: hides the raw Python lists — the "temporary storage")
# ---------------------------------------------------------------------------

class DataStore:
    """
    The ONLY place in the app that touches the raw Python lists.
    Everything else (routes) must go through these methods.
    This is the in-memory stand-in for a database, as required by the brief
    ("Temporary Storage - Use Python Lists only; NO DATABASE").
    """

    def __init__(self):
        self._users = []      # list[User]
        self._products = []   # list[Product]
        self._orders = []     # list[Order]
        self._carts = {}      # customer_id -> list[[product_id, quantity]] (persistent, in-memory cart)

    # ---------------- USERS ----------------
    def add_user(self, role, username, password, full_name, email):
        if self.get_user_by_username(username):
            raise ValueError("That username is already taken.")
        cls = ROLE_CLASSES.get(role)
        if cls is None:
            raise ValueError("Unknown role.")
        user = cls(username, password, full_name, email)
        self._users.append(user)
        return user

    def get_user_by_username(self, username):
        username = (username or "").strip().lower()
        for u in self._users:
            if u.username.lower() == username:
                return u
        return None

    def get_user_by_id(self, user_id):
        for u in self._users:
            if u.id == int(user_id):
                return u
        return None

    def list_users(self, role=None):
        users = self._users
        if role:
            users = [u for u in users if u.role == role]
        return sorted(users, key=lambda u: u.id)

    def update_user(self, user_id, **fields):
        user = self.get_user_by_id(user_id)
        if not user:
            raise ValueError("User not found.")
        for key, value in fields.items():
            if key == "password" and value:
                user.set_password(value)
            elif hasattr(user, key) and key not in ("id", "role"):
                setattr(user, key, value)
        return user

    def delete_user(self, user_id):
        user = self.get_user_by_id(user_id)
        if not user:
            raise ValueError("User not found.")
        self._users.remove(user)

    # ---------------- PRODUCTS ----------------
    def add_product(self, **fields):
        product = Product(**fields)
        self._products.append(product)
        return product

    def get_product(self, product_id):
        for p in self._products:
            if p.id == int(product_id):
                return p
        return None

    def list_products(self):
        return sorted(self._products, key=lambda p: p.id)

    def update_product(self, product_id, **fields):
        product = self.get_product(product_id)
        if not product:
            raise ValueError("Product not found.")
        for key, value in fields.items():
            if key == "price":
                value = round(float(value), 2)
            if key == "stock":
                value = int(value)
            if hasattr(product, key):
                setattr(product, key, value)
        return product

    def delete_product(self, product_id):
        product = self.get_product(product_id)
        if not product:
            raise ValueError("Product not found.")
        self._products.remove(product)

    # ---------------- ORDERS ----------------
    def add_order(self, customer, cart, shipping_address="", phone=""):
        """cart: list of (product_id, quantity) tuples."""
        if not cart:
            raise ValueError("Cannot place an empty order.")
        items = []
        for product_id, qty in cart:
            product = self.get_product(product_id)
            if not product:
                raise ValueError("A product in your cart no longer exists.")
            if qty <= 0:
                raise ValueError("Quantity must be at least 1.")
            if qty > product.stock:
                raise ValueError(f"Only {product.stock} unit(s) of '{product.name}' left.")
            items.append(OrderItem(product, qty))
        # all validated -> now commit stock changes
        for product_id, qty in cart:
            self.get_product(product_id).reduce_stock(qty)
        order = Order(customer, items, shipping_address=shipping_address, phone=phone)
        self._orders.append(order)
        return order

    def get_order(self, order_id):
        for o in self._orders:
            if o.id == int(order_id):
                return o
        return None

    def list_orders(self, customer_id=None):
        orders = self._orders
        if customer_id:
            orders = [o for o in orders if o.customer_id == int(customer_id)]
        return sorted(orders, key=lambda o: o.created_at, reverse=True)

    def update_order_status(self, order_id, status):
        order = self.get_order(order_id)
        if not order:
            raise ValueError("Order not found.")
        previous_status = order.status
        order.set_status(status)
        # Restock automatically the moment an order transitions INTO Cancelled,
        # but only once — flipping between other statuses never touches stock.
        if status == "Cancelled" and previous_status != "Cancelled":
            for item in order.items:
                product = self.get_product(item.product_id)
                if product:
                    product.stock += item.quantity
        return order

    def delete_order(self, order_id):
        order = self.get_order(order_id)
        if not order:
            raise ValueError("Order not found.")
        self._orders.remove(order)

    # ---------------- CART (persistent per-customer, in-memory) ----------------
    def get_cart_items(self, customer_id):
        """Returns display-ready rows: {product, quantity, subtotal}. Drops any
        line whose product was deleted since it was added, so the cart never
        crashes on a stale reference."""
        raw = self._carts.get(customer_id, [])
        items = []
        for product_id, qty in raw:
            product = self.get_product(product_id)
            if not product:
                continue
            items.append({"product": product, "quantity": qty, "subtotal": round(product.price * qty, 2)})
        return items

    def cart_count(self, customer_id):
        return sum(qty for _, qty in self._carts.get(customer_id, []))

    def cart_total(self, customer_id):
        total = 0
        for product_id, qty in self._carts.get(customer_id, []):
            product = self.get_product(product_id)
            if product:
                total += product.price * qty
        return round(total, 2)

    def add_to_cart(self, customer_id, product_id, quantity):
        product = self.get_product(product_id)
        if not product:
            raise ValueError("Product not found.")
        if quantity <= 0:
            raise ValueError("Quantity must be at least 1.")
        cart = self._carts.setdefault(customer_id, [])
        for entry in cart:
            if entry[0] == product_id:
                new_qty = entry[1] + quantity
                if new_qty > product.stock:
                    raise ValueError(f"Only {product.stock} unit(s) of '{product.name}' available.")
                entry[1] = new_qty
                return
        if quantity > product.stock:
            raise ValueError(f"Only {product.stock} unit(s) of '{product.name}' available.")
        cart.append([product_id, quantity])

    def update_cart_item(self, customer_id, product_id, quantity):
        product = self.get_product(product_id)
        if not product:
            raise ValueError("Product not found.")
        if quantity <= 0:
            self.remove_from_cart(customer_id, product_id)
            return
        if quantity > product.stock:
            raise ValueError(f"Only {product.stock} unit(s) of '{product.name}' available.")
        cart = self._carts.setdefault(customer_id, [])
        for entry in cart:
            if entry[0] == product_id:
                entry[1] = quantity
                return
        cart.append([product_id, quantity])

    def remove_from_cart(self, customer_id, product_id):
        cart = self._carts.get(customer_id, [])
        self._carts[customer_id] = [e for e in cart if e[0] != product_id]

    def clear_cart(self, customer_id):
        self._carts[customer_id] = []

    def checkout_cart(self, customer, shipping_address="", phone=""):
        cart = self._carts.get(customer.id, [])
        if not cart:
            raise ValueError("Your cart is empty.")
        order = self.add_order(customer, [(pid, qty) for pid, qty in cart],
                                shipping_address=shipping_address, phone=phone)
        self.clear_cart(customer.id)
        return order

    # ---------------- ANALYTICS (derived, nothing stored) ----------------
    def analytics(self):
        total_sales = sum(o.total for o in self._orders if o.status != "Cancelled")
        return {
            "total_users": len(self._users),
            "total_customers": len([u for u in self._users if u.role == "customer"]),
            "total_products": len(self._products),
            "low_stock": [p for p in self._products if 0 < p.stock <= 5],
            "out_of_stock": [p for p in self._products if p.stock == 0],
            "total_orders": len(self._orders),
            "pending_orders": len([o for o in self._orders if o.status == "Pending"]),
            "total_sales": round(total_sales, 2),
        }

    def orders_by_status_counts(self):
        """dict of {status: count} -> feeds the admin donut chart."""
        counts = {s: 0 for s in Order.VALID_STATUSES}
        for o in self._orders:
            counts[o.status] = counts.get(o.status, 0) + 1
        return counts

    # Alias matching the "status_counts()" naming used elsewhere in the spec.
    status_counts = orders_by_status_counts

    def sales_by_day(self):
        """list of [label, total] sorted chronologically -> feeds the line chart.
        Buckets by calendar day once orders span multiple days. If everything
        happened on the same day (common right after seeding/demo use), it
        buckets by minute instead so the trend line still has 2+ points to draw
        rather than collapsing into a single dot."""
        relevant = [o for o in self._orders if o.status != "Cancelled"]
        if not relevant:
            return []
        days = {o.created_at.strftime("%Y-%m-%d") for o in relevant}
        fmt = "%Y-%m-%d" if len(days) > 1 else "%Y-%m-%d %H:%M:%S"
        totals = {}
        for o in relevant:
            label = o.created_at.strftime(fmt)
            totals[label] = totals.get(label, 0) + o.total
        return [[label, round(total, 2)] for label, total in sorted(totals.items())]

    def products_by_category_counts(self):
        """dict of {category: item_count} -> feeds a secondary donut chart."""
        counts = {}
        for p in self._products:
            counts[p.category] = counts.get(p.category, 0) + 1
        return counts

    # Alias matching the "category_counts()" naming used elsewhere in the spec.
    category_counts = products_by_category_counts

    def top_selling_products(self, limit=5):
        """list of [product_name, units_sold] sorted descending -> bar chart."""
        sold = {}
        for o in self._orders:
            if o.status == "Cancelled":
                continue
            for item in o.items:
                sold[item.product_name] = sold.get(item.product_name, 0) + item.quantity
        ranked = sorted(sold.items(), key=lambda x: x[1], reverse=True)
        return [[name, qty] for name, qty in ranked[:limit]]

    def revenue_by_customer(self, limit=8):
        """list of [customer_name, revenue] sorted descending -> bar chart."""
        revenue = {}
        for o in self._orders:
            if o.status == "Cancelled":
                continue
            revenue[o.customer_name] = revenue.get(o.customer_name, 0) + o.total
        ranked = sorted(revenue.items(), key=lambda x: x[1], reverse=True)
        return [[name, round(total, 2)] for name, total in ranked[:limit]]


def seed(store: DataStore):
    """Create the real admin/staff accounts, plus one demo customer for testing the store."""
    store.add_user("admin", "markiven592", "changeme123", "Mark Kevin Mag-aso", "markiven592@gmail.com")
    store.add_user("staff", "jymart114", "changeme123", "Jymart Bongolo", "jymart114@gmail.com")
    store.add_user("customer", "customer", "customer123", "Juan Dela Cruz", "juan@example.com")

    store.add_product(name="Wireless Mouse", description="Ergonomic 2.4GHz wireless mouse.",
                       price=349.00, stock=25, category="Electronics", created_by="admin")
    store.add_product(name="Mechanical Keyboard", description="RGB backlit mechanical keyboard.",
                       price=1499.00, stock=12, category="Electronics", created_by="staff")
    store.add_product(name="Notebook (A5)", description="120-page dotted notebook.",
                       price=79.00, stock=100, category="Stationery", created_by="staff")
    store.add_product(name="Ceramic Mug", description="350ml matte ceramic mug.",
                       price=149.00, stock=4, category="Home", created_by="admin")

    # --- Electronics ---
    store.add_product(name="USB-C Hub (7-in-1)", description="HDMI, USB 3.0, SD card, and PD passthrough.",
                       price=899.00, stock=18, category="Electronics", created_by="staff")
    store.add_product(name="Bluetooth Earbuds", description="True wireless earbuds with charging case.",
                       price=1299.00, stock=20, category="Electronics", created_by="admin")
    store.add_product(name="Portable Power Bank 10000mAh", description="Slim fast-charging power bank.",
                       price=699.00, stock=30, category="Electronics", created_by="staff")
    store.add_product(name="Webcam 1080p", description="Clip-on HD webcam with built-in mic.",
                       price=999.00, stock=0, category="Electronics", created_by="admin")

    # --- Stationery ---
    store.add_product(name="Gel Pen Set (12pcs)", description="Smooth-writing gel pens in assorted colors.",
                       price=99.00, stock=60, category="Stationery", created_by="staff")
    store.add_product(name="Sticky Notes Bundle", description="5 pads of 3x3 sticky notes, neon colors.",
                       price=65.00, stock=80, category="Stationery", created_by="staff")
    store.add_product(name="Desk Planner 2026", description="Undated weekly planner with monthly tabs.",
                       price=249.00, stock=3, category="Stationery", created_by="admin")

    # --- Home ---
    store.add_product(name="Scented Candle (Vanilla)", description="Soy wax candle, 40-hour burn time.",
                       price=189.00, stock=22, category="Home", created_by="admin")
    store.add_product(name="Throw Pillow Cover", description="45x45cm linen-blend cushion cover.",
                       price=159.00, stock=15, category="Home", created_by="staff")
    store.add_product(name="Stainless Steel Tumbler", description="500ml insulated tumbler, keeps drinks cold 12hrs.",
                       price=299.00, stock=5, category="Home", created_by="admin")

    # --- Apparel ---
    store.add_product(name="Cotton Crewneck Tee", description="Unisex 100% cotton tee, relaxed fit.",
                       price=349.00, stock=40, category="Apparel", created_by="staff")
    store.add_product(name="Canvas Tote Bag", description="Heavy-duty canvas tote, 15L capacity.",
                       price=229.00, stock=27, category="Apparel", created_by="admin")

    # --- Grocery ---
    store.add_product(name="Single-Origin Coffee Beans (250g)", description="Medium roast, notes of caramel and citrus.",
                       price=379.00, stock=35, category="Grocery", created_by="staff")
    store.add_product(name="Artisan Honey (Pure, 350ml)", description="Raw unfiltered honey from local apiaries.",
                       price=259.00, stock=2, category="Grocery", created_by="admin")

    # The demo customer starts with a saved address/phone for convenience at checkout,
    # but with NO orders — Recent Orders / My Orders should stay empty until they
    # actually place one themselves.
    juan = store.get_user_by_username("customer")
    juan.shipping_address = "123 Rizal St., Brgy. San Isidro, Quezon City, Metro Manila"
    juan.phone = "0917-123-4567"
