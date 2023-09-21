from fastapi import APIRouter, BackgroundTasks, WebSocket
import os
import asyncio
import json
from typing import List
from datetime import datetime, timedelta

from utils.response import ErrorResponse, SuccessResponse, SuccessNoContentResponse, ServerError
from data.bidding import valid_load_status, valid_rebid_status, valid_cancel_status, valid_assignment_status
from utils.bids.bidding import Bid
from utils.bids.transporters import Transporter
from utils.bids.shipper import Shipper
from utils.redis import Redis
from schemas.bidding import HistoricalRatesReq, TransporterBidReq, TransporterAssignReq
from utils.utilities import log
from config.socket import manager


bidding_router: APIRouter = APIRouter(prefix="/bid")

transporter = Transporter()
bid = Bid()
shipper = Shipper()
redis = Redis()


@bidding_router.get("/status/{status}")
async def get_bids_according_to_status(status: str):

    try:
        if status not in valid_load_status:
            return ErrorResponse(data=[], dev_msg=os.getenv("STATUS_ERROR"), client_msg=os.getenv("GENERIC_ERROR"))

        (bids, error) =await bid.get_status_wise(status)

        if error:
            return ErrorResponse(data=[], dev_msg=error, client_msg=os.getenv("GENERIC_ERROR"))

        return SuccessResponse(data=bids, dev_msg="Correct status, data fetched", client_msg=f"Fetched all {status} bids successfully!")

    except Exception as err:
        return ServerError(err=err, errMsg=str(err))


@bidding_router.patch("/publish/{bid_id}")
async def publish_new_bid(bid_id: str, bg_tasks: BackgroundTasks):

    try:

        (valid_bid_id, error) = await bid.is_valid(bid_id)

        if not valid_bid_id:
            return ErrorResponse(data=[], client_msg=os.getenv("NOT_FOUND_ERROR"), dev_msg=error)

        (update_successful, error) = await bid.update_status(bid_id=bid_id, status="pending")

        if not update_successful:
            return ErrorResponse(data=bid_id, client_msg=os.getenv("BID_PUBLISH_ERROR"), dev_msg=error)
        # This might have to be done in a separate thread
        # bg_tasks.add_task(transporter.notify(bid_id))

        return SuccessResponse(data=bid_id, client_msg=f"Bid-{bid_id} is now published!", dev_msg="Bid status was updated successfully!")

    except Exception as err:
        return ServerError(err=err, errMsg=str(err))


@bidding_router.post("/rate/{bid_id}", response_model=None)
async def provide_new_rate_for_bid(bid_id: str, bid_req: TransporterBidReq):

    try:

        if bid_req.rate <= 0:
            return ErrorResponse(data=bid_req.rate, client_msg="Invalid Rate Entered, Rate Entered Must be Greater Than Zero", dev_msg="Rate must be greater than zero")

        (valid_bid_id, error) = await bid.is_valid(bid_id)

        log("BID IS VALID", bid_id)

        if not valid_bid_id:
            return ErrorResponse(data=bid_id, client_msg=os.getenv("NOT_FOUND_ERROR"), dev_msg=error)

        (error, bid_details) = await bid.details(bid_id)

        if not bid_details:
            return ErrorResponse(data=[], client_msg=os.getenv("BID_RATE_ERROR"), dev_msg=error)

        if bid_details.load_status != "live":
            return ErrorResponse(data=[], client_msg=f"This Load is not Accepting Bids yet, start time is {bid_details.bid_time}", dev_msg="Tried bidding, but bid is not live yet")

        log("BID DETAILS FOUND", bid_id)

        if bid_details.bid_mode == "private_pool":
            log("REQUEST TRANSPORTER ID:", bid_req.transporter_id)
            log("BID SHIPPER ID", bid_details.bl_shipper_id)
            (allowed_transporter_to_bid, error) = await transporter.allowed_to_bid(shipper_id=bid_details.bl_shipper_id, transporter_id=bid_req.transporter_id)

            if not allowed_transporter_to_bid:
                return ErrorResponse(data=[], client_msg="Transporter Not Allowed to participate in the private Bid", dev_msg="bid is private, transporter not allowed")

        log("TRANSPORTER ALLOWED TO BID", bid_id)

        (transporter_attempts, error) = await transporter.attempts(
            bid_id=bid_id, transporter_id=bid_req.transporter_id)

        if error:
            return ErrorResponse(data=[], client_msg=os.getenv("BID_RATE_ERROR"), dev_msg=error)

        if transporter_attempts >= bid_details.no_of_tries:
            return ErrorResponse(data=[], client_msg="You have exceeded the number of tries for this bid!", dev_msg=f"Number of tries for Bid-{bid_id} exceeded!")

        log("BID TRIES OK", bid_id)

        (rate, error) = await transporter.is_valid_bid_rate(bid_id, bid_details.show_current_lowest_rate_transporter,
                                                            bid_req.rate, bid_req.transporter_id, bid_details.bid_price_decrement)

        log("RATE OBJECT", rate)

        if error:
            return ErrorResponse(data={}, dev_msg=error, client_msg=os.getenv("BID_RATE_ERROR"))

        if not rate["valid"]:
            return ErrorResponse(data=[], client_msg=f"You entered an incorrect bid rate! Decrement is {bid_details.bid_price_decrement}", dev_msg="Incorrect bid price entered")

        log("VALID RATE", bid_id)

        (new_record, error) = await bid.new_bid(
            bid_id, bid_req.transporter_id, bid_req.rate, bid_req.comment)

        log("NEW BID INSERTED", bid_id)

        if error:
            return ErrorResponse(data=[], dev_msg=error, client_msg=os.getenv("BID_RATE_ERROR"))

        (transporter_name, error) = await transporter.name(
            transporter_id=bid_req.transporter_id)

        log("TRANSPORTER NAME", transporter_name)

        if error:
            return ErrorResponse(data=[], client_msg=os.getenv("BID_RATE_ERROR"), dev_msg=error)

        (sorted_bid_details, error) = await redis.update(sorted_set=bid_id,
                                                         transporter_id=str(bid_req.transporter_id), comment=bid_req.comment, transporter_name=transporter_name, rate=bid_req.rate, attempts=transporter_attempts + 1)

        log("BID DETAILS", sorted_bid_details)

        socket_successful = await manager.broadcast(json.dumps(sorted_bid_details))
        log("SOCKET EVENT SENT", socket_successful)

        return SuccessResponse(data=sorted_bid_details, dev_msg="Bid submitted successfully", client_msg=f"Bid for Bid-{bid_id} submitted!")

    except Exception as err:
        return ServerError(err=err, errMsg=str(err))


@bidding_router.get("/lowest/{bid_id}")
async def get_lowest_price_of_current_bid(bid_id: str):

    try:

        (lowest_price, error) = redis.get_first(bid_id)

        if error:

            (lowest_price, error) = await bid.lowest_price(bid_id)

            if error:
                return ErrorResponse(data=[], client_msg="Something went wrong while fetching the lowest price for this bid", dev_msg=error)

        return SuccessResponse(data=lowest_price, dev_msg="Lowest price found for current bid", client_msg="Fetched lowest price for Bid-{bid_id}!")

    except Exception as err:
        return ServerError(err=err, errMsg=str(err))


@bidding_router.post("/history/{bid_id}")
async def fetch_all_rates_given_by_transporter(bid_id: str, req: HistoricalRatesReq):

    try:
        (valid_bid_id, error) = await bid.is_valid(bid_id)

        if not valid_bid_id:
            return ErrorResponse(data=bid_id, client_msg=os.getenv("INVALID_BID_ERROR"), dev_msg=error)

        return transporter.historical_rates(transporter_id=req.transporter_id, bid_id=bid_id)

    except Exception as err:
        return ServerError(err=err, errMsg=str(err))


@bidding_router.put("/rebid/{bid_id}")
async def rebid(bid_id: str):

    try:
        (valid_bid_id, error) = await bid.is_valid(bid_id)

        if not valid_bid_id:
            return ErrorResponse(data=[], client_msg=os.getenv("INVALID_BID_ERROR"), dev_msg=error)

        (bid_details, error) = await bid.details(bid_id=bid_id)

        if error:
            return ErrorResponse(data=[], client_msg="Something went wrong while trying to rebid", dev_msg=error)

        if bid_details.status not in valid_rebid_status:
            return ErrorResponse(data=[], client_msg="This bid is not valid for rebid!", dev_msg=f"Bid-{bid_id} is {bid_details.status}, cannot be rebid!")

        # call create load api

    except Exception as err:
        return ServerError(err=err, errMsg=str(err))


@bidding_router.put("/cancel/{bid_id}")
async def cancel_bid(bid_id: str):

    try:
        (valid_bid_id, error) = await bid.is_valid(bid_id)

        if not valid_bid_id:
            return ErrorResponse(data=[], client_msg=os.getenv("INVALID_BID_ERROR"), dev_msg=error)

        (bid_details, error) = await bid.details(bid_id=bid_id)

        if error:
            return ErrorResponse(data=[], client_msg="Something went wrong while trying to cancel", dev_msg=error)

        if bid_details.status not in valid_cancel_status:

            return ErrorResponse(data=[], client_msg="This bid is not valid and cannot be cancelled!", dev_msg=f"Bid-{bid_id} is {bid_details.status}, cannot be cancelled!")
        (update_successful, error) = await bid.update_status(bid_id=bid_id, status="cancelled")

        if not update_successful:
            return ErrorResponse(data=bid_id, client_msg=os.getenv("BID_CANCEL_ERROR"), dev_msg=error)

        return SuccessNoContentResponse(dev_msg="Bid cancelled successfully", client_msg="Your Bid is Successfully Cancelled")

    except Exception as err:
        return ServerError(err=err, errMsg=str(err))


@bidding_router.post("/assign/{bid_id}")
async def assign(bid_id: str, transporters: List[TransporterAssignReq]):

    try:
        (valid_bid_id, error) = await bid.is_valid(bid)

        if not valid_bid_id:
            return ErrorResponse(data=[], client_msg=os.getenv("INVALID_BID_ERROR"), dev_msg=error)

        (bid_details, error) = await bid.details(bid_id=bid_id)

        if error:
            return ErrorResponse(data=[], client_msg="Something went wrong while trying to Assign Transporter", dev_msg=error)

        if bid_details.load_status not in valid_assignment_status:
            return ErrorResponse(data=[], client_msg="Transporter cannot be assigned to this bid", dev_msg=f"transporter cannot be assigned to bid with status- {bid_details.load_status}")

        if len(transporters) >= 0:
            (update_successful_bid_status, error) = await bid.update_bid_status(bid_id=bid_id)

            if not update_successful_bid_status:
                return ErrorResponse(data=[], client_msg="Something Went Wrong while Assigning Transporters", dev_msg=error)

        (assigned_loads, error) = await bid.assign(bid_id=bid_id, transporters=transporters)

        if error:
            return ErrorResponse(data=[], client_msg="Something Went Wrong While Assigning Transporters", dev_msg=error)

        return SuccessResponse(data=assigned_loads, dev_msg="Load Assigned Successfully", client_msg=f"Load-{bid_id} assignment was successful!")

    except Exception as err:
        return ServerError(err=err, errMsg=str(err))


@bidding_router.get("/increment/{bid_id}/{current_time}")
async def increment_time(bid_id: str, current_time: str):

    try:
        (valid_bid_id, error) = await bid.is_valid(bid_id=bid_id)

        if not valid_bid_id:
            return ErrorResponse(data=[], client_msg=os.getenv("INVALID_BID_ERROR"), dev_msg=error)
        (error, bid_details) = await bid.details(bid_id=bid_id)
        if not error:
            return ErrorResponse(data=[], client_msg="Something went wrong while trying to increment Bid Time", dev_msg=error)
        (error, bid_setting_details) = await bid.bid_setting_details(shipper_id=bid_details.bl_shipper_id)
        if not error:
            return ErrorResponse(data=[], client_msg="Something went wrong while trying to increment Bid Time", dev_msg=error)

        current_time_object = datetime.strptime(
            current_time, '%Y-%m-%d %H:%M:%S.%f')

        if (bid_details.bid_end_time-current_time_object).total_seconds()/60 > bid_setting_details.bid_increment_time:
            return SuccessNoContentResponse(dev_msg="No Increment Needed", client_msg="No Increment Needed.")

        (bid_end_time_update, error) = await bid.update_bid_end_time(bid_id=bid_id, bid_end_time=(bid_details.bid_end_time+timedelta(minutes=bid_setting_details.bid_increment_duration)))

        if not bid_end_time_update:
            return ErrorResponse(data=bid_id, client_msg="Something Went Wrong While Incrementing Bid Time", dev_msg=error)

        return SuccessResponse(data=bid_id, client_msg="Bid End Time Updated Successfully!", dev_msg="Bid end time was updated successfully!")

    except Exception as err:
        return ServerError(err=err, errMsg=str(err))


@bidding_router.get("/{status}")
async def get_bids_according_to_filter_criteria(status: str, shipper_id: str, regioncluster_id: str, branch_id: str, from_date: datetime, to_date: datetime):

    try:
        if status not in valid_load_status:
            return ErrorResponse(data=[], dev_msg=os.getenv("STATUS_ERROR"), client_msg=os.getenv("GENERIC_ERROR"))

        (bids, error) = await bid.get_filter_wise(status=status, shipper_id=shipper_id, regioncluster_id=regioncluster_id, branch_id=branch_id, from_date=from_date, to_date=to_date)

        if error:
            return ErrorResponse(data=[], dev_msg=error, client_msg=os.getenv("GENERIC_ERROR"))

        return SuccessResponse(data=bids, dev_msg="Correct status, data fetched", client_msg=f"Fetched all {status} bids successfully!")

    except Exception as err:
        return ServerError(err=err, errMsg=str(err))


@bidding_router.get("/exists/redis/{sorted_set}")
async def if_exists_endpoint(sorted_set: str):
    try:
        exist_flag = await redis.if_exists(sorted_set=sorted_set)
        if exist_flag:
            return SuccessResponse(data=exist_flag, client_msg="Data Present in Redis", dev_msg="data present in redis")
        return ErrorResponse(data=[], dev_msg="No data regarding the given key found in redis")
    except Exception as err:
        return ServerError(err=err, errMsg=str(err))
