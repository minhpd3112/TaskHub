from typing import Generic, TypeVar

from pydantic import BaseModel

DataT = TypeVar("DataT")


class PaginationMeta(BaseModel):
    page: int
    limit: int
    total: int
    total_pages: int


class SuccessResponse(BaseModel, Generic[DataT]):
    data: DataT


class PaginatedResponse(BaseModel, Generic[DataT]):
    data: list[DataT]
    pagination: PaginationMeta


class ErrorDetail(BaseModel):
    field: str | None = None
    rule: str | None = None


class ErrorBody(BaseModel):
    code: str
    message: str
    details: ErrorDetail | list[ErrorDetail] | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody
