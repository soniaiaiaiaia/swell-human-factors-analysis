from __future__ import annotations

from data_cleaning import run as clean_data
from figures import run as make_figures
from modeling import run as run_models
from statistical_analysis import run as run_statistics


def main() -> None:
    clean_data()
    run_statistics()
    run_models()
    make_figures()
    print("Completed: cleaned data, inferential tables, LOSO models, and figures.")


if __name__ == "__main__":
    main()

