import math
import os
import ast
import pytz
from datetime import datetime, timedelta
from string import Template

from sqlalchemy import func, text, and_, select, or_, exists

from config.db_config import Session
from config.redis import r as redis
from config.scheduler import Scheduler
from data.bidding import (filter_wise_fetch_query, live_bid_details,
                          status_wise_fetch_query, transporter_analysis, assignment_events)
from models.models import (BiddingLoad, BidSettings, BidTransaction,
                           LoadAssigned, MapLoadSrcDestPair, ShipperModel,
                           TransporterModel, Segment, MapTransporterSegment, 
                           TrackingFleet, MapUser)
from schemas.bidding import FilterBidsRequest
from utils.redis import Redis
from utils.response import ErrorResponse
from utils.utilities import (add_filter, convert_date_to_string, log,
                             structurize, structurize_assignment_data,
                             structurize_bidding_stats,
                             structurize_confirmed_cancelled_trip_trend_stats,
                             structurize_transporter_bids)

sched = Scheduler()
redis = Redis()


class Bid:

    def initiate(self, shipper_id: str | None = None):

        session = Session()
        ist_timezone = pytz.timezone("Asia/Kolkata")
        current_time = convert_date_to_string(datetime.now(ist_timezone))

        try:

            bids = session.query(BiddingLoad).filter(
                BiddingLoad.is_active == True, BiddingLoad.load_status == "not_started")
            
            if shipper_id:
                bids = bids.filter(BiddingLoad.bl_shipper_id == shipper_id)
                
            bids = bids.all()
            
            log("THE BIDS TO INITIATE:", bids)
            if not bids:
                return

            for bid in bids:
                log("THE BID TIME", convert_date_to_string(bid.bid_time))
                log("THE CURRENT TIME", current_time)
                if convert_date_to_string(bid.bid_time) == current_time:
                    setattr(bid, "load_status", "live")
                    setattr(bid, "updated_at", "NOW()")

            session.commit()

            log("BIDS ARE IN PROGRESS", bids)
            return

        except Exception as e:
            session.rollback()
            log("ERROR DURING INITIATE BID", str(e))
            return

        finally:
            session.close()

    async def get_status_wise(self, status: str, shipper_id: str | None = None) -> (any, str):
        session = Session()

        try:

            filter_criteria = {
                "load_status": status
            }

            query = status_wise_fetch_query

            if shipper_id is not None:
                filter_criteria["shipper_id"] = shipper_id
                query += ' AND t_bidding_load.bl_shipper_id = :shipper_id'

            bid_array = session.execute(text(query), params=filter_criteria)

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
                'from_date_filter': ' AND t_bidding_load.bid_time > \'$from_date\'',
                'to_date_filter': ' AND t_bidding_load.bid_time <= \'$to_date\''
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

    async def update_status(self, bid_id: str, status: str, user_id: str, reason: str | None = None) -> (bool, str):

        session = Session()

        try:

            log("bid_id", bid_id)
            log("status", status)

            bid_to_be_updated = session.query(BiddingLoad).filter(
                BiddingLoad.bl_id == bid_id).first()

            if not bid_to_be_updated:
                return (False, "Bid requested could not be found")

            setattr(bid_to_be_updated, "load_status", status)
            setattr(bid_to_be_updated, "updated_at", "NOW()")
            setattr(bid_to_be_updated, "updated_by", user_id)

            if reason:
                setattr(bid_to_be_updated, "bl_cancellation_reason", reason)

            if bid_to_be_updated.bid_mode == "indent":
                assigning_load = LoadAssigned(
                    la_bidding_load_id = bid_to_be_updated.bl_id,
                    la_transporter_id = bid_to_be_updated.indent_transporter_id,
                    trans_pos_in_bid = 0,
                    price = bid_to_be_updated.indent_amount,
                    price_difference_percent = 0.0,
                    no_of_fleets_assigned = bid_to_be_updated.no_of_fleets,
                    is_assigned = True,
                )

                session.add(assigning_load)

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
                return (False, "Bid Details Not Found")

            return (True, bid_details)

        except Exception as e:
            session.rollback()
            return (False, str(e))

        finally:
            session.close()

    async def new(self, bid_id: str, transporter_id: str, rate: float, comment: str, user_id: str) -> (any, str):

        session = Session()

        try:

            attempt_number = 1
            last_comment = comment
            attempted = session.query(BidTransaction).filter(
                BidTransaction.transporter_id == transporter_id, BidTransaction.bid_id == bid_id).count()

            if attempted:
                attempt_number = attempted + 1

            if not comment:
                last_commented_bid = session.query(BidTransaction).filter(
                    BidTransaction.transporter_id == transporter_id, BidTransaction.bid_id == bid_id, BidTransaction.comment != None, BidTransaction.comment != ""
                ).order_by(BidTransaction.created_at.desc()).first()
                
                if last_commented_bid:
                    last_comment = last_commented_bid.comment
            

            bid = BidTransaction(
                bid_id=bid_id,
                transporter_id=transporter_id,
                rate=rate,
                comment=last_comment,
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

    async def decrement_on_lowest_price(self, bid_id: str, rate: float, decrement: float, is_decrement_in_percentage: bool) -> (any, str):

        session = Session()
        log("DECREMENTING ON CURRENT LOWEST PRICE")
        try:
            (lowest_price, error) = await self.lowest_price(bid_id=bid_id)

            log("LOWEST PRICE BEFORE CONVERT", lowest_price)

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

            log("LOWEST PRICE", lowest_price)
            log("DECREMENT", decrement)
            log("RATE", rate)

            if (rate + (math.ceil(decrement*lowest_price*0.01) if is_decrement_in_percentage else decrement) <= lowest_price):

                log("NEW RATE", rate + (math.ceil(decrement * lowest_price * 0.01) if is_decrement_in_percentage else decrement))

                log("BID RATE OK", rate)
                return ({
                    "valid": True,
                }, "")
            log("BID RATE NOT OK", rate)
            rupees_sign ="₹" if not is_decrement_in_percentage else ""
            percentage_sign = "%" if is_decrement_in_percentage else ""
            return ({
                "valid": False
            }, f"Incorrect Bid price, has to be lower, the decrement is {rupees_sign} {decrement} {percentage_sign}")

        except Exception as e:
            session.rollback()
            return ({}, str(e))

        finally:
            session.close()

    async def decrement_on_transporter_lowest_price(self, bid_id: str, transporter_id: str, rate: float, decrement: float, is_decrement_in_percentage: bool) -> (any, str):

        session = Session()

        try:
            bid = session.query(BidTransaction).filter(
                BidTransaction.transporter_id == transporter_id, BidTransaction.bid_id == bid_id).order_by(BidTransaction.rate).first()

            if not bid:
                return ({"valid": True}, "")

            log("TRANSPORTER BID RATE OK", bid)

            decrement = int(decrement)
            rate = int(rate)

            if (int(bid.rate) >= rate + (math.ceil(decrement*int(bid.rate)*0.01) if is_decrement_in_percentage else decrement)):
                return ({
                    "valid": True,
                }, "")
            log("TRANSPORTER BID RATE NOT VALID", bid)
            rupees_sign ="₹" if not is_decrement_in_percentage else ""
            percentage_sign = "%" if is_decrement_in_percentage else ""
            return ({
                "valid": False
            }, f"Incorrect Bid price, has to be lower,decrement is {rupees_sign} {decrement} {percentage_sign}")

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

    async def details_for_assignment(self, bid_id: str, transporter_id: str | None=None) -> (bool, any):

        session = Session()

        log("FETCHING DETAILS FOR ASSIGNMENT")

        try:

            bid_detail_arr = []

            details = (
                session.query(BidTransaction,
                              TransporterModel.name,
                              LoadAssigned
                              )
                .join(TransporterModel, TransporterModel.trnsp_id == BidTransaction.transporter_id)
                .outerjoin(LoadAssigned, LoadAssigned.la_bidding_load_id == BidTransaction.bid_id)
                .filter(BidTransaction.bid_id == bid_id)
            )

            if transporter_id:
                details = details.filter(BidTransaction.transporter_id == transporter_id)
                
            details = details.all()

            log("BID DETAILS FOR ASSIGNMENT", details)

            for bid in details:
                bid_details, transporter_name, load_assigned = bid

                obj = {
                    "bid_details": bid_details,
                    "transporter_name": transporter_name,
                    "load_assigned": load_assigned
                }
                bid_detail_arr.append(obj)

            log("Bid Details", bid_detail_arr)
            res = structurize_assignment_data(bid_detail_arr)

            if len(res) == 0:
                return (True, [])

            return (True, res[0])

        except Exception as e:
            session.rollback()
            return (False, str(e))
        finally:
            session.close()

    async def assign(self, bid_id: str, transporters: list, split: bool, status: str, user_id: str) -> (list, str):

        session = Session()

        try:

            transporter_ids = []
            fetched_transporter_ids = []
            assigned_transporters = []

            for transporter in transporters:
                transporter_ids.append(
                    getattr(transporter, "la_transporter_id"))

            transporter_details = session.query(LoadAssigned).filter(
                LoadAssigned.la_bidding_load_id == bid_id, LoadAssigned.la_transporter_id.in_(transporter_ids)).all()

            for transporter_detail in transporter_details:
                fetched_transporter_ids.append(
                    transporter_detail.la_transporter_id)

            transporters_not_assigned = list(
                set(transporter_ids) - set(fetched_transporter_ids))

            transporters_to_be_updated = list(
                set(transporter_ids).intersection(set(fetched_transporter_ids)))

            ist_timezone = pytz.timezone("Asia/Kolkata")
            current_time = datetime.now(ist_timezone)
            current_time = current_time.replace(
                tzinfo=None, second=0, microsecond=0)

            for transporter in transporters:
                if getattr(transporter, "la_transporter_id") in transporters_not_assigned:
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
                        history=str(
                            [(assignment_events["assign"], getattr(transporter, "no_of_fleets_assigned"), str(current_time), None)]),
                        is_assigned=True,
                        is_active=True,
                        created_by=user_id
                    )
                    assigned_transporters.append(assign_detail)

            for transporter_detail in transporter_details:
                log("TRANSPORTERS TO BE UPDATED", transporters_to_be_updated)
                if getattr(transporter_detail, "la_transporter_id") in transporters_to_be_updated:

                    for transporter in transporters:
                        if getattr(transporter, "la_transporter_id") == getattr(transporter_detail, "la_transporter_id"):

                            setattr(transporter_detail, "la_transporter_id", getattr(
                                transporter, "la_transporter_id"))
                            setattr(transporter_detail, "trans_pos_in_bid",
                                    getattr(transporter, "trans_pos_in_bid"))
                            setattr(transporter_detail, "price",
                                    getattr(transporter, "price"))
                            setattr(transporter_detail, "price_difference_percent", getattr(
                                transporter, "price_difference_percent"))
                            setattr(transporter_detail, "no_of_fleets_assigned", getattr(
                                transporter, "no_of_fleets_assigned"))
                            setattr(transporter_detail, "is_assigned", True)
                            setattr(transporter_detail, "is_active", True)
                            setattr(transporter_detail,
                                    "updated_at", str(current_time))
                            setattr(transporter_detail, "updated_by", user_id)
                            if not transporter_detail.history:
                                setattr(transporter_detail, "history", str(
                                    [(assignment_events["assign"],getattr(transporter, "no_of_fleets_assigned"), str(current_time), None)]))
                            else:
                                history_fetched = ast.literal_eval(
                                    getattr(transporter_detail, "history"))
                                task = (assignment_events["assign"],transporter.no_of_fleets_assigned,
                                        str(current_time), None)
                                history_fetched.append(task)
                                setattr(transporter_detail, "history",
                                        str(history_fetched))

            bid_details = session.query(BiddingLoad).filter(
                BiddingLoad.bl_id == bid_id).first()

            if not bid_details:
                return [], "Error While Fetching Bid Details"

            setattr(bid_details, "split", split)
            setattr(bid_details, "load_status", status)
            setattr(bid_details, "updated_at", "NOW()")

            session.bulk_save_objects(assigned_transporters)
            session.commit()

            if assigned_transporters:
                return (assigned_transporters, "")
            else:
                return ([], "")

        except Exception as e:
            session.rollback()
            return ([], str(e))

        finally:
            session.close()

    def close(self, shipper_id: str | None=None):

        session = Session()
        ist_timezone = pytz.timezone("Asia/Kolkata")
        current_time = convert_date_to_string(datetime.now(ist_timezone))

        try:

            bids = session.query(BiddingLoad).filter(
                BiddingLoad.is_active == True, BiddingLoad.load_status == "live")
            
            if shipper_id:
                bids = bids.filter(BiddingLoad.bl_shipper_id == shipper_id)
                
            bids = bids.all()
            
            log("THE BIDS TO CLOSE:", bids)

            if not bids:
                log("ERROR OCCURED DURING FETCH BIDS STATUSWISE TO CLOSE", bids)
                return

            for bid in bids:
                if convert_date_to_string(bid.bid_end_time) == current_time:
                    setattr(bid, "load_status", "pending")
                    setattr(bid, "updated_at", "NOW()")
                    # redis.delete(sorted_set=bid)

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
                return (False, "Setting Details not Found")

            return (True, setting_details)

        except Exception as e:
            session.rollback()
            return (False, str(e))

        finally:
            session.close()

    async def update_bid_end_time(self, bid_id: str, bid_end_time: datetime, extended_time: int) -> (any, str):

        session = Session()

        try:
            bid_details = session.query(BiddingLoad).filter(
                BiddingLoad.bl_id == bid_id).first()

            if not bid_details:
                return False, "Error While Fetching Bid Details"

            setattr(bid_details, "bid_end_time", bid_end_time)
            setattr(bid_details, "bid_extended_time", extended_time)

            session.commit()

            return (True, "")

        except Exception as e:
            session.rollback()
            return (False, str(e))

        finally:
            session.close()

    async def live_details(self, bid_id: str) -> (bool, any):

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

    async def public(self, blocked_shippers: list, transporter_id: str, status: str | None = None) -> (any, str):

        session = Session()

        try:

            statuses = ['pending', 'partially_confirmed'] if status == 'pending' else [status]

            bids_query = (session
                          .query(BiddingLoad,
                                 ShipperModel.shpr_id,
                                 ShipperModel.name,
                                 ShipperModel.contact_no,
                                 func.array_agg(MapLoadSrcDestPair.src_city),
                                 func.array_agg(MapLoadSrcDestPair.dest_city),
                                 func.array_agg(select(func.count())
                                                            .where(
                                                                TrackingFleet.tf_transporter_id == transporter_id,
                                                                TrackingFleet.tf_bidding_load_id == BiddingLoad.bl_id,
                                                                TrackingFleet.is_active == True  
                                                            )
                                                            .correlate(BiddingLoad)
                                                            .subquery()
                                                        ).label('tf_vehicle_count')
                                 )
                          .outerjoin(ShipperModel, ShipperModel.shpr_id == BiddingLoad.bl_shipper_id)
                          .outerjoin(MapLoadSrcDestPair, and_(MapLoadSrcDestPair.mlsdp_bidding_load_id == BiddingLoad.bl_id, MapLoadSrcDestPair.is_active == True))
                          .filter(BiddingLoad.is_active == True,  BiddingLoad.bid_mode == "open_market")
                          )

            if status:
                bids_query = bids_query.filter(
                    BiddingLoad.load_status.in_(statuses))

            bids = bids_query.group_by(BiddingLoad, *BiddingLoad.__table__.c,
                                       ShipperModel.name, ShipperModel.contact_no, ShipperModel.shpr_id ).all()
            log("BIDS IN PUBLIC", bids)
            if not bids:
                return ([], "")

            filtered_bids = []
            for bid in bids:
                (bid_load, shipper_id, _, _, _, _, _) = bid
                if shipper_id not in blocked_shippers:
                    filtered_bids.append(bid)
                    log("BID LOAD ID::", bid_load.bl_id)

            return (structurize_transporter_bids(bids=filtered_bids), "")

        except Exception as e:
            session.rollback()
            return ([], str(e))
        finally:
            session.close()

    async def private(self, shippers: any, transporter_id: str, user_id: str, status: str | None = None) -> (any, str):

        session = Session()

        try:

            statuses = ['pending', 'partially_confirmed'] if status == 'pending' else [status]

            bids_query = (session
                          .query(BiddingLoad,
                                 ShipperModel.shpr_id,
                                 ShipperModel.name,
                                 ShipperModel.contact_no,
                                 func.array_agg(MapLoadSrcDestPair.src_city),
                                 func.array_agg(MapLoadSrcDestPair.dest_city),
                                 func.array_agg(select(func.count())
                                                            .where(
                                                                TrackingFleet.tf_transporter_id == transporter_id,
                                                                TrackingFleet.tf_bidding_load_id == BiddingLoad.bl_id,
                                                                TrackingFleet.is_active == True  
                                                                  )
                                                            .correlate(BiddingLoad)
                                                            .subquery()
                                                ).label('tf_vehicle_count')
                                 )
                          .outerjoin(ShipperModel, ShipperModel.shpr_id == BiddingLoad.bl_shipper_id)
                          .outerjoin(MapLoadSrcDestPair, and_(MapLoadSrcDestPair.mlsdp_bidding_load_id == BiddingLoad.bl_id, MapLoadSrcDestPair.is_active == True))
                          .filter(BiddingLoad.is_active == True, 
                                  BiddingLoad.bl_shipper_id.in_(shippers), 
                                  BiddingLoad.bid_mode == "private_pool", 
                                  BiddingLoad.bl_segment_id == None,
                                  or_(BiddingLoad.bl_branch_id == None,
                                      exists()
                                      .where(
                                            MapUser.mpus_shipper_id == BiddingLoad.bl_shipper_id,
                                            MapUser.mpus_branch_id == BiddingLoad.bl_branch_id,
                                            MapUser.mpus_user_id == user_id,
                                            MapUser.is_active == True
                                            )
                                      )
                                  )
                          )

            if status:
                bids_query = bids_query.filter(
                    BiddingLoad.load_status.in_(statuses))

            bids = bids_query.group_by(BiddingLoad, *BiddingLoad.__table__.c,
                                       ShipperModel.name, ShipperModel.contact_no, ShipperModel.shpr_id ).all()

            if not bids:
                return (bids, "")
            return (structurize_transporter_bids(bids=bids), "")

        except Exception as e:
            session.rollback()
            return ([], str(e))
        finally:
            session.close()

    async def segment(self, shippers: any, transporter_id: str, user_id: str, status: str | None = None) -> (any, str):

        session = Session()

        try:

            statuses = ['pending', 'partially_confirmed'] if status == 'pending' else [status]

            (transporter_allowed_segments, error) = await self.segments(shippers= shippers, transporter_id= transporter_id)
            
            log("ERROR ::", error)
            if error:
                return([], error)
            
            bids_query = (session
                          .query(BiddingLoad,
                                 ShipperModel.shpr_id,
                                 ShipperModel.name,
                                 ShipperModel.contact_no,
                                 func.array_agg(MapLoadSrcDestPair.src_city),
                                 func.array_agg(MapLoadSrcDestPair.dest_city),
                                 func.array_agg(select(func.count())
                                                            .where(
                                                                TrackingFleet.tf_transporter_id == transporter_id,
                                                                TrackingFleet.tf_bidding_load_id == BiddingLoad.bl_id,
                                                                TrackingFleet.is_active == True  
                                                                  )
                                                            .correlate(BiddingLoad)
                                                            .subquery()
                                                ).label('tf_vehicle_count')
                                 )
                          .outerjoin(ShipperModel, ShipperModel.shpr_id == BiddingLoad.bl_shipper_id)
                          .outerjoin(MapLoadSrcDestPair, and_(MapLoadSrcDestPair.mlsdp_bidding_load_id == BiddingLoad.bl_id, MapLoadSrcDestPair.is_active == True))
                          .filter(BiddingLoad.is_active == True, 
                                  BiddingLoad.bl_segment_id.in_(transporter_allowed_segments), 
                                  BiddingLoad.bid_mode == "private_pool",
                                  or_(BiddingLoad.bl_branch_id == None,
                                      exists()
                                      .where(
                                            MapUser.mpus_shipper_id == BiddingLoad.bl_shipper_id,
                                            MapUser.mpus_branch_id == BiddingLoad.bl_branch_id,
                                            MapUser.mpus_user_id == user_id,
                                            MapUser.is_active == True
                                            )
                                      )
                                  )
                          )

            if status:
                bids_query = bids_query.filter(
                    BiddingLoad.load_status.in_(statuses))

            bids = bids_query.group_by(BiddingLoad, *BiddingLoad.__table__.c,
                                       ShipperModel.name, ShipperModel.contact_no, ShipperModel.shpr_id ).all()

            if not bids:
                return (bids, "")
            return (structurize_transporter_bids(bids=bids), "")

        except Exception as e:
            session.rollback()
            return ([], str(e))
        finally:
            session.close()

    async def segments(self, shippers: any, transporter_id: str) -> (any, str):

        session = Session()

        try:

            shipper_segments = (
                            session.query(Segment)
                            .filter(Segment.is_active == True, Segment.seg_shipper_id.in_(shippers))
                            .all()
                            )

            shipper_segment_ids = []
            for shipper_segment in shipper_segments:
                shipper_segment_ids.append(shipper_segment.seg_id)

            log("SHIPPER SEGMENTS ::", shipper_segment_ids)

            transporter_allowed_segments = (
                            session.query(MapTransporterSegment)
                            .filter(MapTransporterSegment.is_active == True, MapTransporterSegment.mts_segment_id.in_(shipper_segment_ids), MapTransporterSegment.mts_transporter_id == transporter_id)
                            .all()
                            )

            transporter_allowed_segment_ids = []

            for transporter_allowed_segment in transporter_allowed_segments:
                transporter_allowed_segment_ids.append(transporter_allowed_segment.mts_segment_id)

            log("TRANSPORTED ALLOWED SEGMENTS :", transporter_allowed_segment_ids)

            if not transporter_allowed_segment_ids:
                return ([],"")

            return (transporter_allowed_segment_ids, "")
            
        except Exception as e:
            session.rollback()
            return ([], str(e))
        finally:
            session.close()

    async def bidding_details(self, bid_id: str) -> (any, str):

        session = Session()

        try:

            bids = (session
                    .query(BidTransaction)
                    .filter(BidTransaction.bid_id == bid_id, BidTransaction.is_active == True)
                    .all()
                    )

            return (bids, "")

        except Exception as e:
            session.rollback()
            return ([], str(e))
        finally:
            session.close()

    async def stats(self, filter: FilterBidsRequest):

        session = Session()

        try:
            query = session.query(BiddingLoad).filter(
                BiddingLoad.is_active == True)

            query = add_filter(query=query, filter=filter)

            bids = query.all()

            return (structurize_bidding_stats(bids=bids), "")

        except Exception as e:
            session.rollback()
            return ([], str(e))
        finally:
            session.close()

    async def cancellation_reasons(self, filter: FilterBidsRequest):

        session = Session()

        try:
            query = session.query(BiddingLoad.bl_cancellation_reason, func.count(BiddingLoad.bl_cancellation_reason)).filter(
                BiddingLoad.load_status == "cancelled", BiddingLoad.is_active == True).group_by(BiddingLoad.bl_cancellation_reason)

            query = add_filter(query=query, filter=filter)

            cancellations = query.all()

            log("CANCELLATION", cancellations)
            if not cancellations:
                return (cancellations, "")
            result = []
            for cancellation in cancellations:
                result.append({
                    'reason': cancellation[0],
                    'count': cancellation[1]
                })

            return (result, "")

        except Exception as e:
            session.rollback()
            return ([], str(e))
        finally:
            session.close()

    async def transporter_analysis(self, filter: FilterBidsRequest):

        session = Session()
        results = []

        try:

            where_conditions = []

            query = transporter_analysis

            if filter.shipper_id:
                where_conditions.append(f'tbl.bl_shipper_id = :shipper_id')

            if filter.rc_id:
                where_conditions.append(f'tbl.bl_region_cluster_id = :rc_id')

            if filter.branch_id:
                where_conditions.append(f'tbl.branch_id = :branch_id')

            if filter.from_date:
                where_conditions.append(f'tbl.created_at >= :from_date')

            if filter.to_date:
                where_conditions.append(f'tbl.created_at <= :to_date')

            if where_conditions:
                query += ' WHERE ' + ' AND '.join(where_conditions)

            query += ''' GROUP BY tt."name";'''

            query = text(query)

            params = {
                'shipper_id': filter.shipper_id,
                'rc_id': filter.rc_id,
                'branch_id': filter.branch_id,
                'from_date': filter.from_date,
                'to_date': filter.to_date,
            }

            transporters = session.execute(query, params=params).all()

            if not transporters:
                return ([], "")

            log(transporters)
            for transporter in transporters:
                name, participated, selected, avg_assignment_delay = transporter
                if avg_assignment_delay is not None and avg_assignment_delay != 'E':
                    avg_assignment_delay = int(avg_assignment_delay)

                results.append({
                    "name": name,
                    "participated": participated,
                    "selected": selected,
                    "assignment_delay": avg_assignment_delay if avg_assignment_delay is not None else None
                })

            return (results, "")

        except Exception as e:
            session.rollback()
            return ([], str(e))
        finally:
            session.close()

    async def confirmed_cancelled_bid_trend_stats(self, filter: FilterBidsRequest, type: str):

        session = Session()

        try:
            query = session.query(BiddingLoad).filter(BiddingLoad.load_status.in_(
                ['confirmed', 'cancelled']), BiddingLoad.is_active == True)

            query = add_filter(query=query, filter=filter)

            bids = query.all()

            return (structurize_confirmed_cancelled_trip_trend_stats(bids=bids, filter=filter, type=type), "")

        except Exception as e:
            session.rollback()
            return ([], str(e))
        finally:
            session.close()

    async def assigned_load_details(self, bid_ids: any, transporter_id: str):

        session = Session()

        try:

            load_assignment_details = []

            assigned_load_details = session.query(LoadAssigned).filter(LoadAssigned.la_bidding_load_id.in_(bid_ids), LoadAssigned.la_transporter_id == transporter_id, LoadAssigned.is_active).all()

            for bid_id in bid_ids:
                assigned_load_details_for_bid_id = next((assigned_load for assigned_load in assigned_load_details if assigned_load.la_bidding_load_id == bid_id), None)
                
                if assigned_load_details_for_bid_id:
                    load_assignment_detail = {
                                                "bid_id":bid_id, 
                                                "la_id": assigned_load_details_for_bid_id.la_id,
                                                "la_bidding_load_id": assigned_load_details_for_bid_id.la_bidding_load_id,
                                                "la_transporter_id": assigned_load_details_for_bid_id.la_transporter_id,
                                                "is_assigned": assigned_load_details_for_bid_id.is_assigned,
                                                "price": assigned_load_details_for_bid_id.price,
                                                "pmr_price": assigned_load_details_for_bid_id.pmr_price,
                                                "pmr_comment": assigned_load_details_for_bid_id.pmr_comment,
                                                "is_pmr_approved": assigned_load_details_for_bid_id.is_pmr_approved,
                                                "is_negotiated_by_aculead": assigned_load_details_for_bid_id.is_negotiated_by_aculead
                                                }
                else:
                    load_assignment_detail = {
                                                "bid_id":bid_id,
                                                "la_id": None,
                                                "la_bidding_load_id": None,
                                                "la_transporter_id": None,
                                                "is_assigned": None,
                                                "price": None,
                                                "pmr_price": None,
                                                "pmr_comment": None,
                                                "is_pmr_approved": None,
                                                "is_negotiated_by_aculead": None
                                                } 

                load_assignment_details.append(load_assignment_detail)
                
            return (load_assignment_details, "")
        except Exception as e:
            session.rollback()
            return ([], str(e))
        finally:
            session.close()
