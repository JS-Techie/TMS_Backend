import asyncio,nest_asyncio
from websockets.sync.client import connect
import json

nest_asyncio.apply()

async def send_event(sorted_bid_details:any):
    try :
        
       async with connect("ws://localhost:8000/ws") as websocket:
            message = await websocket.recv()
            print(f"Received: {message}")
            websocket.send(json.dumps(sorted_bid_details))
            
            await websocket.send_text("check")
            
            
            return True,""
    except Exception as e:
        return False, str(e)


# async def send_event(sorted_bid_details : any):
#     loop = asyncio.get_event_loop()
#     loop.run_until_complete(bid_details(sorted_bid_details=sorted_bid_details))