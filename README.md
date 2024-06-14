# Analyse nginx logs

Script is analyse nginx log file and create HTML report. Record in report is in order by decriasing time_sum.
Log_analyzer has config file log_analyzer.ini with the default values of log_dir, report_dir, template_dir and report_size.
You can create your own config file and run scripts with arg --config. Default config will be overriten.

Log files must locate in log folder. Reports will be saved in report folder.

## Installation

````bash
poetry install
poetry run python src/log_analyzer.py
````

## Examples
````bash
poetry run python src/log_analyzer/log_analyzer.py
poetry run python src/log_analyzer/log_analyzer.py --config 'new_config_path.ini'
make log_analyzer
````

## Tests
````
make test
````