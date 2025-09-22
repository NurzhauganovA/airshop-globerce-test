from collections.abc import Sequence
from typing import Any, Generic, Optional, TypeVar

from fastapi import Query
from fastapi_pagination.bases import AbstractPage, AbstractParams, CursorRawParams
from fastapi_pagination.cursor import CursorParams as BaseCursorParams
from fastapi_pagination.types import Cursor
from fastapi_pagination.utils import create_pydantic_model

T = TypeVar("T")


class CursorParamsWithOutTotal(BaseCursorParams):
    size: int = Query(10, ge=1, le=100, description="Page size")

    # Пришлось переопределить так как под капотом вызывается count
    def to_raw_params(self) -> CursorRawParams:
        raw = super().to_raw_params()
        raw.include_total = False
        return raw


class CursorPageWithOutTotal(AbstractPage[T], Generic[T]):
    items: Sequence[T]
    current_page: Optional[str] = None
    current_page_backwards: Optional[str] = None
    previous_page: Optional[str] = None
    next_page: Optional[str] = None

    __params_type__ = CursorParamsWithOutTotal

    @classmethod
    def create(
        cls,
        items: Sequence[T],
        params: AbstractParams,
        *,
        current: Optional[Cursor] = None,
        current_backwards: Optional[Cursor] = None,
        next_: Optional[Cursor] = None,
        previous: Optional[Cursor] = None,
        **kwargs: Any,
    ) -> "CursorParamsWithOutTotal[T]":
        if not isinstance(params, CursorParamsWithOutTotal):
            raise TypeError("CursorPageWithOutTotal expects CursorParamsWithOutTotal")

        kwargs.pop("params", None)  # не сохраняем params в модели
        return create_pydantic_model(
            cls,
            items=items,
            current_page=params.encode_cursor(current),
            current_page_backwards=params.encode_cursor(current_backwards),
            next_page=params.encode_cursor(next_),
            previous_page=params.encode_cursor(previous),
            **kwargs,
        )
