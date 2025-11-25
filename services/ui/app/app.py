import asyncio
from datetime import datetime
from fastapi import FastAPI, APIRouter
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select, func
from starlette.middleware.sessions import SessionMiddleware

from CONFIG import SECRET_KEY
from i18n import t
from .db import Base, engine, run_light_migrations, SessionLocal
from .llm.llm_bootstrap import ensure_models_ready, get_bootstrap_state
from .models import Folder, Conversation

# Routers grouped by domain
from .routes.routes_conversations import router as conversations_router
from .routes.routes_folders import router as folders_router
from .routes.routes import router as general_router


app = FastAPI()

# Session storage for conversation state and other lightweight per-user data
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

# Serve static frontend assets (JS/CSS/images)
app.mount("/static", StaticFiles(directory="static"), name="static")

# LLM bootstrap status endpoint
status_router = APIRouter()

# =========== Endpoints Routes ===========
@app.on_event("startup")
async def on_startup():
    """
    Initialize database schema and run lightweight migrations.
    Also seeds minimal data when the app is launched with an empty database:
    - Creates a default 'General' folder.
    - Creates a starter conversation containing a welcome message.
    """
    run_light_migrations(engine)
    Base.metadata.create_all(bind=engine)

    # Seed only when no folders exist
    with SessionLocal() as db:
        if db.execute(select(func.count(Folder.id))).scalar() == 0:
            folder = Folder(name=t("default_folder_name"))
            db.add(folder)
            db.commit()
            db.refresh(folder)

            conv = Conversation(
                title=t("welcome_title"),
                summary=t("welcome_summary"),
                messages=[
                    {
                        "role": "assistant",
                        "content": t("welcome_body"),
                        "ts": datetime.utcnow().isoformat(),
                    }
                ],
                msg_count=1,
                updated_at=datetime.utcnow(),
            )
            db.add(conv)
            db.commit()

    # Launch the Ollama template bootstrap in the background
    asyncio.create_task(ensure_models_ready())

@status_router.get("/llm/bootstrap-status")
def llm_bootstrap_status():
    """
    Returns the current bootstrap status for LLM models
    so the frontend can show progress / loading state.
    """
    return get_bootstrap_state()


# =========== Register Endpoints Routes ===========
# (without prefixes to preserve the existing URL structure)
app.include_router(general_router)        # "/", "/app", general endpoints
app.include_router(conversations_router)  # /conversations/*, /message
app.include_router(folders_router)        # /folders/* and /documents/*
app.include_router(status_router)         # /llm/bootstrap-status
