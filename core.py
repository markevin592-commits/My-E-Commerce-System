"""
core.py
-------
The shared setup every page depends on. Route files (routes/*.py) import from here:

    app              the Flask application (+ CSRF protection and upload limit)
    store            the single in-memory DataStore, already filled by seed()
    current_user()   who is logged in right now
    login_required / roles_required(...)   access-control decorators
    is_gmail()       the "must be a real Gmail address" rule

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
from flask import Flask, render_template, redirect, url_for, session, flash
from flask_wtf import CSRFProtect

from models import DataStore, seed

app = Flask(__name__)
app.secret_key = "change-this-secret-key-before-deploying"  # used to sign the session cookie
csrf = CSRFProtect(app)  # every POST form now needs a valid {{ csrf_token() }} field
app.config["MAX_CONTENT_LENGTH"] = 3 * 1024 * 1024  # reject uploads over 3 MB


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
