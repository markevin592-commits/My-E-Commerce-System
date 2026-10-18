"""
routes/account.py
-----------------
Your own account (all logged-in roles):
    /profile    update name, email, shipping address and phone
    /settings   change password
"""

from flask import render_template, request, redirect, url_for, flash

from core import app, store, current_user, login_required, is_gmail


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
