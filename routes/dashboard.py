from fastapi import APIRouter, Request

from schemas.bidding import FilterBidsRequest
from utils.bids.bidding import Bid
from utils.response import ErrorResponse, ServerError, SuccessResponse

dashboard_router = APIRouter(prefix="/dashboard", tags=["Dashboard routes"])

bid = Bid()


@dashboard_router.post("/stats")
async def get_status_wise_bid_count(request: Request, filter_criteria: FilterBidsRequest):

    try:

        bid_details, error = await bid.stats(filter=filter_criteria)

        if error:
            return ErrorResponse(data=[], dev_msg=error, client_msg="Something went wrong while fetching bid details")

        return SuccessResponse(data=bid_details, dev_msg="All bid stats fetched", client_msg="Requested stats fetched successfully")

    except Exception as e:
        return ServerError(err=e, errMsg=str(e))


@dashboard_router.post("/cancellations")
async def get_cancelled_load_analysis(request: Request, filter_criteria: FilterBidsRequest):

    try:

        bid_details, error = await bid.cancellation_reasons(filter=filter_criteria)

        if error:
            return ErrorResponse(data=[], dev_msg=error, client_msg="Something went wrong while fetching cancellation reasons")

        return SuccessResponse(data=bid_details, dev_msg="All cancellation reasons fetched", client_msg="Requested cancellation stats fetched successfully")

    except Exception as e:
        return ServerError(err=e, errMsg=str(e))


@dashboard_router.post("/trend/{type}")
async def get_confirmed_cancelled_comparison_trip_trend(request: Request, filter_criteria: FilterBidsRequest, type: str):

    try:

        get_confirmed_cancelled_trip_trend_comparision, error = await bid.confirmed_cancelled_bid_trend_stats(filter=filter_criteria, type= type)

        if error:
            return ErrorResponse(data=[], dev_msg=error, client_msg="Something went wrong while fetching bid details")

        return SuccessResponse(data=get_confirmed_cancelled_trip_trend_comparision, dev_msg="All bid trend stats fetched", client_msg="Requested trend stats fetched successfully")

    except Exception as e:
        return ServerError(err=e, errMsg=str(e))


@dashboard_router.post("/transporters")
async def get_transporter_analysis(request: Request, filter_criteria: FilterBidsRequest):

    try:

        bid_details, error = await bid.transporter_analysis(filter=filter_criteria)

        if error:
            return ErrorResponse(data=[], dev_msg=error, client_msg="Something went wrong while fetching transporter details")

        return SuccessResponse(data=bid_details, dev_msg="All bid stats fetched", client_msg="Requested stats fetched successfully")

    except Exception as e:
        return ServerError(err=e, errMsg=str(e))
