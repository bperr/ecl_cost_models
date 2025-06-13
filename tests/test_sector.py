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

    # Availabilities (MW) (>= puissances)
    availabilities = pd.Series([1000] * 9, index=timestamps)

    # Prices (€/MWh)
    historical_prices = pd.Series([50, 60, 55, 52, 65, 70, 68, 66, 64], index=timestamps)

    # Sector instance in production mode
    sector_prod = Sector(sector_name="solar", historical_powers=powers_prod, is_load=False)
    sector_prod.availabilities = availabilities

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


# ------- Tests compute_load_factor -------

def test_compute_load_factor_production(sector_setup):
    sector = sector_setup["sector_prod"]
    assert sector._compute_load_factor(price=60, price_no_power=50, price_full_power=70) == 0.5
    assert sector._compute_load_factor(price=40, price_no_power=50, price_full_power=70) == 0
    assert sector._compute_load_factor(price=90, price_no_power=50, price_full_power=70) == 1


def test_compute_load_factor_consumption(sector_setup):
    sector = sector_setup["sector_cons"]
    assert sector._compute_load_factor(price=60, price_no_power=70, price_full_power=50) == -0.5
    assert sector._compute_load_factor(price=40, price_no_power=70, price_full_power=50) == -1
    assert sector._compute_load_factor(price=90, price_no_power=70, price_full_power=50) == 0


# ------- Tests build_availabilities -------

@pytest.mark.parametrize("is_controllable, provided_avail, expected_avail", [
    # test 1 : given availabilities (nucléaire)
    (
            True,
            pd.Series([300, 300, 300, 300, 300], index=date_range("2015-01-01", periods=5, freq="H")),
            pd.Series([300, 300, 300, 300, 300], index=date_range("2015-01-01", periods=5, freq="H"))
    ),
    # test 2 : controllable = True (fossil) → constant availability = max power
    (
            True,
            pd.Series(),  # empty
            pd.Series([200] * 5, index=date_range("2015-01-01", periods=5, freq="H"))
    ),
    # test 3 : controllable = False (renewable) → availabilities = powers
    (
            False,
            pd.Series(),  # empty
            pd.Series([100, 200, 150, 180, 170], index=date_range("2015-01-01", periods=5, freq="H"))
    ),
])
def test_build_availabilities_parametrized(is_controllable, provided_avail, expected_avail):
    index = date_range("2015-01-01", periods=5, freq="H")
    powers = pd.Series([100, 200, 150, 180, 170], index=index)

    sector = Sector("test", powers)
    sector.is_controllable = is_controllable
    sector.build_availabilities(provided_avail)

    pd.testing.assert_series_equal(sector.availabilities, expected_avail)
    assert len(sector.availabilities) == len(sector.historical_powers)


# ------- Tests build_price_model -------

@pytest.mark.parametrize("sector_key, ascending", [
    ("sector_prod", True),  # production : price_no_power < price_full_power
    ("sector_cons", False),  # consumption : price_no_power > price_full_power
])
def test_build_price_model(sector_setup, sector_key, ascending):
    sector = sector_setup[sector_key]
    historical_prices = sector_setup["historical_prices"]
    prices_init = (0, 100, 0, 100, 10)

    sector.build_price_model(historical_prices, prices_init)
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

    sector = Sector("solar", historical_powers=historical_powers, is_load=False)
    sector.availabilities = availabilities

    # The model must find price_no_power ≈ 50 and price_full_power ≈ 100
    sector.build_price_model(historical_prices, prices_init=(0, 100, 0, 100, 10))

    price_no_power, price_full_power = sector.price_model

    assert abs(price_no_power - 50) < 1
    assert abs(price_full_power - 100) < 1


def test_price_model_with_noise():
    rng = np.random.default_rng(0)  # Random number generator

    idx = pd.date_range("2022-01-01", periods=20, freq="H")
    normalized_powers = np.linspace(0, 1, 20)
    # normal distribution as "noise", standard deviation of 100 :
    powers = pd.Series(normalized_powers * 1000 + rng.normal(0, 100, size=20), index=idx)
    availabilities = pd.Series([1000] * 20, index=idx)
    prices = pd.Series(50 + normalized_powers * 50, index=idx)  # price range from 50 to 100

    sector = Sector("solar", historical_powers=powers, is_load=False)
    sector.availabilities = availabilities
    sector.build_price_model(prices, prices_init=(0, 100, 0, 100, 10))

    price_no_power, price_full_power = sector.price_model
    assert abs(price_no_power - 50) < 2
    assert abs(price_full_power - 100) < 2


def test_price_model_step_behavior():
    n = 100
    threshold_price = 50

    # Price range from 50 to 100
    historical_prices = pd.Series(np.linspace(0, 100, n), index=date_range("2015-01-01", periods=n, freq="H"))

    # Low power before the threshold, high afterwards
    historical_powers = pd.Series([0 if price < threshold_price else 1000 for price in historical_prices],
                                  index=historical_prices.index)

    # Steady availabilities (ex : fossil)
    availabilities = pd.Series(1000, index=historical_prices.index)

    # sector creation
    sector = Sector("gas", historical_powers, is_load=False)
    sector.availabilities = availabilities

    # price model construction
    sector.build_price_model(historical_prices, prices_init=(0, 100, 0, 100, 10))

    price_no_power, price_full_power = sector.price_model

    # Test : both prices should be almost equal to the threshold price
    assert abs(price_no_power - threshold_price) < 1
    assert abs(price_full_power - threshold_price) < 1


def test_full_power_all_the_time():
    n = 50
    prices = pd.Series(np.linspace(30, 100, n), index=date_range("2015-01-01", periods=n, freq="H"))

    # Power is always equal to availability (ex : Renewables) --> load factor = 1 for all prices
    powers = pd.Series(1000, index=prices.index)
    availabilities = pd.Series(1000, index=prices.index)

    sector = Sector("RES", powers, is_load=False)
    sector.availabilities = availabilities

    sector.build_price_model(prices, prices_init=(0, 120, 0, 120, 10))

    price_no_power, price_full_power = sector.price_model

    # modelled prices should make a step at minimum price (or at 0)
    assert abs(price_no_power - min(0, prices.min())) < 2
    assert abs(price_full_power - min(0, prices.min())) < 2


# ------- Test plot_result -------

@pytest.mark.parametrize("is_load, price_model, expected_title", [
    (False, (40, 70), "TestZone - solar - Production"),
    (True, (70, 40), "TestZone - hydro - Consumption"),
])
def test_plot_result_variants(tmp_path, is_load, price_model, expected_title):
    import matplotlib.pyplot as plt

    index = pd.date_range("2015-01-01", periods=5, freq="H")
    powers = pd.Series([100, 200, 150, 180, 170], index=index)
    if is_load:
        powers = -powers  # Pour que load_factor soit entre -1 et 0

    prices = pd.Series([50, 60, 55, 52, 65], index=index)

    name = "solar" if not is_load else "hydro"
    sector = Sector(name, powers, is_load)
    sector.availabilities = pd.Series([200, 200, 200, 200, 200], index=index)
    sector._price_model = price_model

    path = tmp_path / f"{name}_plot.png"
    sector.plot_result(zone_name="TestZone", historical_prices=prices, path=path)

    plt.show()

    assert path.exists()
