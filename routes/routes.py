from fastapi import APIRouter, FastAPI

from routes.bids.shipper import shipper_bidding_router
from routes.bids.transporter import transporter_bidding_router
from middleware.auth import AuthMiddleware

router: APIRouter = APIRouter(prefix="/api/v1")


def setup_routes(app: FastAPI):

    router.include_router(shipper_bidding_router)
    router.include_router(transporter_bidding_router)

    app.add_middleware(AuthMiddleware)
    app.include_router(router)
 
