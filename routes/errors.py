"""
routes/errors.py
----------------
Friendly handling for things that go wrong: expired forms (CSRF), oversized
uploads, and the 403 / 404 / 500 pages.
"""
from flask import flash, redirect, render_template, request, url_for
from flask_wtf.csrf import CSRFError

from core import app, current_user


@app.errorhandler(CSRFError)
def handle_csrf_error(e):
    flash("Your session expired or that form was already submitted. Please try again.", "error")
    return redirect(request.referrer or url_for("index"))


@app.errorhandler(413)
def handle_file_too_large(e):
    flash("That picture is too big — please keep it under 3 MB.", "error")
    return redirect(request.referrer or url_for("index"))


@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404


@app.errorhandler(403)
def forbidden(e):
    return render_template("403.html", user=current_user()), 403


@app.errorhandler(500)
def server_error(e):
    return render_template("500.html"), 500
