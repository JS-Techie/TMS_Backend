from fastapi import APIRouter, Request

from schemas.bidding import FilterBidsRequest
from utils.response import ServerError, SuccessResponse, ErrorResponse
from utils.bids.bidding import Bid

dashboard_router = APIRouter(prefix="/dashboard", tags=["Dashboard routes"])

bid = Bid()


@dashboard_router.post("/stats")
async def get_bid_details(request: Request, filter_criteria: FilterBidsRequest):

    try:

        bid_details, error = await bid.stats(filter=filter_criteria)

        if error:
            return ErrorResponse(data=[], dev_msg=error, client_msg="Something went wrong while fetching bid details")

        return SuccessResponse(data=bid_details, dev_msg="All bid stats fetched", client_msg="Requested stats fetched successfully")

    except Exception as e:
        return ServerError(err=e, errMsg=str(e))


@dashboard_router.post("/cancellations")
async def get_bid_details(request: Request, filter_criteria: FilterBidsRequest):

    try:

        bid_details, error = await bid.cancellation_reasons(filter=filter_criteria)

        if error:
            return ErrorResponse(data=[], dev_msg=error, client_msg="Something went wrong while fetching cancellation reasons")

        return SuccessResponse(data=bid_details, dev_msg="All cancellation reasons fetched", client_msg="Requested stats fetched successfully")

    except Exception as e:
        return ServerError(err=e, errMsg=str(e))

# TODO


@dashboard_router.post("/trend")
async def get_bid_details(request: Request, filter_criteria: FilterBidsRequest):

    try:

        bid_details, error = await bid.stats(filter=filter_criteria)

        if error:
            return ErrorResponse(data=[], dev_msg=error, client_msg="Something went wrong while fetching bid details")

        return SuccessResponse(data=bid_details, dev_msg="All bid stats fetched", client_msg="Requested stats fetched successfully")

    except Exception as e:
        return ServerError(err=e, errMsg=str(e))


@dashboard_router.post("/transporters")
async def get_bid_details(request: Request, filter_criteria: FilterBidsRequest):

    try:

        bid_details, error = await bid.transporter_analysis(filter=filter_criteria)

        if error:
            return ErrorResponse(data=[], dev_msg=error, client_msg="Something went wrong while fetching transporter details")

        return SuccessResponse(data=bid_details, dev_msg="All bid stats fetched", client_msg="Requested stats fetched successfully")

    except Exception as e:
        return ServerError(err=e, errMsg=str(e))
