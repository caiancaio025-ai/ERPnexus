import os

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.auth.access import AVAILABLE_MODULES, AVAILABLE_ROLES
from app.core.config import settings


class LoginInput(BaseModel):
    identifier: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=3, max_length=128)

    @model_validator(mode="after")
    def validate_login_password(self) -> "LoginInput":
        # Excecao EXCLUSIVA para a conta local pre-cadastrada de testes.
        # Em producao e para qualquer outra conta, preservar minimo de 8.
        if len(self.password) < 8:
            dev_login = (
                settings.app_env == "development"
                and os.environ.get("SENTICO_DEV_TEST_ACCOUNT") == "1"
                and self.identifier.strip().lower() == "adm"
                and self.password == "123"
            )
            if not dev_login:
                raise ValueError("A senha deve ter pelo menos 8 caracteres.")
        return self


class UserOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str
    username: str
    role: str
    modules: list[str]
    is_active: bool


class AdminUserCreate(BaseModel):
    name: str = Field(min_length=3, max_length=120)
    email: str = Field(min_length=5, max_length=254)
    username: str = Field(min_length=3, max_length=60, pattern=r"^[a-zA-Z0-9._-]+$")
    password: str = Field(min_length=8, max_length=128)
    role: str
    modules: list[str] = Field(default_factory=list)
    is_active: bool = True

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in AVAILABLE_ROLES:
            raise ValueError("Perfil de usuário inválido.")
        return normalized

    @field_validator("modules")
    @classmethod
    def validate_modules(cls, value: list[str]) -> list[str]:
        invalid = set(value) - set(AVAILABLE_MODULES)
        if invalid:
            raise ValueError(f"Módulos inválidos: {', '.join(sorted(invalid))}.")
        return value


class AdminUserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=3, max_length=120)
    email: str | None = Field(default=None, min_length=5, max_length=254)
    username: str | None = Field(
        default=None, min_length=3, max_length=60, pattern=r"^[a-zA-Z0-9._-]+$"
    )
    password: str | None = Field(default=None, min_length=8, max_length=128)
    role: str | None = None
    modules: list[str] | None = None
    is_active: bool | None = None

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = value.strip().lower()
        if normalized not in AVAILABLE_ROLES:
            raise ValueError("Perfil de usuário inválido.")
        return normalized

    @field_validator("modules")
    @classmethod
    def validate_modules(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return value
        invalid = set(value) - set(AVAILABLE_MODULES)
        if invalid:
            raise ValueError(f"Módulos inválidos: {', '.join(sorted(invalid))}.")
        return value
