from sqlalchemy.sql.functions import func
from datetime import datetime,timedelta
import os
from sqlalchemy import text
import json

from utils.response import ErrorResponse
from config.db_config import Session
from models.models import BiddingLoad, MapLoadSrcDestPair, LoadAssigned, TransporterModel, LkpReason, BidTransaction, MapLoadMaterial, LkpMaterial, PriceMatchRequest, WorkflowApprovals, Tracking, TrackingFleet, MapShipperTransporter, BidSettings
from utils.utilities import log, convert_date_to_string, structurize
from config.redis import r as redis
from utils.redis import Redis
from config.scheduler import Scheduler

sched = Scheduler()
redis = Redis()


class Bid:

    def initiate(self):

        session = Session()
        current_time = convert_date_to_string(datetime.now()+timedelta(minutes=1))
        bids_to_be_initiated = []

        try:

            bids=(session.query(BiddingLoad).filter(BiddingLoad.is_active == True, BiddingLoad.load_status == "not_started").all())
            log("THE BIDS TO INITIATE:", bids)
            if not bids:
                log("ERROR OCCURED DURING FETCH BIDS STATUSWISE")
                return

            for bid in bids:
                log("THE BID TIME",convert_date_to_string(bid.bid_time))
                log("THE CURRENT TIME", current_time)
                if convert_date_to_string(bid.bid_time) == current_time:                    
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
            

    def close(self):

        session = Session()
        current_time = convert_date_to_string(datetime.now()+timedelta(minutes=1))

        try:

            bids=(session.query(BiddingLoad).filter(BiddingLoad.is_active == True, BiddingLoad.load_status == "live").all())
            log("THE BIDS TO CLOSE:", bids)

            if not bids:
                log("ERROR OCCURED DURING FETCH BIDS STATUSWISE TO CLOSE", bids)
                return

            for bid in bids:
                if convert_date_to_string(bid.bid_end_time) == current_time:
                    setattr(bid, "load_status", "pending")
                    redis.delete(sorted_set=bid) ##MEHUL : No checks here because if there is no sorted set then it will return false too, so how to catch exception ?
            
            session.commit()
            
            return

        except Exception as e:
            session.rollback()
            log("ERROR DURING CLOSE BID", str(e))
            return

        finally:
            session.close()


    async def get_status_wise(self, status: str) -> (any, str):
        session = Session()

        try:
            
            bid_array = session.execute(text("""
            SELECT
                t_bidding_load.bl_id,
                t_bidding_load.bid_time,
                t_bidding_load.reporting_from_time,
                t_bidding_load.reporting_to_time,
                t_bidding_load.load_type,
                t_bidding_load.bl_cancellation_reason,
                t_map_load_src_dest_pair.src_city,
                t_map_load_src_dest_pair.dest_city,
                t_load_assigned.la_transporter_id,
                t_load_assigned.trans_pos_in_bid,
                t_load_assigned.price,
                t_load_assigned.price_difference_percent,
                t_load_assigned.no_of_fleets_assigned,
                t_transporter.name,
                t_transporter.contact_name,
                t_transporter.contact_no,
                t_tracking_fleet.tf_id,
                t_tracking_fleet.fleet_no,
                t_tracking_fleet.src_addrs,
                t_tracking_fleet.dest_addrs
            FROM t_bidding_load
            LEFT JOIN t_load_assigned ON t_load_assigned.la_bidding_load_id = t_bidding_load.bl_id
            LEFT JOIN t_transporter ON t_transporter.trnsp_id = t_load_assigned.la_transporter_id
            LEFT JOIN t_map_load_src_dest_pair ON t_map_load_src_dest_pair.mlsdp_bidding_load_id = t_bidding_load.bl_id
            LEFT JOIN t_tracking_fleet ON t_tracking_fleet.tf_transporter_id = t_load_assigned.la_transporter_id
            WHERE
                t_bidding_load.is_active = true
                AND t_bidding_load.load_status = :load_status;"""), params={"load_status": status})
            
            rows=bid_array.fetchall()

            log("BIDS", rows)
            b_arr = []
            for row in rows:
                log("ROW",row.bl_id)
                b_arr.append(row._mapping)
                
            return (structurize(b_arr), "")
        
        except Exception as e:
            session.rollback()
            return ({}, str(e))

        finally:
            session.close()



    async def get_filter_wise(status: str, shipper_id: str, regioncluster_id: str, branch_id: str, from_date: datetime, to_date: datetime) -> (any, str):
        session = Session()

        try:

            bid_array = session.execute(text("""
            SELECT
                t_bidding_load.bl_id,
                t_bidding_load.bid_time,
                t_bidding_load.reporting_from_time,
                t_bidding_load.reporting_to_time,
                t_bidding_load.load_type,
                t_bidding_load.bl_cancellation_reason,
                t_map_load_src_dest_pair.src_city,
                t_map_load_src_dest_pair.dest_city,
                t_load_assigned.la_transporter_id,
                t_load_assigned.trans_pos_in_bid,
                t_load_assigned.price,
                t_load_assigned.price_difference_percent,
                t_load_assigned.no_of_fleets_assigned,
                t_transporter.name,
                t_transporter.contact_name,
                t_transporter.contact_no,
                t_tracking_fleet.tf_id,
                t_tracking_fleet.fleet_no,
                t_tracking_fleet.src_addrs,
                t_tracking_fleet.dest_addrs
            FROM t_bidding_load
            LEFT JOIN t_load_assigned ON t_load_assigned.la_bidding_load_id = t_bidding_load.bl_id
            LEFT JOIN t_transporter ON t_transporter.trnsp_id = t_load_assigned.la_transporter_id
            LEFT JOIN t_map_load_src_dest_pair ON t_map_load_src_dest_pair.mlsdp_bidding_load_id = t_bidding_load.bl_id
            LEFT JOIN t_tracking_fleet ON t_tracking_fleet.tf_transporter_id = t_load_assigned.la_transporter_id
            WHERE
                t_bidding_load.is_active = true
                AND t_bidding_load.load_status = :load_status;"""), params={"load_status": status})
            
            rows=bid_array.fetchall()

            log("BIDS", rows)
            b_arr = []
            for row in rows:
                log("ROW",row.bl_id)
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

            bid_details = session.query(BiddingLoad).filter(
                BiddingLoad.bl_id == bid_id).first()
            log("BID DETIALS >>", bid_details)
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

        try:
            (lowest_price, error) = await self.lowest_price(bid_id=bid_id)

            if error:
                return ErrorResponse(data=[], dev_msg=str(error), client_msg=os.getenv("BID_SUBMIT_ERROR"))

            if (rate + decrement <= lowest_price):
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
            if (bid.rate >= rate + decrement):
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

    async def update_bid_status(self, bid_id: str) -> (bool, str):

        session = Session()
        try:
            bid_details = session.query(BiddingLoad).filter(
                BiddingLoad.bl_id == bid_id).first()

            if not bid_details:
                return False, "Error While Fetching Bid Details"

            setattr(bid_details, "split", True)
            setattr(bid_details, "load_status", "confirmed")

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

    async def bid_setting_details(self, shipper_id: str) -> (bool, str):

        session = Session()

        try:

            bid_setting_details = session.query(BidSettings).filter(
                BidSettings.bdsttng_shipper_id == shipper_id).first()

            if not bid_setting_details:
                return False, ""

            return (True, bid_setting_details)

        except Exception as e:
            session.rollback()
            return (False, str(e))

        finally:
            session.close()

    async def update_bid_end_time(self, bid_id: str, bid_end_time: datetime) -> (bool, str):

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
