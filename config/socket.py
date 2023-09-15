# from fastapi_socketio import SocketManager

# # socket = None 

# # def setup_socket(app):

# #     global socket

# #     socket = SocketManager(app=app)
    
# #     return socket


# import socketio

# def setup_socket():
#     sio: any = socketio.AsyncServer(async_mode="asgi")
#     socket_app = socketio.ASGIApp(sio)
    
#     return (sio,socket_app)