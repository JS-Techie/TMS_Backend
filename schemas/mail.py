from pydantic import BaseModel

class PriceMatchEmail(BaseModel):
    transporter_id : str
    lowest_price : float
    negotiated_price : float
    transporter_name : str
    no_of_fleets_assigned : int
    