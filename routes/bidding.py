from fastapi import APIRouter, BackgroundTasks
import os


from utils.response import *
from data.bidding import valid_load_status,valid_rebid_status, valid_cancel_status
from utils.bids.bidding import Bid
from utils.bids.transporters import Transporter
from utils.redis import Redis
from schemas.bidding import HistoricalRatesReq,TransporterBidReq


bidding_router: APIRouter = APIRouter(prefix="/bid")

transporter = Transporter()
bid = Bid()
redis = Redis()


@bidding_router.get("/status/{status}")
async def get_bids_according_to_status(status: str):

    try:
        if status not in valid_load_status:
            return ErrorResponse(data=[], dev_msg=os.getenv("STATUS_ERROR"), client_msg=os.getenv("GENERIC_ERROR"))

        (bids, error) = await bid.get_status_wise(status)

        if error:
            return ErrorResponse(data=[], dev_msg=err, client_msg=os.getenv("GENERIC_ERROR"))

        return SuccessResponse(data=bids, dev_msg="Correct status, data fetched", client_msg=f"Fetched all {status} bids successfully!")

    except Exception as err:
        return ServerError(err=err, errMsg=str(err))


@bidding_router.patch("/publish/{bid_id}")
async def publish_new_bid(bid_id: str, bg_tasks: BackgroundTasks):

    try:

        (valid_bid_id, error) = await bid.is_valid(bid_id)

        if not valid_bid_id:
            return ErrorResponse(data=[], client_msg=os.getenv("NOT_FOUND_ERROR"), dev_msg=error)

        (update_successful, error) = await bid.update_status(bid_id=bid_id, status="live")

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

        (valid_bid_id, error) = await bid.is_valid(bid_id)

        if not valid_bid_id:
            return ErrorResponse(data=bid_id, client_msg=os.getenv("NOT_FOUND_ERROR"), dev_msg=error)

        (bid_details, error) = await bid.details(bid_id)

        if error:
            return ErrorResponse(data=[], client_msg=os.getenv("BID_RATE_ERROR"), dev_msg=error)

        if bid_details.load_status != "live":
            return ErrorResponse(data=[], client_msg=f"This Load is not Accepting Bids yet, start time is {bid_details.bid_time}", dev_msg="Tried bidding, but bid is not live yet")

        (transporter_attempts, error) = await transporter.attempts(
            bid_id=bid_id, transporter_id=bid_req.transporter_id)

        if error:
            return ErrorResponse(data=[], client_msg=os.getenv("BID_RATE_ERROR"), dev_msg=error)

        if transporter_attempts >= bid_details.no_of_tries:
            return ErrorResponse(data=[], client_msg="You have exceeded the number of tries for this bid!", dev_msg=f"Number of tries for Bid-{bid_id} exceeded!")

        (rate, error) = transporter.is_valid_bid_rate(bid_id, bid_details.show_current_lowest_rate_transporter,
                                                      bid_req.rate, bid_req.transporter_id, bid_details.bid_price_decrement)

        if error:
            return ErrorResponse(data={}, dev_msg=error, client_msg=os.getenv("BID_RATE_ERROR"))

        if not rate.valid:
            return ErrorResponse(data=[], client_msg=f"You entered an incorrect bid rate! Decrement is {bid_details.bid_price_decrement}", dev_msg="Incorrect bid price entered")

        (new_record, error) = bid.new_bid(
            bid_id, bid_req.transporter_id, bid_req.rate,bid_req.comment)

        if error:
            return ErrorResponse(data=[], dev_msg=error, client_msg=os.getenv("BID_RATE_ERROR"))
        
        (transporter_name,error) = transporter.name(transporter_id = bidReq.transporter_id)
        
        if error:
            return ErrorResponse(data=[],client_msg=os.getenv("BID_RATE_ERROR"),dev_msg=error)
        
        
        (sorted_bid_details, error) = redis.update(sorted_set=bid_id,
                                                   transporter_id=bid.transporter_id,transporter_name=transporter_name, rate=bid.rate)

        # emit socket event here

        return SuccessResponse(data=new_record, dev_msg="Bid submitted successfully", client_msg=f"Bid for Bid-{bid_id} submitted!")

    except Exception as err:
        return ServerError(err=err, errMsg=str(err))


@bidding_router.get("/lowest/{bid_id}")
async def get_lowest_price_of_current_bid(bid_id: str):

    try:

        (lowest_price, error) = redis.get_first(bid_id)

        if error:

            (lowest_price, error) = bid.lowest_price(bid_id)

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
            return ErrorResponse(data=bid_id, client_msg="The bid requested is not available at this time", dev_msg=error)

        return transporter.historical_rates(transporter_id=req.transporter_id, bid_id=bid_id)

    except Exception as err:
        return ServerError(err=err, errMsg=str(err))



@bidding_router.put("/rebid/{bid_id}")
async def rebid(bid_id: str):
    
    try:
        (valid_bid_id, error) = await bid.is_valid(bid_id)
        
        if not valid_bid_id:
            return ErrorResponse(data=[], client_msg="The bid requested is not available at this time", dev_msg=error)
        
        (bid_details,error )= await bid.details(bid_id=bid_id)
        
        if error:
            return ErrorResponse(data=[],client_msg="Something went wrong while trying to rebid", dev_msg=error)
        
        if bid_details.status not in valid_rebid_status:
            return ErrorResponse(data=[],client_msg="This bid is not valid for rebid!",dev_msg=f"Bid-{bid_id} is {bid_details.status}, cannot be rebid!")
        
        #call create load api
        
        
        
    except Exception as err:
        return ServerError(err=err, errMsg=str(err))
        
        
        
        
@bidding_router.put("/cancel/{bid_id}")
async def rebid(bid_id: str):
    
    try:
        (valid_bid_id, error) = await bid.is_valid(bid_id)
        
        if not valid_bid_id:
            return ErrorResponse(data=[], client_msg="The bid requested is not available at this time", dev_msg=error)
        
        (bid_details,error) = await bid.details(bid_id=bid_id)
        
        if error:
            return ErrorResponse(data=[],client_msg="Something went wrong while trying to cancel", dev_msg=error)
        
        if bid_details.status not in valid_cancel_status:
            return ErrorResponse(data=[],client_msg="This bid is not valid and cannot be cancelled!",dev_msg=f"Bid-{bid_id} is {bid_details.status}, cannot be cancelled!")
        
        
        (update_successful, error) = await bid.update_status(bid_id=bid_id, status="cancelled")
        
        if not update_successful:
            return ErrorResponse(data=bid_id, client_msg=os.getenv("BID_CANCEL_ERROR"), dev_msg=error)
        
        return SuccessNoContentResponse(dev_msg="Bid cancelled successfully", client_msg="Your Bid is Successfully Cancelled")
        
        
    except Exception as err:
        return ServerError(err=err, errMsg=str(err))