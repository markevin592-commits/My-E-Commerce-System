"""
routes/analytics.py
-------------------
Store analytics (admin only):  /analytics
Line, donut and bar charts: sales over time, orders by status, products by
category, top sellers, revenue by customer.
"""

from flask import render_template

from core import app, store, roles_required


@app.route("/analytics")
@roles_required("admin")
def analytics():
    return render_template(
        "analytics.html",
        stats=store.analytics(),
        orders=store.list_orders(),
        products=store.list_products(),
        status_counts=store.orders_by_status_counts(),
        sales_by_day=store.sales_by_day(),
        category_counts=store.products_by_category_counts(),
        top_products=store.top_selling_products(),
        revenue_by_customer=store.revenue_by_customer(),
    )
