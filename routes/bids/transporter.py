import json
import os
import pytz
from datetime import datetime
from fastapi import APIRouter, Request

from config.socket import manager
from data.bidding import valid_bid_status, valid_transporter_status
from schemas.bidding import TransporterBidReq, TransporterLostBidsReq
from utils.bids.bidding import Bid
from utils.bids.shipper import Shipper
from utils.bids.transporters import Transporter
from utils.redis import Redis
from utils.response import ErrorResponse, ServerError, SuccessResponse
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
    (bids, error) = ([], "")

    try:

        if status not in valid_transporter_status:
            return ErrorResponse(data=[], dev_msg="Invalid status", client_msg=os.getenv("GENERIC_ERROR"))

        if not transporter_id:
            return ErrorResponse(data=[], dev_msg=os.getenv("TRANSPORTER_ID_NOT_FOUND_ERROR"), client_msg=os.getenv("GENERIC_ERROR"))

        if status == "assigned":
            (bids, error) = await transporter.assigned_bids(transporter_id=transporter_id)
        else:
            if status == "active":
                (bids, error) = await transporter.bids_by_status(transporter_id=transporter_id, status="not_started")
            else:
                (bids, error) = await transporter.bids_by_status(transporter_id=transporter_id, status=status)

        if error:
            return ErrorResponse(data=[], dev_msg=error, client_msg=os.getenv("GENERIC_ERROR"))

        updated_bids = None
        log("STATUS ", status)
        if status != "assigned":
            updated_private_bids = []
            updated_public_bids = []

            if status == "not_started":
                (bids_participated, error) = await transporter.participated_bids(transporter_id=transporter_id)

                if bids_participated:

                    filtered_private_bids = [
                        private_record for private_record in bids["private"]
                        if not any(participated_bid["bid_id"] == private_record["bid_id"] and participated_bid["load_status"] == "not_started" for participated_bid in bids_participated)
                    ]

                    filtered_public_bids = [
                        public_record for public_record in bids["public"]
                        if not any(participated_bid["bid_id"] == public_record["bid_id"] and participated_bid["load_status"] == "not_started" for participated_bid in bids_participated)
                    ]

                    bids["private"] = filtered_private_bids
                    bids["public"] = filtered_public_bids

            if status == "active":
                (bids_participated, error) = await transporter.participated_bids(transporter_id=transporter_id)

                if bids_participated:

                    filtered_private_bids = [
                        private_record for private_record in bids["private"]
                        if any(participated_bid["bid_id"] == private_record["bid_id"] and participated_bid["load_status"] == "not_started" for participated_bid in bids_participated)
                    ]

                    filtered_public_bids = [
                        public_record for public_record in bids["public"]
                        if any(participated_bid["bid_id"] == public_record["bid_id"] and participated_bid["load_status"] == "not_started" for participated_bid in bids_participated)
                    ]

                    bids["private"] = filtered_private_bids
                    bids["public"] = filtered_public_bids
                    log("BIDS PUBLIC :", bids["public"])

            if status == "pending":
                (bids_participated, error) = await transporter.participated_bids(transporter_id=transporter_id)

                if bids_participated:

                    filtered_private_bids = [
                        private_record for private_record in bids["private"]
                        if any(participated_bid["bid_id"] == private_record["bid_id"] and participated_bid["load_status"] == "pending" for participated_bid in bids_participated)
                    ]

                    filtered_public_bids = [
                        public_record for public_record in bids["public"]
                        if any(participated_bid["bid_id"] == public_record["bid_id"] and participated_bid["load_status"] == "pending" for participated_bid in bids_participated)
                    ]

                    bids["private"] = filtered_private_bids
                    bids["public"] = filtered_public_bids

            for private_bid in bids["private"]:

                lowest_price_response = await lowest_price_of_bid_and_transporter(request=request, bid_id=private_bid["bid_id"])
                if lowest_price_response["data"] == []:
                    return lowest_price_response

                lowest_price_data = lowest_price_response["data"]
                updated_private_bids.append(
                    {**private_bid, **lowest_price_data})

            for public_bid in bids["public"]:

                lowest_price_response = await lowest_price_of_bid_and_transporter(request=request, bid_id=public_bid["bid_id"])
                if lowest_price_response["data"] == []:
                    return lowest_price_response

                lowest_price_data = lowest_price_response["data"]
                updated_public_bids.append({**public_bid, **lowest_price_data})

            updated_bids = {
                "all": updated_private_bids+updated_public_bids,
                "private": updated_private_bids,
                "public": updated_public_bids
            }

        else:

            updated_bids = []
            for bid in bids:

                lowest_price_response = await lowest_price_of_bid_and_transporter(request=request, bid_id=bid["bid_id"])
                if lowest_price_response["data"] == []:
                    return lowest_price_response

                lowest_price_data = lowest_price_response["data"]
                updated_bids.append({**bid, **lowest_price_data})

        return SuccessResponse(data=updated_bids, dev_msg="Fetched bids successfully", client_msg=f"Fetched all {status} bids successfully!")

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

        updated_bids = []
        for bid in bids:

            lowest_price_response = await lowest_price_of_bid_and_transporter(request=request, bid_id=bid["bid_id"])
            if lowest_price_response["data"] == []:
                return lowest_price_response

            lowest_price_data = lowest_price_response["data"]
            updated_bids.append({**bid, **lowest_price_data})

        return SuccessResponse(data=updated_bids, dev_msg="Fetched bids successfully", client_msg="Fetched all selected bids successfully!")

    except Exception as err:
        return ServerError(err=err, errMsg=str(err))


@transporter_bidding_router.get("/completed")
async def fetch_completed_bids(request: Request):

    transporter_id = request.state.current_user["transporter_id"]

    try:

        if not transporter_id:
            return ErrorResponse(data=[], dev_msg=os.getenv("TRANSPORTER_ID_NOT_FOUND_ERROR"), client_msg=os.getenv("GENERIC_ERROR"))

        (bids, error) = await transporter.completed(transporter_id=transporter_id)

        if error:
            return ErrorResponse(data=[], dev_msg=error, client_msg=os.getenv("GENERIC_ERROR"))

        if not bids:
            return SuccessResponse(data=[], client_msg="You dont have any completed bids yet", dev_msg="Not completed any bids")

        private_bids = []
        public_bids = []
        for bid in bids:

            lowest_price_response = await lowest_price_of_bid_and_transporter(request=request, bid_id=bid["bid_id"])
            if lowest_price_response["data"] == []:
                return lowest_price_response

            lowest_price_data = lowest_price_response["data"]
            
            if bid["bid_mode"] == "private_pool":
                private_bids.append({**bid, **lowest_price_data})
            else:
                public_bids.append({**bid, **lowest_price_data})
                
        bids = {
                "all": private_bids + public_bids,
                "private": private_bids,
                "public": public_bids
            }

        return SuccessResponse(data=bids, dev_msg="Fetched bids successfully", client_msg="Fetched all completed bids successfully!")

    except Exception as err:
        return ServerError(err=err, errMsg=str(err))


@transporter_bidding_router.post("/rate/{bid_id}", response_model=None)
async def provide_new_rate_for_bid(request: Request, bid_id: str, bid_req: TransporterBidReq):

    transporter_id, user_id = request.state.current_user[
        "transporter_id"], request.state.current_user["id"]

    # user_id = os.getenv("USERID")

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

        ist_timezone = pytz.timezone("Asia/Kolkata")
        current_time = datetime.now(ist_timezone)
        current_time = current_time.replace(
            tzinfo=None, second=0, microsecond=0)

        if bid_details.load_status not in valid_bid_status:
            if current_time < bid_details.bid_time and current_time < bid_details.bid_end_time:
                return ErrorResponse(data=[], client_msg=f"This Load is not Accepting Bids yet, the start time is {bid_details.bid_time}", dev_msg="Tried bidding, but bid is not live yet")

            elif current_time > bid_details.bid_time and current_time > bid_details.bid_end_time:
                return ErrorResponse(data=[], client_msg=f"This Load is not Accepting Bids anymore, the end time was {bid_details.bid_end_time}", dev_msg="Tried bidding, but bid is not live anymore")

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
            return ErrorResponse(data={}, dev_msg=error, client_msg=error)

        if not rate["valid"]:
            return ErrorResponse(data=[], client_msg=f"You entered an incorrect bid rate! Decrement is {bid_details.bid_price_decrement}", dev_msg="Incorrect bid price entered")

        log("VALID RATE", bid_id)

        (new_bid_transaction, error) = await bid.new(
            bid_id, transporter_id, bid_req.rate, bid_req.comment, user_id=user_id)

        log("NEW BID INSERTED", new_bid_transaction)

        if error:
            return ErrorResponse(data=[], dev_msg=error, client_msg=os.getenv("BID_RATE_ERROR"))

        (transporter_name, error) = await transporter.name(
            transporter_id=transporter_id)

        log("TRANSPORTER NAME", transporter_name)

        if error:
            return ErrorResponse(data=[], client_msg=os.getenv("BID_RATE_ERROR"), dev_msg=error)

        (sorted_bid_details, error) = await redis.update(sorted_set=bid_id,
                                                         transporter_id=transporter_id, comment=new_bid_transaction.comment, transporter_name=transporter_name, rate=bid_req.rate, attempts=transporter_attempts + 1)

        log("BID DETAILS", sorted_bid_details)

        await manager.broadcast(bid_id=bid_id, message=json.dumps(sorted_bid_details))

        log("SOCKET EVENT SENT", sorted_bid_details)

        return SuccessResponse(data=sorted_bid_details, dev_msg="Bid submitted successfully", client_msg=f"Bid for Bid-{bid_id} submitted!")

    except Exception as err:
        return ServerError(err=err, errMsg=str(err))


@transporter_bidding_router.post("/lost")
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
            return SuccessResponse(data=[], dev_msg="Not lost any bid", client_msg="No lost bids to show right now!")

        updated_bids = []
        for bid in bids:

            lowest_price_response = await lowest_price_of_bid_and_transporter(request=request, bid_id=bid["bid_id"])
            if lowest_price_response["data"] == []:
                return lowest_price_response

            lowest_price_data = lowest_price_response["data"]
            updated_bids.append({**bid, **lowest_price_data})

        return SuccessResponse(data=updated_bids, dev_msg="Fetched lost bids successfully", client_msg="Fetched all lost bids successfully!")

    except Exception as err:
        return ServerError(err=err, errMsg=str(err))


@transporter_bidding_router.get("/lowest/{bid_id}")
async def lowest_price_of_bid_and_transporter(request: Request, bid_id: str):

    transporter_id = str(request.state.current_user["transporter_id"])
    log("TRANSPORTER DATA TYPE :", type(transporter_id))

    try:
        if not transporter_id:
            return ErrorResponse(data=[], dev_msg=os.getenv("TRANSPORTER_ID_NOT_FOUND_ERROR"), client_msg=os.getenv("GENERIC_ERROR"))

        (transporter_lowest_price, error) = await transporter.lowest_price(
            bid_id=bid_id, transporter_id=transporter_id)

        if error:
            return ErrorResponse(data=[], dev_msg=error, client_msg="Something went wrong file fetching lowest price of transporter, please try again in sometime!")

        log("FOUND TRANSPORTER LOWEST PRICE", transporter_lowest_price)

        (success, bid_details) = await bid.details(bid_id=bid_id)
        if not success:
            return ErrorResponse(data=[], dev_msg=error, client_msg="Something went wrong while fetching bid details for transporter, please try again in sometime!")

        (bid_lowest_price, error) = (None, None)

        if bid_details.show_current_lowest_rate_transporter:
            (bid_lowest_price, error) = await bid.lowest_price(bid_id=bid_id)

        if error:
            return ErrorResponse(data=[], dev_msg=error, client_msg="Something went wrong while fetching bid details for transporter, please try again in sometime!")

        log("FOUND BID LOWEST PRICE", bid_lowest_price)

        # transporter_position, error = redis.position(
        #     sorted_set=bid_id, key=transporter_id)

        # if error:
        #     return ErrorResponse(data=[], dev_msg=error, client_msg="Something went wrong file fetching bid details for transporter, please try again in sometime!")

        # if not transporter_position:
        (transporter_position, error) = await transporter.position(transporter_id=transporter_id, bid_id=bid_id)

        if error:
            return ErrorResponse(data=[], dev_msg=error, client_msg="Something went wrong file fetching bid details for transporter, please try again in sometime!")
        log("TRANSPORTER POSITION ", transporter_position)
        return SuccessResponse(data={
            "bid_lowest_price": bid_lowest_price if bid_lowest_price != float("inf") else None,
            "transporter_lowest_price": transporter_lowest_price if transporter_lowest_price != 0.0 else None,
            "position": transporter_position+1 if transporter_position != None else None
            # "transporter_rates": transporter_historical_rates
        }, dev_msg="Found all rates successfully", client_msg="Fetched lowest price of bid and transporter successfully")

    except Exception as err:
        return ServerError(err=err, errMsg=str(err))
