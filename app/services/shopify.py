import os
import requests


class ShopifyClient:
    """
    Multi-shop ready Shopify client.
    """

    SHOP_PREFIX = {
        "abc-led": "ABCLED",
        # later:
        # "abcstore": "ABCSTORE",
    }

    def __init__(self, shop_key: str = "abc-led"):
        self.shop_key = shop_key or "abc-led"

        prefix = self.SHOP_PREFIX.get(self.shop_key)
        if not prefix:
            raise ValueError(f"Onbekende shop_key '{self.shop_key}'. Voeg toe aan SHOP_PREFIX.")

        shop = os.getenv(f"{prefix}_SHOPIFY_SHOP") or os.getenv("SHOPIFY_SHOP")

        token = (
            os.getenv(f"{prefix}_SHOPIFY_ACCESS_TOKEN")
            or os.getenv(f"{prefix}_SHOPIFY_TOKEN")
            or os.getenv("SHOPIFY_ACCESS_TOKEN")
            or os.getenv("SHOPIFY_TOKEN")
        )

        version = (
            os.getenv(f"{prefix}_SHOPIFY_API_VERSION")
            or os.getenv("SHOPIFY_API_VERSION")
            or "2024-07"
        )

        if not shop or not token:
            raise RuntimeError(
                f"Shopify env vars missen voor {self.shop_key}. "
                f"Verwacht: {prefix}_SHOPIFY_SHOP + "
                f"{prefix}_SHOPIFY_ACCESS_TOKEN (of {prefix}_SHOPIFY_TOKEN). "
                f"Fallback: SHOPIFY_SHOP + SHOPIFY_ACCESS_TOKEN (of SHOPIFY_TOKEN)."
            )

        shop = shop.replace("https://", "").replace("http://", "").strip("/")

        self.shop = shop
        self.version = version
        self.session = requests.Session()
        self.session.headers.update(
            {
                "X-Shopify-Access-Token": token,
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        )
        self.base_url = f"https://{self.shop}/admin/api/{self.version}"

    def close(self):
        try:
            self.session.close()
        except Exception:
            pass

    # -------------------------
    # REST helpers
    # -------------------------

    def list_orders(self, limit: int = 50):
        """
        Paid + unfulfilled
        """
        url = f"{self.base_url}/orders.json"
        params = {
            "status": "open",
            "financial_status": "paid",
            "fulfillment_status": "unfulfilled",
            "limit": limit,
        }
        r = self.session.get(url, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        return data.get("orders", [])

    def get_order(self, order_id: int):
        """
        Haal 1 order op (incl. regels)
        """
        url = f"{self.base_url}/orders/{order_id}.json"
        r = self.session.get(url, timeout=30)
        r.raise_for_status()
        data = r.json()
        return data.get("order")

    def get_customer(self, customer_id: int):
        """
        Haal 1 klant op (voor B2B company / naam) - gebruiken we als fallback voor de orderlijst.
        """
        url = f"{self.base_url}/customers/{customer_id}.json"
        r = self.session.get(url, timeout=30)
        r.raise_for_status()
        data = r.json()
        return data.get("customer")

    # -------------------------
    # GraphQL helper
    # -------------------------

    def graphql(self, query: str, variables: dict | None = None) -> dict:
        """
        Shopify GraphQL Admin API call.
        """
        url = f"https://{self.shop}/admin/api/{self.version}/graphql.json"
        payload = {"query": query, "variables": variables or {}}
        r = self.session.post(url, json=payload, timeout=30)
        r.raise_for_status()

        data = r.json() or {}
        if data.get("errors"):
            raise RuntimeError(f"GraphQL errors: {data['errors']}")
        return data.get("data") or {}


def fetch_order_pick_names(client: ShopifyClient, order_ids: list[int]) -> dict[int, str]:
    """
    Haalt custom.pick_klantnaam op voor meerdere orders in 1 GraphQL call.
    Retourneert: { order_id_int: "Naam" }
    """
    if not order_ids:
        return {}

    gids = [f"gid://shopify/Order/{oid}" for oid in order_ids]

    q = """
    query($ids: [ID!]!) {
      nodes(ids: $ids) {
        ... on Order {
          id
          metafield(namespace: "custom", key: "pick_klantnaam") { value }
        }
      }
    }
    """
    data = client.graphql(q, {"ids": gids})
    out: dict[int, str] = {}

    for node in (data.get("nodes") or []):
        if not node:
            continue

        gid = node.get("id") or ""
        mf = node.get("metafield") or {}
        val = (mf.get("value") or "").strip()
        if not val:
            continue

        try:
            numeric_id = int(gid.rsplit("/", 1)[-1])
            out[numeric_id] = val
        except Exception:
            pass

    return out


def fetch_orders(shop: str = "abc-led", limit: int = 50):
    client = ShopifyClient(shop_key=shop)
    try:
        orders = client.list_orders(limit=limit)

        # 1) Metafield namen in bulk ophalen en toevoegen aan orders
        order_ids = [int(o["id"]) for o in orders if o.get("id")]
        try:
            pick_names = fetch_order_pick_names(client, order_ids)
        except Exception:
            pick_names = {}

        for o in orders:
            oid = o.get("id")
            if oid in pick_names:
                o["pick_klantnaam"] = pick_names[oid]

        # 2) (optioneel) customer fallback (blijft zoals je had)
        customer_cache = {}

        for o in orders:
            cust = o.get("customer") or {}
            cust_id = cust.get("id")
            if not cust_id:
                continue

            ship = o.get("shipping_address") or {}
            bill = o.get("billing_address") or {}

            has_name = bool(
                ship.get("name")
                or ship.get("first_name")
                or ship.get("last_name")
                or ship.get("company")
                or bill.get("name")
                or bill.get("first_name")
                or bill.get("last_name")
                or bill.get("company")
                or cust.get("name")
                or cust.get("first_name")
                or cust.get("last_name")
                or cust.get("email")
                or o.get("email")
                or o.get("contact_email")
            )
            if has_name:
                continue

            if cust_id in customer_cache:
                o["customer"] = customer_cache[cust_id]
                continue

            try:
                full_customer = client.get_customer(int(cust_id))
                if full_customer:
                    customer_cache[cust_id] = full_customer
                    o["customer"] = full_customer
            except Exception:
                pass

        return orders
    finally:
        client.close()

def fetch_order_pick_name(client: ShopifyClient, order_id: int) -> str | None:
    """
    Haalt custom.pick_klantnaam op voor 1 order via GraphQL (snel, 1 call).
    Retourneert de string of None.
    """
    gid = f"gid://shopify/Order/{int(order_id)}"

    q = """
    query($id: ID!) {
      order(id: $id) {
        metafield(namespace: "custom", key: "pick_klantnaam") { value }
      }
    }
    """
    data = client.graphql(q, {"id": gid}) or {}
    order = data.get("order") or {}
    mf = order.get("metafield") or {}
    val = (mf.get("value") or "").strip()
    return val or None


def get_order_pick_name(shop: str = "abc-led", order_id: int = 0) -> str | None:
    """
    Convenience wrapper: opent zelf een client en haalt pick_klantnaam op voor 1 order.
    """
    if not order_id:
        return None

    client = ShopifyClient(shop_key=shop)
    try:
        return fetch_order_pick_name(client, int(order_id))
    finally:
        client.close()
