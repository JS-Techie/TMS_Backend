from config.db_config import Session
from utils.response import *
from models.models import *
from utils.db import *
from utils.bids.biddingDeprecated import Bid

bid = Bid()

class Transporter:

    async def notify(bid_id: str):
        log("Notification to transporters will be sent here!")

    async def historical_rates(transporter_id: str, bid_id: str):

        session = Session()

        model = get_bid_model_name(bid_id)

        try:

            rates = (session
                     .query(model)
                     .filter(model.transporter_id == transporter_id)
                     .order_by(model.created_at.desc())
                     .all()
                     )

            return SuccessResponse(data=rates, dev_msg="Historical rates for requested transporter was found", client_msg="Requested rates found!")

        except Exception as err:
            session.rollback()
            return ServerError(err=err, errMsg=str(err))

        finally:
            session.close()

    async def is_valid_bid_rate(bid_id : str, show_rate_to_transporter : bool,rate : float,transporter_id : str,decrement : float) -> (any, str):

        session = Session()

        try:
            
            if show_rate_to_transporter:
                return bid.decrement_on_lowest_price(bid_id,rate,decrement)
            
            return bid.decrement_on_transporter_lowest_price(bid_id,transporter_id,rate,decrement)


        except Exception as e:
            session.rollback()
            return ({}, str(e))
        finally:
            session.rollback()

    async def attempts(bid_id: str, transporter_id: str) -> (int, str):

        session = Session()
        model = get_bid_model_name(bid_id)

        try:
            no_of_tries = session.query(model).filter(
                model.transporter_id == transporter_id).count()

            return (no_of_tries, "")

        except Exception as e:
            session.rollback()
            return (0, str(e))

        finally:
            session.close()

    async def lowest_price(bid_id: str, transporter_id: str) -> (float, str):

        session = Session()
        model = get_bid_model_name(bid_id=bid_id)

        try:

            transporter_bid = (session
                               .query(model)
                               .filter(model.transporter_id == transporter_id)
                               .order_by(model.rate)
                               .first()
                               )

            return (transporter_bid.rate, "")

        except Exception as e:
            session.rollback()
            return (0.0, str(e))

        finally:
            session.close()
