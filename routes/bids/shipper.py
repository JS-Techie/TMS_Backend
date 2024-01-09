
import os
import pytz
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
                             TransporterUnassignRequest, AssignmentHistoryReq)
from services.mail import Email
from utils.bids.bidding import Bid
from utils.bids.shipper import Shipper
from utils.bids.transporters import Transporter
from utils.redis import Redis
from utils.response import (ErrorResponse, ServerError,
                            SuccessNoContentResponse, SuccessResponse)
from utils.utilities import log
from utils.notification_service_manager import notification_service_manager, NotificationServiceManagerReq

shipper_bidding_router: APIRouter = APIRouter(
    prefix="/shipper/bid", tags=["Shipper routes for bidding"])

transporter = Transporter()
bid = Bid()
shipper = Shipper()
redis = Redis()
mail = Email()
fm = FastMail(email_conf)

acu, shp = os.getenv("ACULEAD"), os.getenv("SHIPPER")


@shipper_bidding_router.get("/control")
async def initiate_and_close_bid(request: Request):

    try:

        userdata = request.state.current_user
        shipper_id = None
        log(" ID ", userdata["id"])
        
        
        if userdata["user_type"] == "shp":
            shipper_id = userdata["shipper_id"]
            log("SHIPPER ID ", shipper_id)
            
        initiation_response = bid.initiate(shipper_id= shipper_id)

        log("BID INITIATION RESPONSE ", initiation_response)

        expulsion_response = bid.close(shipper_id= shipper_id)

        log("BID CLOSING RESPONSE ", expulsion_response)
        
        return SuccessResponse(data=[], client_msg="SUCCESS", dev_msg={ "initiation_response": initiation_response , "expulsion_response": expulsion_response})

    except Exception as err:
        return ServerError(err=err, errMsg=str(err))


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
    authtoken = request.headers.get("authorization", "")

    try:
        ist_timezone = pytz.timezone("Asia/Kolkata")
        current_time = datetime.now(ist_timezone)
        current_time = current_time.replace(
            tzinfo=None, second=0, microsecond=0)

        (valid_bid_id, error) = await bid.is_valid(bid_id)

        if not valid_bid_id:
            return ErrorResponse(data=[], client_msg=os.getenv("NOT_FOUND_ERROR"), dev_msg=error)

        (success, bid_details) = await bid.details(bid_id=bid_id)

        if not success:
            return ErrorResponse(data=bid_id, dev_msg=success)

        if current_time > bid_details.bid_time:
            return ErrorResponse(data=[], client_msg=f"Bid Time was {bid_details.bid_time.replace(second =0, microsecond =0)}. Bid could not be published Anymore.", dev_msg="Already Crossed Bid Time. Bid Couldnot be published.")

        (update_successful, error) = await bid.update_status(bid_id=bid_id, status="not_started" if bid_details.bid_mode != "indent" else "confirmed", user_id=user_id)

        if not update_successful:
            return ErrorResponse(data=bid_id, client_msg=os.getenv("BID_PUBLISH_ERROR"), dev_msg=error)

        # (success, error)= await transporter.notify(bid_id=bid_id, authtoken=request.headers.get("authorization", ""))
        # if not success:
        #     return ErrorResponse(data=[], dev_msg=error)
        
        (bid_related_kam, error) = await bid.transporter_kams(bid_id=bid_details.bl_id, bid_mode=bid_details.bid_mode, shipper_id=bid_details.bl_shipper_id, segment_id=bid_details.bl_segment_id ,indent_transporter_id=bid_details.indent_transporter_id)
        
        if error:
            return ErrorResponse(data=[], dev_msg=error)
        
        log("::: BID RELATED KAM ::: ", bid_related_kam)
        
        (notification_response_success, error) = await notification_service_manager(authtoken=authtoken, req=NotificationServiceManagerReq(**{
                                                                                                                                                "receiver_ids": bid_related_kam,
                                                                                                                                                "text":f"Bid L-{bid_id[-5:].upper()} has been published! HURRY & BID NOW !!!",
                                                                                                                                                "type":"Bid Publish",
                                                                                                                                                "deep_link":"transporter_dashboard_upcoming"
                                                                                                                                            }
                                                                                                                                            )
                                                                                    )
        
        if error:
            log("::: NOTIFICATION ERROR DURING BID PUBLISH ::: ",error)

        return SuccessResponse(data=bid_id, client_msg=f"Bid  L-{bid_id[-5:].upper()} is now published!", dev_msg="Bid status was updated successfully!")

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

        return SuccessResponse(data=lowest_price, dev_msg="Lowest price found for current bid", client_msg=f"Fetched lowest price for Bid  L-{bid_id[-5:].upper()}!")

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

            return ErrorResponse(data=[], client_msg="This bid is not valid and cannot be cancelled!", dev_msg=f"Bid  L-{bid_id[-5:].upper()} is {bid_details.load_status}, cannot be cancelled!")

        log("BID STATUS IS VALID")
        (update_successful, error) = await bid.update_status(bid_id=bid_id, status="cancelled", user_id=user_id, reason=r.reason)

        if not update_successful:
            return ErrorResponse(data=[], client_msg=os.getenv("BID_CANCEL_ERROR"), dev_msg=error)
        log("BID STATUS IS NOW CANCELLED")
        
        (bid_related_kam, error) = await bid.transporter_kams(bid_id=bid_id, bid_mode=bid_details.bid_mode, shipper_id=bid_details.bl_shipper_id, segment_id=bid_details.bl_segment_id ,indent_transporter_id=bid_details.indent_transporter_id)
        
        if error:
            return ErrorResponse(data=[], dev_msg=error)
        
        log("::: BID RELATED KAM ::: ", bid_related_kam)
        
        (notification_response_success, error) = await notification_service_manager(authtoken=request.headers.get("authorization", ""), req=NotificationServiceManagerReq(**{
                                                                                                                                                "receiver_ids": bid_related_kam,
                                                                                                                                                "text":f"Bid L-{bid_id[-5:].upper()} has been Cancelled. SORRY for the INCONVENIENCE",
                                                                                                                                                "type":"Bid Cancellation",
                                                                                                                                                "deep_link":"#"
                                                                                                                                            }
                                                                                                                                            )
                                                                                    )
        
        if error:
            log("::: NOTIFICATION ERROR DURING BID PUBLISH ::: ",error)

        
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
            return ErrorResponse(data=[], client_msg="Something Went Wrong While Assigning Transporters", dev_msg=error)

        return SuccessResponse(data=assigned_loads, dev_msg="Load Assigned Successfully", client_msg=f"Load  L-{bid_id[-5:].upper()} assignment was successful!")

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
    user_type = request.state.current_user["user_type"]

    try:

        (valid_bid_id, error) = await bid.is_valid(bid_id=bid_id)

        if not valid_bid_id:
            return ErrorResponse(data=[], client_msg=os.getenv("INVALID_BID_ERROR"), dev_msg=error)

        (assignment_details, error) = await transporter.bid_match(bid_id=bid_id, transporters=transporters, user_id=user_id, user_type= user_type)

        if error:
            if error == "Transporter already assigned":
                return ErrorResponse(data=[], client_msg="Price Match Ineligible as some transporters are already assigned", dev_msg=error)
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
        
        transporter_ids = [transporter.transporter_id for transporter in transporters]
        
        (bid_related_kam, error) = await bid.transporter_kams(transporter_ids=transporter_ids)
        
        if error:
            return ErrorResponse(data=[], dev_msg=error)
        
        log("::: BID RELATED KAM ::: ", bid_related_kam)
        
        (notification_response_success, error) = await notification_service_manager(authtoken=request.headers.get("authorization", ""), req=NotificationServiceManagerReq(**{
                                                                                                                                                "receiver_ids": bid_related_kam,
                                                                                                                                                "text":f"Bid L-{bid_id[-5:].upper()} has asked for a Price Match" if user_type != "acu" else f"The Price for Bid L-{bid_id[-5:].upper()} has been Negotiated" ,
                                                                                                                                                "type":"Bid match and Negotiation",
                                                                                                                                                "deep_link":"transporter_dashboard_pending"
                                                                                                                                            }
                                                                                                                                            )
                                                                                    )
        
        if error:
            log("::: NOTIFICATION ERROR DURING BID PUBLISH ::: ",error)


        return SuccessResponse(data=assignment_details, client_msg="Successfully Requested Bid Match" if user_type != "acu" else "Successfully Bid Matched", dev_msg="Bid Match Request Successful")

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

        return SuccessResponse(data=unassigned_transporter, client_msg=f"Successfully unassigned transporter for Bid  L-{bid_id[-5:].upper()}", dev_msg="Unassigned requested transporter from bid")

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
                               client_msg=f"Successfully unassigned transporter for Bid  L-{bid_id[-5:].upper()}",
                               dev_msg="Unassigned requested transporter from bid")

    except Exception as err:
        return ServerError(err=err, errMsg=str(err))


@shipper_bidding_router.post("/history/assignment/{bid_id}")
async def fetch_transporter_specific_bid_assignment_history(request: Request, bid_id: str, req: AssignmentHistoryReq):

    try:

        (valid_bid_id, error) = await bid.is_valid(bid_id)

        if not valid_bid_id:
            return ErrorResponse(data=bid_id, client_msg=os.getenv("INVALID_BID_ERROR"), dev_msg=error)

        (rates, error) = await transporter.assignment_history(transporter_id=req.transporter_id, bid_id=bid_id)

        if error:
            return ErrorResponse(data=[], client_msg="Something went wrong while fetching assignment history, please try again in sometime", dev_msg=error)

        return SuccessResponse(data=rates, client_msg="Fetched assignment history successfully", dev_msg="Fetched assignment history")

    except Exception as err:
        return ServerError(err=err, errMsg=str(err))
