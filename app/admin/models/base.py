from sqladmin.authentication import AuthenticationBackend
from sqladmin.models import ModelViewMeta, ModelView
from sqlalchemy import inspect

from app.core import security


class BaseAdminMeta(ModelViewMeta):
    def __new__(mcls, name, bases, attrs, **kwargs):
        cls = super().__new__(mcls, name, bases, attrs, **kwargs)

        model = getattr(cls, "model", None)
        if model is None:
            return cls

        if getattr(cls, "column_list", None):
            return cls

        exclude = set(getattr(cls, "column_exclude_list", None) or ())

        mapper = inspect(model)
        columns = [col.key for col in mapper.columns]
        cls.column_list = [name for name in columns if name not in exclude]
        return cls


class BaseAdmin(ModelView, metaclass=BaseAdminMeta):
    column_list = None  # Если не заполнять возьмет все поля модели


class AdminAuth(AuthenticationBackend):
    def __init__(self, secret_key: str, session_factory, user_controller):
        super().__init__(secret_key=secret_key)
        self._session_factory = session_factory
        self._user_controller = user_controller

    def _authenticate_user(self, db, username: str, password: str):
        user = self._user_controller.get_by_username_or_phone(
            db, user_credential=username
        )
        if not user:
            return None
        if not security.verify_password(password, user.password_hash):
            return None
        if not getattr(user, "is_admin", False):
            return None
        return user

    async def login(self, request):
        form = await request.form()
        username = form.get("username")
        password = form.get("password")
        if not username or not password:
            return False

        with self._session_factory() as db:
            user = self._authenticate_user(db, username, password)
        if not user:
            return False

        request.session.update({"user_id": user.id})
        return True

    async def logout(self, request):
        request.session.clear()
        return True

    async def authenticate(self, request):
        user_id = request.session.get("user_id")
        if not user_id:
            return False

        with self._session_factory() as db:
            user = self._user_controller.get(db, id=user_id)

        if not user or not getattr(user, "is_admin", False):
            request.session.clear()
            return False

        return True
