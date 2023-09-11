from fastapi import APIRouter, FastAPI

from routes.bidding import bidding_router

router: APIRouter = APIRouter(prefix="/api")


def setup_routes(app: FastAPI):

    router.include_router(bidding_router)

    app.include_router(router)
