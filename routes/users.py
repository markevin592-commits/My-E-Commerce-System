"""
routes/users.py
---------------
User management (admin only) - full CRUD:
    /admin/users                 list all accounts
    /admin/users/add             create an account (any role)
    /admin/users/edit/<id>       edit details / reset password / activate-deactivate
    /admin/users/delete/<id>     delete an account
"""

from flask import render_template, request, redirect, url_for, flash

from core import app, store, current_user, roles_required, is_gmail


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
