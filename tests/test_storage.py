import pytest
import pandas as pd
from pandas import Timestamp
from unittest.mock import patch, MagicMock

from src.storage import Storage


@pytest.fixture
def storage_setup():
    # Time series with positive and negative powers
    timestamps = [
        Timestamp("01/01/2015 12:00:00"),
        Timestamp("02/01/2015 13:00:00"),
        Timestamp("03/01/2015 14:00:00"),
    ]
    powers = pd.Series([-100, 0, 150], index=timestamps)

    # Sector patch
    sector = patch("src.storage.Sector")
    sector_cls = sector.start()

    # Mocks pour load et generator
    sector_load = MagicMock(name="sector_load")
    sector_generator = MagicMock(name="sector_generator")

    # Configuration du comportement du mock : 1er appel pour load, 2e pour generator
    sector_cls.side_effect = [sector_load, sector_generator]

    yield {
        "powers": powers,
        "sector_cls": sector_cls,
        "sector_load": sector_load,
        "sector_generator": sector_generator,
    }

    patch.stopall()


def test_storage_initializes_load_and_generator(storage_setup):
    powers = storage_setup["powers"]
    sector_cls = storage_setup["sector_cls"]
    sector_load = storage_setup["sector_load"]
    sector_generator = storage_setup["sector_generator"]

    # Creation of the object storage
    storage = Storage("hydro pump storage", powers, is_controllable=True)

    # Check that Sector class has been called twice
    assert sector_cls.call_count == 2

    # Get the calls of Sector class
    load_call, generator_call = sector_cls.call_args_list

    # Check the names
    assert load_call.args[0] == "hydro pump storage"
    assert generator_call.args[0] == "hydro pump storage"

    # Check the powers series
    assert load_call.args[1].equals(powers[powers <= 0])
    assert generator_call.args[1].equals(powers[powers >= 0])

    # Check the parameter is_load
    assert load_call.kwargs.get("is_load") is True
    assert generator_call.kwargs.get("is_load", False) is False

    # Check the attributes
    assert storage.load is sector_load
    assert storage.generator is sector_generator
