from typing import List, Type
from uuid import UUID

import pytest
from pydantic import SecretStr
from sqlalchemy import Column, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.orm.attributes import Mapped  # type: ignore[attr-defined]
from sqlalchemy.orm.decl_api import declarative_base
from starlite.middleware.session.memory_backend import MemoryBackendConfig

from starlite_users import StarliteUsersConfig
from starlite_users.adapter.sqlalchemy.guid import GUID
from starlite_users.adapter.sqlalchemy.mixins import (
    SQLAlchemyRoleMixin,
    SQLAlchemyUserMixin,
)
from starlite_users.config import RoleManagementHandlerConfig
from starlite_users.guards import roles_accepted, roles_required
from starlite_users.schema import (
    BaseUserCreateDTO,
    BaseUserRoleReadDTO,
    BaseUserUpdateDTO,
)
from starlite_users.service import BaseUserService
from tests.conftest import _Base, password_manager
from tests.constants import ENCODING_SECRET
from tests.utils import MockSQLAlchemyUserRepository

Base = declarative_base(cls=_Base)


class User(Base, SQLAlchemyUserMixin):  # type: ignore[valid-type, misc]
    __tablename__ = "user"

    roles: Mapped[List["Role"]] = relationship("Role", secondary="user_role", lazy="joined")


class Role(Base, SQLAlchemyRoleMixin):  # type: ignore[valid-type, misc]
    __tablename__ = "role"


class UserRole(Base):  # type: ignore[valid-type, misc]
    __tablename__ = "user_role"

    user_id = Column(GUID(), ForeignKey("user.id"))
    role_id = Column(GUID(), ForeignKey("role.id"))


class UserService(BaseUserService[User, BaseUserCreateDTO, BaseUserUpdateDTO, Role]):
    pass


@pytest.fixture()
def admin_role() -> Role:
    return Role(
        id=UUID("9b62b52c-4278-4124-aca8-783ab281c196"),
        name="administrator",
        description="X",
    )


@pytest.fixture()
def writer_role() -> Role:
    return Role(
        id=UUID("76ddde3c-91d0-4b58-baa4-bfc4b3892ab2"),
        name="writer",
        description="He who writes",
    )


@pytest.fixture()
def admin_user(admin_role: Role) -> User:
    return User(
        id=UUID("01676112-d644-4f93-ab32-562850e89549"),
        email="admin@example.com",
        password_hash=password_manager.hash(SecretStr("iamsuperadmin")),
        is_active=True,
        is_verified=True,
        roles=[admin_role],
    )


@pytest.fixture()
def generic_user() -> User:
    return User(
        id=UUID("555d9ddb-7033-4819-a983-e817237b88e5"),
        email="good@example.com",
        password_hash=password_manager.hash(SecretStr("justauser")),
        is_active=True,
        is_verified=True,
        roles=[],
    )


@pytest.fixture(
    params=[
        pytest.param("session", id="session"),
        pytest.param("jwt", id="jwt"),
        pytest.param("jwt_cookie", id="jwt_cookie"),
    ],
)
def starlite_users_config(
    request: pytest.FixtureRequest, mock_user_repository: MockSQLAlchemyUserRepository
) -> StarliteUsersConfig:
    return StarliteUsersConfig(  # pyright: ignore
        auth_backend=request.param,
        secret=ENCODING_SECRET,
        session_backend_config=MemoryBackendConfig(),
        user_model=User,
        user_read_dto=BaseUserRoleReadDTO,
        role_model=Role,
        user_service_class=UserService,
        user_repository_class=mock_user_repository,  # type: ignore[arg-type]
        role_management_handler_config=RoleManagementHandlerConfig(
            guards=[roles_accepted("administrator"), roles_required("administrator")]
        ),
    )


@pytest.fixture()
def mock_user_repository(
    admin_user: User,
    generic_user: User,
    unverified_user: User,
    admin_role: Role,
    writer_role: Role,
    monkeypatch: pytest.MonkeyPatch,
) -> Type[MockSQLAlchemyUserRepository]:
    UserRepository = MockSQLAlchemyUserRepository
    user_store = {
        str(admin_user.id): admin_user,
        str(generic_user.id): generic_user,
        str(unverified_user.id): unverified_user,
    }
    role_store = {
        str(admin_role.id): admin_role,
        str(writer_role.id): writer_role,
    }
    monkeypatch.setattr(UserRepository, "user_store", user_store)
    monkeypatch.setattr(UserRepository, "role_store", role_store)
    return UserRepository
