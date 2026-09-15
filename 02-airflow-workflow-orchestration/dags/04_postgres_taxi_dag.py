# Update the ingest_data_local DAG (2022) to match 04_postgres_taxi (2026) from Kestra. 



import os
from datetime import datetime

from airflow import DAG

from airflow.providers.standard.operators.bash import BashOperator
from airflow.providers.standard.operators.python import PythonOperator 

from ingest_task import ingest_callable

AIRFLOW_HOME = os.environ.get("AIRFLOW_HOME", "/opt/airflow/")


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
TABLE_NAME_TEMPLATE='yellow_taxi_trips_{{ logical_date.strftime(\'%Y_%m\') }}'
CHUNKSIZE=100000
PG_CONN_ID="pg_ny_taxi"

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
            "pg_conn_id": PG_CONN_ID,
            "year": "{{ logical_date.strftime(\'%Y\') }}",
            "month": "{{ logical_date.strftime(\'%m\') }}",
            "target_table": TABLE_NAME_TEMPLATE,
            "chunksize": CHUNKSIZE,
        },
    )
    
    wget_task >> ingest_task
    
    