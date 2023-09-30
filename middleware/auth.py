from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from jose import jwt, jws
from jose.exceptions import JWTError
from fastapi.responses import JSONResponse
import os

from utils.response import ErrorResponse
from utils.utilities import log


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):

        prefixes = ['/api/v1/shipper/bid', "api/v1/transporter/bid"]

        try:

            if any(prefix in request.url.path for prefix in prefixes):
                auth_header = request.headers.get("authorization", "")
                log("AUTH HEADER", auth_header)

                if not auth_header:
                    error_response = ErrorResponse(
                        data=[], dev_msg="Token not found!", client_msg=os.getenv("GENERIC_LOGIN_ERROR")
                    )
                    return JSONResponse(content=error_response, status_code=401)

                if not auth_header.startswith("Bearer"):
                    error_response = ErrorResponse(
                        data=[], dev_msg="Token is invalid because no Bearer!", client_msg=os.getenv("GENERIC_LOGIN_ERROR")
                    )
                    return JSONResponse(content=error_response, status_code=401)

                split_token = auth_header.split(" ")

                log("LENGTH OF SPLIT TOKEN", len(split_token))

                if not split_token or len(split_token) <= 1:
                    error_response = ErrorResponse(
                        data=[], dev_msg="Token is invalid because no token after Bearer!", client_msg=os.getenv("GENERIC_LOGIN_ERROR")
                    )
                    return JSONResponse(content=error_response, status_code=401)

                token = split_token[1]

                log("TOKEN", token)

                if not token:
                    error_response = ErrorResponse(
                        data=[], dev_msg="Token not found/invalid!", client_msg=os.getenv("GENERIC_LOGIN_ERROR")
                    )
                    return JSONResponse(content=error_response, status_code=401)

                log("JWT SECRET", os.getenv("JWT_SECRET"))
                log("ALGO", os.getenv("JWT_ALGORITHM"))

                payload = jwt.decode(token=token, key=os.getenv("JWT_SECRET"), algorithms=[os.getenv("JWT_ALGORITHM")], 
                                     options={
                    "verify_signature": False
                }
                )

                request.state.current_user = payload

                log("PAYLOAD",payload)

            return await call_next(request)

        except JWTError as jwt_error:

            error_response = ErrorResponse(
                data=[], dev_msg=str(jwt_error), client_msg="You could not be authenticated, please try again with correct credentials!"
            )
            return JSONResponse(content=error_response, status_code=401)

        except Exception as e:
            log("IN EXCEPT")
            error_response = ErrorResponse(
                data=[], dev_msg=str(e), client_msg="You could not be authenticated, please try again with correct credentials!"
            )
            return JSONResponse(content=error_response, status_code=401)
