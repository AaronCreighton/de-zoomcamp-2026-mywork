# Update the ingest_data_local DAG (2022) to match 04_postgres_taxi (2026) from Kestra. 



import os
from datetime import datetime

from airflow import DAG

from airflow.providers.standard.operators.bash import BashOperator
from airflow.providers.standard.operators.python import PythonOperator
from airflow.providers.common.sql.operators.sql import SQLExecuteQueryOperator


from load_taxi_local import load_callable

AIRFLOW_HOME = os.environ.get("AIRFLOW_HOME", "/opt/airflow/")
CHUNKSIZE=100000
PG_CONN_ID="pg_ny_taxi"
   
    
    
def make_dag(TAXI_COLOUR):
    # Schedule_interval="0 6 2 * *" means the DAG will run at 6:00 AM on the 2nd day of every month.
    # to update the schedule interval, you can use the cron expression from: https://crontab.guru/

    URL_PREFIX = "https://github.com/DataTalksClub/nyc-tlc-data/releases/download/" + TAXI_COLOUR + "/"
    URL_TEMPLATE = URL_PREFIX + "/" + TAXI_COLOUR + "_tripdata_{{ logical_date.strftime(\'%Y-%m\') }}.csv.gz"
    OUTPUT_FILE_TEMPLATE = AIRFLOW_HOME + "/" + TAXI_COLOUR + "_tripdata_{{ logical_date.strftime(\'%Y-%m\') }}.csv.gz"
    STAGING_TABLE='tripdata_'+ TAXI_COLOUR + '_staging'
    FINAL_TABLE='tripdata_'+ TAXI_COLOUR
    
    
    with DAG(
        dag_id="04_postgres_taxi_"+TAXI_COLOUR+"_dag",
        start_date=datetime(2021, 1, 1),
        schedule="0 6 2 * *",
    ) as local_workflow:

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
                "taxi_colour": TAXI_COLOUR,
                "target_table": STAGING_TABLE,
                "chunksize": CHUNKSIZE,
            },
        )
    
        create_final = SQLExecuteQueryOperator(
            task_id="transform_task",
            conn_id=PG_CONN_ID,
            sql=f"sql/transform_"+TAXI_COLOUR+".sql",
            params={"final_table": FINAL_TABLE,
                    "staging_table": STAGING_TABLE,
                    "taxi_colour": TAXI_COLOUR
                    },
            split_statements=True,
            autocommit=False, #make true for testing, making each statement a transaction. 
        )
        
        extract_task >> load_task >> create_final


    return local_workflow


for colour in ["yellow", "green"]:
    globals()[f"dag_{colour}"] = make_dag(TAXI_COLOUR=colour)