from config.db_config import Session
from utils.response import ServerError, SuccessResponse
from models.models import BidTransaction, TransporterModel, MapShipperTransporter, LoadAssigned, BiddingLoad, User, ShipperModel, MapLoadSrcDestPair
from utils.bids.bidding import Bid
from utils.utilities import log, structurize_transporter_bids
import os

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

    async def notify(self, bid_id: str):
        log(bid_id)
        log("Notification to transporters will be sent here!")

    async def historical_rates(self, transporter_id: str, bid_id: str):

        session = Session()

        try:

            rates = (session
                     .query(BidTransaction)
                     .filter(BidTransaction.transporter_id == transporter_id, BidTransaction.bid_id == bid_id)
                     .order_by(BidTransaction.created_at.desc())
                     .all()
                     )

            return SuccessResponse(data=rates, dev_msg="Historical rates for requested transporter was found", client_msg="Requested rates found!")

        except Exception as err:
            session.rollback()
            return ServerError(err=err, errMsg=str(err))

        finally:
            session.close()

    async def is_valid_bid_rate(self, bid_id: str, show_rate_to_transporter: bool, rate: float, transporter_id: str, decrement: float, status: str) -> (any, str):

        session = Session()

        try:

            if show_rate_to_transporter and status == "live":
                return await bid.decrement_on_lowest_price(bid_id=bid_id, rate=rate, decrement=decrement)
            return await bid.decrement_on_transporter_lowest_price(bid_id, transporter_id, rate, decrement)

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

    async def bid_match(self, bid_id: str, transporters: any) -> (any, str):
        session = Session()
        user_id = os.getenv("USER_ID")
        try:

            transporter_ids = []
            fetched_transporter_ids = []
            assigned_transporters = []

            for transporter in transporters:
                transporter_ids.append(
                    getattr(transporter, "transporter_id"))

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
                        pmr_price=getattr(
                            transporter, "rate"),
                        is_active=False,
                        created_by=user_id
                    )
                    assigned_transporters.append(assign_detail)

            log("Assigned Transporters", assigned_transporters)
            for transporter_detail in transporter_details:
                if getattr(transporter_detail, "la_transporter_id") in transporters_to_be_updated:
                    for transporter in transporters:
                        if getattr(transporter, "transporter_id") == getattr(transporter_detail, "la_transporter_id"):
                            setattr(transporter_detail, "la_transporter_id",
                                    getattr(transporter, "transporter_id"))
                            setattr(transporter_detail, "pmr_price",
                                    getattr(transporter, "rate"))
                            setattr(transporter_detail, "trans_pos_in_bid",
                                    getattr(transporter, "trans_pos_in_bid"))
                            setattr(transporter_detail, "is_active", False)

            log("Data changed for UPdate")
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

    async def unassign(self, bid_id: str, transporter_id: str) -> (any, str):

        session = Session()

        try:

            transporter = (session
                           .query(LoadAssigned)
                           .filter(LoadAssigned.la_bidding_load_id == bid_id,
                                   LoadAssigned.la_transporter_id == transporter_id,
                                   LoadAssigned.is_active == True)
                           .first()
                           )

            if not transporter:
                return ({}, "Transporter details could not be found")

            transporter.is_active = False

            bid = (session
                   .query(BiddingLoad)
                   .filter(BiddingLoad.bl_id == bid_id)
                   .first()
                   )

            if not bid:
                return ({}, "Bid details could not be found")

            bid.load_status = "partially_confirmed"

            session.commit()

            return (transporter, "")

        except Exception as e:
            session.rollback()
            return ({}, str(e))
        finally:
            session.close()

    async def bids_by_status(self, transporter_id: str, status: str | None = None) -> (any, str):

        session = Session()

        try:
            shippers, error = await self.shippers(transporter_id=transporter_id)
            if error:
                return [], error

            public_bids, error = await bid.public(status=status)
            if error:
                return [], error

            private_bids = []
            if shippers:
                private_bids, error = await bid.private(shippers=shippers, status=status)
                if error:
                    return [], error

            return {
                "all": private_bids + public_bids,
                "private": private_bids,
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
            bid_ids = (session
                       .query(LoadAssigned.la_bidding_load_id)
                       .filter(LoadAssigned.la_transporter_id == transporter_id)
                       .all()
                       )

            if not bid_ids:
                return ([], "Not been selected in any bids yet!")

            bids = (session
                    .query(BiddingLoad, ShipperModel, MapLoadSrcDestPair)
                    .outerjoin(ShipperModel.shpr_id == BiddingLoad.bl_shipper_id)
                    .outerjoin(MapLoadSrcDestPair.mlsdp_bidding_load_id == BiddingLoad.bl_id)
                    .filter(BiddingLoad.is_active == True, BiddingLoad.bl_id.in_(bid_ids))
                    .all()
                    )

            if not bids:
                return ([], "Could not find bid details from bid IDs")

            return (structurize_transporter_bids(bids=bids), "")

        except Exception as e:
            session.rollback()
            return [], str(e)
        finally:
            session.close()

    async def shippers(self, transporter_id: str) -> (any, str):

        session = Session()

        try:

            shippers = (session
                        .query(MapShipperTransporter.mst_shipper_id)
                        .filter(MapShipperTransporter.mst_transporter_id == transporter_id)
                        .all()
                        )

            if not shippers:
                return ([], "This transporter is not mapped to any shipper")

            return (shippers, "")

        except Exception as e:
            session.rollback()
            return ([], str(e))
        finally:
            session.close()
