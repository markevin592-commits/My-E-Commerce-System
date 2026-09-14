"""
app.py
------
Flask entry point for the Multi-User Web-Based Management System.

Roles (3, as required):
    admin    -> manage users, manage products, manage all orders, analytics
    staff    -> manage products, manage orders
    customer -> browse store, place orders, manage own profile

Storage: everything lives in-memory inside a single DataStore instance
(models.DataStore) built on plain Python lists. Restarting the server
resets all data (by design - "Temporary Storage", no database).
"""

from functools import wraps
import re
from flask import (
    Flask, render_template, request, redirect, url_for, session, flash, abort
)
from flask_wtf import CSRFProtect
from flask_wtf.csrf import CSRFError

from models import DataStore, Order, seed

app = Flask(__name__)
app.secret_key = "change-this-secret-key-before-deploying"  # used to sign the session cookie
csrf = CSRFProtect(app)  # every POST form now needs a valid {{ csrf_token() }} field


@app.errorhandler(CSRFError)
def handle_csrf_error(e):
    flash("Your session expired or that form was already submitted. Please try again.", "error")
    return redirect(request.referrer or url_for("index"))

store = DataStore()
seed(store)


# ---------------------------------------------------------------------------
# VALIDATION HELPERS
# ---------------------------------------------------------------------------

def is_gmail(email):
    """Every account on this system must use a real Gmail address."""
    return bool(re.match(r"^[^@\s]+@gmail\.com$", (email or "").strip(), re.IGNORECASE))


# ---------------------------------------------------------------------------
# AUTH HELPERS / DECORATORS  (role-based access control)
# ---------------------------------------------------------------------------

def current_user():
    user_id = session.get("user_id")
    return store.get_user_by_id(user_id) if user_id else None


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user():
            flash("Please log in to continue.", "error")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def roles_required(*roles):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            user = current_user()
            if not user:
                flash("Please log in to continue.", "error")
                return redirect(url_for("login"))
            if user.role not in roles:
                return render_template("403.html", user=user), 403
            return view(*args, **kwargs)
        return wrapped
    return decorator


@app.context_processor
def inject_user():
    """
    Makes current_user available in every template, plus a small role-specific
    'sidebar_stat' widget so the empty space at the bottom of the sidebar is
    always filled with something useful instead of blank space.
    """
    user = current_user()
    sidebar_stat = None
    cart_count = 0
    stock_alert = None
    if user:
        if user.role == "admin":
            sidebar_stat = {"label": "Total Sales", "value": f"₱{store.analytics()['total_sales']:.2f}"}
        elif user.role == "staff":
            sidebar_stat = {"label": "Pending Orders", "value": store.analytics()["pending_orders"]}
        elif user.role == "customer":
            sidebar_stat = {"label": "My Orders", "value": len(store.list_orders(customer_id=user.id))}
            cart_count = store.cart_count(user.id)
        if user.role in ("admin", "staff"):
            a = store.analytics()
            stock_alert = {"out": len(a["out_of_stock"]), "low": len(a["low_stock"])}
    return {"current_user": user, "sidebar_stat": sidebar_stat, "cart_count": cart_count, "stock_alert": stock_alert}


# ---------------------------------------------------------------------------
# PUBLIC ROUTES: signup / login / logout
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    """
    Logged-in users land on their role dashboard. Anyone else (guests) lands
    straight on the public shop so they can browse without being forced
    through login/signup first. Login/Signup are just links on that page.
    """
    user = current_user()
    if user:
        return redirect(url_for(user.dashboard_url()))
    return render_template("public_shop.html", products=store.list_products())


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if current_user():
        return redirect(url_for(current_user().dashboard_url()))

    if request.method == "POST":
        full_name = request.form.get("full_name", "")
        username = request.form.get("username", "")
        email = request.form.get("email", "")
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        role = request.form.get("role", "customer")

        errors = []
        if not full_name.strip():
            errors.append("Full name is required.")
        if not username.strip() or len(username.strip()) < 3:
            errors.append("Username must be at least 3 characters.")
        if not email.strip() or not is_gmail(email):
            errors.append("A valid Gmail address (e.g. name@gmail.com) is required.")
        if len(password) < 6:
            errors.append("Password must be at least 6 characters.")
        if password != confirm:
            errors.append("Passwords do not match.")
        if role not in ("customer", "staff"):
            # Admin accounts are never self-service; only 'customer' or 'staff' may sign up.
            role = "customer"
        if store.get_user_by_username(username):
            errors.append("That username is already taken.")

        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("signup.html", form=request.form)

        try:
            store.add_user(role, username, password, full_name, email)
        except ValueError as e:
            flash(str(e), "error")
            return render_template("signup.html", form=request.form)

        flash("Account created successfully! You can now log in.", "success")
        return redirect(url_for("login"))

    return render_template("signup.html", form={})


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user():
        return redirect(url_for(current_user().dashboard_url()))

    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")

        if not username.strip() or not password:
            flash("Both fields are required.", "error")
            return render_template("login.html")

        user = store.get_user_by_username(username)
        if not user or not user.check_password(password):
            flash("Invalid username or password.", "error")
            return render_template("login.html")
        if not user.active:
            flash("This account has been deactivated. Contact an administrator.", "error")
            return render_template("login.html")

        session["user_id"] = user.id
        flash(f"Welcome back, {user.full_name}!", "success")
        return redirect(url_for(user.dashboard_url()))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("login"))


# ---------------------------------------------------------------------------
# DASHBOARDS (one per role -> polymorphism drives which template/data is shown)
# ---------------------------------------------------------------------------

@app.route("/admin/dashboard")
@roles_required("admin")
def admin_dashboard():
    return render_template(
        "dashboard_admin.html",
        stats=store.analytics(),
        recent_orders=store.list_orders()[:5],
        products=store.list_products(),
        status_counts=store.orders_by_status_counts(),
        sales_by_day=store.sales_by_day(),
        top_products=store.top_selling_products(limit=4),
    )


@app.route("/staff/dashboard")
@roles_required("staff")
def staff_dashboard():
    return render_template(
        "dashboard_staff.html",
        stats=store.analytics(),
        products=store.list_products(),
        orders=store.list_orders()[:8],
    )


@app.route("/customer/dashboard")
@roles_required("customer")
def customer_dashboard():
    user = current_user()
    all_orders = store.list_orders(customer_id=user.id)
    total_spent = round(sum(o.total for o in all_orders if o.status != "Cancelled"), 2)
    return render_template(
        "dashboard_customer.html",
        orders=all_orders[:5],
        products=store.list_products()[:4],
        cart_items=store.get_cart_items(user.id),
        cart_total=store.cart_total(user.id),
        order_count=len(all_orders),
        total_spent=total_spent,
    )


# ---------------------------------------------------------------------------
# USER MANAGEMENT (admin only) - full CRUD
# ---------------------------------------------------------------------------

@app.route("/admin/users")
@roles_required("admin")
def manage_users():
    return render_template("users.html", users=store.list_users())


@app.route("/admin/users/add", methods=["GET", "POST"])
@roles_required("admin")
def add_user():
    if request.method == "POST":
        full_name = request.form.get("full_name", "")
        username = request.form.get("username", "")
        email = request.form.get("email", "")
        password = request.form.get("password", "")
        role = request.form.get("role", "customer")

        errors = []
        if not full_name.strip():
            errors.append("Full name is required.")
        if not username.strip() or len(username.strip()) < 3:
            errors.append("Username must be at least 3 characters.")
        if not email.strip() or not is_gmail(email):
            errors.append("A valid Gmail address (e.g. name@gmail.com) is required.")
        if len(password) < 6:
            errors.append("Password must be at least 6 characters.")
        if role not in ("admin", "staff", "customer"):
            errors.append("Invalid role selected.")

        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("user_form.html", form=request.form, mode="add")

        try:
            store.add_user(role, username, password, full_name, email)
            flash(f"User '{username}' created.", "success")
            return redirect(url_for("manage_users"))
        except ValueError as e:
            flash(str(e), "error")
            return render_template("user_form.html", form=request.form, mode="add")

    return render_template("user_form.html", form={}, mode="add")


@app.route("/admin/users/edit/<int:user_id>", methods=["GET", "POST"])
@roles_required("admin")
def edit_user(user_id):
    user = store.get_user_by_id(user_id)
    if not user:
        flash("User not found.", "error")
        return redirect(url_for("manage_users"))

    if request.method == "POST":
        full_name = request.form.get("full_name", "")
        email = request.form.get("email", "")
        password = request.form.get("password", "")
        active = request.form.get("active") == "on"

        errors = []
        if not full_name.strip():
            errors.append("Full name is required.")
        if not email.strip() or not is_gmail(email):
            errors.append("A valid Gmail address (e.g. name@gmail.com) is required.")
        if password and len(password) < 6:
            errors.append("Password must be at least 6 characters.")

        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("user_form.html", form=request.form, mode="edit", target=user)

        try:
            store.update_user(user_id, full_name=full_name, email=email,
                               password=password or None, active=active)
            flash("User updated.", "success")
            return redirect(url_for("manage_users"))
        except ValueError as e:
            flash(str(e), "error")

    return render_template("user_form.html", form=user.to_dict(), mode="edit", target=user)


@app.route("/admin/users/delete/<int:user_id>", methods=["POST"])
@roles_required("admin")
def delete_user(user_id):
    if current_user().id == user_id:
        flash("You cannot delete your own account while logged in.", "error")
        return redirect(url_for("manage_users"))
    try:
        store.delete_user(user_id)
        flash("User deleted.", "success")
    except ValueError as e:
        flash(str(e), "error")
    return redirect(url_for("manage_users"))


# ---------------------------------------------------------------------------
# PRODUCT MANAGEMENT (admin + staff) - full CRUD
# ---------------------------------------------------------------------------

@app.route("/products")
@roles_required("admin", "staff")
def manage_products():
    return render_template("products.html", products=store.list_products())


@app.route("/products/add", methods=["GET", "POST"])
@roles_required("admin", "staff")
def add_product():
    if request.method == "POST":
        name = request.form.get("name", "")
        description = request.form.get("description", "")
        price = request.form.get("price", "")
        stock = request.form.get("stock", "")
        category = request.form.get("category", "")

        errors = []
        if not name.strip():
            errors.append("Product name is required.")
        try:
            price_val = float(price)
            if price_val < 0:
                errors.append("Price cannot be negative.")
        except ValueError:
            errors.append("Price must be a number.")
            price_val = 0
        try:
            stock_val = int(stock)
            if stock_val < 0:
                errors.append("Stock cannot be negative.")
        except ValueError:
            errors.append("Stock must be a whole number.")
            stock_val = 0

        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("product_form.html", form=request.form, mode="add")

        store.add_product(name=name, description=description, price=price_val,
                           stock=stock_val, category=category,
                           created_by=current_user().username)
        flash(f"Product '{name}' added.", "success")
        return redirect(url_for("manage_products"))

    return render_template("product_form.html", form={}, mode="add")


@app.route("/products/edit/<int:product_id>", methods=["GET", "POST"])
@roles_required("admin", "staff")
def edit_product(product_id):
    product = store.get_product(product_id)
    if not product:
        flash("Product not found.", "error")
        return redirect(url_for("manage_products"))

    if request.method == "POST":
        name = request.form.get("name", "")
        description = request.form.get("description", "")
        price = request.form.get("price", "")
        stock = request.form.get("stock", "")
        category = request.form.get("category", "")

        errors = []
        if not name.strip():
            errors.append("Product name is required.")
        try:
            price_val = float(price)
            if price_val < 0:
                errors.append("Price cannot be negative.")
        except ValueError:
            errors.append("Price must be a number.")
            price_val = product.price
        try:
            stock_val = int(stock)
            if stock_val < 0:
                errors.append("Stock cannot be negative.")
        except ValueError:
            errors.append("Stock must be a whole number.")
            stock_val = product.stock

        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("product_form.html", form=request.form, mode="edit", target=product)

        store.update_product(product_id, name=name, description=description,
                              price=price_val, stock=stock_val, category=category)
        flash("Product updated.", "success")
        return redirect(url_for("manage_products"))

    return render_template("product_form.html", form=product.to_dict(), mode="edit", target=product)


@app.route("/products/delete/<int:product_id>", methods=["POST"])
@roles_required("admin", "staff")
def delete_product(product_id):
    try:
        store.delete_product(product_id)
        flash("Product deleted.", "success")
    except ValueError as e:
        flash(str(e), "error")
    return redirect(url_for("manage_products"))


# ---------------------------------------------------------------------------
# STORE / ORDERS  (customer browses + checks out; staff/admin fulfil)
# ---------------------------------------------------------------------------

@app.route("/store")
@roles_required("customer")
def store_page():
    return render_template("store.html", products=store.list_products())


@app.route("/store/order", methods=["POST"])
@roles_required("customer")
def place_order():
    product_ids = request.form.getlist("product_id")
    quantities = request.form.getlist("quantity")

    cart = []
    for pid, qty in zip(product_ids, quantities):
        try:
            qty_int = int(qty)
        except ValueError:
            continue
        if qty_int > 0:
            cart.append((int(pid), qty_int))

    try:
        order = store.add_order(current_user(), cart)
        flash(f"Order #{order.id} placed successfully! Total: ₱{order.total:.2f}", "success")
    except ValueError as e:
        flash(str(e), "error")

    return redirect(url_for("store_page"))


@app.route("/store/buy-now/review", methods=["POST"])
@roles_required("customer")
def buy_now_review():
    """Show a confirmation page (item, personal info, shipping) before placing the order."""
    product_id = request.form.get("product_id", type=int)
    quantity = request.form.get("quantity", 1, type=int)
    user = current_user()
    product = store.get_product(product_id)

    if not product:
        flash("That product is no longer available.", "error")
        return redirect(url_for("store_page"))
    if quantity <= 0 or quantity > product.stock:
        flash(f"Only {product.stock} unit(s) of '{product.name}' available.", "error")
        return redirect(request.referrer or url_for("store_page"))

    return render_template(
        "order_review.html", product=product, quantity=quantity,
        subtotal=round(product.price * quantity, 2),
        shipping_address=user.shipping_address, phone=user.phone,
    )


@app.route("/store/buy-now/confirm", methods=["POST"])
@roles_required("customer")
def buy_now_confirm():
    """Actually place the order after the customer has reviewed/confirmed their details."""
    product_id = request.form.get("product_id", type=int)
    quantity = request.form.get("quantity", 1, type=int)
    shipping_address = request.form.get("shipping_address", "").strip()
    phone = request.form.get("phone", "").strip()
    user = current_user()
    product = store.get_product(product_id)

    if not product:
        flash("That product is no longer available.", "error")
        return redirect(url_for("store_page"))

    # Re-render the SAME review page (not a redirect) on any problem, so whatever
    # the customer already typed into the address/phone fields isn't lost.
    if not shipping_address or not phone:
        flash("Shipping address and phone number are required.", "error")
        return render_template(
            "order_review.html", product=product, quantity=quantity,
            subtotal=round(product.price * quantity, 2),
            shipping_address=shipping_address, phone=phone,
        )

    try:
        order = store.add_order(user, [(product_id, quantity)],
                                 shipping_address=shipping_address, phone=phone)
        store.update_user(user.id, shipping_address=shipping_address, phone=phone)
        flash(f"Order #{order.id} placed successfully! Total: ₱{order.total:.2f}", "success")
        return redirect(url_for("order_detail", order_id=order.id))
    except ValueError as e:
        flash(str(e), "error")
        return render_template(
            "order_review.html", product=product, quantity=quantity,
            subtotal=round(product.price * quantity, 2),
            shipping_address=shipping_address, phone=phone,
        )


# ---------------------------------------------------------------------------
# CART (customer only) — persistent, in-memory, survives navigating away
# ---------------------------------------------------------------------------

@app.route("/cart")
@roles_required("customer")
def view_cart():
    user = current_user()
    return render_template(
        "cart.html",
        items=store.get_cart_items(user.id),
        total=store.cart_total(user.id),
    )


@app.route("/cart/add", methods=["POST"])
@roles_required("customer")
def add_to_cart():
    product_id = request.form.get("product_id", type=int)
    quantity = request.form.get("quantity", 1, type=int)

    try:
        store.add_to_cart(current_user().id, product_id, quantity)
        flash("Added to cart.", "success")
    except ValueError as e:
        flash(str(e), "error")

    return redirect(request.referrer or url_for("store_page"))


@app.route("/cart/update/<int:product_id>", methods=["POST"])
@roles_required("customer")
def update_cart(product_id):
    quantity = request.form.get("quantity", 0, type=int)
    try:
        store.update_cart_item(current_user().id, product_id, quantity)
    except ValueError as e:
        flash(str(e), "error")
    return redirect(url_for("view_cart"))


@app.route("/cart/remove/<int:product_id>", methods=["POST"])
@roles_required("customer")
def remove_from_cart(product_id):
    store.remove_from_cart(current_user().id, product_id)
    flash("Item removed from cart.", "success")
    return redirect(url_for("view_cart"))


@app.route("/cart/checkout", methods=["POST"])
@roles_required("customer")
def checkout_cart():
    user = current_user()
    shipping_address = request.form.get("shipping_address", "").strip()
    phone = request.form.get("phone", "").strip()

    if not shipping_address or not phone:
        flash("Shipping address and phone number are required to check out.", "error")
        return redirect(url_for("view_cart"))

    try:
        order = store.checkout_cart(user, shipping_address=shipping_address, phone=phone)
        # Remember these as the customer's default for next time (Buy Now uses them too).
        store.update_user(user.id, shipping_address=shipping_address, phone=phone)
        flash(f"Order #{order.id} placed successfully! Total: ₱{order.total:.2f}", "success")
        return redirect(url_for("order_detail", order_id=order.id))
    except ValueError as e:
        flash(str(e), "error")
        return redirect(url_for("view_cart"))


@app.route("/orders")
@roles_required("admin", "staff")
def manage_orders():
    return render_template("orders.html", orders=store.list_orders(), statuses=Order.VALID_STATUSES)


@app.route("/orders/status/<int:order_id>", methods=["POST"])
@roles_required("admin", "staff")
def update_order_status(order_id):
    new_status = request.form.get("status", "")
    try:
        store.update_order_status(order_id, new_status)
        flash(f"Order #{order_id} marked as {new_status}.", "success")
    except ValueError as e:
        flash(str(e), "error")
    return redirect(url_for("manage_orders"))


@app.route("/orders/delete/<int:order_id>", methods=["POST"])
@roles_required("admin")
def delete_order(order_id):
    try:
        store.delete_order(order_id)
        flash("Order deleted.", "success")
    except ValueError as e:
        flash(str(e), "error")
    return redirect(url_for("manage_orders"))


@app.route("/my-orders")
@roles_required("customer")
def my_orders():
    user = current_user()
    return render_template("my_orders.html", orders=store.list_orders(customer_id=user.id))


@app.route("/orders/<int:order_id>")
@login_required
def order_detail(order_id):
    order = store.get_order(order_id)
    if not order:
        abort(404)
    user = current_user()
    # Customers may only open their own orders; staff/admin may open any of them.
    if user.role == "customer" and order.customer_id != user.id:
        abort(403)
    back_endpoint = "my_orders" if user.role == "customer" else "manage_orders"
    return render_template("order_detail.html", order=order, back_endpoint=back_endpoint,
                            statuses=Order.VALID_STATUSES)


# ---------------------------------------------------------------------------
# ANALYTICS (admin only)
# ---------------------------------------------------------------------------

@app.route("/analytics")
@roles_required("admin")
def analytics():
    return render_template(
        "analytics.html",
        stats=store.analytics(),
        orders=store.list_orders(),
        products=store.list_products(),
        status_counts=store.orders_by_status_counts(),
        sales_by_day=store.sales_by_day(),
        category_counts=store.products_by_category_counts(),
        top_products=store.top_selling_products(),
        revenue_by_customer=store.revenue_by_customer(),
    )


# ---------------------------------------------------------------------------
# PROFILE + SETTINGS (all logged-in roles)
# ---------------------------------------------------------------------------

@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    user = current_user()
    if request.method == "POST":
        full_name = request.form.get("full_name", "")
        email = request.form.get("email", "")
        shipping_address = request.form.get("shipping_address", "").strip()
        phone = request.form.get("phone", "").strip()

        errors = []
        if not full_name.strip():
            errors.append("Full name is required.")
        if not email.strip() or not is_gmail(email):
            errors.append("A valid Gmail address (e.g. name@gmail.com) is required.")

        if errors:
            for e in errors:
                flash(e, "error")
        else:
            store.update_user(user.id, full_name=full_name, email=email,
                               shipping_address=shipping_address, phone=phone)
            flash("Profile updated.", "success")
        return redirect(url_for("profile"))

    return render_template("profile.html", user=user)


@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    user = current_user()
    if request.method == "POST":
        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not user.check_password(current_password):
            flash("Current password is incorrect.", "error")
        elif len(new_password) < 6:
            flash("New password must be at least 6 characters.", "error")
        elif new_password != confirm_password:
            flash("New passwords do not match.", "error")
        else:
            user.set_password(new_password)
            flash("Password changed successfully.", "success")
        return redirect(url_for("settings"))

    return render_template("settings.html", user=user)


# ---------------------------------------------------------------------------
# ERROR HANDLERS  (validation & error handling requirement)
# ---------------------------------------------------------------------------

@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404


@app.errorhandler(403)
def forbidden(e):
    return render_template("403.html", user=current_user()), 403


@app.errorhandler(500)
def server_error(e):
    return render_template("500.html"), 500


if __name__ == "__main__":
    # debug=True is fine for local development / grading; turn off in real production.
    app.run(debug=True)
