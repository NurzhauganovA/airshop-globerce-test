from fastapi import APIRouter, Depends
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.pagination.cursor_pagination import (
    CursorParamsWithOutTotal,
    CursorPageWithOutTotal,
)
from app.controllers.internal import (
    country_controller,
    city_controller,
)

from app.schemas.address_schema import (
    CountryModelSchema,
    CityModelSchema,
)

router = APIRouter()


@router.get(
    "/common/countries", response_model=CursorPageWithOutTotal[CountryModelSchema]
)
async def get_countries(
    db: Session = Depends(get_db),
    params: CursorParamsWithOutTotal = Depends(),
):
    query = country_controller.get_cursor_query(db=db)
    return paginate(db, query, params)


@router.get("/common/cities", response_model=CursorPageWithOutTotal[CityModelSchema])
async def get_cities(
    db: Session = Depends(get_db),
    params: CursorParamsWithOutTotal = Depends(),
):
    query = city_controller.get_cursor_query(db=db)
    return paginate(db, query, params)
