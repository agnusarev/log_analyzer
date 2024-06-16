import argparse
import configparser
import functools
import getpass
import gzip
import json
import os
import re
from collections.abc import Generator
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from statistics import mean, median
from string import Template
from typing import Any, Dict, List, Union

import structlog

FILE_REGEX = r"nginx-access-ui.log-[0-9]{8}(.gz|$)"
DATE_REGEX = r"[0-9]{8}"
URL_REGEX = r"""((\"(GET|POST|HEAD|PUT|DELETE)\s)(?P<url>.+)(http\/(1\.1|2\.0)))"""

def get_user() -> str:
    return getpass.getuser()


structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S", utc=True),
        structlog.processors.JSONRenderer(),
    ],
    logger_factory=structlog.PrintLoggerFactory(),
)

logger = structlog.get_logger()
log = logger.bind(user=get_user())


def logging_decorator(func: Any) -> Any:
    @functools.wraps(func)
    def wrapper(*args, **kwargs):  # type: ignore
        try:
            result = func(*args, **kwargs)
            return result
        except KeyboardInterrupt as e:
            log.error(f"KeyboardInterrupt while running {func.__name__}. exception: {str(e)}")
            log.info("Analyse log have stopped. Status: error.")
            raise e
        except Exception as e:
            log.error(f"Exception raised in {func.__name__}. exception: {str(e)}")
            log.info("Analyse log have stopped. Status: error.")
            raise e

    return wrapper


@dataclass
class LogFile:
    path: Path
    date: datetime


@logging_decorator
def read_log(path: Path) -> Generator[str, None, None]:
    reader: Any = gzip.open if str(path).endswith(".gz") else open

    try:
        file = reader(path, mode="rt", encoding="utf-8")
    except FileNotFoundError:
        log.info(f"File {path} isn't exist.")
        raise
    except PermissionError:
        log.info(f"File {path} cann't be read.")
        raise
    except OSError as e:
        log.error(f"Exception raised while opening file {path}: {str(e)}")
        raise
    log.info(f"File {path} starting to read.")
    while line := file.readline():
        yield line
    log.info(f"File {path} ended reading.")
    file.close()


@logging_decorator
def find_latest_log(path: Path) -> Union[LogFile, None]:
    last_date = datetime.strptime("20000101", "%Y%m%d")
    last_file = ""
    files = [file for file in os.listdir(path) if re.match(FILE_REGEX, file)]

    if not files:
        log.info("None files to read log.")
        return None

    for file in files:
        date = datetime.strptime(re.findall(DATE_REGEX, file)[0], "%Y%m%d")
        if date > last_date:
            last_file = file
            last_date = date
    _log = Path(f"{path}/{last_file}").absolute()
    log.info(f"Latest log have found. Path: {_log}")
    return LogFile(path=_log, date=last_date)


def compare(x: dict, y: dict) -> float:
    return float(y["time_sum"]) - float(x["time_sum"])


@logging_decorator
def create_totals(iter: Generator, report_size: int) -> List:
    lineformat = re.compile(
        URL_REGEX,
        re.IGNORECASE,
    )
    log_dict: Dict[str, list[float]] = dict()
    total_requests: int = 0
    total_request_time: float = 0.0
    count_analyse_row = 0
    count_skip_row = 0
    for i in iter:
        data = re.search(lineformat, i)
        if data:
            count_analyse_row += 1
            datadict = data.groupdict()
            url = datadict["url"]
            request_time = float(i.split(" ")[-1])
            total_requests += 1
            total_request_time += request_time
            if url not in log_dict:
                log_dict[url] = [request_time]
            else:
                log_dict[url] += [request_time]
        else:
            count_skip_row += 1
    log.info(f"{count_analyse_row} was analysed, {count_skip_row} was skipped")
    totals: List[Dict[str, Union[str, int, float]]] = []
    for key in log_dict.keys():
        totals += [
            {
                "url": key,
                "count": len(log_dict[key]),
                "count_perc": f"{len(log_dict[key]) / total_requests * 100:.3f}",
                "time_sum": f"{sum(log_dict[key]):.3f}",
                "time_perc": f"{sum(log_dict[key]) / total_request_time * 100:.3f}",
                "time_avg": f"{mean(log_dict[key]):.3f}",
                "time_max": f"{max(log_dict[key]):.3f}",
                "time_med": f"{median(log_dict[key]):.3f}",
            }
        ]
    return sorted(totals, key=functools.cmp_to_key(compare))[:report_size]  # type: ignore


@logging_decorator
def create_report(totals: List, date: datetime, template_path: Path, report_path: Path) -> None:
    with open(Path.joinpath(template_path, "report.html"), mode="r", encoding="utf-8") as file_template:
        template = Template(file_template.read().rstrip())
        result = template.safe_substitute(table_json=json.dumps(totals))
    log.info("Template report have read.")

    report_name: str = f"report-{date.strftime("%Y.%m.%d")}.html"
    with open(Path.joinpath(report_path, report_name), mode="w", encoding="utf-8") as file_report:
        file_report.write(result)
    log.info("Report have created.")


@logging_decorator
def main() -> None:
    parser = argparse.ArgumentParser(description="Analyse nginx log files")
    parser.add_argument("--config", type=Path, help="Define config file")
    args = parser.parse_args()

    config = configparser.ConfigParser()

    if args.config and Path(args.config).is_file():
        config.read([Path("log_analyzer.ini"), Path(args.config)])
    else:
        config.read(Path("log_analyzer.ini"))

    config_dict: Any = {
        "report_size": int(config.get("default", "report_size")),
        "report_dir": Path(config.get("default", "report_dir")),
        "log_dir": Path(config.get("default", "log_dir")),
        "template_dir": Path(config.get("default", "template_dir")),
    }

    file = find_latest_log(config_dict["log_dir"])
    if file:
        totals = create_totals(read_log(path=file.path), config_dict["report_size"])
        create_report(totals, file.date, config_dict["template_dir"], config_dict["report_dir"])
    log.info("Analyse log have finished. Status: succeed.")


if __name__ == "__main__":
    main()
