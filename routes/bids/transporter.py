from fastapi import APIRouter, Request
import os
import json

from config.socket import manager
from schemas.bidding import TransporterBidReq, TransporterLostBidsReq
from data.bidding import valid_bid_status
from utils.bids.bidding import Bid
from utils.bids.transporters import Transporter
from utils.bids.shipper import Shipper
from utils.redis import Redis
from utils.response import ErrorResponse, SuccessResponse, ServerError
from utils.utilities import log


transporter_bidding_router: APIRouter = APIRouter(
    prefix="/transporter/bid", tags=["Transporter routes for bidding"])

transporter = Transporter()
bid = Bid()
shipper = Shipper()
redis = Redis()

shp, trns, acu = os.getenv("SHIPPER"), os.getenv(
    "TRANSPORTER"), os.getenv("ACULEAD")


@transporter_bidding_router.get("/status/{status}")
async def fetch_bids_for_transporter_by_status(request: Request, status: str | None = None):

    transporter_id = request.state.current_user["transporter_id"]

    try:

        if not transporter_id:
            return ErrorResponse(data=[], dev_msg=os.getenv("TRANSPORTER_ID_NOT_FOUND_ERROR"), client_msg=os.getenv("GENERIC_ERROR"))

        (bids, error) = await transporter.bids_by_status(transporter_id=transporter_id, status=status)

        if error:
            return ErrorResponse(data=[], dev_msg=error, client_msg=os.getenv("GENERIC_ERROR"))

        return SuccessResponse(data=bids, dev_msg="Fetched bids successfully", client_msg=f"Fetched all {status} bids successfully!")

    except Exception as err:
        return ServerError(err=err, errMsg=str(err))


@transporter_bidding_router.get("/selected")
async def fetch_selected_bids(request: Request):

    transporter_id = request.state.current_user["transporter_id"]

    try:

        if not transporter_id:
            return ErrorResponse(data=[], dev_msg=os.getenv("TRANSPORTER_ID_NOT_FOUND_ERROR"), client_msg=os.getenv("GENERIC_ERROR"))

        (bids, error) = await transporter.selected(transporter_id=transporter_id)

        if error:
            return ErrorResponse(data=[], dev_msg=error, client_msg=os.getenv("GENERIC_ERROR"))

        if not bids:
            return SuccessResponse(data=[], client_msg="You have not been selected in any bids yet", dev_msg="Not selected in any bids")

        return SuccessResponse(data=bids, dev_msg="Fetched bids successfully", client_msg="Fetched all selected bids successfully!")

    except Exception as err:
        return ServerError(err=err, errMsg=str(err))


@transporter_bidding_router.post("/rate/{bid_id}", response_model=None)
async def provide_new_rate_for_bid(request: Request, bid_id: str, bid_req: TransporterBidReq):

    transporter_id = request.state.current_user["transporter_id"]

    try:

        if not transporter_id:
            return ErrorResponse(data=[], dev_msg=os.getenv("TRANSPORTER_ID_NOT_FOUND_ERROR"), client_msg=os.getenv("GENERIC_ERROR"))

        if bid_req.rate <= 0:
            return ErrorResponse(data=bid_req.rate, client_msg="Invalid Rate Entered, Rate Entered Must be Greater Than Zero", dev_msg="Rate must be greater than zero")

        log("BID REQUEST DETAILS", bid_req)

        (valid_bid_id, error) = await bid.is_valid(bid_id)

        log("BID IS VALID", bid_id)

        if not valid_bid_id:
            return ErrorResponse(data=bid_id, client_msg=os.getenv("NOT_FOUND_ERROR"), dev_msg=error)

        (error, bid_details) = await bid.details(bid_id)

        if not bid_details:
            return ErrorResponse(data=[], client_msg=os.getenv("BID_RATE_ERROR"), dev_msg=error)
        log("BID DETAILS LOAD STATUS", bid_details.load_status)

        if bid_details.load_status not in valid_bid_status:
            return ErrorResponse(data=[], client_msg=f"This Load is not Accepting Bids yet, start time is {bid_details.bid_time}", dev_msg="Tried bidding, but bid is not live yet")

        log("BID DETAILS FOUND", bid_id)

        if bid_details.bid_mode == "private_pool":
            log("REQUEST TRANSPORTER ID:", transporter_id)
            log("BID SHIPPER ID", bid_details.bl_shipper_id)
            (allowed_transporter_to_bid, error) = await transporter.allowed_to_bid(shipper_id=bid_details.bl_shipper_id, transporter_id=transporter_id)

            if not allowed_transporter_to_bid:
                return ErrorResponse(data=[], client_msg="Transporter Not Allowed to participate in the private Bid", dev_msg="bid is private, transporter not allowed")

        log("TRANSPORTER ALLOWED TO BID", bid_id)

        (transporter_attempts, error) = await transporter.attempts(
            bid_id=bid_id, transporter_id=transporter_id)

        if error:
            return ErrorResponse(data=[], client_msg=os.getenv("BID_RATE_ERROR"), dev_msg=error)

        if transporter_attempts >= bid_details.no_of_tries:
            return ErrorResponse(data=[], client_msg="You have exceeded the number of tries for this bid!", dev_msg=f"Number of tries for Bid-{bid_id} exceeded!")

        log("BID TRIES OK", bid_id)

        (rate, error) = await transporter.is_valid_bid_rate(bid_id=bid_id, show_rate_to_transporter=bid_details.show_current_lowest_rate_transporter,
                                                            rate=bid_req.rate, transporter_id=transporter_id, decrement=bid_details.bid_price_decrement, status=bid_details.load_status)

        log("RATE OBJECT", rate)

        if error:
            return ErrorResponse(data={}, dev_msg=error, client_msg=os.getenv("BID_RATE_ERROR"))

        if not rate["valid"]:
            return ErrorResponse(data=[], client_msg=f"You entered an incorrect bid rate! Decrement is {bid_details.bid_price_decrement}", dev_msg="Incorrect bid price entered")

        log("VALID RATE", bid_id)

        (new_record, error) = await bid.new(
            bid_id, transporter_id, bid_req.rate, bid_req.comment, user_id=user_id)

        log("NEW BID INSERTED", bid_id)

        if error:
            return ErrorResponse(data=[], dev_msg=error, client_msg=os.getenv("BID_RATE_ERROR"))

        (transporter_name, error) = await transporter.name(
            transporter_id=transporter_id)

        log("TRANSPORTER NAME", transporter_name)

        if error:
            return ErrorResponse(data=[], client_msg=os.getenv("BID_RATE_ERROR"), dev_msg=error)

        (sorted_bid_details, error) = await redis.update(sorted_set=bid_id,
                                                         transporter_id=(transporter_id), comment=bid_req.comment, transporter_name=transporter_name, rate=bid_req.rate, attempts=transporter_attempts + 1)

        log("BID DETAILS", sorted_bid_details)

        socket_successful = await manager.broadcast(bid_id=bid_id, message=json.dumps(sorted_bid_details))

        log("SOCKET EVENT SENT", socket_successful)

        return SuccessResponse(data=sorted_bid_details, dev_msg="Bid submitted successfully", client_msg=f"Bid for Bid-{bid_id} submitted!")

    except Exception as err:
        return ServerError(err=err, errMsg=str(err))


@transporter_bidding_router.get("/lost")
async def fetch_lost_bids_for_transporter_based_on_participation(request: Request, t: TransporterLostBidsReq):

    transporter_id = request.state.current_user["transporter_id"]


    try:
        if not transporter_id:
            return ErrorResponse(data=[], dev_msg=os.getenv("TRANSPORTER_ID_NOT_FOUND_ERROR"), client_msg=os.getenv("GENERIC_ERROR"))

        (bids, error) = ([], "")

        if t.particpated:
            (bids, error) = await transporter.participated_and_lost_bids(
                transporter_id=transporter_id)
        else:
            (bids, error) = await transporter.not_participated_and_lost_bids(
                transporter_id=transporter_id)

        if error:
            return ErrorResponse(data=[], dev_msg=error, client_msg="Something went wrong file fetching bids, please try again in some time")
        
        if not bids:
            return SuccessResponse(data=[],dev_msg="Not lost any bid",client_msg="No lost bids to show right now!")

        return SuccessResponse(data=bids, dev_msg="Fetched lost bids successfully", client_msg="Fetched all lost bids successfully!")

    except Exception as err:
        return ServerError(err=err, errMsg=str(err))
