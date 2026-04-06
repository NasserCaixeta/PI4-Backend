from pydantic import BaseModel


class ErrorResponse(BaseModel):
    error: str
    code: str


class HealthResponse(BaseModel):
    status: str
    database: str
