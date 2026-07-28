from collections.abc import Sequence
from typing import Any

from fastapi.responses import JSONResponse


def build_error_response(
    *,
    status_code: int,
    request_id: str,
    error_code: str,
    message: str,
    details: Sequence[dict[str, Any]] | dict[str, Any] | None = None,
) -> JSONResponse:
    payload: dict[str, Any] = {
        "error_code": error_code,
        "message": message,
        "request_id": request_id,
    }
    if details is not None:
        payload["details"] = details
    return JSONResponse(
        status_code=status_code,
        content=payload,
        headers={"X-Request-ID": request_id},
    )
