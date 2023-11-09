from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field
from typing import Union


class FilterBidsRequest(BaseModel):
    shipper_id: UUID | None = None
    rc_id: UUID | None = None
    branch_id: UUID | None = None
    from_date: datetime | None = None
    to_date: datetime | None = None


class HistoricalRatesReq(BaseModel):
    transporter_id: UUID


class TransporterBidReq(BaseModel):
    rate: float
    comment: str


class TransporterAssignReq(BaseModel):
    la_transporter_id: UUID
    trans_pos_in_bid: str
    price: float
    price_difference_percent: float
    no_of_fleets_assigned: int
    
    
class TransporterBidMatchRequest(BaseModel):
    transporter_id: UUID
    trans_pos_in_bid: str
    rate : float
    comment : str | None = None


class TransporterUnassignRequest(BaseModel):
    transporter_id : str
    unassignment_reason : str

class TransporterLostBidsReq(BaseModel):
    particpated : bool

class CancelBidReq(BaseModel):
    reason : str
    
    
class NotificationReq(BaseModel):
    nt_receiver_id : str
    nt_text : str=Field(..., min_length=1)
    nt_type : Union[str, None] = Field(None, min_length=1)  
    nt_deep_link : str=Field(..., min_length=1)
    
    class Config:
        orm_mode=True
        anystr_strip_whitespace = True