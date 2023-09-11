from sqlalchemy import update

from utils.response import *
from config.db_config import Session
from models.models import *
from utils.db import append_model_to_file, get_table_and_model


async def initiate_bid():
    pass

async def close_bid():
    pass

async def fetch_bids_statuswise(status: str):

    session = Session()

    try:

        bids = (session.query(BiddingLoad, MapLoadSrcDestPair, LoadAssigned, Transporter)
                .join(MapLoadSrcDestPair)
                .join(LoadAssigned)
                .join(LkpReason)
                .join(Transporter)
                .filter(BiddingLoad.load_status == status)
                .filter(MapLoadSrcDestPair.mlsdp_bidding_load_id == BiddingLoad.bl_id)
                .filter(LoadAssigned.la_bidding_load_id == BiddingLoad.bl_id)
                .filter(Transporter.trnsp_id == LoadAssigned.la_transporter_id)
                .all()
                )

        return SuccessResponse(data=bids, dev_msg="Correct status, data fetched", client_msg=f"Fetched all {status} bids successfully!")

    except Exception as e:
        session.rollback()
        return ServerError(err=e, errMsg=str(e))

    finally:
        session.close()


async def bid_id_is_valid(bid_id: str) -> (bool, str):

    session = Session()

    try:
        if not bid_id:
            return (False, "The Bid ID provided is empty")

        bid = session.query(BiddingLoad).filter(
            BiddingLoad.bl_id == bid_id).first()

        if not bid:
            return (False, "Bid ID not found!")

        return (True, "")

    except Exception as e:
        session.rollback()
        return (False, str(e))

    finally:
        session.close()


async def update_bid_status(bid_id: str, status: str) -> (bool, str):

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


async def create_bid_table(bid_id: str) -> (bool, str):

    try:

        table_name = 't_' + bid_id.replace('-', '')

        (success, model_or_err) = await get_table_and_model(table_name)

        if success:
            append_model_to_file(model_or_err)
            return (True, "")
        return (False, model_or_err)
    except Exception as e:
        return (False, str(e))
