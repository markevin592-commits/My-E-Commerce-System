"""
routes/orders.py
----------------
Orders after they are placed:
    /orders                   staff/admin: all orders
    /orders/status/<id>       staff/admin: change status (cancelling restocks the items)
    /orders/delete/<id>       admin: delete an order
    /my-orders                customer: their own order history
    /orders/<id>              order detail (customers can only open their own)
"""

from flask import render_template, request, redirect, url_for, flash, abort

from models import Order
from core import app, store, current_user, login_required, roles_required


# ---------------------------------------------------------------------------
# STAFF / ADMIN: manage orders
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# CUSTOMER: my orders
# ---------------------------------------------------------------------------

@app.route("/my-orders")
@roles_required("customer")
def my_orders():
    user = current_user()
    return render_template("my_orders.html", orders=store.list_orders(customer_id=user.id))


# ---------------------------------------------------------------------------
# ORDER DETAIL (any logged-in role, access-checked)
# ---------------------------------------------------------------------------

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
