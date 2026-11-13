"""Cobertura da conta de teste apenas para desenvolvimento."""

import os

import pytest
from pydantic import ValidationError

from app.auth.schemas import LoginInput
from app.core.config import settings


def test_short_password_only_for_explicit_adm_dev(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setenv("SENTICO_DEV_TEST_ACCOUNT", "1")
    assert LoginInput(identifier="adm", password="123").password == "123"
    with pytest.raises(ValidationError):
        LoginInput(identifier="outro", password="123")
    with pytest.raises(ValidationError):
        LoginInput(identifier="adm", password="456")


def test_weak_login_denied_when_disabled_or_production(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.delenv("SENTICO_DEV_TEST_ACCOUNT", raising=False)
    with pytest.raises(ValidationError):
        LoginInput(identifier="adm", password="123")
    monkeypatch.setenv("SENTICO_DEV_TEST_ACCOUNT", "1")
    monkeypatch.setattr(settings, "app_env", "production")
    with pytest.raises(ValidationError):
        LoginInput(identifier="adm", password="123")
    assert LoginInput(identifier="adm", password="senha-forte-123").identifier == "adm"
