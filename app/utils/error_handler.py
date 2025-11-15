from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

class ErrorHandler(Exception):
    def __init__(self, message: str, status_code: int):
        self.message = message
        self.status_code = status_code

class BadRequestError(ErrorHandler):
    def __init__(self, message: str = "Bad Request"):
        super().__init__(message, status.HTTP_400_BAD_REQUEST)

class UnprocessableEntityError(ErrorHandler):
    def __init__(self, message: str = "Unprocessable Entity"):
        super().__init__(message, status.HTTP_422_UNPROCESSABLE_ENTITY)

class TooManyRequestsError(ErrorHandler):
    def __init__(self, message: str = "Too Many Requests"):
        super().__init__(message, status.HTTP_429_TOO_MANY_REQUESTS)

def setup_error_handlers(app):
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"success": False, "message": str(exc.detail)},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        errors = exc.errors()
        if errors and len(errors) > 0:
            error = errors[0]
            field = error.get('loc', [])[-1] if error.get('loc') else ''
            error_msg = error.get('msg', 'Validation error')
            full_msg = f"{field}: {error_msg}"
        else:
            full_msg = 'Validation error'
        
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"success": False, "message": full_msg},
        )

    @app.exception_handler(ErrorHandler)
    async def error_handler_exception_handler(request: Request, exc: ErrorHandler):
        return JSONResponse(
            status_code=exc.status_code,
            content={"success": False, "message": exc.message},
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"success": False, "message": "Internal Server Error"},
        )

    @app.exception_handler(BadRequestError)
    async def bad_request_handler(request: Request, exc: BadRequestError):
        return JSONResponse(
            status_code=exc.status_code,
            content={"success": False, "message": exc.message},
        )

    @app.exception_handler(UnprocessableEntityError)
    async def unprocessable_entity_handler(request: Request, exc: UnprocessableEntityError):
        return JSONResponse(
            status_code=exc.status_code,
            content={"success": False, "message": exc.message},
        )

    @app.exception_handler(TooManyRequestsError)
    async def too_many_requests_handler(request: Request, exc: TooManyRequestsError):
        return JSONResponse(
            status_code=exc.status_code,
            content={"success": False, "message": exc.message},
        )