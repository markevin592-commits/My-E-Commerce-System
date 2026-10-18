"""
routes/dashboards.py
--------------------
One dashboard per role. Each role's dashboard_url() (see models.py) decides where
login sends you:
    /admin/dashboard     admin     totals, charts, recent orders, stock watch
    /staff/dashboard     staff     orders to fulfil + products
    /customer/dashboard  customer  recent orders, featured products, cart summary
"""

from flask import render_template

from core import app, store, current_user, roles_required


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
        products=store.list_products()[:8],
        cart_items=store.get_cart_items(user.id),
        cart_total=store.cart_total(user.id),
        order_count=len(all_orders),
        total_spent=total_spent,
    )
