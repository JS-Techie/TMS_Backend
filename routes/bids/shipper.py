
import os
from datetime import datetime, timedelta
from typing import List

from fastapi import APIRouter, BackgroundTasks, Request
from fastapi_mail import FastMail

from config.mail import email_conf
from data.bidding import (valid_assignment_status, valid_cancel_status,
                          valid_load_status)
from schemas.bidding import (CancelBidReq, FilterBidsRequest,
                             HistoricalRatesReq, TransporterAssignReq,
                             TransporterBidMatchRequest,
                             TransporterUnassignRequest)
from services.mail import Email
from utils.bids.bidding import Bid
from utils.bids.shipper import Shipper
from utils.bids.transporters import Transporter
from utils.redis import Redis
from utils.response import (ErrorResponse, ServerError,
                            SuccessNoContentResponse, SuccessResponse)
from utils.utilities import log

shipper_bidding_router: APIRouter = APIRouter(
    prefix="/shipper/bid", tags=["Shipper routes for bidding"])

transporter = Transporter()
bid = Bid()
shipper = Shipper()
redis = Redis()
mail = Email()
fm = FastMail(email_conf)

acu, shp = os.getenv("ACULEAD"), os.getenv("SHIPPER")


@shipper_bidding_router.get("/status/{status}")
async def get_bids_according_to_status(request: Request, status: str):

    shipper_id = None
    if request.state.current_user["user_type"] == shp:
        shipper_id = request.state.current_user["shipper_id"]

    try:

        if status not in valid_load_status:
            return ErrorResponse(data=[], dev_msg=os.getenv("STATUS_ERROR"), client_msg=os.getenv("GENERIC_ERROR"))

        (bids, error) = await bid.get_status_wise(status=status, shipper_id=shipper_id)

        if error:
            return ErrorResponse(data=[], dev_msg=error, client_msg=os.getenv("GENERIC_ERROR"))

        if len(bids) == 0:
            return SuccessResponse(data=[], dev_msg="No bids to show", client_msg=f"There are no {status} bids to show right now!")

        return SuccessResponse(data=bids, dev_msg="Correct status, data fetched", client_msg=f"Fetched all {status} bids successfully!")

    except Exception as err:
        return ServerError(err=err, errMsg=str(err))


@shipper_bidding_router.post("/filter/{status}")
async def get_bids_according_to_filter_criteria(request: Request, status: str, filter_criteria: FilterBidsRequest):

    try:
        if status not in valid_load_status:
            return ErrorResponse(data=[], dev_msg=os.getenv("STATUS_ERROR"), client_msg=os.getenv("GENERIC_ERROR"))

        (bids, error) = await bid.get_filter_wise(status=status, filter_criteria=filter_criteria)

        if error:
            return ErrorResponse(data=[], dev_msg=error, client_msg=os.getenv("GENERIC_ERROR"))

        return SuccessResponse(data=bids, dev_msg="Correct status, data fetched", client_msg=f"Fetched all {status} bids successfully!")

    except Exception as err:
        return ServerError(err=err, errMsg=str(err))


@shipper_bidding_router.patch("/publish/{bid_id}")
async def publish_new_bid(request: Request, bid_id: str, bg_tasks: BackgroundTasks):

    user_id = request.state.current_user["id"]

    try:

        (valid_bid_id, error) = await bid.is_valid(bid_id)

        if not valid_bid_id:
            return ErrorResponse(data=[], client_msg=os.getenv("NOT_FOUND_ERROR"), dev_msg=error)

        (update_successful, error) = await bid.update_status(bid_id=bid_id, status="not_started", user_id=user_id)

        if not update_successful:
            return ErrorResponse(data=bid_id, client_msg=os.getenv("BID_PUBLISH_ERROR"), dev_msg=error)
        
        (success, error)= await transporter.notify(bid_id=bid_id, authtoken=request.headers.get("authorization", ""))
        if not success:
            return ErrorResponse(data=[], dev_msg=error)
        
        return SuccessResponse(data=bid_id, client_msg=f"Bid-{bid_id} is now published!", dev_msg="Bid status was updated successfully!")

    except Exception as err:
        return ServerError(err=err, errMsg=str(err))


@shipper_bidding_router.get("/increment/{bid_id}")
async def increment_time_of_bid(request: Request, bid_id: str):

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


@shipper_bidding_router.get("/lowest/{bid_id}")
async def get_lowest_price_of_current_bid(request: Request, bid_id: str):

    try:

        (lowest_price, error) = await redis.get_first(bid_id)

        if error:

            (lowest_price, error) = await bid.lowest_price(bid_id)

            if error:
                return ErrorResponse(data=[], client_msg="Something went wrong while fetching the lowest price for this bid", dev_msg=error)

        return SuccessResponse(data=lowest_price, dev_msg="Lowest price found for current bid", client_msg="Fetched lowest price for Bid-{bid_id}!")

    except Exception as err:
        return ServerError(err=err, errMsg=str(err))


@shipper_bidding_router.post("/history/{bid_id}")
async def fetch_all_rates_given_by_transporter(request: Request, bid_id: str, req: HistoricalRatesReq):

    try:

        (valid_bid_id, error) = await bid.is_valid(bid_id)

        if not valid_bid_id:
            return ErrorResponse(data=bid_id, client_msg=os.getenv("INVALID_BID_ERROR"), dev_msg=error)

        (rates, error) = await transporter.historical_rates(transporter_id=req.transporter_id, bid_id=bid_id)

        if error:
            return ErrorResponse(data=[], client_msg="Something went wrong while fetching historical rates, please try again in sometime", dev_msg=error)

        return SuccessResponse(data=rates, client_msg="Fetched all rates successfully", dev_msg="Fetched historical and negotitated rates")

    except Exception as err:
        return ServerError(err=err, errMsg=str(err))


@shipper_bidding_router.post("/cancel/{bid_id}")
async def cancel_bid(request: Request, bid_id: str, r: CancelBidReq):

    user_id = request.state.current_user["id"]

    try:

        if not r.reason:
            return ErrorResponse(data=[], dev_msg="No cancellation reason provided", client_msg="Please provide a valid cancellation reason")

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
        (update_successful, error) = await bid.update_status(bid_id=bid_id, status="cancelled", user_id=user_id, reason=r.reason)

        if not update_successful:
            return ErrorResponse(data=[], client_msg=os.getenv("BID_CANCEL_ERROR"), dev_msg=error)
        log("BID STATUS IS NOW CANCELLED")
        return SuccessNoContentResponse(dev_msg="Bid cancelled successfully", client_msg="Your Bid is Successfully Cancelled")

    except Exception as err:
        return ServerError(err=err, errMsg=str(err))


@shipper_bidding_router.post("/assign/{bid_id}")
async def assign_to_transporter(request: Request, bid_id: str, transporters: List[TransporterAssignReq]):

    user_id = request.state.current_user["id"]

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

        (assigned_loads, error) = await bid.assign(bid_id=bid_id, transporters=transporters, split=load_split, status=load_status, user_id=user_id)

        if error:
            return ErrorResponse(data=[], client_msg="Something Went Wrong While Assigning Transporters", dev_msg="ERROR WHILE SENDING NOTIFICATION !!! ERROR :::"+error)

        return SuccessResponse(data=assigned_loads, dev_msg="Load Assigned Successfully", client_msg=f"Load-{bid_id} assignment was successful!")

    except Exception as err:
        return ServerError(err=err, errMsg=str(err))


@shipper_bidding_router.get("/details/{bid_id}")
async def bid_details_for_assignment_to_transporter(request: Request, bid_id: str):

    # user_id =  request.state.current_user["id"]

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


@shipper_bidding_router.get("/live/{bid_id}")
async def live_bid_details(request: Request, bid_id: str):

    # user_id =  request.state.current_user["id"]

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

            return SuccessResponse(data=res_array, client_msg="Live Bid Details fetched Successfully!", dev_msg="Live Bid Details fetched Successfully")

        return SuccessResponse(data=bid_details, client_msg="Live Bid Details fetched Successfully!", dev_msg="Live Bid Details fetched Successfully")

    except Exception as err:
        return ServerError(err=err, errMsg=str(err))

# TODO - email


@shipper_bidding_router.post("/match/{bid_id}")
async def bid_match_for_transporters(request: Request, bid_id: str, transporters: List[TransporterBidMatchRequest], bg_tasks: BackgroundTasks):

    user_id = request.state.current_user["id"]

    try:

        (valid_bid_id, error) = await bid.is_valid(bid_id=bid_id)

        if not valid_bid_id:
            return ErrorResponse(data=[], client_msg=os.getenv("INVALID_BID_ERROR"), dev_msg=error)

        (assignment_details, error) = await transporter.bid_match(bid_id=bid_id, transporters=transporters, user_id=user_id)

        if error:
            return ErrorResponse(data=[], client_msg=os.getenv("GENERIC_ERROR"), dev_msg=error)

        # transporter_ids = [t.transporter_id for t in transporters]

        # (email_data,error) = await transporter.details(transporters = transporter_ids)

        # if error:
        #     return ErrorResponse(data=[],dev_msg="Email could not be sent",client_msg="Bid match was successful but email to transporter could not be sent!")

        # (success,message) = mail.price_match(recipients=email_data.recipients,email_data=PriceMatchEmail(transporter_id=))

        # if not success:
        #     return ErrorResponse(data=[],dev_msg="Email could not be sent",client_msg="Bid match was successful but email to transporter could not be sent!")

        # ## Send email as a background task
        # bg_tasks.add_task(fm.send_message,message)

        return SuccessResponse(data=assignment_details, client_msg="Bid Match Successful", dev_msg="Bid Match Successful")

    except Exception as err:
        return ServerError(err=err, errMsg=str(err))


@shipper_bidding_router.post("/unassign/{bid_id}")
async def unassign_transporter_for_bid(request: Request, bid_id: str, tr: TransporterUnassignRequest):

    # user_id =  request.state.current_user["id"]

    try:

        (valid_bid_id, error) = await bid.is_valid(bid_id=bid_id)

        if not valid_bid_id:
            return ErrorResponse(data=[], client_msg=os.getenv("INVALID_BID_ERROR"), dev_msg=error)

        (unassigned_transporter, error) = await transporter.unassign(bid_id=bid_id, transporter_request=tr)

        if error:
            return ErrorResponse(data=[], client_msg=os.getenv("INVALID_BID_ERROR"), dev_msg=error)

        return SuccessResponse(data=unassigned_transporter, client_msg=f"Successfully unassigned transporter for Bid-{bid_id}", dev_msg="Unassigned requested transporter from bid")

    except Exception as err:
        return ServerError(err=err, errMsg=str(err))


@shipper_bidding_router.get("/bids/{bid_id}")
async def details_of_a_bid(request: Request, bid_id: str):

    try:

        (valid_bid_id, error) = await bid.is_valid(bid_id=bid_id)

        if not valid_bid_id:
            return ErrorResponse(data=[], client_msg=os.getenv("INVALID_BID_ERROR"), dev_msg=error)

        (bid_details, error) = await bid.bidding_details(bid_id=bid_id)

        if error:
            return ErrorResponse(data=[], dev_msg=error, client_msg="Something went wrong while trying to fetch bid details, please try again in sometime")

        if not bid_details:
            return SuccessResponse(data=[], client_msg="No bids have been placed yet", dev_msg="No bids have been placed yet")

        return SuccessResponse(data={"bid_details": bid_details,
                                     "no_of_bids": len(bid_details)
                                     },
                               client_msg=f"Successfully unassigned transporter for Bid-{bid_id}",
                               dev_msg="Unassigned requested transporter from bid")

    except Exception as err:
        return ServerError(err=err, errMsg=str(err))
