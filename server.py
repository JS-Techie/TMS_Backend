from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI,WebSocket,WebSocketDisconnect
from fastapi.responses import HTMLResponse

import json,datetime


from routes.routes import setup_routes
from config.socket import manager
from utils.background_jobs import schedule_jobs

app : FastAPI = FastAPI()


setup_routes(app)
# schedule_jobs()


html = """
<!DOCTYPE html>
<html>
    <head>
        <title>Chat</title>
    </head>
    <body>
        <h1>WebSocket Chat</h1>
        <ul id='messages'>
        </ul>
        <script>
            var ws = new WebSocket("ws://localhost:8000/ws");
            ws.onmessage = function(event) {
                var messages = document.getElementById('messages')
                var message = document.createElement('li')
                var content = document.createTextNode(event.data)
                message.appendChild(content)
                messages.appendChild(message)
            };
        </script>
    </body>
</html>
"""


@app.get("/html")
async def get():
    return HTMLResponse(html)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
                data = await websocket.receive_text()
                await manager.broadcast(f"Client says: {data}")
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        message = {"message":"Offline"}
        await manager.broadcast(json.dumps(message))
