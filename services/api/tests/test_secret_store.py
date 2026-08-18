"""Tests for HelmSecretStore."""

from pathlib import Path
import pytest
from services.api.auth.secret_store import HelmSecretStore


def test_helm_secret_store_in_memory():
    store = HelmSecretStore(memory_only=True)
    assert store.load("google_ads") == {}
    assert not store.has_credentials("google_ads")

    store.save("google_ads", {"client_id": "test_id", "developer_token": "token_123"})
    assert store.has_credentials("google_ads")
    creds = store.load("google_ads")
    assert creds["client_id"] == "test_id"
    assert creds["developer_token"] == "token_123"

    store.delete("google_ads")
    assert store.load("google_ads") == {}
    assert not store.has_credentials("google_ads")


def test_helm_secret_store_disk_persistence(tmp_path: Path):
    vault_file = tmp_path / "custom_vault.json"
    store = HelmSecretStore(storage_path=vault_file)
    
    store.save("meta_ads", {"access_token": "EAAxxx", "account_id": "act_12345"})
    assert vault_file.exists()

    # Re-instantiate from disk
    store2 = HelmSecretStore(storage_path=vault_file)
    creds = store2.load("meta_ads")
    assert creds["account_id"] == "act_12345"
    assert creds["access_token"] == "EAAxxx"


def test_home_directory_never_touched(monkeypatch, tmp_path: Path):
    fake_home = tmp_path / "fake_home"
    fake_home.mkdir()
    monkeypatch.setenv("USERPROFILE", str(fake_home))
    monkeypatch.setenv("HOME", str(fake_home))

    vault_file = tmp_path / "backend_vault.json"
    store = HelmSecretStore(storage_path=vault_file)
    store.save("google_ads", {"refresh_token": "rt_test"})

    # Assert ~/.mureo was never created or accessed
    assert not (fake_home / ".mureo").exists()
