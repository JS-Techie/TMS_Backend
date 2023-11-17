from fastapi import APIRouter, Request
import pytz, os
from datetime import datetime, timedelta

from schemas.bidding import FilterBidsRequest
from utils.bids.bidding import Bid
from utils.response import ErrorResponse, ServerError, SuccessResponse

open_router = APIRouter(prefix="", tags=["Open routes"])

bid=Bid()

@open_router.get("bid/increment/{bid_id}")
async def increment_time_of_bid(bid_id: str):

    ist_timezone = pytz.timezone("Asia/Kolkata")
    current_time = datetime.now(ist_timezone)
    current_time = current_time.replace(tzinfo=None)

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

        if (bid_details.bid_end_time-current_time).total_seconds()/60 > setting_details.bid_increment_time:
            return SuccessResponse(data=[],dev_msg="No Increment Needed", client_msg="No Increment Needed.")

        extended_bid_end_time = bid_details.bid_end_time + timedelta(minutes=setting_details.bid_increment_duration)
        extended_time = bid_details.bid_extended_time + setting_details.bid_increment_duration

        (bid_end_time_update, error) = await bid.update_bid_end_time(bid_id=bid_id, bid_end_time=extended_bid_end_time, extended_time=extended_time)

        if not bid_end_time_update:
            return ErrorResponse(data=bid_id, client_msg="Something Went Wrong While Incrementing Bid Time", dev_msg=error)

        return SuccessResponse(data=bid_id, client_msg="Bid End Time Updated Successfully!", dev_msg="Bid end time was updated successfully!")

    except Exception as err:
        return ServerError(err=err, errMsg=str(err))
