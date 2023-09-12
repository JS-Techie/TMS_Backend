from fastapi import APIRouter, BackgroundTasks
from uuid import UUID

from utils.response import *
from data.bidding import valid_load_status
from utils.bids.bidding import Bid
from utils.bids.transporters import Transporter
from utils.redis import Redis
from schemas.bidding import HistoricalRatesReq, TransporterBidReq

bidding_router: APIRouter = APIRouter(prefix="/bid")

transporter = Transporter()
bid = Bid()
redis = Redis()


@bidding_router.get("/{status}")
async def get_bids_according_to_status(status: str):

    try:
        if status not in valid_load_status:
            return ErrorResponse(data=[], dev_msg="Incorrect status requested, please check status parameter in request", client_msg="Something went wrong,please try again in sometime!")

        return await fetch_bids_statuswise(status)

    except Exception as err:
        return ServerError(err=err, errMsg=str(err))


@bidding_router.patch("/publish/{bid_id}")
async def publish_new_bid(bid_id: str, bg_tasks: BackgroundTasks):

    try:

        (valid_bid_id, error) = await bid.is_valid(bid_id)

        if not valid_bid_id:
            return ErrorResponse(data=bid_id, client_msg="The bid requested is not available at this time", dev_msg=error)

        (update_successful, error) = await bid.update_status(bid_id=bid_id, status="live")

        if not update_successful:
            return ErrorResponse(data=bid_id, client_msg=f"Something went wrong while trying to publish Bid-{bid_id}, please try again after sometime!", dev_msg=error)

        (new_bid_table_creation_successful, error) = await bid.create_table(bid_id)

        if not new_bid_table_creation_successful:
            return ErrorResponse(data=bid_id, client_msg=f"Something went wrong while trying to publish Bid-{bid_id}, please try again after sometime!", dev_msg=error)

        bg_tasks.add_task(transporter.notify(bid_id))

        return SuccessResponse(data=bid_id, client_msg=f"Bid-{bid_id} is now published!", dev_msg="Bid status was updated successfully!")

    except Exception as err:
        return ServerError(err=err, errMsg=str(err))


@bidding_router.post("/rate/{bid_id}", response_model=None)
async def provide_new_rate_for_bid(bid_id: str, bidReq: TransporterBidReq):

    try:

        (valid_bid_id, error) = await bid.is_valid(bid_id)

        if not valid_bid_id:
            return ErrorResponse(data=bid_id, client_msg="The bid requested is not available at this time", dev_msg=error)

        (bid_details, error) = await bid.details(bid_id)

        if error:
            return ErrorResponse(data=[], client_msg="Something went wrong while trying to submit your bid, please try again in sometime!", dev_msg=error)

        (transporter_attempts, error) = await transporter.attempts(
            bid_id=bid_id, transporter_id=bid.transporter_id)

        if error:
            return ErrorResponse(data=[], client_msg="Something went wrong while trying to submit your bid, please try again in sometime!", dev_msg=error)

        if transporter_attempts >= bid_details.no_of_tries:
            return ErrorResponse(data=[], client_msg="You have exceeded the number of tries for this bid!", dev_msg=f"Number of tries for Bid-{bid_id} exceeded!")

        (lowest_price, error) = await bid.lowest_price(bid_id)

        if error:
            return ErrorResponse(data=[], client_msg="Something went wrong while fetching the lowest price for this bid", dev_msg=error)

        (transporter_lowest_price, error) = await transporter.lowest_price(bid_id, bid.transporter_id)

        if error:
            return ErrorResponse(data=[], client_msg="Something went wrong while fetching the lowest price for this bid", dev_msg=error)

        (rate, error) = bid.va(bid_mode=bid_details.bid_mode, rate=bid.rate,
                               decrement=bid_details.bid_price_decrement, lowest_price=lowest_price, transporter_lowest=transporter_lowest_price)

        if not rate.valid:
            return ErrorResponse(data=[], client_msg=f"You entered an incorrect bid rate! Your previous rate was {rate.previous_rate}, decrement is {bid_details.bid_price_decrement}", dev_msg="Incorrect bid price entered")

        (update_bid_table, error) = insert_new_record_in_bid_table(
            bid_id, bid.transporter_id, bid.rate)

        if error:
            return ErrorResponse(data=[], dev_msg=error, client_msg="Something went wrong while trying to submit your bid, please try again in 60 seconds!")

        # Update the redis sorted set here
        (sorted_bid_details, error) = redis.update(sorted_set=bid_id,
                                                   transporter_id=bid.transporter_id, rate=bid.rate)

        # emit socket event here

        return SuccessResponse(data=[], dev_msg="Bid submitted successfully", client_msg=f"Bid for Bid-{bid_id} submitted!")

    except Exception as err:
        return ServerError(err=err, errMsg=str(err))


@bidding_router.get("/lowest/{bid_id}")
async def get_lowest_price_of_current_bid(bid_id: str):

    try:

        (lowest_price, error) = get_lowest_price(bid_id)

        if error:
            return ErrorResponse(data=[], client_msg="Something went wrong while fetching the lowest price for this bid", dev_msg=error)

        return SuccessResponse(data=lowest_price, dev_msg="Lowest price found for current bid", client_msg="Fetched lowest price for Bid-{bid_id}!")

    except Exception as err:
        return ServerError(err=err, errMsg=str(err))


@bidding_router.post("/history/{bid_id}")
async def fetch_all_rates_given_by_transporter(bid_id: str, req: HistoricalRatesReq):

    try:
        (valid_bid_id, error) = await bid_id_is_valid(bid_id)

        if not valid_bid_id:
            return ErrorResponse(data=bid_id, client_msg="The bid requested is not available at this time", dev_msg=error)

        return historical_rates(transporter_id=req.transporter_id, bid_id=bid_id)

    except Exception as err:
        return ServerError(err=err, errMsg=str(err))


# Juned you will work on the below APIs

# @bidding_router.post("/filter")
# async def get_bids_according_to_filter(req : FilterBidsRequest):

# return {"Hello"}

# @bidding_router.post("/assign/{bid_id}")
# async def assign_transporters_to_bid(bid_id: UUID):
#     pass


# @bidding_router.patch("/rebid/{bid_id}")
# async def rebid(bid_id: UUID):
#     pass


# @bidding_router.patch("/match/{bid_id}")
# async def negotiate_price_for_bid_match(bid_id: UUID):
#     pass


# @bidding_router.patch("/approval/{bid_id}")
# async def send_bid_for_approval(bid_id: UUID):
#     pass


# @bidding_router.delete("/cancel/{bid_id}")
# async def cancel_bid(bid_id: UUID):
#     pass
