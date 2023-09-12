from pydantic import BaseModel
from uuid import UUID
from datetime import datetime

class FilterBidsRequest(BaseModel):
    shipper_id : UUID | None = None
    rc_id : UUID | None = None
    branch_id : UUID | None = None
    from_date : datetime | None = None
    to_date : datetime | None = None

class HistoricalRatesReq(BaseModel):
    transporter_id : UUID

class TransporterBidReq(BaseModel):
    transporter_id : UUID
    rate : float
    comment : str
