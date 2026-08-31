
import os
from datetime import datetime

from airflow import DAG

from airflow.providers.standard.operators.bash import BashOperator
from airflow.providers.standard.operators.python import PythonOperator 

from ingest_task import ingest_callable

AIRFLOW_HOME = os.environ.get("AIRFLOW_HOME", "/opt/airflow/")

PG_PASSWORD = os.getenv('PG_PASSWORD')
PG_USER = os.getenv('PG_USER')
PG_HOST = os.getenv('PG_HOST')
PG_PORT = os.getenv('PG_PORT')
PG_DATABASE = os.getenv('PG_DATABASE')
TARGET_TABLE='yellow_taxi_trips'
CHUNKSIZE=100000



# Schedule_interval="0 6 2 * *" means the DAG will run at 6:00 AM on the 2nd day of every month.
# to update the schedule interval, you can use the cron expression from: https://crontab.guru/
local_workflow = DAG(
    dag_id="data_ingest_local",
    start_date=datetime(2021, 1, 1),
    schedule="0 6 2 * *",
)

URL_PREFIX = "https://github.com/DataTalksClub/nyc-tlc-data/releases/download/yellow/"
URL_TEMPLATE = URL_PREFIX + "/yellow_tripdata_{{ logical_date.strftime(\'%Y-%m\') }}.csv.gz"
OUTPUT_FILE_TEMPLATE = AIRFLOW_HOME + "/yellow_tripdata_{{ logical_date.strftime(\'%Y-%m\') }}.csv.gz"


with local_workflow:
    
    wget_task = BashOperator(
        task_id="wget_task",
        bash_command=f'wget {URL_TEMPLATE} -O {OUTPUT_FILE_TEMPLATE}'
    )
    
    # test_parameters = BashOperator(
    #     task_id="test_parameters",
    #     bash_command=f'echo "PG_USER: {PG_USER}, PG_PASSWORD: {PG_PASSWORD}, PG_HOST: {PG_HOST}, PG_PORT: {PG_PORT}, PG_DATABASE: {PG_DATABASE}"'
    # )
    
    ingest_task = PythonOperator(
        task_id="ingest_task",
        python_callable=ingest_callable,
        op_kwargs={
            "pg_user": PG_USER,
            "pg_pass": PG_PASSWORD,
            "pg_host": PG_HOST,
            "pg_port": PG_PORT,
            "pg_db": PG_DATABASE,
            "year": "{{ logical_date.strftime(\'%Y\') }}",
            "month": "{{ logical_date.strftime(\'%m\') }}",
            "target_table": TARGET_TABLE,
            "chunksize": CHUNKSIZE,
        },
    )
    
    wget_task >> ingest_task
    
    