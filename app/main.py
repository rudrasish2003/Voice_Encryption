from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api import audit, auth, health, identify, people

app = FastAPI(title="Voice Identification API", version="0.1.0")

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(people.router)
app.include_router(identify.router)
app.include_router(audit.router)

# Simple local console UI (register/browse/identify) served same-origin so its
# fetch() calls hit this API without CORS. Open http://localhost:8000/ui/
app.mount("/ui", StaticFiles(directory="static", html=True), name="ui")
