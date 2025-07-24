import pytest
import pandas as pd
from pandas import Timestamp
from unittest.mock import patch, MagicMock, call, ANY

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

    # Load et generator sectors mocks
    sector_load = MagicMock(name="sector_load")
    sector_generator = MagicMock(name="sector_generator")

    # Configuring mock behaviour: 1st call for load, 2nd for generator
    sector_cls.side_effect = [sector_load, sector_generator]

    yield {
        "powers": powers,
        "sector_cls": sector_cls,
        "sector_load": sector_load,
        "sector_generator": sector_generator,
    }

    patch.stopall()

#TODO add test with opf_mode=True and check indexes
def test_storage_initializes_load_and_generator(storage_setup):
    powers = storage_setup["powers"]
    sector_cls = storage_setup["sector_cls"]
    sector_load = storage_setup["sector_load"]
    sector_generator = storage_setup["sector_generator"]

    # Creation of the object storage
    storage = Storage("hydro pump storage", powers, is_controllable=True,opf_mode=False)

    # Check that Sector class has been called properly
    assert sector_cls.call_count == 2

    expected_calls = [
        call("hydro pump storage", ANY, is_controllable=True, is_storage_load=True),
        call("hydro pump storage", ANY, is_controllable=True)
    ]

    sector_cls.assert_has_calls(expected_calls, any_order=False)

    # Verify series in calls
    actual_calls = sector_cls.call_args_list

    # Load call
    load_call = actual_calls[0]
    expected_load_series = powers[powers <= 0]
    pd.testing.assert_series_equal(load_call.args[1], expected_load_series)

    # Generator call
    generator_call = actual_calls[1]
    expected_generator_series = powers[powers >= 0]
    pd.testing.assert_series_equal(generator_call.args[1], expected_generator_series)

    # Check the attributes
    assert storage.load is sector_load
    assert storage.generator is sector_generator
