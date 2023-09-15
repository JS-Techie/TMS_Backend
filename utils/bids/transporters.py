from config.db_config import Session
from utils.response import ServerError,SuccessResponse
from models.models import BidTransaction,TransporterModel, MapShipperTransporter
from utils.bids.bidding import Bid
from utils.utilities import log

bid = Bid()

class Transporter:

    async def notify(self,bid_id: str):
        log(bid_id)
        log("Notification to transporters will be sent here!")

    async def historical_rates(self,transporter_id: str, bid_id: str):

        session = Session()

        try:

            rates = (session
                     .query(BidTransaction)
                     .filter(BidTransaction.transporter_id == transporter_id,BidTransaction.bid_id == bid_id)
                     .order_by(BidTransaction.created_at.desc())
                     .all()
                     )

            return SuccessResponse(data=rates, dev_msg="Historical rates for requested transporter was found", client_msg="Requested rates found!")

        except Exception as err:
            session.rollback()
            return ServerError(err=err, errMsg=str(err))

        finally:
            session.close()

    async def is_valid_bid_rate(self,bid_id : str, show_rate_to_transporter : bool,rate : float,transporter_id : str,decrement : float) -> (any, str):

        session = Session()

        try:
            
            if show_rate_to_transporter:
                return await bid.decrement_on_lowest_price(bid_id,rate,decrement)
            
            return await bid.decrement_on_transporter_lowest_price(bid_id,transporter_id,rate,decrement)


        except Exception as e:
            session.rollback()
            return ({}, str(e))
        finally:
            session.rollback()

    async def attempts(self,bid_id: str, transporter_id: str) -> (int, str):

        session = Session()

        try:
            no_of_tries = session.query(BidTransaction).filter(
                BidTransaction.transporter_id == transporter_id,BidTransaction.bid_id == bid_id).count()


            return (no_of_tries, "")

        except Exception as e:
            session.rollback()
            return (0, str(e))

        finally:
            session.close()

    async def lowest_price(self,bid_id: str, transporter_id: str) -> (float, str):

        session = Session()
        try:

            transporter_bid = (session
                               .query(BidTransaction)
                               .filter(BidTransaction.transporter_id == transporter_id,BidTransaction.bid_id == bid_id)
                               .order_by(BidTransaction.rate)
                               .first()
                               )

            return (transporter_bid.rate, "")

        except Exception as e:
            session.rollback()
            return (0.0, str(e))

        finally:
            session.close()


    async def name(self,transporter_id : str) -> (str,str):
        
        session = Session()
        
        try:
            transporter = session.query(TransporterModel).filter(TransporterModel.trnsp_id == transporter_id).first()
            
            if not transporter:
                return ("","Requested transporter details was not found")
            
            return (transporter.name,"") 
           
        except Exception as err:
            session.rollback()
            return ("",str(err))
        finally:
            session.close()
        
        

    async def is_transporter_allowed_to_bid(shipper_id, transporter_id)->(bool,str):
        session=Session()
        
        try:
            
            transporter_details = session.query(MapShipperTransporter).filter(MapShipperTransporter.mst_shipper_id==shipper_id, MapShipperTransporter.mst_transporter_id==transporter_id).first()
            
            if not transporter_details:
                return(False, "transporter not tagged with the specific shipper")
            
            return (True,"")
            
        except Exception as e:
            session.rollback()
            return (False, str(e))
        finally:
            session.close()