from typing import Any

from pydantic import BaseModel


class APIResponse(BaseModel):
    code: int = 0
    message: str = "success"
    data: Any = None


def success(data: Any = None, message: str = "success") -> dict:
    return {"code": 0, "message": message, "data": data}


def error(code: int, message: str, data: Any = None) -> dict:
    return {"code": code, "message": message, "data": data}