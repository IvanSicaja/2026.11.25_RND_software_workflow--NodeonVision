"""Shared pytest fixtures for the system tests and the pytest-bdd scenarios."""
import pytest

from nodeon_driver import NodeonDriver


@pytest.fixture
def drv(tmp_path):
    """A fresh Nodeon (own temporary folder and settings) for every test."""
    driver = NodeonDriver(tmp_path)
    yield driver
    driver.close()
    driver.restore()
