from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.services.shopify import ShopifyClient

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@router.get("/orders", response_class=HTMLResponse)
def orders_page(request: Request):
    shopify = ShopifyClient()
    try:
        orders = shopify.list_orders()
    finally:
        shopify.close()

    rows = []
    for o in orders:
        customer = o.get("customer") or {}
        shipping_lines = o.get("shipping_lines") or []
        shipping_title = shipping_lines[0].get("title") if shipping_lines else "-"

        rows.append({
            "id": o.get("id"),
            "name": o.get("name"),
            "created_at": o.get("created_at"),
            "total_price": o.get("total_price"),
            "currency": o.get("currency"),
            "customer": (f"{customer.get('first_name','')} {customer.get('last_name','')}".strip() or "-"),
            "shipping": shipping_title or "-",
        })

    return templates.TemplateResponse("orders.html", {"request": request, "orders": rows})