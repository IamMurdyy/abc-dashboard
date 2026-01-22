from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.services.shopify import ShopifyClient

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/orders", response_class=HTMLResponse)
def orders_page(request: Request):
    # Voorbereiding voor multi-shop (nu nog vast op ABC-LED)
    shop_key = request.query_params.get("shop") or "abc-led"

    shopify = ShopifyClient(shop_key)
    try:
        orders = shopify.list_orders()
    finally:
        shopify.close()

    rows = []
    for o in orders:
        customer = o.get("customer") or {}
        shipping_lines = o.get("shipping_lines") or []
        shipping_title = shipping_lines[0].get("title") if shipping_lines else "-"

        rows.append(
            {
                "id": o.get("id"),
                "name": o.get("name"),
                "created_at": o.get("created_at"),
                "total_price": o.get("total_price"),
                "currency": o.get("currency"),
                "customer": (
                    f"{customer.get('first_name','')} {customer.get('last_name','')}".strip()
                    or "-"
                ),
                "shipping": shipping_title or "-",
            }
        )

    return templates.TemplateResponse(
        "orders.html",
        {
            "request": request,
            "orders": rows,
            "active_page": "orders",
            "active_shop": shop_key,
            "shops": [
                {"key": "abc-led", "name": "ABC-LED", "href": "/orders?shop=abc-led"},
                # later:
                # {"key": "abcstore", "name": "ABCstore", "href": "/orders?shop=abcstore"},
            ],
        },
    )


@router.post("/orders/fetch")
def orders_fetch(request: Request):
    # Haal shop uit querystring, zodat je form action "/orders/fetch?shop=abc-led" kan doen
    shop_key = request.query_params.get("shop") or "abc-led"

    try:
        shopify = ShopifyClient(shop_key=shop_key)
        try:
            orders = shopify.list_orders()
        finally:
            shopify.close()

        count = len(orders) if orders else 0
        msg = f"Orders opgehaald: {count}"

        # 303 = na POST terug naar GET (netjes voor browsers)
        return RedirectResponse(
            url=f"/orders?shop={shop_key}&toast={msg}&toast_type=success",
            status_code=303,
        )

    except Exception as e:
        msg = f"Fout bij ophalen orders: {type(e).__name__}"
        return RedirectResponse(
            url=f"/orders?shop={shop_key}&toast={msg}&toast_type=error",
            status_code=303,
        )
