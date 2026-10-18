"""
routes/shop.py
--------------
What shoppers see and the Buy Now flow:
    /                         public shop for guests (logged-in users go to their dashboard)
    /store                    the store page for customers (supports ?q=search)
    /store/buy-now/review     Buy Now step 1: review item + shipping details
    /store/buy-now/confirm    Buy Now step 2: place the order
(The cart and checkout live in routes/cart.py.)
"""

from flask import render_template, request, redirect, url_for, flash

from core import app, store, current_user, roles_required


# ---------------------------------------------------------------------------
# PUBLIC SHOP (landing page)
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


# ---------------------------------------------------------------------------
# STORE (customers)
# ---------------------------------------------------------------------------

@app.route("/store")
@roles_required("customer")
def store_page():
    return render_template("store.html", products=store.list_products(),
                            search_query=request.args.get("q", ""))


# Older all-in-one order form. The current UI uses Buy Now (below) and the cart
# (routes/cart.py) instead, but this route is kept so nothing that posts to it breaks.
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


# ---------------------------------------------------------------------------
# BUY NOW  (review -> confirm)
# ---------------------------------------------------------------------------

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
