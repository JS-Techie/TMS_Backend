from sqlalchemy.sql.functions import func
from datetime import datetime, timedelta
import os, math

from sqlalchemy import text
from string import Template
import json
from collections import defaultdict

from utils.response import ErrorResponse
from config.db_config import Session
from models.models import BiddingLoad, MapLoadSrcDestPair, LoadAssigned, TransporterModel, LkpReason, BidTransaction, MapLoadMaterial, LkpMaterial, PriceMatchRequest, WorkflowApprovals, Tracking, TrackingFleet, MapShipperTransporter, BidSettings
from utils.utilities import log, convert_date_to_string, structurize, structurize_assignment_data
from config.redis import r as redis
from utils.redis import Redis
from data.bidding import status_wise_fetch_query, filter_wise_fetch_query,live_bid_details
from schemas.bidding import FilterBidsRequest
from config.scheduler import Scheduler
from utils.utilities import log

sched = Scheduler()
redis = Redis()


class Bid:

    def initiate(self):

        session = Session()
        current_time = convert_date_to_string(
            datetime.now()+timedelta(minutes=1))

        try:

            bids = (session.query(BiddingLoad).filter(
                BiddingLoad.is_active == True, BiddingLoad.load_status == "not_started").all())
            log("THE BIDS TO INITIATE:", bids)
            if not bids:
                log("ERROR OCCURED DURING FETCH BIDS STATUSWISE")
                return

            for bid in bids:
                log("THE BID TIME", convert_date_to_string(bid.bid_time))
                log("THE CURRENT TIME", current_time)
                if convert_date_to_string(bid.bid_time) == current_time:
                    setattr(bid, "load_status", "live")

            session.commit()

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

            bid_array = session.execute(text(status_wise_fetch_query), params={
                                        "load_status": status})

            rows = bid_array.fetchall()

            log("BIDS", rows)
            b_arr = []
            for row in rows:
                log("ROW", row.bl_id)
                b_arr.append(row._mapping)

            return (structurize(b_arr), "")

        except Exception as e:
            session.rollback()
            return ({}, str(e))

        finally:
            session.close()

    async def get_filter_wise(self, status: str, filter_criteria: FilterBidsRequest) -> (any, str):
        session = Session()

        try:

            filter_values = {
                'shipper_id_filter': ' AND t_bidding_load.bl_shipper_id = \'$shipper_id\'',
                'regioncluster_id_filter': ' AND t_bidding_load.bl_region_cluster_id = \'$region_cluster_id\'',
                'branch_id_filter': ' AND t_bidding_load.bl_branch_id = \'$branch_id\'',
                'from_date_filter': ' AND t_bidding_load.created_at > \'$from_date\'',
                'to_date_filter': ' AND t_bidding_load.created_at <= \'$to_date\''
            }

            filter_values["shipper_id_filter"] = Template(filter_values['shipper_id_filter']).safe_substitute(
                shipper_id=filter_criteria.shipper_id) if filter_criteria.shipper_id else ""
            filter_values["regioncluster_id_filter"] = Template(filter_values["regioncluster_id_filter"]).safe_substitute(
                region_cluster_id=filter_criteria.rc_id) if filter_criteria.rc_id else ""
            filter_values["branch_id_filter"] = Template(filter_values["branch_id_filter"]).safe_substitute(
                branch_id=filter_criteria.branch_id) if filter_criteria.branch_id else ""
            filter_values["from_date_filter"] = Template(filter_values["from_date_filter"]).safe_substitute(
                from_date=filter_criteria.from_date) if filter_criteria.from_date else ""
            filter_values["to_date_filter"] = Template(filter_values["to_date_filter"]).safe_substitute(
                to_date=filter_criteria.to_date) if filter_criteria.to_date else ""

            filter_wise_query = Template(
                filter_wise_fetch_query).safe_substitute(filter_values)
            log("QUERY >>>>", filter_wise_query)
            bid_array = session.execute(text(filter_wise_query), params={
                                        "load_status": status})

            rows = bid_array.fetchall()

            log("BIDS", rows)
            b_arr = []
            for row in rows:
                log("ROW", row.bl_id)
                b_arr.append(row._mapping)

            return (structurize(b_arr), "")

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

            log("BID ID WAS PROVIDED", bid_id)

            bid = session.query(BiddingLoad).filter(
                BiddingLoad.bl_id == bid_id, BiddingLoad.is_active == True).first()

            if not bid:
                log("BID ID NOT FOUND IN BIDDING LOADS")
                return (False, "Bid ID not found!")

            log("BID ID FOUND")

            return (True, "")

        except Exception as e:
            session.rollback()
            log(str(e))
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

    async def details(self, bid_id: str) -> (bool, any):

        session = Session()

        try:

            bid_details = session.query(BiddingLoad).filter(
                BiddingLoad.bl_id == bid_id).first()
            log("BID DETIALS >>", bid_details)
            if not bid_details:
                return (False, {})

            return (True, bid_details)

        except Exception as e:
            session.rollback()
            return (False, str(e))

        finally:
            session.close()

    async def new(self, bid_id: str, transporter_id: str, rate: float, comment: str) -> (any, str):

        session = Session()
        user_id = os.getenv("USER_ID")

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
                attempt_number=attempt_number,
                created_by=user_id
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
        log("DECREMENTING ON CURRENT LOWEST PRICE")
        try:
            (lowest_price, error) = await self.lowest_price(bid_id=bid_id)

            log("LOWEST PRICE BEFORE CONVERT",lowest_price)

            if error:
                return ErrorResponse(data=[], dev_msg=str(error), client_msg=os.getenv("BID_SUBMIT_ERROR"))
            
            if lowest_price == float("inf"):
                log("LOWEST PRICE INFINITY")
                return ({
                    "valid": True,
                }, "") 
            
            lowest_price = int(lowest_price)
            decrement = int(decrement)
            rate = int(rate)

            log("LOWEST PRICE",lowest_price)
            log("DECREMENT",decrement)
            log("RATE",rate)



            if (rate + math.ceil(decrement*lowest_price*0.01) <= lowest_price):

                log("NEW RATE",rate + math.ceil(decrement * lowest_price * 0.01))

                log("BID RATE OK", rate)
                return ({
                    "valid": True,
                }, "")
            log("BID RATE NOT OK", rate)
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
            if not bid:
                return ({"valid": True}, "")
            log("TRANSPORTER BID RATE OK", bid)

            decrement = int(decrement)
            rate = int(rate)
            
            if (int(bid.rate) >= rate + math.ceil(decrement*int(bid.rate)*0.01)):
                return ({
                    "valid": True,
                }, "")
            log("TRANSPORTER BID RATE NOT VALID", bid)
            return ({
                "valid": False
            }, "Incorrect Bid price, has to be lower")

        except Exception as e:
            session.rollback()
            return ({}, str(e))

        finally:
            session.close()

    async def lowest_price(self, bid_id: str) -> (float, str):
        log("FETCHING LOWEST PRICE FROM DB")
        session = Session()

        try:
            bid = session.query(BidTransaction).filter(
                BidTransaction.bid_id == bid_id).order_by(BidTransaction.rate.asc()).first()

            if not bid:
                return (float("inf"), "")
            
            log("BID DETAILS OK", bid)
            return (bid.rate, "")

        except Exception as e:
            session.rollback()
            return (0, str(e))

        finally:
            session.close()

    async def details_for_assignment(self, bid_id: str) -> (bool, any):

        session = Session()

        try:

            bid_detail_arr = []

            details = (
                session.query(BidTransaction,
                              TransporterModel.name,
                            PriceMatchRequest.pmr_price,
                            LoadAssigned
                            )
                .join(TransporterModel, TransporterModel.trnsp_id == BidTransaction.transporter_id)
                .outerjoin(PriceMatchRequest, PriceMatchRequest.pmr_bidding_load_id == BidTransaction.bid_id)
                .outerjoin(LoadAssigned,LoadAssigned.la_bidding_load_id == BidTransaction.bid_id)
                .filter(BidTransaction.bid_id == bid_id)
                .all()
            )

            # log("DETAILS",details)

            for bid in details:
                bid_details, transporter_name,price_match_rate,load_assigned = bid
                # price_match_rate, load_assigned 

                obj = {
                    "bid_details": bid_details,
                    "transporter_name": transporter_name,
                    "price_match_rate": price_match_rate,
                    "load_assigned":load_assigned
                }

                bid_detail_arr.append(obj)

            return (True, structurize_assignment_data(bid_detail_arr))

            # return(True,bid_detail_arr)

        except Exception as e:
            session.rollback()
            return (False, str(e))
        finally:
            session.close()

    async def status_update(self, bid_id: str, split: bool, status: str) -> (bool, str):

        session = Session()
        try:
            
            bid_details = session.query(BiddingLoad).filter(
                BiddingLoad.bl_id == bid_id).first()

            if not bid_details:
                return False, "Error While Fetching Bid Details"

            setattr(bid_details, "split", split)
            setattr(bid_details, "load_status", status)

            session.commit()

            return (True, "")

        except Exception as e:
            session.rollback()
            return (False, str(e))

        finally:
            session.close()

    async def assign(self, bid_id: str, transporters: list) -> (list, str):

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
                    la_bidding_load_id=bid_id,
                    la_transporter_id=getattr(
                        transporter, "la_transporter_id"),
                    trans_pos_in_bid=getattr(
                        transporter, "trans_pos_in_bid"),
                    price=getattr(transporter, "price"),
                    price_difference_percent=getattr(
                        transporter, "price_difference_percent"),
                    no_of_fleets_assigned=getattr(
                        transporter, "no_of_fleets_assigned"),
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

    def close(self):

        session = Session()
        current_time = convert_date_to_string(
            datetime.now()+timedelta(minutes=1))

        try:

            bids = (session.query(BiddingLoad).filter(
                BiddingLoad.is_active == True, BiddingLoad.load_status == "live").all())
            log("THE BIDS TO CLOSE:", bids)

            if not bids:
                log("ERROR OCCURED DURING FETCH BIDS STATUSWISE TO CLOSE", bids)
                return

            for bid in bids:
                if convert_date_to_string(bid.bid_end_time) == current_time:
                    setattr(bid, "load_status", "pending")
                    # MEHUL : No checks here because if there is no sorted set then it will return false too, so how to catch exception ?
                    redis.delete(sorted_set=bid)

            session.commit()

            return

        except Exception as e:
            session.rollback()
            log("ERROR DURING CLOSE BID", str(e))
            return

        finally:
            session.close()

    async def setting_details(self, shipper_id: str) -> (bool, str):

        session = Session()

        try:

            setting_details = session.query(BidSettings).filter(
                BidSettings.bdsttng_shipper_id == shipper_id).first()

            if not setting_details:
                return False, ""

            return (True, setting_details)

        except Exception as e:
            session.rollback()
            return (False, str(e))

        finally:
            session.close()

    async def update_bid_end_time(self, bid_id: str, bid_end_time: datetime) -> (any, str):

        session = Session()

        try:
            bid_details = session.query(BiddingLoad).filter(
                BiddingLoad.bl_id == bid_id).first()

            if not bid_details:
                return False, "Error While Fetching Bid Details"

            setattr(bid_details, "bid_end_time", bid_end_time)

            session.commit()

            return (True, "")

        except Exception as e:
            session.rollback()
            return (False, str(e))

        finally:
            session.close()

    async def live_details(self,bid_id : str) -> (bool,any):

        session = Session()

        try:
            
            bid_details = session.execute(text(live_bid_details), params={
                                        "bid_id": bid_id})

            if not bid_details:
                return ({}, "Error While Fetching Bid Details")

            return (bid_details, "")

        except Exception as e:
            session.rollback()
            return (False, str(e))

        finally:
            session.close()