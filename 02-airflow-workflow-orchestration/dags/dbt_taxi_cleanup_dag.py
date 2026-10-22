# Changed the Airflow DAG from 08_gcp_taxi_upload_dag.py to meet the needs of DBT.
# this holds the upload of the taxi data to GCP bucket, and then load into BigQuery.
#this triggers off dbt_taxi_download_dag.py.

import logging
import os
from datetime import datetime
from utils.config import COLOURS
from utils.assets import loaded_assets, LOADED
from airflow.exceptions import AirflowException

from airflow.sdk import dag, task



CHUNKSIZE=100000

# GCP variables
GCP_CONN_ID = "gcp_zoomcamp"


    
def make_dag(TAXI_COLOUR):
    
    
    # Variables added to target table in BiqQuery, also help with matching columns between source and target tables.
    METADATA = ["filename", "ingestion_timestamp"]
         
    # newer Taskflow API, of Airflow Dag factory function, compared to postgres dag.
    @dag(
        dag_id="dbt_taxi_cleanup_"+TAXI_COLOUR+"_dag",
        start_date=datetime(2019, 1, 1),
        schedule= loaded_assets(TAXI_COLOUR),
        catchup=False,
    )
    def local_workflow():   

        
        @task
        def delete_loaded(*, triggering_asset_events):
            per_asset = []
            for asset, events in triggering_asset_events.items():
                logging.warning("%s: extras=%s", asset.name, [e.extra for e in events])
                paths = {
                    p
                    for e in events
                    if e.extra
                    for p in e.extra.get("paths", ())
                }
                logging.info(
                    "%s: %d event(s), %d with a path", asset.name, len(events), len(paths)
                )
                per_asset.append(paths)
                
            if len(per_asset) != len(LOADED):
                raise AirflowException(
                    f"expected {len(LOADED)} consumers, got {len(per_asset)}"
                )
                
            
            candidates = set.intersection(*per_asset)
            if not candidates:
                logging.info("no month loaded by every consumer yet")
            
            removed = []
            for path in candidates:
                try:
                    os.remove(path)
                    removed.append(path)
                except FileNotFoundError:
                    pass
            return removed
        
        delete_loaded()
        
        
        
    return local_workflow()


for colour  in COLOURS:
    generate_dag = make_dag(colour)
    globals()["dag_" + colour] = generate_dag
