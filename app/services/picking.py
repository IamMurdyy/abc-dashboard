from typing import Any, Dict, List

PICKUP_TITLE = "Afhalen in de winkel"
RED_TITLES = {"Pakket Belgie", "Pakket"}

def _money_to_float(v: Any) -> float:
    try:
        return float(v)
    except Exception:
        return 0.0

def _get_customer_name(order: Dict[str, Any]) -> str:
    # Shopify: soms shipping_address, soms customer/default_address.
    ship = order.get("shipping_address") or {}
    first = (ship.get("first_name") or "").strip()
    last = (ship.get("last_name") or "").strip()

    if first or last:
        return f"{first} {last}".strip()

    cust = order.get("customer") or {}
    first = (cust.get("first_name") or "").strip()
    last = (cust.get("last_name") or "").strip()
    name = f"{first} {last}".strip()

    return name or "-"

def _get_shipping_method(order: Dict[str, Any]) -> str:
    # Shopify REST: shipping_lines is list, meestal 1
    lines = order.get("shipping_lines") or []
    if lines and isinstance(lines, list):
        title = (lines[0].get("title") or "").strip()
        if title:
            return title
    # fallback
    return "-"

def _get_order_subtotal(order: Dict[str, Any]) -> float:
    if order.get("current_subtotal_price") is not None:
        return _money_to_float(order.get("current_subtotal_price"))
    if order.get("subtotal_price") is not None:
        return _money_to_float(order.get("subtotal_price"))
    return _money_to_float(order.get("total_price"))

def _get_unit_price(item: Dict[str, Any]) -> float:
    # Shopify line item price is string
    return _money_to_float(item.get("price"))

def _get_mpn(item: Dict[str, Any]) -> str:
    # pragmatische fallback: sku als mpn als we (nog) geen metafield ophalen
    # later kunnen we hier variant metafield mm-google-shopping.mpn inpluggen
    mpn = (item.get("mpn") or "").strip()  # als je het ooit toevoegt
    if mpn:
        return mpn
    sku = (item.get("sku") or "").strip()
    return sku or "-"

def build_pick_rows(orders: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []

    for order in orders:
        order_number = order.get("name") or order.get("order_number") or "-"
        customer_name = _get_customer_name(order)
        shipping_method = _get_shipping_method(order)
        order_subtotal = _get_order_subtotal(order)

        is_pickup = shipping_method == PICKUP_TITLE
        is_red = shipping_method in RED_TITLES

        for item in (order.get("line_items") or []):
            qty = int(item.get("quantity") or 0)
            product_name = (item.get("title") or "-").strip()
            unit_price = _get_unit_price(item)
            mpn = _get_mpn(item)

            rows.append({
                "order_number": order_number,
                "customer_name": customer_name,
                "mpn": mpn,
                "qty": qty,
                "product_name": product_name,
                "unit_price": unit_price,
                "order_subtotal": order_subtotal,
                "shipping_method": shipping_method,

                # styling flags
                "is_pickup": is_pickup,
                "is_red": is_red,
                "is_qty_multi": qty > 1,
            })

    # sorteren op ordernummer (als string werkt vaak prima: "#10001")
    rows.sort(key=lambda r: str(r["order_number"]))
    return rows
