# Update the ingest_data_local DAG (2022) to match 04_postgres_taxi (2026) from Kestra. 



import os
from datetime import datetime

from airflow import DAG

from airflow.providers.standard.operators.bash import BashOperator
from airflow.providers.standard.operators.python import PythonOperator 

from load_taxi_local import load_callable

AIRFLOW_HOME = os.environ.get("AIRFLOW_HOME", "/opt/airflow/")


# Schedule_interval="0 6 2 * *" means the DAG will run at 6:00 AM on the 2nd day of every month.
# to update the schedule interval, you can use the cron expression from: https://crontab.guru/
local_workflow = DAG(
    dag_id="04_postgres_taxi_dag",
    start_date=datetime(2021, 1, 1),
    schedule="0 6 2 * *",
)

TAXI_COLOUR = 'yellow'
URL_PREFIX = "https://github.com/DataTalksClub/nyc-tlc-data/releases/download/" + TAXI_COLOUR + "/"
URL_TEMPLATE = URL_PREFIX + "/" + TAXI_COLOUR + "_tripdata_{{ logical_date.strftime(\'%Y-%m\') }}.csv.gz"
OUTPUT_FILE_TEMPLATE = AIRFLOW_HOME + "/" + TAXI_COLOUR + "_tripdata_{{ logical_date.strftime(\'%Y-%m\') }}.csv.gz"
TABLE_NAME_TEMPLATE='tripdata_'+ TAXI_COLOUR + '_staging'
CHUNKSIZE=100000
PG_CONN_ID="pg_ny_taxi"

with local_workflow:
    
    extract_task = BashOperator(
        task_id="extract_task",
        bash_command=f'wget {URL_TEMPLATE} -O {OUTPUT_FILE_TEMPLATE}'
    )
    
    
    load_task = PythonOperator(
        task_id="load_data_task",
        python_callable=load_callable,
        op_kwargs={
            "url": URL_TEMPLATE, 
            "pg_conn_id": PG_CONN_ID,
            "year": "{{ logical_date.strftime(\'%Y\') }}",
            "month": "{{ logical_date.strftime(\'%m\') }}",
            "target_table": TABLE_NAME_TEMPLATE,
            "chunksize": CHUNKSIZE,
        },
    )
    
    extract_task >> load_task
    
    