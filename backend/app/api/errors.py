"""Error handlers: every error leaves the API in the same JSON shape. Owner: Member A."""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.errors import AppError
from app.schemas import ErrorDetail, ErrorResponse

logger = logging.getLogger("code_apex")

_HTTP_CODES = {400: "bad_request", 404: "not_found", 405: "method_not_allowed"}


def error_response(
    status_code: int, code: str, message: str, details: dict | None = None
) -> JSONResponse:
    body = ErrorResponse(error=ErrorDetail(code=code, message=message, details=details))
    return JSONResponse(status_code=status_code, content=body.model_dump(mode="json"))


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError) -> JSONResponse:
        if exc.status_code >= 500:
            logger.error("%s on %s: %s", exc.code, request.url.path, exc.message)
        return error_response(exc.status_code, exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        problems = [
            {
                "field": ".".join(str(part) for part in error.get("loc", ())),
                "message": str(error.get("msg", "")),
            }
            for error in exc.errors()
        ]
        return error_response(422, "validation_error", "The request is not valid.", {"problems": problems})

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _HTTP_CODES.get(exc.status_code, "http_error")
        message = str(exc.detail) if exc.detail else "The request failed."
        return error_response(exc.status_code, code, message)

    @app.exception_handler(Exception)
    async def _unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error on %s", request.url.path)
        return error_response(500, "internal_error", "Something went wrong on the server.")