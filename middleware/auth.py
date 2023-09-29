# class AuthMiddleware(BaseHTTPMiddleware):
#     async def dispatch(self, request: Request, call_next):
#         try:
#             prefixes = ["/api/master/", "/api/shipper/",
#                         "/api/transporter/", "/api/secure/", "/api/track"]
#             if any(prefix in request.url.path for prefix in prefixes):
#                 token = request.headers.get(
#                     "authorization", "").split("Bearer ")[1]
#                 print("---====token ", token)

#                 try:

#                     payload = jwt.decode(
#                         token, SECRET_KEY, algorithms=[ALGORITHM])

#                     print("---====payload ", payload)

#                     # request.state.user_id = payload.get("id")

#                     # request.state.user_type = payload.get("user_type")

#                     request.state.current_user = payload

#                     response = await call_next(request)

#                     return response

#                 except ExpiredSignatureError:

#                     raise HTTPException(
#                         status_code=401, detail="Token has expired")

#                 except JWTError:

#                     raise HTTPException(
#                         status_code=401, detail="Invalid token")

#                 except JWSSignatureError:

#                     raise HTTPException(
#                         status_code=401, detail="Invalid token signature")

#             else:

#                 return await call_next(request)

#         except Exception as ex:

#             print("auth_error :-----", ex)

#             raise HTTPException(
#                 status_code=401, detail=f"Server Error: {str(ex)}")
