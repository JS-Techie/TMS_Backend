from fastapi import APIRouter, FastAPI

from routes.bidding import bidding_router

router: APIRouter = APIRouter(prefix="/api/v1")


def setup_routes(app: FastAPI):

    router.include_router(bidding_router)

    app.include_router(router)
