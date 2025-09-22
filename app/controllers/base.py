# app/controllers/base_controller.py

from typing import Any, Dict, Generic, List, Optional, Type, TypeVar, Union

from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session
from sqlalchemy.orm.query import Query

# Define TypeVar to link the SQLAlchemy model type to the Pydantic schemas
ModelType = TypeVar("ModelType", bound=declarative_base())
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)


class BaseController(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    """
    A generic base class for all database controllers.
    It provides basic create, read, update, and delete functionality.
    """

    def __init__(self, model: Type[ModelType]):
        """
        Initializes the controller with a specific SQLAlchemy model.
        """
        self._model = model

    def get(self, db: Session, id: Any) -> Optional[ModelType]:
        """
        Retrieves a single record by its primary key.
        """
        return db.query(self._model).get(id)

    def get_multi(
        self, db: Session, *, skip: int = 0, limit: int = 100
    ) -> List[ModelType]:
        """
        Retrieves multiple records.
        """
        return db.query(self._model).offset(skip).limit(limit).all()

    def create(self, db: Session, *, obj_in: CreateSchemaType) -> ModelType:
        """
        Creates a new record in the database.
        """
        obj_in_data = jsonable_encoder(obj_in)
        db_obj = self._model(**obj_in_data)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update(
        self,
        db: Session,
        *,
        db_obj: ModelType,
        obj_in: Union[UpdateSchemaType, Dict[str, Any]]
    ) -> ModelType:
        """
        Updates an existing record.
        """
        obj_data = jsonable_encoder(db_obj)
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.dict(exclude_unset=True)
        for field in obj_data:
            if field in update_data:
                setattr(db_obj, field, update_data[field])
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def remove(self, db: Session, *, id: int) -> ModelType:
        """
        Removes a record from the database.
        """
        obj = db.query(self._model).get(id)
        db.delete(obj)
        db.commit()
        return obj

    def bulk_create(
        self, db: Session, *, many_obj: list[CreateSchemaType]
    ) -> list[ModelType] | list:
        """
        Bulk creates obj in the database.
        """
        objects = [self._model(**obj.model_dump()) for obj in many_obj]
        if not objects:
            return objects

        db.add_all(objects)
        db.commit()
        for obj in objects:
            db.refresh(obj)
        return objects

    def get_cursor_query(self, db: Session, base_query: Query | None = None):
        """В случае если в сущности нет created_at нужно переопределить метод"""
        if not getattr(self._model, "created_at", None):
            raise Exception("Необходимо переопределить метод")

        query = base_query or db.query(self._model)
        return query.order_by(self._model.created_at.desc(), self._model.id.desc())
