from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

from app.routes.orders import router as orders_router

app = FastAPI(title="ABC Dashboard")

app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(orders_router)

@app.get("/")
def root():
    return RedirectResponse(url="/orders")

@app.get("/healthz")
def healthz():
    return {"ok": True}
