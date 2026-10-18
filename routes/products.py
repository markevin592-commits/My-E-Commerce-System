"""
routes/products.py
------------------
Product management (admin + staff) - full CRUD, including product pictures:
    /products                    list the catalog
    /products/add                add a product (optional picture upload)
    /products/edit/<id>          edit a product / replace or remove its picture
    /products/delete/<id>        delete a product (and its uploaded picture)
"""

import os
import uuid
from flask import render_template, request, redirect, url_for, flash

from core import app, store, current_user, roles_required


# ---------------------------------------------------------------------------
# PRODUCT PICTURE UPLOADS
# Like everything else in this project the files are temporary: they live in
# static/uploads/ and are forgotten when the server's data resets.
# ---------------------------------------------------------------------------


UPLOAD_DIR = os.path.join(app.static_folder, "uploads")
ALLOWED_IMAGE_EXT = {"png", "jpg", "jpeg", "gif", "webp"}


def _looks_like_image(header):
    """Check the file's first bytes (not just its name) so a renamed .exe/.txt is refused."""
    return (
        header.startswith(b"\x89PNG\r\n\x1a\n")
        or header.startswith(b"\xff\xd8\xff")
        or header[:6] in (b"GIF87a", b"GIF89a")
        or (header[:4] == b"RIFF" and header[8:12] == b"WEBP")
    )


def save_product_image(file_storage):
    """Validate and save an uploaded product picture.

    Returns the path relative to /static (e.g. "uploads/ab12.png"), or None when
    no file was chosen. Raises ValueError with a friendly message if it's not a
    real image.
    """
    if not file_storage or not file_storage.filename:
        return None
    filename = file_storage.filename
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_IMAGE_EXT:
        raise ValueError("Product picture must be a PNG, JPG, GIF, or WEBP image.")
    header = file_storage.stream.read(16)
    file_storage.stream.seek(0)
    if not _looks_like_image(header):
        raise ValueError("That file doesn't look like a real image. Please choose a PNG, JPG, GIF, or WEBP.")
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    saved_name = f"{uuid.uuid4().hex}.{ext}"
    file_storage.save(os.path.join(UPLOAD_DIR, saved_name))
    return f"uploads/{saved_name}"


def remove_uploaded_image(image_path):
    """Delete a previously uploaded picture. Bundled images (img/products/...) are never touched."""
    if image_path and image_path.startswith("uploads/"):
        target = os.path.join(UPLOAD_DIR, os.path.basename(image_path))
        if os.path.isfile(target):
            os.remove(target)


# ---------------------------------------------------------------------------
# PRODUCT CRUD
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

        image_path = None
        if not errors:
            try:
                image_path = save_product_image(request.files.get("image"))
            except ValueError as e:
                errors.append(str(e))

        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("product_form.html", form=request.form, mode="add")

        store.add_product(name=name, description=description, price=price_val,
                           stock=stock_val, category=category,
                           created_by=current_user().username,
                           image=image_path or "")
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

        new_image = None
        if not errors:
            try:
                new_image = save_product_image(request.files.get("image"))
            except ValueError as e:
                errors.append(str(e))

        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("product_form.html", form=request.form, mode="edit", target=product)

        fields = dict(name=name, description=description, price=price_val,
                      stock=stock_val, category=category)
        if new_image:                                   # a new picture replaces the old one
            remove_uploaded_image(product.image)
            fields["image"] = new_image
        elif request.form.get("remove_image") == "on":  # or the picture was explicitly removed
            remove_uploaded_image(product.image)
            fields["image"] = ""
        store.update_product(product_id, **fields)
        flash("Product updated.", "success")
        return redirect(url_for("manage_products"))

    return render_template("product_form.html", form=product.to_dict(), mode="edit", target=product)


@app.route("/products/delete/<int:product_id>", methods=["POST"])
@roles_required("admin", "staff")
def delete_product(product_id):
    try:
        product = store.get_product(product_id)
        store.delete_product(product_id)
        if product:
            remove_uploaded_image(product.image)
        flash("Product deleted.", "success")
    except ValueError as e:
        flash(str(e), "error")
    return redirect(url_for("manage_products"))
