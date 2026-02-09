from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.services.shopify import fetch_orders
from app.services.picking import build_pick_rows

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/picklijsten", response_class=HTMLResponse)
def picklijsten(request: Request, shop: str = "abc-led"):
    """
    Picklijst:
    - Haalt ALLE paid + unfulfilled orders op (geen cap)
    - Rows worden gebouwd met app.services.picking.build_pick_rows()
      zodat de template keys (unit_price, order_subtotal, etc.) kloppen.
    - Teller = aantal bestellingen (orders)
    """
    # Picklijst moet ALTIJD alles ophalen (geen max_total cap)
    orders = fetch_orders(shop=shop, limit=50, max_total=None)

    # Rows in exact het format dat picklists.html verwacht
    rows = build_pick_rows(orders)

    aantal_bestellingen = len(orders)

    return templates.TemplateResponse(
        "picklists.html",
        {
            "request": request,
            "shop": shop,
            "rows": rows,
            "aantal_bestellingen": aantal_bestellingen,
            "active_page": "picklijsten",
            "active_shop": shop,
        },
    )