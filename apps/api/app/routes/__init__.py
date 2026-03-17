from app.routes.admin_routes import router as admin_router
from app.routes.auth_routes import router as auth_router
from app.routes.collection_routes import router as collection_router
from app.routes.file_routes import router as file_router
from app.routes.health_routes import router as health_router
from app.routes.user_routes import router as user_router


def get_routers():
    return [
        health_router,
        auth_router,
        user_router,
        collection_router,
        file_router,
        admin_router,
    ]
