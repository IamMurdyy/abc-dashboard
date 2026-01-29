from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, FileResponse

from app.routes.orders import router as orders_router
from app.routes.picklists import router as picklists_router

app = FastAPI(title="ABC Dashboard")

app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(orders_router)
app.include_router(picklists_router)

@app.get("/")
def root():
    return RedirectResponse(url="/orders")

@app.get("/healthz")
def healthz():
    return {"ok": True}

@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return FileResponse("app/static/favicon.ico")
