# ABC Dashboard

Interne web-app (FastAPI) voor o.a. Shopify orders, picklijsten en exports.

## Lokaal draaien
1) Maak een .env in de root met:

SHOPIFY_SHOP=jouwstore.myshopify.com
SHOPIFY_ACCESS_TOKEN=shpat_...
SHOPIFY_API_VERSION=2025-07

2) Installeren en runnen:

python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload

Open daarna: http://127.0.0.1:8000