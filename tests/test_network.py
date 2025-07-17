from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from pandas import Timestamp

from src.network import Network


@pytest.fixture(scope="function")
def network_setup():
    # --- Timestamps ---
    timestamps = [
        Timestamp("01/01/2015  12:00:00"),
        Timestamp("05/02/2015  13:00:00"),
        Timestamp("10/03/2015  14:00:00"),
        Timestamp("15/04/2015  09:00:00"),
        Timestamp("20/05/2015  16:00:00"),
        Timestamp("25/06/2015  08:00:00"),
        Timestamp("30/07/2015  19:00:00"),
        Timestamp("04/09/2015  11:00:00"),
        Timestamp("10/11/2015  22:00:00"),
    ]

    # --- Data ---
    historical_prices = pd.Series([50, 55, 53, 48, 60, 58, 62, 64, 59], index=timestamps)
    sectors_historical_powers = pd.DataFrame({
        "solar": [100, 150, 200, 250, 180, 300, 270, 220, 190],
        "hydro pump storage": [-50, -60, 40, -20, 60, -70, 80, -10, 30],
    }, index=timestamps)

    # --- Patch Zone ---
    zone_cls = patch("src.network.Zone").start()
    zone = MagicMock(name="zone_mock")
    zone.name = "FR"
    zone_cls.return_value = zone

    yield {
        "historical_prices": historical_prices,
        "sectors_historical_powers": sectors_historical_powers,
        "storages": ["hydro pump storage"],
        "controllable_sectors": ["hydro pump storage"],
        "zone_cls": zone_cls,
        "zone": zone,
    }

    patch.stopall()


def make_sector(name, price_model, is_storage_load):
    mock = MagicMock()
    mock.name = name
    mock.price_model = price_model
    mock.is_storage_load = is_storage_load
    return mock


def test_add_zone(network_setup):
    setup = network_setup
    network = Network()

    # Add zone
    skipped_timestep_counter = network.add_zone(zone_name="FR",
                                                sectors_historical_powers=setup["sectors_historical_powers"],
                                                storages=setup["storages"],
                                                controllable_sectors=setup["controllable_sectors"],
                                                historical_prices=setup["historical_prices"])

    # Check that Zone has been created with the correct parameters
    setup["zone_cls"].assert_called_once_with("FR", setup["historical_prices"])

    # Check add_sector et add_storage calls
    setup["zone"].add_sector.assert_called_once_with("solar", setup["sectors_historical_powers"]["solar"],
                                                     False)
    setup["zone"].add_storage.assert_called_once_with("hydro pump storage",
                                                      setup["sectors_historical_powers"]["hydro pump storage"],
                                                      True)

    # Check that zone has been added to networks.zone
    assert setup["zone"] in network._zones.values()
    pd.testing.assert_index_equal(network._datetime_index, setup["sectors_historical_powers"].index)
    assert skipped_timestep_counter == 0


def test_add_zone_updates_datetime_index(network_setup):
    setup = network_setup
    network = Network()

    timestamps = pd.DatetimeIndex([
        Timestamp("01/01/2015  12:00:00"),
        Timestamp("05/02/2015  13:00:00"),
        Timestamp("10/03/2015  14:00:00"),
        Timestamp("15/04/2015  09:00:00"),
        Timestamp("20/05/2015  16:00:00"),
        Timestamp("25/06/2015  08:00:00"),
        Timestamp("30/07/2015  19:00:00"),
        Timestamp("04/09/2015  11:00:00"),
        Timestamp("10/11/2015  22:00:00"),
    ])

    network._datetime_index = timestamps

    # --- Data ---
    historical_prices = pd.Series([50, None, None, 48, None, None, None, None, None], index=timestamps)
    sectors_historical_powers = pd.DataFrame({
        "solar": [100, 150, 200, 250, 180, 300, 270, 220, 190],
        "hydro pump storage": [-50, -60, 40, -20, 60, -70, 80, -10, 30],
    }, index=timestamps)

    skipped_timestep_counter = network.add_zone(zone_name="FR", sectors_historical_powers=sectors_historical_powers,
                                                storages=setup["storages"],
                                                controllable_sectors=setup["controllable_sectors"],
                                                historical_prices=historical_prices)

    # Check that Zone has been created with the correct parameters
    setup["zone_cls"].assert_called_once_with("FR", historical_prices)

    # Check add_sector et add_storage calls
    setup["zone"].add_sector.assert_called_once_with("solar", sectors_historical_powers["solar"],
                                                     False)
    setup["zone"].add_storage.assert_called_once_with("hydro pump storage",
                                                      sectors_historical_powers["hydro pump storage"],
                                                      True)

    # Check that zone has been added to networks.zone
    assert setup["zone"] in network._zones.values()

    expected_index = pd.DatetimeIndex([
        Timestamp("01/01/2015  12:00:00"),
        Timestamp("15/04/2015  09:00:00"),
    ])
    pd.testing.assert_index_equal(network._datetime_index, expected_index)
    assert skipped_timestep_counter == 7


def test_build_price_models(network_setup):
    network = Network()
    zone = network_setup["zone"]

    network._zones[zone.name] = zone

    # Calls build_price_models
    network.build_price_models((0, 100, 0, 100, 10))

    # Check the call of build_price_model of zone
    zone.build_price_model.assert_called_once_with((0, 100, 0, 100, 10))


def test_build_price_models_raises_when_no_zones():
    network = Network()
    with pytest.raises(ValueError, match="No zones available to build price models."):
        network.build_price_models((0, 100, 0, 100, 10))


def test_check_price_models_valid():
    price_models = {
        "FR": {
            "solar": [None, None, 50, 100],  # Non-storage sector with valid production prices
            # Storage sector with valid consumption prices (cons_full <= cons_none & cons_none <= prod_none)
            "battery": [10, 20, 40, 50]
        }
    }

    storages = ["battery"]

    # Should not raise
    Network.check_price_models(price_models, storages)


@pytest.mark.parametrize("zone, sector, prices, storages, expected_error", [
    # Not None cons prices for solar sector (not storage)
    ("FR", "solar", [20, 30, 50, 60], [], "Sector 'solar' in zone 'FR' is not storage but has consumption prices"),
    # Production price p0 > p100
    ("FR", "solar", [None, None, 100, 90], [], "Logical error: Prod_none > Prod_full for 'solar' in zone 'FR'"),
    # Consumption price c100 > c0
    ("FR", "battery", [30, 20, 50, 60], ["battery"],
     "Logical error: Cons_full > Cons_none for 'battery' in zone 'FR'"),
    # prod_none is None
    ("FR", "solar", [None, None, None, 100], [], "Missing production prices for 'solar' in zone 'FR"),
    # prod_full is None
    ("FR", "solar", [None, None, 10, None], [], "Missing production prices for 'solar' in zone 'FR"),
    # Storage: cons_full is None
    ("FR", "battery", [None, 40, 10, 20], ["battery"],
     "Missing consumption prices for storage sector 'battery' in zone 'FR"),
    # Storage: cons_none is None
    ("FR", "battery", [30, None, 10, 20], ["battery"],
     "Missing consumption prices for storage sector 'battery' in zone 'FR"),
    # Storage: cons_none > prod_none
    ("FR", "battery", [30, 50, 40, 60], ["battery"],
     r"Logical error: Cons_none > Prod_none for 'battery' in zone 'FR' \(50 > 40\)")
])
def test_check_price_models_raises_errors(zone, sector, prices, storages, expected_error):
    price_models = {
        zone: {
            sector: prices
        }
    }

    with pytest.raises(ValueError, match=expected_error):
        Network.check_price_models(price_models, storages)


def test_set_price_model(network_setup):
    # Network object creation
    network = Network()
    network._zones = {"FR": network_setup["zone"]}

    # Mock price models to set
    price_models = {
        "FR": {
            "solar": [None, None, 10, 40],
            "hydro pump storage": [0, 20, 30, 70]
        }
    }

    # Call the tested method
    network.set_price_model(price_models)

    # Check that the zone's set_price_model has been called with the correct parameters
    network_setup["zone"].set_price_model.assert_called_once_with(price_models["FR"])


def test_run_opf():
    pass
