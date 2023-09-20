from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import json

from config.socket import manager
from routes.routes import setup_routes

app: FastAPI = FastAPI()
setup_routes(app)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await manager.broadcast(f"Client says: {data}")

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        message = {"message": "Offline"}
        await manager.broadcast(json.dumps(message))
