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
        "zone_cls": zone_cls,
        "zone": zone,
    }

    patch.stopall()


def make_sector(name, price_model, is_load):
    mock = MagicMock()
    mock.name = name
    mock.price_model = price_model
    mock.is_load = is_load
    return mock


def test_add_zone(network_setup):
    setup = network_setup
    network = Network()

    # Add zone
    network.add_zone("FR", setup["sectors_historical_powers"], setup["storages"], setup["historical_prices"])

    # Check that Zone has been created with the correct parameters
    setup["zone_cls"].assert_called_once_with("FR", setup["historical_prices"])

    # Check add_sector et add_storage calls
    setup["zone"].add_sector.assert_called_once_with("solar", setup["sectors_historical_powers"]["solar"])
    setup["zone"].add_storage.assert_called_once_with("hydro pump storage",
                                                      setup["sectors_historical_powers"]["hydro pump storage"])

    # Check that zone has been added to networks.zone
    assert setup["zone"] in network.zones


def test_build_price_models(network_setup):
    network = Network()
    network.zones.append(network_setup["zone"])

    # Calls build_price_models
    network.build_price_models((0, 100, 0, 100, 10))

    # Check the call of build_price_model of zone
    network_setup["zone"].build_price_model.assert_called_once_with((0, 100, 0, 100, 10))


def test_build_price_models_raises_when_no_zones():
    network = Network()
    with pytest.raises(ValueError, match="No zones available to build price models."):
        network.build_price_models((0, 100, 0, 100, 10))


def test_check_price_models_valid(network_setup):
    network = Network()
    zone = network_setup["zone"]

    sector_1 = make_sector("solar", (50, 100), False)  # p0 <= p100
    sector_2 = make_sector("battery", (20, 10), True)  # c0 >= c100

    zone.sectors = [sector_1, sector_2]
    network.zones = [zone]

    # Should not raise
    network.check_price_models()


@pytest.mark.parametrize("name, price_model, is_load, expected_error", [
    ("solar", [], False, "Prices values are missing for solar"),
    ("solar", (100, 90), False, "Production price p0 must be lower than p100"),
    ("battery", (20, 30), True, "Consumption price c100 must be lower than c0"),
])
def test_check_price_models_raises_errors(network_setup, name, price_model, is_load, expected_error):
    network = Network()
    zone = network_setup["zone"]

    bad_sector = MagicMock()
    bad_sector.name = name
    bad_sector.price_model = price_model
    bad_sector.is_load = is_load

    zone.sectors = [bad_sector]
    network.zones = [zone]

    with pytest.raises(ValueError, match=expected_error):
        network.check_price_models()
