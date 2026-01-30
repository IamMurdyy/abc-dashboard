from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.services.shopify import ShopifyClient

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def _shipping_method(order: dict) -> str:
    lines = order.get("shipping_lines") or []
    titles = [(l.get("title") or "").strip() for l in lines]
    titles = [t for t in titles if t]
    if titles:
        return ", ".join(titles)
    return "Afhalen / Pickup"


def _customer_name_from_order(order: dict) -> str:
    """
    Probeer klantnaam te bepalen zonder extra API call.
    """
    customer = order.get("customer") or {}
    shipping_address = order.get("shipping_address") or {}
    billing_address = order.get("billing_address") or {}

    # 1) Shopify customer first/last (als aanwezig)
    first = (customer.get("first_name") or "").strip()
    last = (customer.get("last_name") or "").strip()
    full = (first + " " + last).strip()
    if full:
        return full

    # 2) B2B / zakelijke klant: company uit default_address (als aanwezig in order payload)
    default_addr = customer.get("default_address") or {}
    company = (default_addr.get("company") or "").strip()
    if company:
        return company

    # 3) shipping address: name of first/last
    name = (shipping_address.get("name") or "").strip()
    if name:
        return name
    sfirst = (shipping_address.get("first_name") or "").strip()
    slast = (shipping_address.get("last_name") or "").strip()
    sfull = (sfirst + " " + slast).strip()
    if sfull:
        return sfull

    # 4) billing address: name of first/last
    bname = (billing_address.get("name") or "").strip()
    if bname:
        return bname
    bfirst = (billing_address.get("first_name") or "").strip()
    blast = (billing_address.get("last_name") or "").strip()
    bfull = (bfirst + " " + blast).strip()
    if bfull:
        return bfull

    # 5) order-level email (staat vaak op order, ook bij guest checkout)
    order_email = (order.get("email") or "").strip()
    if order_email:
        return order_email

    return ""  # leeg = nog geen resultaat


def _customer_name(order: dict, shopify: ShopifyClient, customer_cache: dict) -> str:
    """
    Definitieve klantnaam: eerst uit order, anders via extra customer call (met cache).
    """
    # probeer alles uit order payload
    name = _customer_name_from_order(order)
    if name:
        return name

    # fallback: customer id -> klant ophalen
    customer = order.get("customer") or {}
    customer_id = customer.get("id")
    if not customer_id:
        return "-"

    if customer_id in customer_cache:
        c = customer_cache[customer_id]
    else:
        try:
            c = shopify.get_customer(int(customer_id))
        except Exception:
            c = None
        customer_cache[customer_id] = c

    if not c:
        return f"Customer #{customer_id}"

    # customer payload is meestal rijker: first/last, company, email
    first = (c.get("first_name") or "").strip()
    last = (c.get("last_name") or "").strip()
    full = (first + " " + last).strip()
    if full:
        return full

    default_addr = c.get("default_address") or {}
    company = (default_addr.get("company") or "").strip()
    if company:
        return company

    email = (c.get("email") or "").strip()
    if email:
        return email

    return f"Customer #{customer_id}"


@router.get("/orders", response_class=HTMLResponse)
def orders_page(request: Request):
    shop_key = request.query_params.get("shop") or "abc-led"

    shopify = ShopifyClient(shop_key)
    try:
        orders = shopify.list_orders()
        customer_cache = {}

        rows = []
        for o in orders:
            rows.append(
                {
                    "id": o.get("id"),
                    "name": o.get("name"),
                    "created_at": o.get("created_at"),
                    "total_price": o.get("total_price"),
                    "currency": o.get("currency"),
                    "customer": _customer_name(o, shopify, customer_cache),
                    "shipping": _shipping_method(o),
                }
            )
    finally:
        shopify.close()

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


@router.get("/orders/refresh")
def orders_refresh(request: Request):
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

    except Exception:
        msg = "Fout bij ophalen orders"
        return RedirectResponse(
            url=f"/orders?shop={shop_key}&toast={msg}&toast_type=error",
            status_code=303,
        )


@router.get("/orders/{order_id:int}", response_class=HTMLResponse)
def order_detail(request: Request, order_id: int):
    shop_key = request.query_params.get("shop") or "abc-led"

    shopify = ShopifyClient(shop_key)
    try:
        order = shopify.get_order(order_id)
        customer_cache = {}
        customer_name = "-" if not order else _customer_name(order, shopify, customer_cache)
        shipping_method = "-" if not order else _shipping_method(order)
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
            "customer_name": customer_name,
            "shipping_method": shipping_method,
        },
    )
