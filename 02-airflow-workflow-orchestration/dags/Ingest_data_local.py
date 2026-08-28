
import os
From datetime import datetime

from airflow import DAG

from airflow.providers.standard.operators.bash import BashOperator
from airflow.providers.standard.operators.python import PythonOperator 


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


with local_workflow:
    
    wget_task = BashOperator(
        task_id="wget_task",
        bash_command=f'wget {URL_TEMPLATE} -O {OUTPUT_FILE_TEMPLATE}'
    )
    
    ingest_task = BashOperator(
        task_id="ingest_task",
        bash_command=f'ls {AIRFLOW_HOME}'
    )
    
    wget_task >> ingest_task
    
    