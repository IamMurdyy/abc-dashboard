from __future__ import annotations
import httpx
from typing import Any, Dict, List, Optional

from app.core.config import SHOPIFY_SHOP, SHOPIFY_ACCESS_TOKEN, SHOPIFY_API_VERSION

BASE_URL = f"https://{SHOPIFY_SHOP}/admin/api/{SHOPIFY_API_VERSION}"

class ShopifyClient:
    def __init__(self) -> None:
        self.headers = {
            "X-Shopify-Access-Token": SHOPIFY_ACCESS_TOKEN,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        self.client = httpx.Client(headers=self.headers, timeout=30.0)

    def close(self) -> None:
        self.client.close()

    def list_orders(
        self,
        status: str = "any",
        financial_status: Optional[str] = "paid",
        fulfillment_status: Optional[str] = "unfulfilled",
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {"status": status, "limit": limit}
        if financial_status:
            params["financial_status"] = financial_status
        if fulfillment_status:
            params["fulfillment_status"] = fulfillment_status

        url = f"{BASE_URL}/orders.json"
        r = self.client.get(url, params=params)
        r.raise_for_status()
        data = r.json()
        return data.get("orders", [])