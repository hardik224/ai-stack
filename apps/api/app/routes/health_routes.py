from fastapi import APIRouter

from app.controllers import health_controller


router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    return health_controller.health()


@router.get("/db-health")
def db_health():
    return health_controller.db_health()
