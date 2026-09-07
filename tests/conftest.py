import pytest

from campaign_lab.analysis import clean
from campaign_lab.generate import generate


@pytest.fixture(scope="session")
def raw():
    return generate()


@pytest.fixture(scope="session")
def df(raw):
    return clean(raw)
