from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from app.services.shopify import (
    ShopifyClient,
    get_order_pick_name,
    fetch_order_pick_names,  # <-- komt zo meteen in shopify.py erbij (of exporten)
)

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
    Fallback klantnaam bepalen zonder extra API call.
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
    order_email = (order.get("email") or order.get("contact_email") or "").strip()
    if order_email:
        return order_email

    return ""


def _customer_name(order: dict) -> str:
    """
    Definitieve klantnaam:
    1) pick_klantnaam (verrijkt via bulk GraphQL per batch)
    2) fallback uit order payload
    3) '-' als alles leeg is
    """
    mf = (order.get("pick_klantnaam") or "").strip()
    if mf:
        return mf

    name = _customer_name_from_order(order)
    if name:
        return name

    return "-"


def _map_order_row(o: dict) -> dict:
    return {
        "id": o.get("id"),
        "name": o.get("name"),
        "created_at": o.get("created_at"),
        "total_price": o.get("total_price"),
        "currency": o.get("currency"),
        "customer": _customer_name(o),
        "shipping": _shipping_method(o),
    }


def _enrich_pick_names(client: ShopifyClient, orders: list[dict]) -> None:
    """
    Zet order["pick_klantnaam"] op basis van Flow metafield custom.pick_klantnaam
    (bulk GraphQL per batch, dus snel).
    """
    order_ids = [int(o["id"]) for o in orders if o.get("id")]
    if not order_ids:
        return

    try:
        pick_names = fetch_order_pick_names(client, order_ids)
    except Exception:
        pick_names = {}

    if not pick_names:
        return

    for o in orders:
        oid = o.get("id")
        if oid in pick_names:
            o["pick_klantnaam"] = pick_names[oid]


@router.get("/orders", response_class=HTMLResponse)
def orders_page(request: Request):
    shop_key = request.query_params.get("shop") or "abc-led"

    client = ShopifyClient(shop_key)
    try:
        orders, next_page_info = client.list_orders_page(limit=50, page_info=None)
        _enrich_pick_names(client, orders)
    finally:
        client.close()

    rows = [_map_order_row(o) for o in orders]

    return templates.TemplateResponse(
        "orders.html",
        {
            "request": request,
            "orders": rows,
            "next_page_info": next_page_info,  # <-- nodig voor "Laad meer"
            "active_page": "orders",
            "active_shop": shop_key,
            "shops": [
                {"key": "abc-led", "name": "ABC-LED", "href": "/orders?shop=abc-led"},
            ],
        },
    )


@router.get("/orders/more")
def orders_more(request: Request):
    shop_key = request.query_params.get("shop") or "abc-led"
    page_info = (request.query_params.get("page_info") or "").strip()

    if not page_info:
        return JSONResponse({"orders": [], "next_page_info": None})

    client = ShopifyClient(shop_key)
    try:
        orders, next_page_info = client.list_orders_page(limit=50, page_info=page_info)
        _enrich_pick_names(client, orders)
    finally:
        client.close()

    rows = [_map_order_row(o) for o in orders]

    return JSONResponse(
        {
            "orders": rows,
            "next_page_info": next_page_info,
        }
    )


@router.get("/orders/refresh")
def orders_refresh(request: Request):
    """
    Refresh doet geen zware Shopify calls meer.
    We herladen gewoon /orders (die laadt altijd de eerste pagina).
    """
    shop_key = request.query_params.get("shop") or "abc-led"

    return RedirectResponse(
        url=f"/orders?shop={shop_key}&toast=Orders%20ververst&toast_type=success",
        status_code=303,
    )


@router.get("/orders/{order_id:int}", response_class=HTMLResponse)
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
            },
            status_code=404,
        )

    # Klantnaam: 1 snelle GraphQL call voor alleen deze order
    try:
        customer_name = get_order_pick_name(shop=shop_key, order_id=order_id) or "-"
    except Exception:
        customer_name = "-"

    # (optionele) fallback als metafield leeg is
    if customer_name == "-":
        cust = order.get("customer") or {}
        ship = order.get("shipping_address") or {}
        bill = order.get("billing_address") or {}

        first = (cust.get("first_name") or "").strip()
        last = (cust.get("last_name") or "").strip()
        full = (first + " " + last).strip()
        if full:
            customer_name = full
        elif (ship.get("name") or "").strip():
            customer_name = ship["name"].strip()
        elif (bill.get("name") or "").strip():
            customer_name = bill["name"].strip()

    # Status
    financial_status = (order.get("financial_status") or "-").replace("_", " ").title()
    fulfillment_status = (order.get("fulfillment_status") or "unfulfilled").replace("_", " ").title()

    created_at = order.get("created_at") or "-"
    currency = order.get("currency") or "EUR"

    def to_float(x):
        try:
            return float(str(x))
        except Exception:
            return 0.0

    subtotal = to_float(order.get("subtotal_price"))
    tax = to_float(order.get("total_tax"))
    discounts = to_float(order.get("total_discounts"))
    total = to_float(order.get("total_price"))

    shipping_lines = order.get("shipping_lines") or []
    shipping = sum(to_float(sl.get("price")) for sl in shipping_lines)

    # Als subtotal ontbreekt, bereken uit regels
    if subtotal == 0.0:
        line_items = order.get("line_items") or []
        subtotal = sum(to_float(li.get("price")) * int(li.get("quantity") or 0) for li in line_items)

    note = (order.get("note") or "").strip() or None
    tags = (order.get("tags") or "").strip() or None

    shipping_method = _shipping_method(order)

    fulfillments_raw = order.get("fulfillments") or []
    fulfillments = []
    for f in fulfillments_raw:
        fulfillments.append(
            {
                "name": f.get("name"),
                "status": f.get("status"),
                "created_at": f.get("created_at"),
                "tracking_company": f.get("tracking_company"),
                "tracking_numbers": f.get("tracking_numbers") or [],
                "tracking_urls": f.get("tracking_urls") or [],
            }
        )

    return templates.TemplateResponse(
        "order_detail.html",
        {
            "request": request,
            "order": order,
            "active_page": "orders",
            "active_shop": shop_key,
            "customer_name": customer_name,
            "status": {
                "financial": f"Betaling: {financial_status}",
                "fulfillment": f"Fulfillment: {fulfillment_status}",
            },
            "created_at": created_at,
            "money": {
                "currency": currency,
                "subtotal": f"{subtotal:.2f}",
                "shipping": f"{shipping:.2f}",
                "discounts": f"{discounts:.2f}",
                "tax": f"{tax:.2f}",
                "total": f"{total:.2f}",
            },
            "tags": tags,
            "note": note,
            "shipping_method": shipping_method,
            "fulfillments": fulfillments,
        },
    )