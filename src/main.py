from pathlib import Path

from src.controller import Controller

# studies_dir = Path(__file__).parents[1] / "studies"
# work_dir = studies_dir / "study_1"
# db_dir = studies_dir / "database"


if __name__ == "__main__":
    work_dir = Path("C:/Users/b.perreyon/Documents/ECL cost models/wk dir/new")
    db_dir = Path("C:/Users/b.perreyon/Documents/ECL cost models/database/fixed")
    # work_dir = Path("C:/Users/n.barla/Documents/Local_codes/ecl_cost_models/instance/studies/study_1")
    # db_dir = Path("C:/Users/n.barla/Documents/Local_codes/ecl_cost_models/instance/database/2025-08")

    # controller = Controller(work_dir=work_dir, db_dir=db_dir)
    # controller.build_price_models()
    # exit(0)

    controller = Controller(work_dir=work_dir, db_dir=db_dir)
    controller.run_opfs()
