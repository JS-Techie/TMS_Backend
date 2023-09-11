from fastapi import APIRouter, BackgroundTasks
from uuid import UUID

from utils.response import *
from data.bidding import valid_load_status
from utils.bids.bidding import fetch_bids_statuswise, bid_id_is_valid, update_bid_status, create_bid_table
from utils.bids.transporters import notify_transporters_for_bid, historical_rates
from schemas.bidding import HistoricalRatesReq

bidding_router: APIRouter = APIRouter(prefix="/bid")


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

        (valid_bid_id, error) = await bid_id_is_valid(bid_id)

        if not valid_bid_id:
            return ErrorResponse(data=bid_id, client_msg="The bid requested is not available at this time", dev_msg=error)

        (update_successful, error) = await update_bid_status(bid_id=bid_id, status="live")

        if not update_successful:
            return ErrorResponse(data=bid_id, client_msg=f"Something went wrong while trying to publish Bid-{bid_id}, please try again after sometime!", dev_msg=error)

        (new_bid_table_creation_successful, error) = await create_bid_table(bid_id)

        if not new_bid_table_creation_successful:
            return ErrorResponse(data=bid_id, client_msg=f"Something went wrong while trying to publish Bid-{bid_id}, please try again after sometime!", dev_msg=error)

        bg_tasks.add_task(notify_transporters_for_bid(bid_id))

        return SuccessResponse(data=bid_id, client_msg=f"Bid-{bid_id} is now published!", dev_msg="Bid status was updated successfully!")

    except Exception as err:
        return ServerError(err=err, errMsg=str(err))

# @bidding_router.post("/rate/{bid_id}",response_model=None)
# async def provide_new_rate_for_bid(bid_id: UUID):

#     session = Session()

#     try:
#         #check number of tries in the bid from settings
#         #if this transporter has already provided equal or more than number of bids, then they are not allowed agaim
#         # if they are allowed, get the bid decrement price and check if new price entered meets bid decrement criteria
#         # if it meets bid decrement criteria, update the record in redis sorted set and send response back to the frontend as a socket event which basicallt sends the entire sorted set back
#         # also append this record to a table in DB
#         return SuccessResponse(data=[])

#     except Exception as err:
#         session.rollback()
#         return ServerError(err=err,errMsg=str(err))

#     finally:
#         session.close()


@bidding_router.post("/history/{bid_id}")
async def fetch_all_rates_given_by_transporter(bid_id: str, req: HistoricalRatesReq):

    try:
        (valid_bid_id, error) = await bid_id_is_valid(bid_id)

        if not valid_bid_id:
            return ErrorResponse(data=bid_id, client_msg="The bid requested is not available at this time", dev_msg=error)

        return historical_rates(transporter_id=req.transporter_id, bid_id=bid_id)

    except Exception as err:
        return ServerError(err=err, errMsg=str(err))


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
