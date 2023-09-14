from fastapi_socketio import SocketManager

socket = {} 

def setup_socket(app):

    global socket

    socket_manager = SocketManager(app=app)
    socket = socket_manager
    
    return socket_manager