# from fastapi import Request
# from starlette.middleware.base import BaseHTTPMiddleware
# from jose import jwt
# import os

# from utils.response import ErrorResponse

# class AuthMiddleware(BaseHTTPMiddleware):
#     async def dispatch(self, request: Request, call_next):

#         token = request.headers.get("authorization", "").split("Bearer ")[1]

#         if not token:
#             return ErrorResponse(data=[],dev_msg="Token not found/invalid!",client_msg="You could not be authenticated, please try again with correct credentials!") 

#         try:
#                 payload = jwt.decode(token, os.getenv("SECRET"), algorithms=[os.getenv("ALGORITHM")])
#                 request.state.current_user = payload
#                 return await call_next(request)

#         except Exception as e:
#              return ErrorResponse(data=[],dev_msg=str(e),client_msg="You could not be authenticated, please try again with correct credentials!")

