# Update the ingest_data_local DAG (2022) to match 04_postgres_taxi (2026) from Kestra.
# Then refined the DAG, so the output in BigQuery is simlar to the



import os
from datetime import datetime

from airflow.sdk import dag, Asset  

from airflow.providers.standard.operators.bash import BashOperator


DOWNLOAD_DIR = "/opt/airflow/taxi_download"



# Schedule_interval="0 6 2 * *" means the DAG will run at 6:00 AM on the 2nd day of every month.
# to update the schedule interval, you can use the cron expression from: https://crontab.guru/
# kestra 05_postgres_taxi_scheduled.py has the following schedule intervals for green and yellow taxi data:
DATASETS = {
    "yellow": {"schedule": "0 10 1 * *"},
    "green":  {"schedule": "0 9 1 * *"},
}
    
def make_dag(TAXI_COLOUR, CONFIG):
    URL_PREFIX = "https://github.com/DataTalksClub/nyc-tlc-data/releases/download/" + TAXI_COLOUR + "/"   
    COlOUR_DATE =  TAXI_COLOUR + "_tripdata_{{ logical_date.strftime(\'%Y-%m\') }}"
    URL_TEMPLATE = URL_PREFIX + "/" + COlOUR_DATE + ".csv.gz"
    OUTPUT_FILE_TEMPLATE = AIRFLOW_HOME + "/" + COlOUR_DATE + ".csv.gz"    
         
    # newer Taskflow API, of Airflow Dag factory function, compared to postgres dag.
    @dag(
        dag_id="dbt_taxi_download_" + TAXI_COLOUR + "_dag",
        start_date=datetime(2019, 1, 1),
        schedule=CONFIG.get("schedule"),
        catchup=False,
    )
    def local_workflow():   

        extract_task = BashOperator(
            task_id="extract_task",
            bash_command="wget -qO- " + URL_TEMPLATE + " " + OUTPUT_FILE_TEMPLATE
        )
        
        
        
        
        
        extract_task


for colour, config in DATASETS.items():
    generate_dag = make_dag(colour, config)
    globals()["dag_" + colour] = generate_dag
