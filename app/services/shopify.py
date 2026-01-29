import os
import requests


class ShopifyClient:
    """
    Multi-shop ready Shopify client.
    Env vars per shop via prefix, bijv:

    ABCLED_SHOPIFY_SHOP=abc-led.myshopify.com
    ABCLED_SHOPIFY_ACCESS_TOKEN=shpat_...   (aanrader)
    # of (fallback):
    ABCLED_SHOPIFY_TOKEN=shpat_...
    ABCLED_SHOPIFY_API_VERSION=2024-10      (optioneel)

    Later:
    ABCSTORE_SHOPIFY_SHOP=abcstore-nl.myshopify.com
    ABCSTORE_SHOPIFY_ACCESS_TOKEN=...
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

        # Shop domain
        shop = os.getenv(f"{prefix}_SHOPIFY_SHOP") or os.getenv("SHOPIFY_SHOP")

        # Token: accepteer zowel ACCESS_TOKEN als TOKEN (per-shop + globale fallback)
        token = (
            os.getenv(f"{prefix}_SHOPIFY_ACCESS_TOKEN")
            or os.getenv(f"{prefix}_SHOPIFY_TOKEN")
            or os.getenv("SHOPIFY_ACCESS_TOKEN")
            or os.getenv("SHOPIFY_TOKEN")
        )

        # API version
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

        # Zorg dat shop netjes is (zonder protocol / trailing slash)
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
        }
        r = self.session.get(url, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        return data.get("orders", [])
    
    def get_order(self, order_id: int):
        """
        Haal 1 order op
        """
        url = f"{self.base_url}/orders/{order_id}.json"
        r = self.session.get(url, timeout=30)
        r.raise_for_status()
        data = r.json()
        return data.get("order")




