import os
import httpx
import json
import requests
import ast
import pytz
from datetime import datetime
from sqlalchemy import text, and_, or_, func, select
from uuid import UUID
from typing import List

from config.db_config import Session
from utils.response import ServerError, SuccessResponse
from models.models import BidTransaction, TransporterModel, MapShipperTransporter, LoadAssigned, BiddingLoad, User, ShipperModel, MapLoadSrcDestPair, BlacklistTransporter, TrackingFleet, BidSettings
from utils.bids.bidding import Bid
from utils.utilities import log, structurize_transporter_bids
from data.bidding import lost_participated_transporter_bids, live_bid_details, assignment_events


bid = Bid()


class Transporter:

    async def id(self, user_id: str) -> (str, str):

        session = Session()

        try:
            if not user_id:
                return (False, "The User ID provided is empty")

            transporter = (session
                           .query(User)
                           .filter(User.user_id == user_id, User.is_active == True)
                           .first()
                           )

            if not transporter:
                return ("", "Transporter ID could not be found")

            return (transporter.user_transporter_id, "")

        except Exception as e:
            session.rollback()
            return ("", str(e))
        finally:
            session.close()

    async def notify(self, bid_id: str, authtoken: any) -> (bool, str):

        session = Session()

        try:
            (bid_details, error) = await self.bid_details(bid_id=bid_id)
            if error:
                return ("", error)

            transporter_ids = []
            user_ids = []

            if bid_details.bid_mode == 'private_pool':
                transporters = session.query(MapShipperTransporter).filter(
                    MapShipperTransporter.mst_shipper_id == bid_details.bl_shipper_id, MapShipperTransporter.is_active == True).all()
                for transporter in transporters:
                    transporter_ids.append(transporter.mst_transporter_id)

            elif bid_details.bid_mode == 'open_market':
                transporters = session.query(TransporterModel).filter(
                    TransporterModel.is_active == True).all()
                for transporter in transporters:
                    transporter_ids.append(transporter.trnsp_id)

            user_details = session.query(User).filter(
                User.user_transporter_id.in_(transporter_ids), User.is_active == True).all()

            login_url = "http://13.235.56.142:8000/api/secure/notification/"
            headers = {
                'Authorization': authtoken
            }

            for user_detail in user_details:
                user_ids.append(str(user_detail.user_id))

            payload = {"nt_receiver_id": user_ids,
                       "nt_text": f"New Bid for a Load needing {bid_details.no_of_fleets} fleets is Available with Load id - {bid_details.bl_id}. The Bidding will start from {bid_details.bid_time}",
                       "nt_type": "PUBLISH NOTIFICATION",
                       "nt_deep_link": "transporter_dashboard_upcoming",
                       }

            log("PAYLOAD", payload)
            log("HEADER", headers)

            with httpx.Client() as client:
                response = client.post(
                    url=login_url, headers=headers, data=json.dumps(payload))

            log("NOTIFICATION CREATE Response", response.json())
            json_response = response.json()

            if json_response["success"] == False:
                return (False, json_response["dev_message"])
            return (True, "")

        except Exception as err:
            session.rollback()
            return ("", str(err))
        finally:
            session.close()

    async def historical_rates(self, transporter_id: str, bid_id: str) -> (any, str):

        session = Session()

        try:

            historical_rates = (session
                                .query(BidTransaction)
                                .filter(BidTransaction.transporter_id == transporter_id, BidTransaction.bid_id == bid_id)
                                .order_by(BidTransaction.created_at.desc())
                                .all()
                                )

            price_match_rates = (session
                                 .query(LoadAssigned)
                                 .filter(LoadAssigned.la_transporter_id == transporter_id, LoadAssigned.la_bidding_load_id == bid_id)
                                 .first()
                                 )

            return ({
                "historical": historical_rates,
                "pmr_price": price_match_rates.pmr_price if price_match_rates else None,
                "pmr_comment": price_match_rates.pmr_comment if price_match_rates else None,
                "pmr_date": price_match_rates.updated_at if price_match_rates else None,
                "no_of_fleets_assigned": price_match_rates.no_of_fleets_assigned if price_match_rates else None,
            }, "")

        except Exception as err:
            session.rollback()
            return ([], str(err))

        finally:
            session.close()

    async def is_valid_bid_rate(self, bid_id: str, show_rate_to_transporter: bool, rate: float, transporter_id: str, decrement: float, is_decrement_in_percentage: bool, status: str) -> (any, str):

        session = Session()

        try:

            if show_rate_to_transporter and status == "live":
                return await bid.decrement_on_lowest_price(bid_id=bid_id, rate=rate, decrement=decrement, is_decrement_in_percentage=is_decrement_in_percentage)
            return await bid.decrement_on_transporter_lowest_price(bid_id=bid_id, transporter_id=transporter_id, rate=rate, decrement=decrement, is_decrement_in_percentage=is_decrement_in_percentage)

        except Exception as e:
            session.rollback()
            return ({}, str(e))
        finally:
            session.close()

    async def attempts(self, bid_id: str, transporter_id: str) -> (int, str):

        session = Session()

        try:
            no_of_tries = session.query(BidTransaction).filter(
                BidTransaction.transporter_id == transporter_id, BidTransaction.bid_id == bid_id).count()

            log("NUMBER OF TRIES", no_of_tries)

            return (no_of_tries, "")

        except Exception as e:
            session.rollback()
            return (0, str(e))

        finally:
            session.close()

    async def lowest_price(self, bid_id: str, transporter_id: str) -> (float, str):

        session = Session()
        try:

            transporter_bid = (session
                               .query(BidTransaction)
                               .filter(BidTransaction.transporter_id == transporter_id, BidTransaction.bid_id == bid_id)
                               .order_by(BidTransaction.rate)
                               .first()
                               )

            if not transporter_bid:
                return (0.0, "")

            return (transporter_bid.rate, "")

        except Exception as e:
            session.rollback()
            return (0.0, str(e))

        finally:
            session.close()

    async def name(self, transporter_id: str) -> (str, str):

        session = Session()

        try:
            transporter = session.query(TransporterModel).filter(
                TransporterModel.trnsp_id == transporter_id).first()

            if not transporter:
                return ("", "Requested transporter details was not found")

            return (transporter.name, "")

        except Exception as err:
            session.rollback()
            return ("", str(err))
        finally:
            session.close()

    async def allowed_to_bid(self, shipper_id: str, transporter_id: str) -> (bool, str):
        session = Session()

        try:
            log("INSIDE ALLOWED TO BID", "OK")
            transporter_details = session.query(MapShipperTransporter).filter(
                MapShipperTransporter.mst_shipper_id == shipper_id, MapShipperTransporter.mst_transporter_id == transporter_id, MapShipperTransporter.is_active == True).first()
            log("TRANSPORTER DETAILS", transporter_details)
            if not transporter_details:
                return (False, "transporter not tagged with the specific shipper")

            return (True, "")

        except Exception as e:
            session.rollback()
            return (False, str(e))
        finally:
            session.close()

    async def bid_match(self, bid_id: str, transporters: any, user_id: str, user_type: str) -> (any, str):
        session = Session()

        try:

            fetched_transporter_ids = []
            assigned_transporters = []
            superuser = (user_type == "acu")
            print("SUPERUSER >>>>>>>", superuser)
            ist_timezone = pytz.timezone("Asia/Kolkata")
            current_time = datetime.now(ist_timezone)
            current_time = current_time.replace(
                tzinfo=None, second=0, microsecond=0)

            transporter_ids = [getattr(transporter, "transporter_id") for transporter in transporters]

            transporter_details = session.query(LoadAssigned).filter(
                LoadAssigned.la_bidding_load_id == bid_id, LoadAssigned.la_transporter_id.in_(transporter_ids)).all()

            log("Fetched Transporter Detail ", transporter_details)
            for transporter_detail in transporter_details:
                fetched_transporter_ids.append(
                    transporter_detail.la_transporter_id)

            transporters_not_assigned = list(
                set(transporter_ids) - set(fetched_transporter_ids))
            log("Transporter IDs not assigned", transporters_not_assigned)
            transporters_to_be_updated = list(
                set(transporter_ids).intersection(set(fetched_transporter_ids)))
            log("Transporter to be Updated", transporters_to_be_updated)

            for transporter in transporters:
                if getattr(transporter, "transporter_id") in transporters_not_assigned:

                    assign_detail = LoadAssigned(
                        la_bidding_load_id=bid_id,
                        la_transporter_id=getattr(
                            transporter, "transporter_id"),
                        trans_pos_in_bid=getattr(
                            transporter, "trans_pos_in_bid"
                        ),
                        no_of_fleets_assigned=0,
                        price=getattr(transporter, "rate"),
                        pmr_price=getattr(
                            transporter, "rate"),
                        pmr_comment=getattr(
                            transporter, "comment"
                        ),
                        is_pmr_approved = True if superuser else False,
                        is_negotiated_by_aculead = True if superuser else False,
                        history = str([(assignment_events["superuser-negotiation"] if superuser else assignment_events["pm-request"] ,getattr(transporter, "rate"), str(current_time), getattr(transporter, "comment"))]),
                        is_active=True,
                        created_at="NOW()",
                        created_by=user_id
                    )
                    assigned_transporters.append(assign_detail)

            log("Assigned Transporters", assigned_transporters)

            for transporter_detail in transporter_details:
                if getattr(transporter_detail, "la_transporter_id") in transporters_to_be_updated:
                    for transporter in transporters:
                        if getattr(transporter_detail, "la_transporter_id") == getattr(transporter, "transporter_id"):
                            
                            task = (assignment_events["superuser-negotiation"] if superuser else assignment_events["pm-request"],getattr(transporter, "rate"), str(current_time), getattr(transporter, "comment"))
                            fetched_history = ast.literal_eval(getattr(transporter_detail, "history"))
                            fetched_history.append(task)

                            setattr(transporter_detail, "la_transporter_id",
                                    getattr(transporter, "transporter_id"))
                            setattr(transporter_detail, "pmr_price",
                                    getattr(transporter, "rate"))
                            setattr(transporter_detail, "trans_pos_in_bid",
                                    getattr(transporter, "trans_pos_in_bid"))
                            setattr(transporter_detail, "pmr_comment",
                                    getattr(transporter, "comment"))
                            setattr(transporter_detail, "is_pmr_approved", True if superuser else False)
                            setattr(transporter_detail, "is_negotiated_by_aculead", True if superuser else False)
                            setattr(transporter_detail, "history", str(fetched_history))
                            setattr(transporter_detail, "updated_at", "NOW()")
                            setattr(transporter_detail, "updated_by", user_id)

            log("Data changed for Update ")

            session.bulk_save_objects(assigned_transporters)
            session.commit()

            if not assigned_transporters:
                return ([], "")

            return (assigned_transporters, "")

        except Exception as e:
            session.rollback()
            return ([], str(e))
        finally:
            session.close()

    async def unassign(self, bid_id: str, transporter_request: any) -> (any, str):

        session = Session()

        try:

            transporter_id = transporter_request.transporter_id
            unassignment_reason = transporter_request.unassignment_reason

            transporters = (session
                            .query(LoadAssigned)
                            .filter(LoadAssigned.la_bidding_load_id == bid_id,
                                    LoadAssigned.is_assigned == True,
                                    LoadAssigned.is_active == True)
                            .all()
                            )

            if not transporters:
                return ({}, "Transporter details could not be found")

            no_transporter_assigned = True

            ist_timezone = pytz.timezone("Asia/Kolkata")
            current_time = datetime.now(ist_timezone)
            current_time = current_time.replace(
                tzinfo=None, second=0, microsecond=0)

            for transporter in transporters:
                if transporter.la_transporter_id == UUID(transporter_id):
                    transporter.is_assigned = False
                    transporter.no_of_fleets_assigned = 0
                    transporter.unassignment_reason = unassignment_reason
                    transporter.pmr_price = None
                    transporter.pmr_comment = None
                    if transporter.history:
                        task = (assignment_events["unassign"],0, str(current_time), unassignment_reason)
                        fetched_history = ast.literal_eval(transporter.history)
                        fetched_history.append(task)
                        transporter.history = str(fetched_history)
                    else:
                        transporter.history = str(
                            [(assignment_events["unassign"],0, str(current_time), unassignment_reason)])

                elif no_transporter_assigned and transporter.la_transporter_id != UUID(transporter_id):
                    no_transporter_assigned = False

            bid = (session
                   .query(BiddingLoad)
                   .filter(BiddingLoad.bl_id == bid_id)
                   .first()
                   )

            if not bid:
                return ({}, "Bid details could not be found")

            if no_transporter_assigned:
                bid.load_status = "pending"
                bid.updated_at = "NOW()"
            else:
                bid.load_status = "partially_confirmed"
                bid.updated_at = "NOW()"

            session.commit()

            return (transporter, "")

        except Exception as e:
            session.rollback()
            return ({}, str(e))
        finally:
            session.close()

    async def bids_by_status(self, transporter_id: str, user_id: str, status: str | None = None) -> (any, str):

        session = Session()

        try:
            shippers, error = await self.shippers(transporter_id=transporter_id)
            if error:
                return [], error

            log("FETCHED SHIPPERS ATTACHED TO TRANSPORTERS", shippers)

            public_bids, error = await bid.public(blocked_shippers=shippers["blocked_shipper_ids"], transporter_id=transporter_id, status=status)

            if error:
                return [], error

            log("FETCHED PUBLIC BIDS", public_bids)

            unsegmented_private_bids = []
            segmented_bids = []
            if shippers["shipper_ids"]:
                unsegmented_private_bids, error = await bid.private(shippers=shippers["shipper_ids"], transporter_id=transporter_id, user_id=user_id, status=status)
                if error:
                    return [], error
                log("FETCHED PRIVATE BIDS", unsegmented_private_bids)
                
                segmented_bids, error = await bid.segment(shippers=shippers["shipper_ids"], transporter_id=transporter_id, user_id=user_id, status=status)
                if error:
                    return [],error
                log("SEGMENTED PRIVATE BIDS", segmented_bids)
                
                
            return {
                "all": unsegmented_private_bids + public_bids + segmented_bids,
                "private": unsegmented_private_bids + segmented_bids,
                "public": public_bids
            }, ""

        except Exception as e:
            session.rollback()
            return [], str(e)
        finally:
            session.close()

    async def selected(self, transporter_id: str) -> (any, str):

        session = Session()

        try:
            bid_arr = (session
                       .query(LoadAssigned)
                       .filter(LoadAssigned.la_transporter_id == transporter_id, LoadAssigned.is_active == True, LoadAssigned.is_assigned == True)
                       .all()
                       )

            if not bid_arr:
                return ([], "")

            bid_ids = [bid.la_bidding_load_id for bid in bid_arr]

            log("BID IDS ", bid_ids)
            bids = (session
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
                    .filter(BiddingLoad.is_active == True, BiddingLoad.bl_id.in_(bid_ids))
                    .group_by(BiddingLoad, *BiddingLoad.__table__.c, ShipperModel.name, ShipperModel.contact_no, ShipperModel.shpr_id )
                    .all()
                    )

            log("BIDS ", bids)
            if not bids:
                return ([], "")

            structured_bids = structurize_transporter_bids(bids=bids)

            load_assigned_dict = {
                load.la_bidding_load_id: load for load in bid_arr}

            for bid in structured_bids:
                if bid["bid_id"] in bid_ids:
                    load_assigned = load_assigned_dict.get(bid["bid_id"])
                    if load_assigned:
                        bid["no_of_fleets_assigned"] = load_assigned.no_of_fleets_assigned
                        bid["pending_vehicles"] = bid["no_of_fleets_assigned"] - bid["no_of_fleets_provided"]

            return (structured_bids, "")

        except Exception as e:
            session.rollback()
            return [], str(e)
        finally:
            session.close()

    async def completed(self, transporter_id: str) -> (any, str):

        session = Session()

        try:
            bid_arr = (session
                       .query(LoadAssigned)
                       .filter(LoadAssigned.la_transporter_id == transporter_id, LoadAssigned.is_active == True, LoadAssigned.is_assigned == True)
                       .all()
                       )

            if not bid_arr:
                return ([], "")

            bid_ids = [bid.la_bidding_load_id for bid in bid_arr]

            log("BID IDS ", bid_ids)
            bids = (session
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
                    .filter(BiddingLoad.is_active == True, BiddingLoad.bl_id.in_(bid_ids), BiddingLoad.load_status == "completed")
                    .group_by(BiddingLoad, *BiddingLoad.__table__.c, ShipperModel.name, ShipperModel.contact_no, ShipperModel.shpr_id )
                    .all()
                    )

            log("BIDS ", bids)
            if not bids:
                return ([], "")

            structured_bids = structurize_transporter_bids(bids=bids)

            load_assigned_dict = {
                load.la_bidding_load_id: load for load in bid_arr}

            for bid in structured_bids:
                if bid["bid_id"] in bid_ids:
                    load_assigned = load_assigned_dict.get(bid["bid_id"])
                    if load_assigned:
                        bid["no_of_fleets_assigned"] = load_assigned.no_of_fleets_assigned
                        bid["pending_vehicles"] = bid["no_of_fleets_assigned"] - bid["no_of_fleets_provided"]

            return (structured_bids, "")

        except Exception as e:
            session.rollback()
            return [], str(e)
        finally:
            session.close()

    async def participated_bids(self, transporter_id: str) -> (any, str):

        session = Session()

        try:
            bid_arr = (session
                       .query(BidTransaction)
                       .distinct(BidTransaction.bid_id)
                       .filter(BidTransaction.transporter_id == transporter_id)
                       .all()
                       )

            if not bid_arr:
                return ([], "")

            log("PARTICIPATED AND NOT LOST", bid_arr)

            bid_ids = [str(bid.bid_id) for bid in bid_arr]

            log("BID IDs OF NOT LOST AND PARTICPATED", bid_ids)

            bids = (session
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
                    .filter(BiddingLoad.is_active == True, BiddingLoad.bl_id.in_(bid_ids))
                    .group_by(BiddingLoad, *BiddingLoad.__table__.c, ShipperModel.name, ShipperModel.contact_no, ShipperModel.shpr_id )
                    .all()
                    )

            if not bids:
                return ([], "")

            return (structurize_transporter_bids(bids=bids), "")

        except Exception as e:
            session.rollback()
            return [], str(e)
        finally:
            session.close()

    async def participated_and_lost_bids(self, transporter_id: str) -> (any, str):

        session = Session()

        try:
            bid_arr = session.execute(text(lost_participated_transporter_bids), params={
                "transporter_id": transporter_id
            })
            log("BID ARRAY ", bid_arr)
            bid_ids = [bid._mapping["bid_id"] for bid in bid_arr]
            log("BID IDS", bid_ids)
            if not bid_ids:
                return ([], "")

            load_status_for_lost_participated = ["completed", "confirmed"]

            bids = (session
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
                    .filter(BiddingLoad.is_active == True, BiddingLoad.bl_id.in_(bid_ids), BiddingLoad.load_status.in_(load_status_for_lost_participated))
                    .group_by(BiddingLoad, *BiddingLoad.__table__.c, ShipperModel.name, ShipperModel.contact_no, ShipperModel.shpr_id )
                    .all()
                    )

            if not bids:
                return ([], "")

            log("PARTICPATED BIDS", bids)

            return (structurize_transporter_bids(bids=bids), "")

        except Exception as e:
            session.rollback()
            return [], str(e)
        finally:
            session.close()

    async def not_participated_and_lost_bids(self, transporter_id: str) -> (any, str):

        session = Session()

        try:
            all_bids, error = await self.bids_by_status(transporter_id=transporter_id)

            if error:
                return ([], error)

            _all = all_bids["all"]

            (participated_bids, error) = await self.participated_bids(transporter_id=transporter_id)

            if error:
                return ([], "Participated bids for transporter could not be fetched")

            log("PARTICIPATED")

            not_participated_bids = [
                bid for bid in _all if bid not in participated_bids]

            # and bid.load_status in particpated_and_lost_status

            if not not_participated_bids:
                return ([], "")

            return not_participated_bids, ""

        except Exception as e:
            session.rollback()
            return [], str(e)
        finally:
            session.close()

    async def shippers(self, transporter_id: str) -> (any, str):

        session = Session()
        shipper_ids = []

        try:
            shipper_and_blacklist_details = (
                session.query(MapShipperTransporter,
                              TransporterModel,
                              BlacklistTransporter
                              )
                .join(TransporterModel, and_(MapShipperTransporter.mst_transporter_id == TransporterModel.trnsp_id, TransporterModel.is_active == True))
                .outerjoin(BlacklistTransporter, and_(BlacklistTransporter.bt_shipper_id == MapShipperTransporter.mst_shipper_id, BlacklistTransporter.bt_transporter_id == transporter_id, BlacklistTransporter.is_active == True))
                .filter(MapShipperTransporter.mst_transporter_id == transporter_id, MapShipperTransporter.is_active == True)
                .all()
            )
            
            transporter_status = ''
            if not shipper_and_blacklist_details:
                aculead_transporter_detail = (
                                            session.query(TransporterModel)
                                            .filter(TransporterModel.trnsp_id == transporter_id, TransporterModel.is_active == True)
                                            .first()
                                            )
                
                if aculead_transporter_detail:
                    transporter_status = aculead_transporter_detail.status

            shipper_ids = []
            mapped_blocked_shipper_ids = []
            unmapped_blocked_shipper_ids = []

            
            for shipper_and_blacklist_detail in shipper_and_blacklist_details:
                (shipper, transporter_details,
                 blacklist_details) = shipper_and_blacklist_detail

                if transporter_details.status == 'partially_blocked':
                    transporter_status = 'partially_blocked'
                    if not blacklist_details:
                        shipper_ids.append(shipper.mst_shipper_id)
                    else:
                        mapped_blocked_shipper_ids.append(shipper.mst_shipper_id)
                        
                else:
                    shipper_ids.append(shipper.mst_shipper_id)
                log("SHIPPER :", shipper)
                log("TRANSPORTER DETAILS :", transporter_details.trnsp_id)
                log("BLACKLIST :", blacklist_details)

            log("SHIPPER IDs", shipper_ids)
            log("BLOCKED SHIPPER IDS", mapped_blocked_shipper_ids)

            if transporter_status == 'partially_blocked':
                unmapped_blocked_shippers = (
                                            session.query(BlacklistTransporter)
                                            .filter(BlacklistTransporter.is_active == True, ~BlacklistTransporter.bt_shipper_id.in_(mapped_blocked_shipper_ids), BlacklistTransporter.bt_transporter_id == transporter_id)
                                            .all()
                                        )
                log("UNMAPPED BLOCKED SHIPPERS ", unmapped_blocked_shippers)
                for unmapped_blocked_shipper in unmapped_blocked_shippers:
                    unmapped_blocked_shipper_ids.append(unmapped_blocked_shipper.bt_shipper_id)
                log("UNMAPPED BLOCKED SHIPPER IDS ", unmapped_blocked_shipper_ids)

            
            all_shipper_ids = {
                "shipper_ids": shipper_ids,
                "blocked_shipper_ids": mapped_blocked_shipper_ids + unmapped_blocked_shipper_ids
            }
            log("ALL SHIPPER IDS ", all_shipper_ids)

            return (all_shipper_ids, "")

        except Exception as e:
            session.rollback()
            return ({}, str(e))
        finally:
            session.close()

    async def bid_details(self, bid_id: str, transporter_id: str | None = None) -> (any, str):

        session = Session()

        log("FINDING BID DETAILS FOR A TRANSPORTER")

        try:

            bid_details = (
                session
                .query(BiddingLoad)
                .filter(BiddingLoad.bl_id == bid_id)
                .first()
            )

            log("BID DETAILS AFTER QUERY", bid_details)

            if not bid_details:
                return ([], "")

            return (bid_details, "")

        except Exception as e:
            session.rollback()
            return ({}, str(e))
        finally:
            session.close()

    async def assigned_bids(self, transporter_id: str) -> (any, str):

        session = Session()

        try:

            _all, error = await self.bids_by_status(transporter_id=transporter_id)

            if error:
                return ([], error)

            all_bids = _all["all"]

            if not all_bids:
                return ([], "")

            log("ALL BIDS FOR A TRANSPORTER", all_bids)

            # Filtering all bids which are confirmed or partially confirmed
            filtered_bid_ids = [str(bid["bid_id"]) for bid in all_bids if bid["load_status"]
                                == "confirmed" or bid["load_status"] == "partially_confirmed"]

            log("BIDS WHICH ARE CONFIRMED OR PARTIALLY CONFIRMED ", filtered_bid_ids)

            bids_which_transporter_has_been_assigned_to = (
                session
                .query(LoadAssigned)
                .filter(LoadAssigned.la_bidding_load_id.in_(filtered_bid_ids), LoadAssigned.la_transporter_id == transporter_id, LoadAssigned.is_active == True, LoadAssigned.is_assigned == True)
                .all()
            )

            if not bids_which_transporter_has_been_assigned_to:
                return ([], "")

            log("BIDS WHICH TRANSPORTER IS ASSIGNED TO ",
                bids_which_transporter_has_been_assigned_to)

            bid_ids = [str(bid.la_bidding_load_id)
                       for bid in bids_which_transporter_has_been_assigned_to]

            bids = (session
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
                    .filter(BiddingLoad.is_active == True, BiddingLoad.bl_id.in_(bid_ids))
                    .group_by(BiddingLoad, *BiddingLoad.__table__.c, ShipperModel.name, ShipperModel.contact_no, ShipperModel.shpr_id )
                    .all()
                    )

            if not bids:
                return ([], "")

            log("ALL BIDS WHICH TRANSPORTER IS ASSIGNED TO ", bids)

            return (structurize_transporter_bids(bids=bids), "")

        except Exception as e:
            session.rollback()
            return ([], str(e))
        finally:
            session.close()

    async def position(self, transporter_id: str, bid_id: str) -> (any, str):
        try:
            session = Session()

            bid_details = session.execute(text(live_bid_details), params={
                "bid_id": bid_id})

            bid_summary = []
            for row in bid_details:
                bid_summary.append(row._mapping)

            if not bid_summary:
                return (None, "")

            log("BID SUMMARY", bid_summary)
            # sorted_bid_summary = sorted(bid_summary, key=lambda x: x['rate'])

            transporter_lowest_rate_bid_dict = {}
            for bid in bid_summary:

                id = bid.transporter_id
                if id in transporter_lowest_rate_bid_dict.keys():
                    if transporter_lowest_rate_bid_dict[id].rate > bid.rate:
                        transporter_lowest_rate_bid_dict[id] = bid

                if id not in transporter_lowest_rate_bid_dict.keys():
                    transporter_lowest_rate_bid_dict[id] = bid

            lowest_rate_bid_summary = [
                lowest_rate_bid_details for lowest_rate_bid_details in transporter_lowest_rate_bid_dict.values()]

            sorted_bid_summary = sorted(lowest_rate_bid_summary, key=lambda x: (
                x['rate'], x['created_at'].timestamp()))

            log("SORTED BID SUMMARY ", sorted_bid_summary)

            _position = 0

            for index, bid_detail in enumerate(sorted_bid_summary):
                if str(bid_detail.transporter_id) == str(transporter_id):
                    return (index, "")
            return (None, "")

        except Exception as e:
            session.rollback()
            return ({}, str(e))

        finally:
            session.close()

    async def assignment_history(self, transporter_id: str, bid_id: str) -> (any, str):

        session = Session()

        try:

            transporter_detail = (session.query(LoadAssigned).filter(LoadAssigned.la_bidding_load_id == bid_id,
                                  LoadAssigned.la_transporter_id == transporter_id, LoadAssigned.is_active == True).first())

            log("TRANSPORTER DETAILS", transporter_detail)
            if not transporter_detail:
                return ([], "")
            if not transporter_detail.history:
                return ([], "")

            log("ASSIGNMENT HISTORY", transporter_detail.history)
            log("TYPE", type(transporter_detail.history))

            assignment_history = ast.literal_eval(transporter_detail.history)[::-1]

            log("ASSIGNMENT HISTORY", assignment_history)
            log("TYPE", type(assignment_history))

            history = []

            for (event, resources, created_at, reason) in assignment_history:
                
                filtered_resources = ""
                if event in (assignment_events["unassign"] ,assignment_events["assign"]):
                    filtered_resources = str(resources)+" vehicle(s)"
                else:
                    filtered_resources = "₹ "+str(resources) if resources else None
                
                history.append({
                    "event": event,
                    "resources": filtered_resources,
                    "created_at": created_at,
                    "reason": reason
                })

            return (history, "")

        except Exception as err:
            session.rollback()
            return ([], str(err))

        finally:
            session.close()

    async def bid_match_approval(self, transporter_id: str, bid_id: str, req: any) -> (any, str):

        session = Session()

        try:

            event = []

            ist_timezone = pytz.timezone("Asia/Kolkata")
            current_time = datetime.now(ist_timezone)
            current_time = current_time.replace(
                tzinfo=None, second=0, microsecond=0)

            transporter_detail = (session.query(LoadAssigned).filter(LoadAssigned.la_bidding_load_id == bid_id,
                                LoadAssigned.la_transporter_id == transporter_id, LoadAssigned.is_active == True).first())

            if not transporter_detail:
                return ([], "Transporter's Assigned Load Detail not Found")

            if req.approval :
                event.append(assignment_events["pm-approved"])
                event.append(req.rate)
                event.append(str(current_time))
                event.append("Price Match Approved by Transporter")

                transporter_detail.is_negotiated_by_aculead = False
                transporter_detail.is_pmr_approved = True

            else:
                if req.rate:
                    event.append(assignment_events["pm-negotiated"])
                    transporter_detail.pmr_price = req.rate
                    transporter_detail.pmr_comment = req.comment
                else:
                    event.append(assignment_events["pm-rejected"])
                event.append(req.rate)
                event.append(str(current_time))
                event.append(req.comment)

                transporter_detail.is_negotiated_by_aculead = False
                transporter_detail.is_pmr_approved = None

            if transporter_detail.history:
                fetched_history = ast.literal_eval(transporter_detail.history)
                fetched_history.append(tuple(event))
                transporter_detail.history = str(fetched_history)
                
            else:
                transporter_detail.history = str([(tuple(event))])

            session.commit()
            return ([],"")

        except Exception as err:
            session.rollback()
            return ([], str(err))

        finally:
            session.close()
