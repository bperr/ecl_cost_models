import pytest
import pandas as pd
from pandas import Timestamp
from src.sector import Sector

@pytest.fixture
def sector_setup():
    # fixed Timestamps
    timestamps = [Timestamp("01/01/2015  12:00:00"),
              Timestamp("05/02/2015  13:00:00"),
              Timestamp("10/03/2015  14:00:00"),
              Timestamp("15/04/2015  09:00:00"),
              Timestamp("20/05/2015  16:00:00"),
              Timestamp("25/06/2015  08:00:00"),
              Timestamp("30/07/2015  19:00:00"),
              Timestamp("04/09/2015  11:00:00"),
              Timestamp("10/11/2015  22:00:00")]

    # --- Data for a sector in a zone ---
    # Powers (MW)
    powers_prod = pd.Series([200, 300, 300, 250, 350, 320, 400, 380, 360], index=timestamps)
    powers_cons = pd.Series([-300, -400, -450, -500, -600, -550, -520, -580, -590], index=timestamps)

    # Availabilities (MW) (>= puissances)
    availabilities = pd.Series([1000] * 9, index=timestamps)

    # Prices (€/MWh)
    historical_prices = pd.Series([50, 60, 55, 52, 65, 70, 68, 66, 64], index=timestamps)

    # Sector instance in production mode
    sector_prod = Sector(sector_name="solar", historical_powers=powers_prod, is_load=False)
    sector_prod.build_availabilities(availabilities)

    # Sector instance in consumption mode
    sector_cons = Sector(sector_name="hydro pump storage", historical_powers=powers_cons, is_load=True)
    sector_cons.build_availabilities(availabilities)

    return {
        "sector_prod": sector_prod,
        "sector_cons": sector_cons,
        "powers_prod": powers_prod,
        "powers_cons": powers_cons,
        "availabilities": availabilities,
        "historical_prices": historical_prices
    }


def test_compute_load_factor_production(sector_setup):
    sector = sector_setup["sector_prod"]
    assert sector._compute_load_factor(price=60, price_no_power=50, price_full_power=70) == 0.5
    assert sector._compute_load_factor(price=40, price_no_power=50, price_full_power=70) == 0
    assert sector._compute_load_factor(price=90, price_no_power=50, price_full_power=70) == 1


def test_compute_load_factor_consumption(sector_setup):
    sector=sector_setup["sector_cons"]
    assert sector._compute_load_factor(price=60, price_no_power=70, price_full_power=50) == -0.5
    assert sector._compute_load_factor(price=40, price_no_power=70, price_full_power=50) == -1
    assert sector._compute_load_factor(price=90, price_no_power=70, price_full_power=50) == 0


def test_build_price_model_production(sector_setup):
    sector = sector_setup["sector_prod"]
    historical_prices = sector_setup["historical_prices"]
    prices_init = (0, 100, 0, 100, 10)

    sector.build_price_model(historical_prices, prices_init)
    price_model = sector.price_model

    assert isinstance(price_model, tuple)
    assert len(price_model) == 2
    assert price_model[0] <= price_model[1]


def test_build_price_model_consumption(sector_setup):
    historical_prices = sector_setup["historical_prices"]
    sector = sector_setup["sector_cons"]

    prices_init = (0, 100, 0, 100, 10)
    sector.build_price_model(historical_prices, prices_init)

    price_model = sector.price_model
    assert price_model[0] >= price_model[1]


def test_plot_result(tmp_path, sector_setup):
    sector = sector_setup["sector_prod"]
    path = tmp_path / "test_plot.png"
    zone_name = "TestZone"
    prices = sector_setup["historical_prices"]

    sector._price_model = (40, 70)
    sector.plot_result(zone_name=zone_name, historical_prices=prices, path=path)

    assert path.exists()
