from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.services.shopify import ShopifyClient, fetch_orders

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
    1) pick_klantnaam (verrijkt door fetch_orders via metafield custom.pick_klantnaam)
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


@router.get("/orders", response_class=HTMLResponse)
def orders_page(request: Request):
    shop_key = request.query_params.get("shop") or "abc-led"

    # Belangrijk: fetch_orders verrijkt orders met pick_klantnaam (metafield) via bulk GraphQL
    orders = fetch_orders(shop=shop_key, limit=50)

    rows = []
    for o in orders:
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


@router.get("/orders/refresh")
def orders_refresh(request: Request):
    shop_key = request.query_params.get("shop") or "abc-led"

    try:
        # Zelfde bron gebruiken als /orders zodat refresh exact hetzelfde gedrag heeft
        orders = fetch_orders(shop=shop_key, limit=50)

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

    # Detail houden we zoals je had: via ShopifyClient order ophalen
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

    # Voor detailpagina proberen we óók pick_klantnaam te tonen als die er is.
    # Omdat get_order() meestal geen metafields bevat, halen we 1 order verrijkt op via fetch_orders.
    customer_name = _customer_name(order)
    if customer_name == "-":
        try:
            enriched = fetch_orders(shop=shop_key, limit=50)
            match = next((o for o in enriched if str(o.get("id")) == str(order_id)), None)
            if match:
                customer_name = _customer_name(match)
        except Exception:
            pass

    shipping_method = _shipping_method(order)

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
