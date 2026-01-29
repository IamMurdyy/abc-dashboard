from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.services.shopify import ShopifyClient

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def _customer_name(order: dict) -> str:
    customer = order.get("customer") or {}
    shipping_address = order.get("shipping_address") or {}
    billing_address = order.get("billing_address") or {}

    # 1) customer object
    first = (customer.get("first_name") or "").strip()
    last = (customer.get("last_name") or "").strip()
    full = (first + " " + last).strip()
    if full:
        return full

    # 2) shipping address: name of first/last
    name = (shipping_address.get("name") or "").strip()
    if name:
        return name
    sfirst = (shipping_address.get("first_name") or "").strip()
    slast = (shipping_address.get("last_name") or "").strip()
    sfull = (sfirst + " " + slast).strip()
    if sfull:
        return sfull

    # 3) billing address: name of first/last
    bname = (billing_address.get("name") or "").strip()
    if bname:
        return bname
    bfirst = (billing_address.get("first_name") or "").strip()
    blast = (billing_address.get("last_name") or "").strip()
    bfull = (bfirst + " " + blast).strip()
    if bfull:
        return bfull

    return "-"


def _shipping_method(order: dict) -> str:
    lines = order.get("shipping_lines") or []
    titles = [(l.get("title") or "").strip() for l in lines]
    titles = [t for t in titles if t]
    if titles:
        return ", ".join(titles)

    # fallback: bij pickup/afhalen kan shipping_lines leeg zijn
    return "Afhalen / Pickup"


@router.get("/orders", response_class=HTMLResponse)
def orders_page(request: Request):
    shop_key = request.query_params.get("shop") or "abc-led"

    shopify = ShopifyClient(shop_key)
    try:
        orders = shopify.list_orders()
    finally:
        shopify.close()

    rows = []
    for o in orders:
        # TEMP DEBUG: check één specifieke order (verwijder later)
        if o.get("name") == "#1192":
            print("DEBUG #1192 shipping_lines:", o.get("shipping_lines"))
            print("DEBUG #1192 shipping_address:", o.get("shipping_address"))
            print("DEBUG #1192 billing_address:", o.get("billing_address"))
            print("DEBUG #1192 customer:", o.get("customer"))

        rows.append(
            {
                "id": o.get("id"),
                "name": o.get("name"),
                "created_at": o.get("created_at"),
                "total_price": o.get("total_price"),
                "currency": o.get("currency"),
                "customer": _customer_name(o),
                "shipping": _shipping_method(o),
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
            ],
        },
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
            {
                "request": request,
                "order": None,
                "active_page": "orders",
                "active_shop": shop_key,
                "customer_name": "-",
                "shipping_method": "-",
            },
            status_code=404,
        )

    return templates.TemplateResponse(
        "order_detail.html",
        {
            "request": request,
            "order": order,
            "active_page": "orders",
            "active_shop": shop_key,
            "customer_name": _customer_name(order),
            "shipping_method": _shipping_method(order),
        },
    )


@router.post("/orders/fetch")
def orders_fetch(request: Request):
    shop_key = request.query_params.get("shop") or "abc-led"

    try:
        shopify = ShopifyClient(shop_key=shop_key)
        try:
            orders = shopify.list_orders()
        finally:
            shopify.close()

        count = len(orders) if orders else 0
        msg = f"Orders opgehaald: {count}"

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
