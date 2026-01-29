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
            # velden die we nodig hebben in de lijst
            "fields": "id,name,created_at,total_price,subtotal_price,currency,email,customer,shipping_lines,shipping_address,billing_address,line_items",
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
        params = {
            "fields": "id,name,created_at,total_price,currency,email,customer,shipping_lines,shipping_address,billing_address,line_items",
        }
        r = self.session.get(url, params=params, timeout=30)
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

def fetch_orders(shop: str = "abc-led", limit: int = 50):
    client = ShopifyClient(shop_key=shop)
    try:
        return client.list_orders(limit=limit)
    finally:
        client.close()
