from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.services.shopify import fetch_orders
from app.services.picking import build_pick_rows

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/picklijsten", response_class=HTMLResponse)
def picklijsten(request: Request, shop: str = "abc-led"):
    orders = fetch_orders(shop=shop)
    rows = build_pick_rows(orders)

    return templates.TemplateResponse(
        "picklists.html",
        {
            "request": request,
            "shop": shop,
            "rows": rows,
            "row_count": len(rows),
            "active_page": "picklijsten",
            "active_shop": shop,
        },
    )
