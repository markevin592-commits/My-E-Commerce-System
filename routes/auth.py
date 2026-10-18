"""
routes/auth.py
--------------
Account entry and exit:
    /signup   create a customer (or staff) account
    /login    sign in and land on your role's dashboard
    /logout   sign out
"""

from flask import render_template, request, redirect, url_for, session, flash

from core import app, store, current_user, is_gmail


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
