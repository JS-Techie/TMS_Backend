from fastapi_mail import FastMail, MessageSchema, MessageType
from pydantic import EmailStr



from utils.utilities import log
from schemas.mail import PriceMatchEmail


class Email:

    def price_match(self,recipients : [EmailStr],email_data: PriceMatchEmail,bid_id : str) -> (bool,any):

        try:

            with open("../services/price_match.html", "r") as template_file:
                html_template = template_file.read()

            email_body = html_template.render(
                transporter_name=email_data["transporter_name"],
                bid_id=bid_id,
                lowest_price=email_data["lowest_price"],
                negotiated_price=email_data["negotiated_price"],
                no_of_fleets_assigned=email_data["no_of_fleets_assigned"]
            )

            message = MessageSchema(
                subject=f"Price Match Request For Bid - {bid_id}",
                recipients=recipients,
                body=email_body,
                subtype=MessageType.html
            )

            return (True,message)
        
        except Exception as e:
            return (False,str(e))

    