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
        shipping_address = o.get("shipping_address") or {}
        shipping_lines = o.get("shipping_lines") or []

        # klantnaam: eerst customer, anders shipping address, anders "-"
        customer_name = (
            f"{customer.get('first_name','')} {customer.get('last_name','')}".strip()
            or (shipping_address.get("name") or "").strip()
            or "-"
        )

        # verzendmethode: alle shipping lines titels
        shipping_titles = [ (l.get("title") or "").strip() for l in shipping_lines ]
        shipping_titles = [t for t in shipping_titles if t]
        shipping_title = ", ".join(shipping_titles) if shipping_titles else "-"

        rows.append(
            {
                "id": o.get("id"),
                "name": o.get("name"),
                "created_at": o.get("created_at"),
                "total_price": o.get("total_price"),
                "currency": o.get("currency"),
                "customer": customer_name,
                "shipping": shipping_title,
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

@router.get("/orders/{order_id}", response_class=HTMLResponse)
def order_detail(request: Request, order_id: int):
    shop_key = request.query_params.get("shop") or "abc-led"

    shopify = ShopifyClient(shop_key)
    try:
        order = shopify.get_order(order_id)
    finally:
        shopify.close()

    if not order:
        return templates.TemplateResponse(
            "order_detail.html",
            {"request": request, "order": None, "active_page": "orders", "active_shop": shop_key},
            status_code=404,
        )

    return templates.TemplateResponse(
        "order_detail.html",
        {
            "request": request,
            "order": order,
            "active_page": "orders",
            "active_shop": shop_key,
        },
    )
