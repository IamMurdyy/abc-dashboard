from typing import Any, Dict, List, Tuple

PICKUP_TITLE = "Afhalen in de winkel"
RED_TITLES = {"Pakket Belgie", "Pakket", "Package Europe"}

PICKUP_ALIASES = {
    "stephensonweg",  # vangt "Stephensonweg 4A"
}

def _money_to_float(v: Any) -> float:
    try:
        return float(v)
    except Exception:
        return 0.0

def _norm_str(v: Any) -> str:
    """Maak string vergelijkingen betrouwbaar (None/ints/spaties)."""
    if v is None:
        return ""
    return str(v).strip()

def _clean(v: Any) -> str:
    return _norm_str(v)

def _full_name_from_address(addr: Dict[str, Any]) -> str:
    """
    Shopify address object heeft vaak 'name' gevuld (volledige naam).
    Fallback naar first/last en daarna company.
    """
    name = _clean(addr.get("name"))
    if name:
        return name

    first = _clean(addr.get("first_name"))
    last = _clean(addr.get("last_name"))
    full = f"{first} {last}".strip()
    if full:
        return full

    company = _clean(addr.get("company"))
    if company:
        return company

    return ""

def _get_customer_name(order: Dict[str, Any]) -> str:
    """
    Klantnaam bepalen.
    0) Eerst Flow-metafield (custom.pick_klantnaam) dat we in shopify.py als order["pick_klantnaam"] zetten.
    Daarna: shipping/billing/customer/email fallbacks.
    """

    # 0) Flow metafield (werkt ook als PII via API redacted is)
    mf_name = _clean(order.get("pick_klantnaam"))
    if mf_name:
        return mf_name

    # 1) shipping_address (meest relevant voor picken)
    ship = order.get("shipping_address") or {}
    ship_name = _full_name_from_address(ship)
    if ship_name:
        return ship_name

    # 2) billing_address (soms wél gevuld)
    bill = order.get("billing_address") or {}
    bill_name = _full_name_from_address(bill)
    if bill_name:
        return bill_name

    # 3) customer object
    cust = order.get("customer") or {}

    cust_name = _clean(cust.get("name"))
    if cust_name:
        return cust_name

    first = _clean(cust.get("first_name"))
    last = _clean(cust.get("last_name"))
    full = f"{first} {last}".strip()
    if full:
        return full

    default_addr = cust.get("default_address") or {}
    default_name = _full_name_from_address(default_addr)
    if default_name:
        return default_name

    # 4) laatste redmiddel: email (beter dan '-')
    email = _clean(order.get("email") or order.get("contact_email") or cust.get("email"))
    if email:
        return email

    return "-"

def _get_shipping_method(order: Dict[str, Any]) -> str:
    lines = order.get("shipping_lines") or []
    if lines and isinstance(lines, list):
        title = _norm_str(lines[0].get("title"))
        if title:
            return title
    return "-"

def _is_pickup_shipping(title: str) -> bool:
    t = _norm_str(title)
    if t == PICKUP_TITLE:
        return True
    low = t.lower()
    return any(alias in low for alias in PICKUP_ALIASES)

def _get_order_subtotal(order: Dict[str, Any]) -> float:
    if order.get("current_subtotal_price") is not None:
        return _money_to_float(order.get("current_subtotal_price"))
    if order.get("subtotal_price") is not None:
        return _money_to_float(order.get("subtotal_price"))
    return _money_to_float(order.get("total_price"))

def _get_unit_price(item: Dict[str, Any]) -> float:
    return _money_to_float(item.get("price"))

def _get_mpn(item: Dict[str, Any]) -> str:
    mpn = _norm_str(item.get("mpn"))
    if mpn:
        return mpn
    sku = _norm_str(item.get("sku"))
    return sku or "-"

def _row_sort_key(r: Dict[str, Any]) -> Tuple[str, str, str]:
    # Sorteer per order, dan product, dan mpn zodat regels van dezelfde order gegroepeerd blijven
    return (
        _norm_str(r.get("order_number")),
        _norm_str(r.get("product_name")),
        _norm_str(r.get("mpn")),
    )

def build_pick_rows(orders: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []

    for order in orders:
        order_number = _norm_str(order.get("name") or order.get("order_number") or "-")
        customer_name = _get_customer_name(order)

        shipping_method_raw = _get_shipping_method(order)
        is_pickup = _is_pickup_shipping(shipping_method_raw)

        # Wat je wil tonen in UI/print
        shipping_method_display = "Afhalen" if is_pickup else shipping_method_raw

        order_subtotal = _get_order_subtotal(order)

        # rood: o.a. Package Europe
        is_red = shipping_method_raw in RED_TITLES

        for item in (order.get("line_items") or []):
            qty = int(item.get("quantity") or 0)
            product_name = _norm_str(item.get("title") or "-")
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
                "shipping_method": shipping_method_display,

                # flags
                "is_pickup": is_pickup,
                "is_red": is_red,
                "is_qty_multi": qty > 1,
            })

    # 1) Zorg dat regels van dezelfde order bij elkaar staan
    rows.sort(key=_row_sort_key)

    # 2) Markeer eerste regel per order (voor template)
    prev_order = None
    for r in rows:
        cur_order = _norm_str(r.get("order_number"))
        r["is_first_in_order"] = (cur_order != prev_order)
        prev_order = cur_order

    return rows
