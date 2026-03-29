from fastapi import FastAPI
from backend.routes.cost import router as cost_router

app = FastAPI()
app.include_router(cost_router)
