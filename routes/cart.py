"""
routes/cart.py
--------------
The customer's cart (persistent in memory, survives navigating away) and checkout:
    /cart                       view the cart
    /cart/add                   add an item
    /cart/update/<product_id>   change a quantity
    /cart/remove/<product_id>   remove an item
    /cart/checkout              place the order (needs shipping address + phone)
"""

from flask import render_template, request, redirect, url_for, flash

from core import app, store, current_user, roles_required


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
