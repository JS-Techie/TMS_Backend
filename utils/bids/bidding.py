from sqlalchemy.sql.functions import func
import datetime,os

from utils.response import ErrorResponse
from config.db_config import Session
from models.models import BiddingLoad, MapLoadSrcDestPair, LoadAssigned, TransporterModel, LkpReason, BidTransaction, MapLoadMaterial, LkpMaterial, PriceMatchRequest
from utils.utilities import log, convert_date_to_string
from config.scheduler import Scheduler

sched = Scheduler()


class Bid:

    async def initiate(self):

        session = Session()
        current_time = convert_date_to_string(datetime.datetime.now())
        bids_to_be_initiated = []

        try:

            (bids, error) = self.get_status_wise(status="not_started")

            if error:
                log("ERROR OCCURED DURING FETCH BIDS STATUSWISE", error)
                return

            for bid in bids:
                if convert_date_to_string(bid.bid_time) == current_time:
                    bids_to_be_initiated.append(bid.bl_id)

            for bid in bids_to_be_initiated:
                setattr(bid, "load_status", "live")

            session.commit()

            scheduler = sched.new_scheduler()
            scheduler.add_job(
                func=self.close, trigger="interval", id="close-bid", minutes=1)
            sched.start(scheduler=scheduler)

            log("BIDS ARE IN PROGRESS", bids)
            return

        except Exception as e:
            session.rollback()
            log("ERROR DURING INITIATE BID", str(e))
            return

        finally:
            session.close()

    async def get_status_wise(self, status: str) -> (any, str):

        session = Session()

        try:

            all_bid_details = (session
                               .query(BiddingLoad, func.array_agg(MapLoadMaterial.mlm_material_id), func.array_agg(LkpMaterial.name), func.array_agg(MapLoadSrcDestPair), func.array_agg(PriceMatchRequest), func.array_agg(LoadAssigned))
                               .outerjoin(MapLoadMaterial, MapLoadMaterial.mlm_bidding_load_id == BiddingLoad.bl_id)
                               .outerjoin(LkpMaterial, MapLoadMaterial.mlm_material_id == LkpMaterial.id)
                               .outerjoin(MapLoadSrcDestPair, MapLoadSrcDestPair.mlsdp_bidding_load_id == BiddingLoad.bl_id)
                               .outerjoin(PriceMatchRequest, PriceMatchRequest.pmr_bidding_load_id == BiddingLoad.bl_id)
                               .outerjoin(LoadAssigned, LoadAssigned.la_bidding_load_id == BiddingLoad.bl_id)
                               .filter
                               (BiddingLoad.is_active == True, BiddingLoad.load_status == status,
                                MapLoadMaterial.is_active == True,
                                MapLoadSrcDestPair.is_active == True,
                                PriceMatchRequest.is_active == True,
                                LoadAssigned.is_active == True)
                               .group_by(BiddingLoad.bl_id)
                               .all())

            bid_array = []

            for detail in all_bid_details:
                bid_details, material_ids, material_details, source_dest, price_match_req, assigned_loads = detail
                bid_array.append({"bid": bid_details, "load_material": material_ids, "lkp_material": material_details,
                                 "Map_load_src_dest_pair": source_dest, "PriceMatchRequest": price_match_req, "LoadAssigned": assigned_loads})

            log("BIDS", bid_array)
    

            return (bid_array, "")

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

            log("bid_id", bid_id)
            log("status", status)

            bid_to_be_updated = session.query(BiddingLoad).filter(
                BiddingLoad.bl_id == bid_id).first()

            if not bid_to_be_updated:
                return (False, "Bid requested could not be found")

            setattr(bid_to_be_updated, "load_status", status)
            session.commit()

            return (True, "")

        except Exception as e:
            session.rollback()
            return (False, str(e))

        finally:
            session.close()

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

    async def new_bid(self, bid_id: str, transporter_id: str, rate: float, comment: str) -> (any, str):

        session = Session()

        try:

            attempt_number = 0
            attempted = session.query(BidTransaction).filter(
                BidTransaction.transporter_id == transporter_id, BidTransaction.bid_id == bid_id).order_by(BidTransaction.created_at.desc()).first()

            if attempted:
                attempt_number = attempted.attempt_number + 1

            bid = BidTransaction(
                bid_id=bid_id,
                transporter_id=transporter_id,
                rate=rate,
                comment=comment,
                attempt_number=attempt_number
            )

            session.add(bid)
            session.commit()
            session.refresh(bid)

            return (bid, "")

        except Exception as e:
            session.rollback()
            return ({}, str(e))
        finally:
            session.close()

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
            session.rollback()
            return ({}, str(e))

        finally:
            session.close()

    async def decrement_on_transporter_lowest_price(self, bid_id: str, transporter_id: str, rate: float, decrement: float) -> (any, str):

        session = Session()

        try:
            bid = session.query(BidTransaction).filter(
                BidTransaction.transporter_id == transporter_id, BidTransaction.bid_id == bid_id).order_by(BidTransaction.created_at).first()

            if (bid.rate > rate + decrement):
                return {{
                    "valid": True,
                }, ""}

            return ({
                "valid": False
            }, "Incorrect Bid price, has to be lower")

        except Exception as e:
            session.rollback()
            return ({}, str(e))

        finally:
            session.close()

    async def lowest_price(self, bid_id: str) -> (float, str):

        session = Session()

        try:
            bid = session.query(BidTransaction).filter(
                BidTransaction.bid_id == bid_id).order_by(BidTransaction.rate.asc()).first()
            return (bid.rate, "")

        except Exception as e:
            session.rollback()
            return (0, str(e))

        finally:
            session.close()

    async def close(self):

        session = Session()
        current_time = convert_date_to_string(datetime.datetime.now())
        bids_to_be_closed = []

        try:
            (bids, error) = self.get_status_wise(status="live")

            if error:
                log("ERROR OCCURED DURING FETCH BIDS STATUSWISE", error)
                return

            for bid in bids:
                if convert_date_to_string(bid.bid_end_time) == current_time:
                    bids_to_be_closed.append(bid.bl_id)

            for bid in bids_to_be_closed:
                setattr(bid, "load_status", "pending")

            return

        except Exception as e:
            session.rollback()
            log("ERROR DURING CLOSE BID", str(e))
            return

        finally:
            session.close()

    async def assign(bid_id: str, transporters: list) -> (list, str):

        session = Session()
        user_id = os.getenv("USER_ID")
        # user["id"]

        try:

            transporter_ids = []
            assigned_transporters = []
            for transporter in transporters:
                transporter_ids.append(
                    getattr(transporter, "la_transporter_id"))
                assign_detail = LoadAssigned(
                    la_bidding_load_id=getattr(
                        transporter, "la_bidding_load_id "),
                    la_transporter_id=getattr(
                        transporter, "la_transporter_id "),
                    trans_pos_in_bid=getattr(transporter, "trans_pos_in_bid "),
                    price=getattr(transporter, "price "),
                    price_difference_percent=getattr(
                        transporter, "price_difference_percent "),
                    no_of_fleets_assigned=getattr(
                        transporter, "no_of_fleets_assigned "),
                    created_by=user_id
                )
                assigned_transporters.append(assign_detail)

            transporter_details = session.query(LoadAssigned).filter(
                LoadAssigned.la_bidding_load_id == bid_id, LoadAssigned.la_transporter_id.in_(transporter_ids)).all()

            if transporter_details:
                return ("", "Bid already assigned to same Transporter")

            session.bulk_save_objects(assigned_transporters)
            session.commit()

            return (assigned_transporters, None)

        except Exception as e:
            session.rollback()
            return (False, str(e))

        finally:
            session.close()

