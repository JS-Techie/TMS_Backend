import math
import os
from datetime import datetime
from string import Template

from sqlalchemy import func, text

from config.db_config import Session
from config.redis import r as redis
from config.scheduler import Scheduler
from data.bidding import (filter_wise_fetch_query, live_bid_details,
                          status_wise_fetch_query, transporter_analysis)
from models.models import (BiddingLoad, BidSettings, BidTransaction,
                           LoadAssigned, MapLoadSrcDestPair, ShipperModel,
                           TransporterModel)
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

    def initiate(self):

        session = Session()
        current_time = convert_date_to_string(
            datetime.now())

        try:

            bids = (session.query(BiddingLoad).filter(
                BiddingLoad.is_active == True, BiddingLoad.load_status == "not_started").all())
            log("THE BIDS TO INITIATE:", bids)
            if not bids:
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
            setattr(bid_to_be_updated, "updated_by", user_id)

            if reason:
                setattr(bid_to_be_updated, "bl_cancellation_reason", reason)

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

    async def new(self, bid_id: str, transporter_id: str, rate: float, comment: str, user_id: str) -> (any, str):

        session = Session()

        try:

            attempt_number = 1
            attempted = session.query(BidTransaction).filter(
                BidTransaction.transporter_id == transporter_id, BidTransaction.bid_id == bid_id).count()

            if attempted:
                attempt_number = attempted + 1

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

            if (rate + math.ceil(decrement*lowest_price*0.01) <= lowest_price):

                log("NEW RATE", rate + math.ceil(decrement * lowest_price * 0.01))

                log("BID RATE OK", rate)
                return ({
                    "valid": True,
                }, "")
            log("BID RATE NOT OK", rate)
            return ({
                "valid": False
            }, f"Incorrect Bid price, has to be lower, the decrement is {decrement} %")

        except Exception as e:
            session.rollback()
            return ({}, str(e))

        finally:
            session.close()

    async def decrement_on_transporter_lowest_price(self, bid_id: str, transporter_id: str, rate: float, decrement: float) -> (any, str):

        session = Session()

        try:
            bid = session.query(BidTransaction).filter(
                BidTransaction.transporter_id == transporter_id, BidTransaction.bid_id == bid_id).order_by(BidTransaction.rate).first()

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
            }, f"Incorrect Bid price, has to be lower,decrement is {decrement} %")

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
                .all()
            )

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
                        is_active=True,
                        created_by=user_id
                    )
                    assigned_transporters.append(assign_detail)

            for transporter_detail in transporter_details:

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
                            setattr(transporter_detail, "is_active", True)

            bid_details = session.query(BiddingLoad).filter(
                BiddingLoad.bl_id == bid_id).first()

            if not bid_details:
                return [], "Error While Fetching Bid Details"

            setattr(bid_details, "split", split)
            setattr(bid_details, "load_status", status)

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

    def close(self):

        session = Session()
        current_time = convert_date_to_string(
            datetime.now())

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

    async def public(self, status: str | None = None) -> (any, str):

        session = Session()

        try:

            bids_query = (session
                          .query(BiddingLoad, ShipperModel, MapLoadSrcDestPair)
                          .outerjoin(ShipperModel, ShipperModel.shpr_id == BiddingLoad.bl_shipper_id)
                          .outerjoin(MapLoadSrcDestPair, MapLoadSrcDestPair.mlsdp_bidding_load_id == BiddingLoad.bl_id)
                          .filter(BiddingLoad.is_active == True, BiddingLoad.bid_mode == "open_market")
                          )

            if status:
                bids_query = bids_query.filter(
                    BiddingLoad.load_status == status)

            bids = bids_query.all()

            if not bids:
                return (bids, "")
            return (structurize_transporter_bids(bids=bids), "")

        except Exception as e:
            session.rollback()
            return ([], str(e))
        finally:
            session.close()

    async def private(self, shippers: any, status: str | None = None) -> (any, str):

        session = Session()

        try:

            bids_query = (session
                          .query(BiddingLoad, ShipperModel, MapLoadSrcDestPair)
                          .outerjoin(ShipperModel, ShipperModel.shpr_id == BiddingLoad.bl_shipper_id)
                          .outerjoin(MapLoadSrcDestPair, MapLoadSrcDestPair.mlsdp_bidding_load_id == BiddingLoad.bl_id)
                          .filter(BiddingLoad.is_active == True, BiddingLoad.bl_shipper_id.in_(shippers), BiddingLoad.bid_mode == "private_pool")
                          )

            if status:
                bids_query = bids_query.filter(
                    BiddingLoad.load_status == status)

            bids = bids_query.all()

            if not bids:
                return (bids, "")
            return (structurize_transporter_bids(bids=bids), "")

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

            if not bids:
                return (bids, "")

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
