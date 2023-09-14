from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi_socketio import SocketManager

from routes.routes import setup_routes
from config.socket import setup_socket

app : FastAPI = FastAPI()

socket = setup_socket(app)
setup_routes(app)


socket.on("bid")
async def test (sid,*args,**kwargs):
    print(sid,args,kwargs)


