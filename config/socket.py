from fastapi import WebSocket
from typing import List,Dict


# class ConnectionManager:
#     def __init__(self):
#         self.active_connections: list[WebSocket] = []

#     async def connect(self, websocket: WebSocket):
#         await websocket.accept()
#         self.active_connections.append(websocket)

#     def disconnect(self, websocket: WebSocket):
#         self.active_connections.remove(websocket)

#     async def send_personal_message(self, message: str, websocket: WebSocket):
#         await websocket.send_text(message)

#     async def broadcast(self, message: str):
#         for connection in self.active_connections:
#             print(connection)
#             await connection.send_text(message)


# manager = ConnectionManager()


class ConnectionManager:
    def __init__(self):
        # Use a dictionary to store active connections for each bid_id (rooms)
        self.rooms: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, bid_id: str):
        await websocket.accept()
        if bid_id in self.rooms:
            self.rooms[bid_id].append(websocket)
        else:
            self.rooms[bid_id] = [websocket]

    def disconnect(self, websocket: WebSocket, bid_id: str):
        if bid_id in self.rooms:
            self.rooms[bid_id].remove(websocket)

    async def broadcast(self, bid_id: str, message: str):
        if bid_id in self.rooms:
            for connection in self.rooms[bid_id]:
                await connection.send_text(message)

manager = ConnectionManager()
