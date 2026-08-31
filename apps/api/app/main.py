from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.auth.admin_router import router as admin_users_router
from app.auth.router import router as auth_router
from app.core.config import settings
from app.core.observability import request_observability_middleware
from app.customers.router import router as customers_router
from app.dashboard.router import router as dashboard_router
from app.finance.router import router as finance_router
from app.employees.router import router as employees_router
from app.health.router import router as health_router
from app.laboratory.router import router as laboratory_router
from app.notifications.router import router as notifications_router
from app.purchasing.router import router as purchasing_router
from app.tracking.router import router as tracking_router

app = FastAPI(
    title="NEXUS API",
    version="0.3.0",
    docs_url="/docs" if settings.app_env != "production" else None,
    redoc_url=None,
)

app.middleware("http")(request_observability_middleware)

app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts_list)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "X-CSRF-Token", "X-Request-ID"],
    expose_headers=["X-Request-ID"],
)
app.include_router(health_router, prefix="/health", tags=["health"])
app.include_router(auth_router, tags=["auth"])
app.include_router(admin_users_router, tags=["admin-users"])
app.include_router(dashboard_router, tags=["dashboard"])
app.include_router(customers_router, tags=["customers"])
app.include_router(finance_router, tags=["finance"])
app.include_router(employees_router, tags=["employees"])
app.include_router(purchasing_router, tags=["purchasing"])
app.include_router(tracking_router, tags=["tracking"])
app.include_router(laboratory_router, tags=["laboratory"])
app.include_router(notifications_router, tags=["notifications"])
