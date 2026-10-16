# Update the ingest_data_local DAG (2022) to match 04_postgres_taxi (2026) from Kestra.
# Then refined the DAG, so the output in BigQuery is simlar to the



import os
from datetime import datetime

import requests
from airflow.sdk import dag, task
from utils.assets import TAXI_GZ
from utils.config import DATASETS




DOWNLOAD_DIR = "/opt/airflow/taxi_download"



    
def make_dag(TAXI_COLOUR, CONFIG):
    URL_PREFIX = "https://github.com/DataTalksClub/nyc-tlc-data/releases/download/" + TAXI_COLOUR + "/"   
    COlOUR_DATE =  TAXI_COLOUR + "_tripdata_{{ logical_date.strftime(\'%Y-%m\') }}"
    URL_TEMPLATE = URL_PREFIX + "/" + COlOUR_DATE + ".csv.gz"
    OUTPUT_FILE_TEMPLATE = DOWNLOAD_DIR + "/" + COlOUR_DATE + ".csv.gz"    
         
    # newer Taskflow API, of Airflow Dag factory function, compared to postgres dag.
    @dag(
        dag_id="dbt_taxi_download_" + TAXI_COLOUR + "_dag",
        start_date=datetime(2019, 1, 1),
        schedule=CONFIG.get("schedule"),
        catchup=False,
    )
    def local_workflow():   

        asset = TAXI_GZ[TAXI_COLOUR]

        @task(outlets=[asset])
        def extract(url, dest, *, outlet_events):
            with requests.get(url, stream=True, timeout=60) as r:
                r.raise_for_status()
                with open(dest, "wb") as f:
                    for chunk in r.iter_content(chunk_size=1 << 20):
                        f.write(chunk)
            outlet_events[asset].extra = {"path": dest}
        
        
        
        extract(URL_TEMPLATE, OUTPUT_FILE_TEMPLATE)
        
    return local_workflow()


for colour, config in DATASETS.items():
    generate_dag = make_dag(colour, config)
    globals()["dag_" + colour] = generate_dag
