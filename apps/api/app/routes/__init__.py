from app.routes.admin_routes import router as admin_router
from app.routes.auth_routes import router as auth_router
from app.routes.chat_routes import router as chat_router
from app.routes.collection_routes import router as collection_router
from app.routes.file_routes import router as file_router
from app.routes.health_routes import router as health_router
from app.routes.search_routes import router as search_router
from app.routes.telegram_routes import router as telegram_router
from app.routes.user_routes import router as user_router
from app.routes.utility_routes import router as utility_router



def get_routers():
    return [
        health_router,
        auth_router,
        user_router,
        collection_router,
        file_router,
        search_router,
        chat_router,
        telegram_router,
        admin_router,
        utility_router,
    ]
