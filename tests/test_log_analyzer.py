import filecmp
import os
from datetime import datetime
from pathlib import Path

from log_analyzer.log_analyzer import (
    create_report,
    create_totals,
    find_latest_log,
    read_log,
)


def test_find_latest_log() -> None:
    _path = Path("tests/data/log").absolute()
    log = find_latest_log(_path)
    assert log.path.name == "nginx-access-ui.log-20150630"


def test_log_analyzer() -> None:
    totals = create_totals(
        read_log(path=Path("tests/data/log/nginx-access-ui.log-20150630").absolute()),
        100,
    )
    create_report(
        totals,
        datetime.strptime("2015.06.30", "%Y.%m.%d"),
        Path("tests/data/template").absolute(),
        Path("tests/data/report").absolute(),
    )
    assert filecmp.cmp(
        Path("tests/data/report/report-2015.06.30.html").absolute(),
        Path("tests/data/report/report-2015.06.30-example.html").absolute(),
    )
    os.remove(Path("tests/data/report/report-2015.06.30.html").absolute())
