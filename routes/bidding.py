
from fastapi import APIRouter, BackgroundTasks
import os
import json
from typing import List
from datetime import datetime, timedelta

from utils.response import ErrorResponse, SuccessResponse, SuccessNoContentResponse, ServerError
from data.bidding import valid_load_status, valid_rebid_status, valid_cancel_status, valid_assignment_status, valid_bid_status
from utils.bids.bidding import Bid
from utils.bids.transporters import Transporter
from utils.bids.shipper import Shipper
from utils.redis import Redis
from schemas.bidding import HistoricalRatesReq, TransporterBidReq, TransporterAssignReq, FilterBidsRequest, TransporterBidMatchRequest,TransporterUnassignRequest
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

        (bids, error) = await bid.get_status_wise(status)

        if error:
            return ErrorResponse(data=[], dev_msg=error, client_msg=os.getenv("GENERIC_ERROR"))

        if len(bids) == 0:
            return SuccessResponse(data=[], dev_msg="Correct status, data fetched", client_msg=f"There are no {status} bids to show right now!")

        return SuccessResponse(data=bids, dev_msg="Correct status, data fetched", client_msg=f"Fetched all {status} bids successfully!")

    except Exception as err:
        return ServerError(err=err, errMsg=str(err))


@bidding_router.post("/filter/{status}")
async def get_bids_according_to_filter_criteria(status: str, filter_criteria: FilterBidsRequest):

    try:
        if status not in valid_load_status:
            return ErrorResponse(data=[], dev_msg=os.getenv("STATUS_ERROR"), client_msg=os.getenv("GENERIC_ERROR"))

        (bids, error) = await bid.get_filter_wise(status=status, filter_criteria=filter_criteria)

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

        (update_successful, error) = await bid.update_status(bid_id=bid_id, status="not_started")

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

        (rate, error) = await transporter.is_valid_bid_rate(bid_id=bid_id, show_rate_to_transporter=bid_details.show_current_lowest_rate_transporter,
                                                            rate=bid_req.rate, transporter_id=bid_req.transporter_id, decrement=bid_details.bid_price_decrement, status=bid_details.load_status)

        log("RATE OBJECT", rate)

        if error:
            return ErrorResponse(data={}, dev_msg=error, client_msg=os.getenv("BID_RATE_ERROR"))

        if not rate["valid"]:
            return ErrorResponse(data=[], client_msg=f"You entered an incorrect bid rate! Decrement is {bid_details.bid_price_decrement}", dev_msg="Incorrect bid price entered")

        log("VALID RATE", bid_id)

        (new_record, error) = await bid.new(
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

        socket_successful = await manager.broadcast(bid_id=bid_id, message=json.dumps(sorted_bid_details))

        log("SOCKET EVENT SENT", socket_successful)

        return SuccessResponse(data=sorted_bid_details, dev_msg="Bid submitted successfully", client_msg=f"Bid for Bid-{bid_id} submitted!")

    except Exception as err:
        return ServerError(err=err, errMsg=str(err))


@bidding_router.get("/increment/{bid_id}")
async def increment_time_of_bid(bid_id: str):

    current_time = datetime.now()
    try:
        (valid_bid_id, error) = await bid.is_valid(bid_id=bid_id)

        if not valid_bid_id:
            return ErrorResponse(data=[], client_msg=os.getenv("INVALID_BID_ERROR"), dev_msg=error)
        (error, bid_details) = await bid.details(bid_id=bid_id)
        if not error:
            return ErrorResponse(data=[], client_msg="Something went wrong while trying to increment Bid Time", dev_msg=error)
        (error, setting_details) = await bid.setting_details(shipper_id=bid_details.bl_shipper_id)
        if not error:
            return ErrorResponse(data=[], client_msg="Something went wrong while trying to increment Bid Time", dev_msg=error)

        current_time_object = datetime.strptime(
            current_time, '%Y-%m-%d %H:%M:%S.%f')

        if (bid_details.bid_end_time-current_time_object).total_seconds()/60 > setting_details.bid_increment_time:
            return SuccessNoContentResponse(dev_msg="No Increment Needed", client_msg="No Increment Needed.")

        (bid_end_time_update, error) = await bid.update_bid_end_time(bid_id=bid_id, bid_end_time=(bid_details.bid_end_time+timedelta(minutes=setting_details.bid_increment_duration)))

        if not bid_end_time_update:
            return ErrorResponse(data=bid_id, client_msg="Something Went Wrong While Incrementing Bid Time", dev_msg=error)

        return SuccessResponse(data=bid_id, client_msg="Bid End Time Updated Successfully!", dev_msg="Bid end time was updated successfully!")

    except Exception as err:
        return ServerError(err=err, errMsg=str(err))


@bidding_router.get("/lowest/{bid_id}")
async def get_lowest_price_of_current_bid(bid_id: str):

    try:

        (lowest_price, error) = await redis.get_first(bid_id)

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

        return await transporter.historical_rates(transporter_id=req.transporter_id, bid_id=bid_id)

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


@bidding_router.delete("/cancel/{bid_id}")
async def cancel_bid(bid_id: str):

    try:
        (valid_bid_id, error) = await bid.is_valid(bid_id)

        if not valid_bid_id:
            return ErrorResponse(data=[], client_msg=os.getenv("INVALID_BID_ERROR"), dev_msg=error)
        log("BID ID IS VALID")
        (details_fetch_successful, bid_details) = await bid.details(bid_id=bid_id)

        if not details_fetch_successful:
            return ErrorResponse(data=[], client_msg="Something went wrong while trying to cancel", dev_msg=bid_details)

        log("BID DETAILS FETCHED")

        if bid_details.load_status not in valid_cancel_status:

            return ErrorResponse(data=[], client_msg="This bid is not valid and cannot be cancelled!", dev_msg=f"Bid-{bid_id} is {bid_details.load_status}, cannot be cancelled!")

        log("BID STATUS IS VALID")
        (update_successful, error) = await bid.update_status(bid_id=bid_id, status="cancelled")

        if not update_successful:
            return ErrorResponse(data=[], client_msg=os.getenv("BID_CANCEL_ERROR"), dev_msg=error)
        log("BID STATUS IS NOW CANCELLED")
        return SuccessNoContentResponse(dev_msg="Bid cancelled successfully", client_msg="Your Bid is Successfully Cancelled")

    except Exception as err:
        return ServerError(err=err, errMsg=str(err))


@bidding_router.post("/assign/{bid_id}")
async def assign_to_transporter(bid_id: str, transporters: List[TransporterAssignReq]):

    total_fleets = 0
    load_status = ""
    load_split = False

    try:

        (valid_bid_id, error) = await bid.is_valid(bid_id=bid_id)

        if not valid_bid_id:
            return ErrorResponse(data=[], client_msg=os.getenv("INVALID_BID_ERROR"), dev_msg=error)

        if len(transporters) <= 0:
            return ErrorResponse(data=[], client_msg="Please select at least one transporter to assign", dev_msg="Transporter assignment array empty/invalid")

        for transporter in transporters:
            total_fleets += getattr(transporter, "no_of_fleets_assigned")

        (error, bid_details) = await bid.details(bid_id=bid_id)

        if not bid_details:
            return ErrorResponse(data=[], client_msg="Something went wrong while trying to Assign Transporter", dev_msg=error)

        if bid_details.load_status not in valid_assignment_status:
            return ErrorResponse(data=[], client_msg=f"Transporter cannot be assigned to this bid as it is {bid_details.load_status}", dev_msg=f"transporter cannot be assigned to bid with status- {bid_details.load_status}")
        
        

        if total_fleets < bid_details.no_of_fleets:
            load_status = "partially_confirmed"
        elif total_fleets == bid_details.no_of_fleets:
            load_status = "confirmed"
        else:
            return ErrorResponse(data=[], client_msg="Assigned number of fleets greater than requested number of fleets", dev_msg="Mismatch of assigned and requested fleets")

        if len(transporters) > 1:
            load_split = True

        (assigned_loads, error) = await bid.assign(bid_id=bid_id, transporters=transporters, split=load_split, status=load_status)

        if error:
            return ErrorResponse(data=[], client_msg="Something Went Wrong While Assigning Transporters", dev_msg=error)

        return SuccessResponse(data=assigned_loads, dev_msg="Load Assigned Successfully", client_msg=f"Load-{bid_id} assignment was successful!")

    except Exception as err:
        return ServerError(err=err, errMsg=str(err))


@bidding_router.get("/details/{bid_id}")
async def bid_details_for_assignment_to_transporter(bid_id: str):

    try:
        (valid_bid_id, error) = await bid.is_valid(bid_id=bid_id)

        if not valid_bid_id:
            return ErrorResponse(data=[], client_msg=os.getenv("INVALID_BID_ERROR"), dev_msg=error)

        (bid_details_found, details) = await bid.details_for_assignment(bid_id=bid_id)

        if not bid_details_found:
            return ErrorResponse(data=[], client_msg="Bid details were not found", dev_msg="Bid details for assignment could not be found")

        return SuccessResponse(data=details, client_msg="Bid details found for assignment", dev_msg="Bid details found for assignment")

    except Exception as err:
        return ServerError(err=err, errMsg=str(err))


@bidding_router.get("/live/{bid_id}")
async def live_bid_details(bid_id: str):

    res_array = []

    try:
        (valid_bid_id, error) = await bid.is_valid(bid_id=bid_id)

        if not valid_bid_id:
            return ErrorResponse(data=[], client_msg=os.getenv("INVALID_BID_ERROR"), dev_msg=error)

        (bid_details, error) = await redis.bid_details(sorted_set=bid_id)

        if error:
            return ErrorResponse(data=[], client_msg=os.getenv("GENERIC_ERROR"), dev_msg=error)

        if not bid_details:

            log("FETCHING LIVE BID FROM DATABASE")

            (bid_details, error) = await bid.live_details(bid_id)

            if error:
                return ErrorResponse(data=[], client_msg=os.getenv("GENERIC_ERROR"), dev_msg=error)

            for bid_detail in bid_details:

                transporter_rate_details = bid_detail._mapping
                log("TRANSPORTER DETAILS : ", transporter_rate_details)

                res_array.append(transporter_rate_details)

                await redis.update(sorted_set=bid_id, transporter_name=transporter_rate_details["transporter_name"], transporter_id=str(transporter_rate_details["transporter_id"]),
                                   comment=transporter_rate_details["comment"], rate=transporter_rate_details["rate"], attempts=transporter_rate_details["attempts"])

            return SuccessResponse(data=res_array, client_msg="Live Bid Details fetched Successfully", dev_msg="Live Bid Details fetched Successfully")

        return SuccessResponse(data=bid_details, client_msg="Live Bid Details fetched Successfully", dev_msg="Live Bid Details fetched Successfully")

    except Exception as err:
        return ServerError(err=err, errMsg=str(err))


@bidding_router.post("/match/{bid_id}")
async def bid_match_for_transporters(bid_id:str, transporters: List[TransporterBidMatchRequest]):
    
    try:
        (valid_bid_id, error) = await bid.is_valid(bid_id=bid_id)

        if not valid_bid_id:
            return ErrorResponse(data=[], client_msg=os.getenv("INVALID_BID_ERROR"), dev_msg=error)
        
        (assignment_details, error) = await transporter.bid_match(bid_id=bid_id, transporters=transporters)
        
        if error:
            return ErrorResponse(data=[], client_msg=os.getenv("GENERIC_ERROR"), dev_msg=error)
        
        return SuccessResponse(data=assignment_details, client_msg="Bid Match Successful", dev_msg="Bid Match Successful")
        
    except Exception as err:
        return ServerError(err=err, errMsg=str(err))


@bidding_router.delete("/unassign/{bid_id}")
async def unassign_transporter_for_bid(bid_id : str,transporter_id : TransporterUnassignRequest):

    try:
        (valid_bid_id, error) = await bid.is_valid(bid_id=bid_id)

        if not valid_bid_id:
            return ErrorResponse(data=[], client_msg=os.getenv("INVALID_BID_ERROR"), dev_msg=error)
    
        (unassigned_transporter,error) = await transporter.unassign(bid_id=bid_id,transporter_id = transporter_id)

        if error:
            return ErrorResponse(data=[], client_msg=os.getenv("INVALID_BID_ERROR"), dev_msg=error)
        
        return SuccessResponse(data=unassigned_transporter,client_msg=f"Successfully unassigned transporter for Bid-{bid_id}",dev_msg="Unassigned requested transporter from bid")
    

    except Exception as err:
        return ServerError(err=err, errMsg=str(err))