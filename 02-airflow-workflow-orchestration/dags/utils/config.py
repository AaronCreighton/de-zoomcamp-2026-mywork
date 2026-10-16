# dags/utils/config.py

# Schedule_interval="0 6 2 * *" means the DAG will run at 6:00 AM on the 2nd day of every month.
# to update the schedule interval, you can use the cron expression from: https://crontab.guru/
# kestra 05_postgres_taxi_scheduled.py has the following schedule intervals for green and yellow taxi data:

DATASETS = {
    "yellow": {"schedule": "0 10 1 * *"},
    "green":  {"schedule": "0 9 1 * *"},
}
COLOURS = tuple(DATASETS)