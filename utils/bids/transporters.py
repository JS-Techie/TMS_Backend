from config.db_config import Session
from utils.response import *


async def notify_transporters_for_bid(bid_id: str):
    print("Notification to transporters will be sent here!")


async def historical_rates(transporter_id: str, bid_id: str):

    session = Session()

    bid_id = bid_id.replace("-", "")
    model = f'T_{bid_id}'

    try:

        rates = (session
                 .query(model)
                 .filter(model.transporter_id == transporter_id)
                 .order_by(model.created_at).desc()
                 .all()
                 )

        return SuccessResponse(data=rates, dev_msg="Historical rates for requested transporter was found", client_msg="Requested rates found!")

    except Exception as err:
        session.rollback()
        return ServerError(err=err, errMsg=str(err))

    finally:
        session.close()
