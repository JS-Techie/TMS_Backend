from sqlalchemy.sql.functions import func
import datetime
import os

from utils.response import ErrorResponse
from config.db_config import Session
from models.models import Shipper as ShipperModel
from utils.utilities import log, convert_date_to_string
from config.scheduler import Scheduler

sched = Scheduler()


class Shipper:

    async def is_valid(self, shipper_id: str) -> (bool, str):

        session = Session()

        try:
            if not shipper_id:
                return (False, "The SHIPPER ID provided is empty")

            bid = session.query(ShipperModel).filter(
                ShipperModel.shpr_id == shipper_id, ShipperModel.is_active == True).first()

            if not bid:
                return (False, "Shipper ID not found!")

            return (True, "")

        except Exception as e:
            session.rollback()
            return (False, str(e))

        finally:
            session.close()
