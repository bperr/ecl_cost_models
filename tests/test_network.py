import pytest
import pandas as pd
from pandas import Timestamp
from unittest.mock import MagicMock, patch

from src.network import Network


@pytest.fixture(scope="function")
def network_test_setup():
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

def test_add_zone(network_test_setup):
    setup = network_test_setup
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

def test_build_price_models(network_test_setup):
    network = Network()
    network.zones.append(network_test_setup["zone"])

    # Calls build_price_models
    network.build_price_models((0, 100, 0, 100, 10))

    # Check the call of build_price_model of zone
    network_test_setup["zone"].build_price_model.assert_called_once_with((0, 100, 0, 100, 10))

def test_check_price_models_valid(network_test_setup):
    network = Network()
    zone = network_test_setup["zone"]

    sector_1 = MagicMock()
    sector_1.name = "solar"
    sector_1.price_model = (50, 100) # p0 <= p100
    sector_1.is_load = False

    sector_2 = MagicMock()
    sector_2.name = "battery"
    sector_2.price_model = (20, 10)  # c100 <= c0
    sector_2.is_load = True

    zone.sectors = [sector_1, sector_2]
    network.zones = [zone]

    # Should not raise
    network.check_price_models()

def test_check_price_models_raises_on_empty_price_model(network_test_setup):
    network = Network()
    zone = network_test_setup["zone"]

    bad_sector = MagicMock()
    bad_sector.name = "solar"
    bad_sector.price_model = []
    bad_sector.is_load = False

    zone.sectors = [bad_sector]
    network.zones = [zone]

    with pytest.raises(ValueError, match="Prices values are missing for solar"):
        network.check_price_models()

def test_check_price_models_raises_on_invalid_production_price(network_test_setup):
    network = Network()
    zone = network_test_setup["zone"]

    sector = MagicMock()
    sector.name = "solar"
    sector.price_model = (100, 90)  # p0 > p100
    sector.is_load = False

    zone.sectors = [sector]
    network.zones = [zone]

    with pytest.raises(ValueError, match="Production price p0 must be lower than p100"):
        network.check_price_models()

def test_check_price_models_raises_on_invalid_consumption_price(network_test_setup):
    network = Network()
    zone = network_test_setup["zone"]

    sector = MagicMock()
    sector.name = "battery"
    sector.price_model = (30, 20)  # c100 > c0
    sector.is_load = True

    zone.sectors = [sector]
    network.zones = [zone]

    with pytest.raises(ValueError, match="Consumption price c100 must be lower than c0"):
        network.check_price_models()