from dotenv import load_dotenv
load_dotenv()

import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from utils.db import generate_tables

from routes.routes import setup_routes
from utils.background_jobs import schedule_jobs
from config.socket import manager
# from utils.redis import Redis

# r = Redis()


app: FastAPI = FastAPI()

setup_routes(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials= True,
    allow_methods= ['*'],
    allow_headers= ['*']
)

# r.delete(sorted_set='133a35cd-d39b-4d22-8b02-56142f0ea63e')

# generate_tables()
# schedule_jobs()

@app.websocket("/ws/{bid_id}")
async def websocket_endpoint(websocket: WebSocket, bid_id: str):
    await manager.connect(websocket, bid_id)
    try:
        while True:
            data = await websocket.receive_text()
            await manager.broadcast(bid_id, f"Client says: {data}")

    except WebSocketDisconnect:
        manager.disconnect(websocket, bid_id)
        message = {"message": "Offline"}
        await manager.broadcast(bid_id, json.dumps(message))
