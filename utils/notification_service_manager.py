from fastapi import Request
import os, httpx
from typing import List
from pydantic import BaseModel

from utils.utilities import log


class NotificationServiceManagerReq(BaseModel):
    receiver_ids:List[str]
    text:str
    type:str | None = None
    deep_link:str
    shipper_id:str | None = None
    branch_id:str | None = None
    transporter_id:str | None = None
    email:str | None = None
    subject:str | None = None
    content:str | None = None
    name:str | None = None
    otp:str | None = None
    msisdn:str | None = None

async def notification_service_manager(authtoken: str, req:NotificationServiceManagerReq) -> (any, str):
    
    host=os.getenv("BACKEND_HOST")
    notification_url = f"{host}/api/secure/notification/"

    async with httpx.AsyncClient() as client:
        try:    
            payload= {
                "receiver_ids": req.receiver_ids,
                "text": req.text,
                "type": req.type,
                "deep_link": req.deep_link,
                "shipper_id": req.shipper_id,
                "branch_id": req.branch_id,
                "transporter_id": req.transporter_id,
                "email": req.email,
                "subject": req.subject,
                "content": req.content,
                "name": req.name,
                "otp": req.otp,
                "msisdn": req.msisdn
            }
            
            headers = {
                'Accept': 'application/json',
                'Content-Type':'application/json',
                'Authorization':authtoken
            }
            response = await client.post(notification_url, json=payload, headers=headers)

            log(":::: NOTIFICATION URL HIT RESPONSE FROM NOTIFICATION SERVICE MANAGER ::::", response)
            log(":::: NOTIFICATION URL HIT RESPONSE TEXT FROM NOTIFICATION SERVICE MANAGER ::::", response.json())
            
            return(response,"")

        except Exception as e:
            print(e)
            return("",str(e))
    
    