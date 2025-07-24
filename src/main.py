from pathlib import Path
from unittest.mock import patch

import pandas as pd

from src.controller import Controller
from src.input_reader import InputReader

# studies_dir = Path(__file__).parents[1] / "studies"
# work_dir = studies_dir / "study_1"
# db_dir = studies_dir / "database"


if __name__ == "__main__":
    work_dir = Path("C:/Users/b.perreyon/Documents/ECL cost models/wk dir/new")
    db_dir = Path("C:/Users/b.perreyon/Documents/ECL cost models/database/fixed")

    # controller = Controller(work_dir=work_dir, db_dir=db_dir)
    # controller.build_price_models()
    # exit(0)

    # Timestamps data extracted from a run. To avoid loading the Entire Excel files each time
    prices_df = pd.DataFrame(
        columns=['BE', 'CH', 'ES', 'FR', 'IT', 'NL'],
        index=pd.Index([pd.Timestamp("2019-01-01 00:00:00"), pd.Timestamp("2019-01-01 01:00:00"),
                        pd.Timestamp("2019-01-01 02:00:00"), pd.Timestamp("2019-01-01 03:00:00"),
                        pd.Timestamp("2019-01-01 04:00:00")], name="Time"),
        data=[
            [69.49, 50.26, 66.88, 51.00, 51.000000, 68.92],
            [66.58, 48.74, 66.88, 46.27, 46.270000, 64.98],
            [65.07, 47.24, 66.00, 39.78, 39.780000, 60.27],
            [52.17, 36.29, 63.64, 27.87, 27.870000, 49.97],
            [47.66, 30.09, 58.85, 23.21, 22.000000, 47.66],
        ],
    )
    powers_df_dict = {
        'BE': pd.DataFrame(
            columns=["RES", "coal", "gas", "hydro dams", "hydro pump storage", "nuclear", "other fossil",
                     "run of river"],
            index=pd.Index([pd.Timestamp("2019-01-01 00:00:00"), pd.Timestamp("2019-01-01 01:00:00"),
                            pd.Timestamp("2019-01-01 02:00:00"), pd.Timestamp("2019-01-01 03:00:00"),
                            pd.Timestamp("2019-01-01 04:00:00")], name="Début de l'heure"),
            data=[
                [924.0, 0.0, 1920, 0, 56.4, 2380, 633.0, 37.6],
                [964.0, 0.0, 1640, 0, 347, 2380, 673.0, 39.4],
                [1005.0, 0.0, 1590, 0, 298, 2380, 631.0, 40.3],
                [1016.0, 0.0, 1600, 0, -197, 2410, 619.0, 38.7],
                [1166.0, 0.0, 1530, 0, -478, 2420, 619.0, 36.6],
            ]
        ),
        'CH': pd.DataFrame(
            columns=["RES", "coal", "gas", "hydro dams", "hydro pump storage", "nuclear", "other fossil",
                     "run of river"],
            index=pd.Index([pd.Timestamp("2019-01-01 00:00:00"), pd.Timestamp("2019-01-01 01:00:00"),
                            pd.Timestamp("2019-01-01 02:00:00"), pd.Timestamp("2019-01-01 03:00:00"),
                            pd.Timestamp("2019-01-01 04:00:00")], name="Début de l'heure"),
            data=[
                [0.7, 0, 0.0, 481, 81.3, 3240.0, 0, 123.0],
                [0.2, 0, 0.0, 393, 76.2, 3240.0, 0, 124.0],
                [0.4, 0, 0.0, 345, 30.9, 3250.0, 0, 126.0],
                [0.6, 0, 0.0, 312, 18.4, 3240.0, 0, 135.0],
                [1.8, 0, 0.0, 339, 12.6, 3240.0, 0, 135.0],
            ]
        ),
        'ES': pd.DataFrame(
            columns=["RES", "coal", "gas", "hydro dams", "hydro pump storage", "nuclear", "other fossil",
                     "run of river"],
            index=pd.Index([pd.Timestamp("2019-01-01 00:00:00"), pd.Timestamp("2019-01-01 01:00:00"),
                            pd.Timestamp("2019-01-01 02:00:00"), pd.Timestamp("2019-01-01 03:00:00"),
                            pd.Timestamp("2019-01-01 04:00:00")], name="Début de l'heure"),
            data=[
                [4216.0, 1920.0, 5600, 1680, -107, 6070, 219.0, 983.0],
                [4187.0, 1710.0, 5570, 1680, -60, 6070, 216.0, 969.0],
                [4149.0, 1640.0, 5550, 1120, -499, 6070, 215.0, 907.0],
                [4099.0, 1520.0, 6040, 830, -1240, 6070, 220.0, 897.0],
                [3918.0, 1490.0, 6000, 944, -1320, 6070, 236.0, 910.0],
            ]
        ),
        'FR': pd.DataFrame(
            columns=["RES", "coal", "gas", "hydro dams", "hydro pump storage", "nuclear", "other fossil",
                     "run of river"],
            index=pd.Index([pd.Timestamp("2019-01-01 00:00:00"), pd.Timestamp("2019-01-01 01:00:00"),
                            pd.Timestamp("2019-01-01 02:00:00"), pd.Timestamp("2019-01-01 03:00:00"),
                            pd.Timestamp("2019-01-01 04:00:00")], name="Début de l'heure"),
            data=[
                [1971.0, 0.0, 2720.0, 1050, -1380, 55600.0, 207.0, 3550.0],
                [1992.0, - 1.0, 2530.0, 740, -1540, 55100.0, 215.0, 3340.0],
                [1922.0, - 1.0, 2420.0, 463, -2370, 54800.0, 214.0, 3200.0],
                [1911.0, 0.0, 2440.0, 145, -2670, 53200.0, 215.0, 3090.0],
                [1953.0, 0.0, 2440.0, 97, -2880, 50100.0, 215.0, 3010.0],
            ]
        ),
        'IT': pd.DataFrame(
            columns=["RES", "coal", "gas", "hydro dams", "hydro pump storage", "nuclear", "other fossil",
                     "run of river"],
            index=pd.Index([pd.Timestamp("2019-01-01 00:00:00"), pd.Timestamp("2019-01-01 01:00:00"),
                            pd.Timestamp("2019-01-01 02:00:00"), pd.Timestamp("2019-01-01 03:00:00"),
                            pd.Timestamp("2019-01-01 04:00:00")], name="Début de l'heure"),
            data=[
                [5575.0, 1940.0, 8826, 289, -28, 0, 3078.0, 1890.0],
                [5591.0, 2090.0, 8385, 145, -72, 0, 3098.0, 1710.0],
                [5589.0, 2180.0, 7863, 164, -138, 0, 2868.0, 1610.0],
                [5633.0, 1830.0, 6804, 126, -306, 0, 2458.0, 1480.0],
                [5749.0, 1710.0, 6574, 124, -529, 0, 2388.0, 1480.0],
            ]
        ),
        'NL': pd.DataFrame(
            columns=["RES", "coal", "gas", "hydro dams", "hydro pump storage", "nuclear", "other fossil",
                     "run of river"],
            index=pd.Index([pd.Timestamp("2019-01-01 00:00:00"), pd.Timestamp("2019-01-01 01:00:00"),
                            pd.Timestamp("2019-01-01 02:00:00"), pd.Timestamp("2019-01-01 03:00:00"),
                            pd.Timestamp("2019-01-01 04:00:00")], name="Début de l'heure"),
            data=[
                [1463.8, 2092.5, 4227.5, 0, 0, 485.2, 1982.5, 0],
                [1487.3, 2090.0, 3890, 0, 0, 485.2, 1992.5, 0],
                [1537.6, 2105.0, 3740, 0, 0, 485.0, 1892.5, 0],
                [1600.3, 2085.0, 3527, 0, 0, 485.0, 1940.0, 0],
                [1625.3, 1980.0, 3255, 0, 0, 485.2, 2082.5, 0],
            ]
        ),
    }

    power_ratings = pd.DataFrame(
        columns=["zone_from", "zone_to", "Capacity (MW)"],
        data=[
            ["BE", "FR", 14490.0],
            ["BE", "NL", 11309.0],
            ["CH", "FR", 7896.0],
            ["CH", "IT", 8558.0],
            ["ES", "FR", 5953.0],
            ["FR", "BE", 14490.0],
            ["FR", "CH", 7896.0],
            ["FR", "ES", 5953.0],
            ["FR", "IT", 5514.0],
            ["IT", "CH", 8558.0],
            ["IT", "FR", 5514.0],
            ["NL", "BE", 11309.0],
        ])

    interco_historical_powers = pd.DataFrame(
        columns=["Time", "zone_from", "zone_to", "Power (MW)"],
        data=[
            [pd.Timestamp("2015-01-01 00:00:00"), "CH", "IT", 2010.00],
            [pd.Timestamp("2015-01-01 00:00:00"), "ES", "FR", 933.30],
            [pd.Timestamp("2015-01-01 00:00:00"), "FR", "BE", 304.53],
            [pd.Timestamp("2015-01-01 00:00:00"), "FR", "CH", 410.00],
            [pd.Timestamp("2015-01-01 00:00:00"), "FR", "IT", 367.00],
            [pd.Timestamp("2015-01-01 00:00:00"), "NL", "BE", 1334.02],

            [pd.Timestamp("2015-01-01 01:00:00"), "CH", "IT", 2051.00],
            [pd.Timestamp("2015-01-01 01:00:00"), "ES", "FR", 1118.86],
            [pd.Timestamp("2015-01-01 01:00:00"), "FR", "BE", 228.24],
            [pd.Timestamp("2015-01-01 01:00:00"), "FR", "CH", 374.00],
            [pd.Timestamp("2015-01-01 01:00:00"), "FR", "IT", 352.00],
            [pd.Timestamp("2015-01-01 01:00:00"), "NL", "BE", 1149.79],

            [pd.Timestamp("2015-01-01 02:00:00"), "CH", "IT", 2066.00],
            [pd.Timestamp("2015-01-01 02:00:00"), "ES", "FR", 954.24],
            [pd.Timestamp("2015-01-01 02:00:00"), "FR", "BE", 75.28],
            [pd.Timestamp("2015-01-01 02:00:00"), "FR", "CH", 282.00],
            [pd.Timestamp("2015-01-01 02:00:00"), "FR", "IT", 189.00],
            [pd.Timestamp("2015-01-01 02:00:00"), "NL", "BE", 1044.77],

            [pd.Timestamp("2015-01-01 03:00:00"), "CH", "IT", 1833.00],
            [pd.Timestamp("2015-01-01 03:00:00"), "ES", "FR", 13.31],
            [pd.Timestamp("2015-01-01 03:00:00"), "FR", "BE", 21.63],
            [pd.Timestamp("2015-01-01 03:00:00"), "FR", "CH", 422.00],
            [pd.Timestamp("2015-01-01 03:00:00"), "FR", "IT", 145.00],
            [pd.Timestamp("2015-01-01 03:00:00"), "NL", "BE", 880.53],

            [pd.Timestamp("2015-01-01 04:00:00"), "CH", "IT", 2185.00],
            [pd.Timestamp("2015-01-01 04:00:00"), "FR", "ES", 238.17],  # Reversed
            [pd.Timestamp("2015-01-01 04:00:00"), "FR", "BE", 484.60],
            [pd.Timestamp("2015-01-01 04:00:00"), "FR", "CH", 445.00],
            [pd.Timestamp("2015-01-01 04:00:00"), "FR", "IT", 1.00],
            [pd.Timestamp("2015-01-01 04:00:00"), "NL", "BE", 842.80],
        ]
    )

    with (patch.object(InputReader, "read_db_prices", return_value=prices_df),
          patch.object(InputReader, "read_db_powers", return_value=powers_df_dict),
          patch.object(InputReader, "read_interco_power_ratings", return_value=power_ratings),
          patch.object(InputReader, "read_interco_powers", return_value=interco_historical_powers)):
        controller = Controller(work_dir=work_dir, db_dir=db_dir)
    controller.run_opfs()
