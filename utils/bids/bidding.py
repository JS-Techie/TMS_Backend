from utilities import *
from config.db_config import *
from utils.response import * 
from models.models import *
class Bid:
    
    def __init__(self):
        log("new bid object created")
        
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
            log("bid_id",bid_id)
            log("status",status)
            
            bid_to_be_updated = session.query(BiddingLoad).filter(BiddingLoad.bl_id == bid_id).first()
            
            if not bid_to_be_updated:
                return (False, "Bid requested could not be found")
            
            setattr(bid_to_be_updated,"load_status",status)
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

    async def new_bid(bid_id: str, transporter_id: str, rate: float, comment: str) -> (any, str):

        session = Session()

        try:

            attempt_number = 0
            attempted = session.query(BidTransaction).filter(
                BidTransaction.transporter_id == transporter_id, BidTransaction.bid_id == bid_id).order_by(BidTransaction.created_at.desc()).first()

            if attempted:
                attempt_number = attempted.attempt_number + 1

            bid = (BidTransaction(
                bid_id = bid_id,
                transporter_id=transporter_id,
                rate=rate,
                comment=comment,
                attempt_number=attempt_number
            ))

            session.add(bid)
            session.commit()
            session.refresh(bid)

            return (bid, "")

        except Exception as e:
            session.rollback()
            return ({}, str(e))
        finally:
            session.close()
