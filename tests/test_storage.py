from unittest.mock import patch, MagicMock, call, ANY

import pandas as pd
import pytest
from pandas import Timestamp

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

    # Load et generator sectors mocks
    sector_load = MagicMock(name="sector_load")
    sector_generator = MagicMock(name="sector_generator")

    # Configuring mock behaviour: 1st call for load, 2nd for generator
    sector_cls = patch("src.storage.Sector", side_effect=[sector_load, sector_generator]).start()

    yield {
        "powers": powers,
        "sector_cls": sector_cls,
        "sector_load": sector_load,
        "sector_generator": sector_generator,
    }

    patch.stopall()


@pytest.fixture(scope='function')
def storage_setup2(storage_setup):
    powers = storage_setup["powers"]
    sector_load = storage_setup["sector_load"]
    sector_generator = storage_setup["sector_generator"]

    sector_load.power_rating = 4
    sector_generator.power_rating = 4

    def gen_side_effect(power):
        sector_generator.available_power = power

    def load_side_effect(power):
        sector_load.available_power = power

    sector_generator.set_available_power.side_effect = gen_side_effect
    sector_load.set_available_power.side_effect = load_side_effect

    storage = Storage(sector_name="hydro pump storage", historical_powers=powers, is_controllable=True, opf_mode=True)
    storage.build_energy_constraints(datetime_index=list(powers.index), energy_rating=10, mean_inflow=1)

    yield {
        "powers": powers,
        "storage": storage
    }

    patch.stopall()


# TODO add test with opf_mode=True and check indexes
def test_storage_initializes_load_and_generator(storage_setup):
    powers = storage_setup["powers"]
    sector_cls = storage_setup["sector_cls"]
    sector_load = storage_setup["sector_load"]
    sector_generator = storage_setup["sector_generator"]

    # Creation of the object storage
    storage = Storage("hydro pump storage", powers, is_controllable=True, opf_mode=False)

    # Check that Sector class has been called properly
    assert sector_cls.call_count == 2

    expected_calls = [
        call("hydro pump storage", ANY, is_controllable=True, is_load=True),
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


def test_build_energy_constraints():
    # Time series with positive and negative powers
    timestamps = [Timestamp(f"01/01/2015 {i}:00:00") for i in range(6)]
    powers = pd.Series([-30, 40, 0, 0, 0, 0], index=timestamps)

    # Creation of the object storage
    storage = Storage(sector_name="hydro pump storage", historical_powers=powers, is_controllable=True, opf_mode=True)
    storage.build_energy_constraints(datetime_index=timestamps, energy_rating=100, mean_inflow=1)
    assert (storage._energy_constraints.values == [
        (0, 100),
        (0, 100),
        (2, 100),
        (18, 88),
        (34, 69),  # inflow + 1/2 consumption rating = +16 | inflow - 1/2 production rating = -19
        (50, 50),
    ]).all()
    storage.build_energy_constraints(datetime_index=timestamps, energy_rating=100, mean_inflow=30)
    assert (storage._energy_constraints.values == [
        (0, 50),
        (0, 50),
        (0, 50),
        (0, 50),
        (5, 50),  # inflow + 1/2 consumption rating = +45 | inflow - 1/2 production rating = +10 -> 0
        (50, 50),
    ]).all()
    storage.build_energy_constraints(datetime_index=timestamps, energy_rating=100, mean_inflow=-30)
    assert (storage._energy_constraints.values == [
        (50, 100),
        (50, 100),
        (50, 100),
        (50, 100),
        (50, 100),  # inflow + 1/2 consumption rating = -15 -> 0 | inflow - 1/2 production rating = -50
        (50, 50),
    ]).all()


def test_update_availabilities(storage_setup2):
    powers = storage_setup2["powers"]
    storage = storage_setup2["storage"]

    assert (storage._energy_constraints.values == [
        (0, 7),
        (2, 6),  # inflow + 1/2 consumption rating = +3 | inflow - 1/2 production rating = -1
        (5, 5),
    ]).all()
    for (hour, stored_energy, constrained_power, available_gen, available_load) in [
        (1, 0, -1, 0, 3),
        (1, 1, 0, 0, 4),
        (1, 2, 0, 1, 3),
        (1, 4, 0, 3, 1),
        (1, 6, 1, 3, 0),
        (1, 7, 2, 2, 0),
        (2, 2, -2, 0, 0),
        (2, 4, 0, 0, 0),
        (2, 5, 1, 0, 0),
        (2, 6, 2, 0, 0),

    ]:
        storage._stored_energy = stored_energy
        storage.update_availabilities(timestep=powers.index[hour])

        assert storage.constrained_production == constrained_power
        assert storage.generator.available_power == available_gen
        assert storage.load.available_power == available_load


@pytest.mark.parametrize("constrained_power, gen_power, load_power, next_energy", [
    (0, 1, 0, 5),
    (0, 0, 0, 6),
    (0, 0, 1, 7),
    (2, 1, 0, 3),
    (2, 0, 0, 4),
    (-1, 0, 0, 7),
    (-0.5, 0, 0.5, 7),
])
def test_compute_new_energy(storage_setup2, constrained_power, gen_power, load_power, next_energy):
    storage = storage_setup2["storage"]

    storage.load.current_power = load_power
    storage.generator.current_power = gen_power
    storage._constrained_production = constrained_power
    storage._timestep = Timestamp("01/01/2015 12:00:00")

    # Compute the new energy
    storage._compute_new_energy()

    # Check results
    expected_next_energy = next_energy  # initial energy + inflow + consumption - production
    assert storage._next_energy == expected_next_energy


def test_update_energy_updates_expected_attributes(storage_setup2):
    storage = storage_setup2["storage"]

    # Run function
    storage._next_energy = 10
    storage.update_energy()

    # Check attributes
    assert storage._stored_energy == 10
    assert storage._next_energy is None
