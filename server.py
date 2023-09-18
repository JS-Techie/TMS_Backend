from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI,WebSocket,WebSocketDisconnect
import json,datetime


from routes.routes import setup_routes
from config.socket import manager

from utils.db import generate_tables

app : FastAPI = FastAPI()


app = FastAPI()




setup_routes(app)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    now = datetime.datetime.now()
    current_time = now.strftime("%H:%M")
    try:
        while True:
            data = await websocket.receive_text()
            if data == "check":
                # Respond to the heartbeat message
                await websocket.send_text("pong")
            else:
                # await manager.send_personal_message(f"You wrote: {data}", websocket)
                message = {"time":current_time,"message":data}
                await manager.broadcast(json.dumps(message))
            
    except WebSocketDisconnect:
        # manager.disconnect(websocket)
        message = {"time":current_time,"message":"Offline"}
        await manager.broadcast(json.dumps(message))

