""" 모든 창구가 같이 쓰는 응밥 양식 """

from typing import Generic, TypeVar

from pydantic import BaseModel

T=TypeVar("T")

class DataResponse(BaseModel, Generic[T]):
    data: T

    