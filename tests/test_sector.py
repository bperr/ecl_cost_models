import matplotlib
import numpy as np
import pandas as pd
import pytest
from pandas import Timestamp
from pandas import date_range

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

    # Availabilities (MW) (>= powers)
    availabilities = pd.Series([1000] * 9, index=timestamps)

    # Prices (€/MWh)
    historical_prices = pd.Series([50, 60, 55, 52, 65, 70, 68, 66, 64], index=timestamps)

    # Sector instance in production mode
    sector_prod = Sector(sector_name="solar", historical_powers=powers_prod, is_controllable=True,
                         is_storage_load=False)
    sector_prod._availabilities = availabilities

    # Sector instance in consumption mode
    sector_cons = Sector(sector_name="hydro pump storage", historical_powers=powers_cons, is_controllable=False,
                         is_storage_load=True)
    sector_cons._availabilities = availabilities

    return {
        "sector_prod": sector_prod,
        "sector_cons": sector_cons,
        "powers_prod": powers_prod,
        "powers_cons": powers_cons,
        "availabilities": availabilities,
        "historical_prices": historical_prices
    }


# ------- Tests compute_use_ratio -------

def test_compute_use_ratio_production(sector_setup):
    sector = sector_setup["sector_prod"]
    assert sector._compute_use_ratio(price=60, price_no_power=50, price_full_power=70) == 0.5
    assert sector._compute_use_ratio(price=40, price_no_power=50, price_full_power=70) == 0
    assert sector._compute_use_ratio(price=90, price_no_power=50, price_full_power=70) == 1


def test_compute_use_ratio_consumption(sector_setup):
    sector = sector_setup["sector_cons"]
    assert sector._compute_use_ratio(price=60, price_no_power=70, price_full_power=50) == -0.5
    assert sector._compute_use_ratio(price=40, price_no_power=70, price_full_power=50) == -1
    assert sector._compute_use_ratio(price=90, price_no_power=70, price_full_power=50) == 0


# ------- Tests build_availabilities -------

@pytest.mark.parametrize("name, is_storage_load, is_controllable, powers, expected_avail", [
    # Test 1 : nuclear → availabilities = max on the rolling month
    (
            "nuclear",
            False,
            True,
            pd.Series(
                [100] * 336 + [300] * 48 + [100] * 336,  # Total = 720h = 30 days
                index=date_range("2015-01-01", periods=720, freq="H")
            ),
            # equals 300 for each timestep (the window of +/- 14 days always has 300 as maximum power)
            pd.Series(
                [300] * 720,
                index=date_range("2015-01-01", periods=720, freq="H")
            )
    ),

    # Test 2 : Fossil (controllable) → availabilities = max(powers) on the year
    (
            "fossil",
            False,
            True,
            pd.Series([100, 200, 150, 180, 170], index=date_range("2015-01-01", periods=5, freq="H")),
            pd.Series([200] * 5, index=date_range("2015-01-01", periods=5, freq="H"))
    ),

    # Test 3 : Renewable (non-controllable) → availabilities = powers
    (
            "solar",
            False,
            False,
            pd.Series([100, 200, 150, 180, 170], index=date_range("2015-01-01", periods=5, freq="H")),
            pd.Series([100, 200, 150, 180, 170], index=date_range("2015-01-01", periods=5, freq="H"))
    ),
])
def test_build_availabilities_parametrized(name, is_storage_load, is_controllable, powers, expected_avail):
    sector = Sector(name, powers, is_controllable, is_storage_load)
    sector.build_availabilities()
    result = sector._availabilities

    pd.testing.assert_series_equal(result, expected_avail)
    assert len(result) == len(powers)


# ------- Tests build_price_model -------

@pytest.mark.parametrize("sector_key, ascending", [
    ("sector_prod", True),  # production : price_no_power < price_full_power
    ("sector_cons", False),  # consumption : price_no_power > price_full_power
])
def test_build_price_model(sector_setup, sector_key, ascending):
    sector = sector_setup[sector_key]
    historical_prices = sector_setup["historical_prices"]
    prices_init = (0, 100, 0, 100, 10)
    zone_name = "EU"

    sector.build_price_model(historical_prices, prices_init, zone_name)
    price_model = sector.price_model

    assert isinstance(price_model, tuple)
    assert len(price_model) == 2

    if ascending:
        assert price_model[0] <= price_model[1]
    else:
        assert price_model[0] >= price_model[1]


def test_price_model_accuracy_on_linear_relation():
    # Construction of a linear relationship between price and power
    idx = pd.date_range("2022-01-01", periods=10, freq="H")

    # Power normalised between 0 (min) and 1 (max)
    normalized_powers = np.linspace(0, 1, 10)  # Only for powers and prices construction
    historical_powers = pd.Series(normalized_powers * 1000, index=idx)  # power = normalized_power * 1000
    availabilities = pd.Series([1000] * 10, index=idx)

    # Linear relationship between powers and prices
    historical_prices = pd.Series(50 + normalized_powers * 50, index=idx)  # price range from 50 to 100

    sector = Sector("solar", historical_powers=historical_powers, is_controllable=False, is_storage_load=False)
    sector._availabilities = availabilities

    # The model must find price_no_power ≈ 50 and price_full_power ≈ 100
    sector.build_price_model(historical_prices, prices_init=(0, 100, 0, 100, 10), zone_name="EU")

    price_no_power, price_full_power = sector.price_model

    assert price_no_power == pytest.approx(50, abs=1)
    assert price_full_power == pytest.approx(100, abs=1)


def test_price_model_with_noise():
    rng = np.random.default_rng(0)  # Random number generator

    idx = pd.date_range("2022-01-01", periods=20, freq="H")
    normalized_powers = np.linspace(0, 1, 20)
    # normal distribution as "noise", standard deviation of 100 :
    powers = pd.Series(normalized_powers * 1000 + rng.normal(0, 100, size=20), index=idx)
    availabilities = pd.Series([1000] * 20, index=idx)
    prices = pd.Series(50 + normalized_powers * 50, index=idx)  # price range from 50 to 100

    sector = Sector("solar", historical_powers=powers, is_storage_load=False, is_controllable=False)
    sector._availabilities = availabilities
    sector.build_price_model(prices, prices_init=(0, 100, 0, 100, 10), zone_name="EU")

    price_no_power, price_full_power = sector.price_model
    assert abs(price_no_power - 50) < 2
    assert abs(price_full_power - 100) < 2


def test_price_model_step_behavior():
    n = 100
    threshold_price = 50

    # Price range from 50 to 100
    historical_prices = pd.Series(np.linspace(0, 100, n), index=date_range("2015-01-01", periods=n, freq="H"))

    # Low power before the threshold, high afterward
    historical_powers = pd.Series([0 if price < threshold_price else 1000 for price in historical_prices],
                                  index=historical_prices.index)

    # Steady availabilities (ex : fossil)
    availabilities = pd.Series(1000, index=historical_prices.index)

    # sector creation
    sector = Sector("gas", historical_powers, is_storage_load=False, is_controllable=True)
    sector._availabilities = availabilities

    # price model construction
    sector.build_price_model(historical_prices, prices_init=(0, 100, 0, 100, 10), zone_name="EU")

    price_no_power, price_full_power = sector.price_model

    # Test : both prices should be almost equal to the threshold price
    assert abs(price_no_power - threshold_price) < 1
    assert abs(price_full_power - threshold_price) < 1


def test_full_power_all_the_time():
    n = 50
    prices = pd.Series(np.linspace(30, 100, n), index=date_range("2015-01-01", periods=n, freq="H"))

    # Power is always equal to availability (ex : Renewables) --> use ratio = 1 for all prices
    powers = pd.Series(1000, index=prices.index)
    availabilities = pd.Series(1000, index=prices.index)

    sector = Sector("RES", powers, is_storage_load=False, is_controllable=False)
    sector._availabilities = availabilities

    sector.build_price_model(prices, prices_init=(0, 120, 0, 120, 10), zone_name="EU")

    price_no_power, price_full_power = sector.price_model

    # modelled prices should make a step at minimum price (or at 0)
    assert abs(price_no_power - min(0, prices.min())) < 2
    assert abs(price_full_power - min(0, prices.min())) < 2


# ------- Test plot_result -------

@pytest.mark.parametrize("is_storage_load, price_model, expected_title", [
    (False, (40, 70), "TestZone - solar - Production"),
    (True, (70, 40), "TestZone - hydro - Consumption"),
])
def test_plot_result_variants(tmp_path, is_storage_load, price_model, expected_title):
    matplotlib.use("Agg")
    index = pd.date_range("2015-01-01", periods=5, freq="H")
    powers = pd.Series([100, 200, 150, 180, 170], index=index)
    if is_storage_load:
        powers = -powers  # in order to have a use_ratio between -1 et 0

    prices = pd.Series([50, 60, 55, 52, 65], index=index)

    name = "solar" if not is_storage_load else "hydro"
    sector = Sector(name, powers, is_storage_load)
    sector._availabilities = pd.Series([200, 200, 200, 200, 200], index=index)
    sector._price_model = price_model

    path = tmp_path / f"{name}_plot.png"
    sector.plot_result(zone_name="TestZone", historical_prices=prices, path=path)

    assert path.exists()


def test_store_simulated_power(sector_setup):
    # fake data
    sector = sector_setup["sector_prod"]
    timestep = pd.Timestamp("2015-01-01 12:00:00")

    sector._current_power = 150

    # tested method
    sector.store_simulated_power(timestep)

    # Verifications
    expected_series = pd.Series([150], index=[timestep])

    pd.testing.assert_series_equal(sector._simulated_powers, expected_series)

    assert sector._current_power == 0
