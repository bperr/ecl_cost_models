from pathlib import Path

from controller import Controller

# studies_dir = Path(__file__).parents[1] / "studies"
# work_dir = studies_dir / "study_1"
# db_dir = studies_dir / "database"


if __name__=="__main__":
    work_dir = Path("C:/Users/a.faivre/PycharmProjects/ECL cost models/Working")
    db_dir = Path("C:/Users/a.faivre/PycharmProjects/ECl cost models/Database")

    controller = Controller(work_dir=work_dir, db_dir=db_dir)
    results = controller.run(export_to_excel=True)
    print(results)
