from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import json

from config.socket import manager
from utils.background_jobs import schedule_jobs
from routes.routes import setup_routes


app: FastAPI = FastAPI()
setup_routes(app)
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

