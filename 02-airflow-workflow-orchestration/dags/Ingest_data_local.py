
import os
from datetime import datetime

from airflow import DAG

from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator 


AIRFLOW_HOME = os.environ.get("AIRFLOW_HOME", "/opt/airflow/")

# Schedule_interval="0 6 2 * *" means the DAG will run at 6:00 AM on the 2nd day of every month.
# to update the schedule interval, you can use the cron expression from: https://crontab.guru/
local_workflow = DAG(
    dag_id="data_ingest_local_dag",
    schedule="0 6 2 * *",
    start_date=datetime(2023, 1, 1),
)

url = "https://github.com/DataTalksClub/nyc-tlc-data/releases/download/yellow/yellow_tripdata_2021-01.csv.gz"


with local_workflow:
    
    wget_task = BashOperator(
        task_id="wget_task",
        bash_command=f'wget {url} -O {AIRFLOW_HOME}/yellow_tripdata_2021-01.csv.gz'
    )
    
    ingest_task = BashOperator(
        task_id="ingest_task",
        bash_command=f'ls {AIRFLOW_HOME}'
    )
    
    wget_task >> ingest_task
    
    