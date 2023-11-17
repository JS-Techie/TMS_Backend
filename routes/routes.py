from fastapi import APIRouter, FastAPI

from middleware.auth import AuthMiddleware
from routes.bids.shipper import shipper_bidding_router
from routes.bids.transporter import transporter_bidding_router
from routes.bids.open import open_router
from routes.dashboard import dashboard_router

router: APIRouter = APIRouter(prefix="/api/v1")


def setup_routes(app: FastAPI):

    router.include_router(shipper_bidding_router)
    router.include_router(transporter_bidding_router)
    router.include_router(dashboard_router)
    router.include_router(open_router)

    app.add_middleware(AuthMiddleware)

    app.include_router(router)
