"""
app.py
------
Entry point for the Multi-User Web-Based Management System.
    run locally:   python app.py
    on Render:     gunicorn app:app

WHERE TO FIND THINGS
    core.py                Flask app setup, the in-memory data store, login helpers / role decorators
    models.py              User / Admin / Staff / Customer, Product, Order, DataStore, seed data
    routes/auth.py         sign up, log in, log out
    routes/dashboards.py   admin / staff / customer dashboards
    routes/users.py        user management (admin)
    routes/products.py     product management + product pictures (admin, staff)
    routes/shop.py         public shop, store page, Buy Now review/confirm
    routes/cart.py         cart + checkout
    routes/orders.py       manage orders, my orders, order detail
    routes/analytics.py    analytics charts (admin)
    routes/account.py      profile, settings
    routes/errors.py       403 / 404 / 413 / 500 pages and CSRF-expired handling
    templates/, static/    HTML pages, CSS, product pictures
"""

from core import app  
import routes  


if __name__ == "__main__":
    # debug=True is fine for local development / grading; turn off in real production.
    app.run(debug=True)
