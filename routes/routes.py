from fastapi import APIRouter, FastAPI

from routes.bidding import bidding_router
from middleware.auth import AuthMiddleware

router: APIRouter = APIRouter(prefix="/api/v1")


def setup_routes(app: FastAPI):

    # app.add_middleware(AuthMiddleware)

    router.include_router(bidding_router)

    app.include_router(router)
