from app.services import health_service


def health():
    return health_service.get_health()


def db_health():
    return health_service.get_db_health()
