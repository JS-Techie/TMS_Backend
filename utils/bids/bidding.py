from sqlalchemy import update
import datetime
import os

from utils.response import *
from config.db_config import Session
from models.models import *
from utils.db import *
from utils.utilities import *


class Bid:

    async def initiate(self):

        try:

            current_time = convert_date_to_string(datetime.datetime.now())
            bids_to_be_initiated = []

            (bids, error) = self.get_status_wise(status="live")

            if error:
                log("ERROR OCCURED DURING FETCH BIDS STATUSWISE", error)
                return

            for bid in bids:
                if convert_date_to_string(bid.created_at) == current_time:
                    bids_to_be_initiated.append(bid.bl_id)

            updated_bids = update(BiddingLoad).where(BiddingLoad.id.in_(
                bids_to_be_initiated)).values(BiddingLoad.load_status == "in_progress")

            log("BIDS ARE IN PROGRESS", bids)

        except Exception as e:
            log("ERROR DURING INITIATE BID", str(e))

        return

    async def get_status_wise(self, status: str) -> (any, str):

        session = Session()

        try:

            bids = (session.query(BiddingLoad, MapLoadSrcDestPair, LoadAssigned, Transporter)
                    .join(MapLoadSrcDestPair)
                    .join(LoadAssigned)
                    .join(LkpReason)
                    .join(Transporter)
                    .filter(BiddingLoad.load_status == status, BiddingLoad.is_active == True)
                    .filter(MapLoadSrcDestPair.mlsdp_bidding_load_id == BiddingLoad.bl_id)
                    .filter(LoadAssigned.la_bidding_load_id == BiddingLoad.bl_id)
                    .filter(Transporter.trnsp_id == LoadAssigned.la_transporter_id)
                    .all()
                    )

            return (bids, "")

        except Exception as e:
            session.rollback()
            return ({}, str(e))

        finally:
            session.close()

    async def is_valid(self, bid_id: str) -> (bool, str):

        session = Session()

        try:
            if not bid_id:
                return (False, "The Bid ID provided is empty")

            bid = session.query(BiddingLoad).filter(
                BiddingLoad.bl_id == bid_id, BiddingLoad.is_active == True).first()

            if not bid:
                return (False, "Bid ID not found!")

            return (True, "")

        except Exception as e:
            session.rollback()
            return (False, str(e))

        finally:
            session.close()

    async def update_status(self, bid_id: str, status: str) -> (bool, str):

        session = Session()

        try:

            updated_bid = (update(BiddingLoad)
                           .where(BiddingLoad.bl_id == bid_id)
                           .values(load_status=status)
                           )

            if not session.execute(updated_bid):
                return (False, "Bid status could not be updated!")

            return (True, "")

        except Exception as e:
            session.rollback()
            return (False, str(e))

        finally:
            session.close()

    async def create_table(self, bid_id: str) -> (bool, str):

        try:

            table_name = 't_' + bid_id.replace('-', '')

            (success, model_or_err) = await get_table_and_model(table_name)

            if success:
                append_model_to_file(model_or_err)
                return (True, "")
            return (False, model_or_err)

        except Exception as e:

            return (False, str(e))

    async def details(self, bid_id: str) -> (bool, str):

        session = Session()

        try:

            bid_details = await session.query(BiddingLoad).filter(BiddingLoad.bl_id == bid_id).first()

            if not bid_details:
                return False, ""

            return (True, bid_details)

        except Exception as e:
            session.rollback()
            return (False, str(e))

        finally:
            session.close()

    async def new_bid():
        pass

    async def decrement_on_lowest_price(self, bid_id: str, rate: float, decrement: float) -> (any, str):

        session = Session()

        try:
            (lowest_price, error) = self.lowest_price(bid_id=bid_id)

            if error:
                return ErrorResponse(data=[], dev_msg=str(error), client_msg=os.getenv("BID_SUBMIT_ERROR"))

            if (rate + decrement < lowest_price):
                return {{
                    "valid": True,
                }, ""}

            return ({
                "valid": False
            }, "Incorrect Bid price, has to be lower")

        except Exception as e:
            return ({}, str(e))

        finally:
            session.close()

    async def decrement_on_transporter_lowest_price(self, bid_id: str, transporter_id: str, rate: float, decrement: float) -> (any, str):

        session = Session()
        model = get_bid_model_name(bid_id=bid_id)

        try:
            bid = session.query(model).filter(
                model.transporter_id == transporter_id).order_by(model.created_at).first()

            if (bid.rate > rate + decrement):
                return {{
                    "valid": True,
                }, ""}

            return ({
                "valid": False
            }, "Incorrect Bid price, has to be lower")

        except Exception as e:
            return ({}, str(e))

        finally:
            session.close()

    async def lowest_price(self, bid_id: str) -> (float, str):

        session = Session()
        model = get_bid_model_name(bid_id)

        try:
            bid = session.query(model).order_by(model.rate).asc().first()
            return (bid.rate, "")

        except Exception as e:
            session.rollback()
            return (0, str(e))

        finally:
            session.close()

    async def close(self,):
        pass
