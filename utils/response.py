from fastapi import Response, status


def SuccessResponse(data: any, dev_msg: str = 'New Record successfully created.', client_msg: str = 'New Record successfully created.'):
    Response.status_code = status.HTTP_200_OK
    return {
        "success": True,
        "data": data,
        "clientMessage": client_msg,
        "devMessage": dev_msg
    }


def SuccessNoContentResponse(dev_msg: str = "Data deleted successfully", client_msg: str = 'Data deleted successfully'):
    Response.status_code = status.HTTP_204_NO_CONTENT
    return {
        "success": True,
        "data": [],
        "clientMessage": client_msg,
        "devMessage": dev_msg
    }


def ErrorResponse(data: any, dev_msg: str, client_msg: str = "Something went wrong, please try again!"):
    Response.status_code = status.HTTP_400_BAD_REQUEST
    return {
        "success": False,
        "data": data,
        "clientMessage": client_msg,
        "devMessage": dev_msg
    }


def AuthError(dev_msg: str = "Authorization error. Insufficient privileges for the requested operation.", client_msg: str = "Access denied. You don't have permission to perform this action.", data: str = None):
    Response.status_code = status.HTTP_401_UNAUTHORIZED
    return {
        "success": False,
        "data": data,
        "clientMessage": client_msg,
        "devMessage": dev_msg
    }


def DataNotFoundError(dev_msg: str = "Resource not found with ID"):
    Response.status_code = status.HTTP_404_NOT_FOUND
    return {
        "success": False,
        "data": None,
        "clientMessage": "No data found.",
        "devMessage": dev_msg
    }


def AlreadyExistError():
    Response.status_code = status.HTTP_409_CONFLICT
    return {
        "success": False,
        "data": None,
        "clientMessage": "This data already exists.",
        "devMessage": "Same resource is already exists!!!"
    }


def ServerError(err: any, errMsg: str):
    Response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    return {
        "success": False,
        "data": err,
        "clientMessage": "Sorry,something went wrong, please try again in sometime!",
        "devMessage": errMsg
    }


def NoModification(dev_msg: str = "No new data to Modify", client_msg="The content you requested is already up-to-date."):
    Response.status_code = status.HTTP_304_NOT_MODIFIED
    return {
        "success": True,
        "data": None,
        "clientMessage": client_msg,
        "devMessage": dev_msg
    }
