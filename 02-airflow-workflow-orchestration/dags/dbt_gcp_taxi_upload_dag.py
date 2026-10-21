# Changed the Airflow DAG from 08_gcp_taxi_upload_dag.py to meet the needs of DBT.
# this holds the upload of the taxi data to GCP bucket, and then load into BigQuery.
#this triggers off dbt_taxi_download_dag.py.

import csv, gzip, re, logging
from datetime import datetime
from utils.config import COLOURS
from utils.assets import TAXI_GZ, BQ_LOADED
from utils.bigquery import build_bqt_ext_sql, build_insert_delete_sql

from airflow.sdk import dag, task, Variable

from airflow.providers.google.cloud.transfers.local_to_gcs import LocalFilesystemToGCSOperator
from airflow.providers.google.cloud.operators.bigquery import BigQueryInsertJobOperator
from airflow.providers.google.cloud.hooks.bigquery import BigQueryHook
from airflow.exceptions import AirflowException


CHUNKSIZE=100000

# GCP variables
GCP_CONN_ID = "gcp_zoomcamp"


    
def make_dag(TAXI_COLOUR):
    
    # table names for external and staging tables in BigQuery
    TABLE_NAME=  TAXI_COLOUR + '_tripdata' 
    
    # GCP variables
    GCS_FILE_PREFIX = "taxi/raw/" + TABLE_NAME
    
    # Variables added to target table in BiqQuery, also help with matching columns between source and target tables.
    METADATA = ["filename", "ingestion_timestamp"]
         
    # newer Taskflow API, of Airflow Dag factory function, compared to postgres dag.
    @dag(
        dag_id="dbt_gcp_taxi_upload_"+TAXI_COLOUR+"_dag",
        start_date=datetime(2019, 1, 1),
        schedule=[TAXI_GZ[TAXI_COLOUR]],
        catchup=False,
    )
    def local_workflow():   

        @task()
        def file_downloaded(*, triggering_asset_events):
            return [
                e.extra["path"]
                for events in triggering_asset_events.values()
                for e in events
            ]
        
        @task
        def get_file_info(src):
            with gzip.open(src, "rt", newline="") as f:
                names = next(csv.reader(f), None)
            if not names:
                raise ValueError(f"no header row in {src}")
            
            date = re.search(r"(\d{4})-(\d{2})", src)
            return {
                "path": src,
                "year": date[1],
                "month": date[2],
                "names": names,
            }
            
        file_info = get_file_info.expand(src=file_downloaded())

            
        upload_task = LocalFilesystemToGCSOperator.partial(
                task_id="upload_to_gcs",
                gcp_conn_id=GCP_CONN_ID,
                bucket=Variable.get("GCP_BUCKET"),
            ).expand_kwargs(
                file_info.map(lambda t: {
                    "src": t["path"],
                    "dst": f"{GCS_FILE_PREFIX}/{t['year']}/{t['month']}.csv.gz",
                })
            )
        
        bq_external_table = BigQueryInsertJobOperator.partial(
                task_id="bq_create_external_table",
                gcp_conn_id=GCP_CONN_ID,
            ).expand_kwargs(
                file_info.map(lambda t: {
                    "configuration": {
                        "query": {
                            "query": build_bqt_ext_sql(
                                t, 
                                Variable.get("GCP_PROJECT"), 
                                Variable.get("GCP_DATASET"), 
                                Variable.get("GCP_BUCKET"),
                                TABLE_NAME,
                                 GCS_FILE_PREFIX
                                ),
                            "useLegacySql": False,
                        }
                    }
                })
            )
        
        
        
        bq_target_table = BigQueryInsertJobOperator(
                                    task_id="bq_create_target_table",
                                    gcp_conn_id=GCP_CONN_ID,
                                    configuration={
                                        "query": {
                                            "query": "{% include 'sql/dbt_target_table_" + colour + "_bigquery.sql' %}",
                                            "useLegacySql": False,
                                        }
                                    },
                                    params={
                                        "project": Variable.get("GCP_PROJECT"),
                                        "dataset": Variable.get("GCP_DATASET"),
                                        "table": TABLE_NAME,
                                    },
                                )
        @task
        def match_columns(target):
            hook = BigQueryHook(gcp_conn_id=GCP_CONN_ID)
            contract = [
                f["name"] for f in
                hook.get_schema(dataset_id=Variable.get("GCP_DATASET"), table_id=TABLE_NAME)["fields"]
            ]

            unexpected = [n for n in target["names"] if n not in contract]
            if unexpected:
                raise AirflowException(f"not in {TABLE_NAME}: {unexpected}")

            missing = [c for c in contract if c not in target["names"] + METADATA]
            if missing:
                logging.warning("absent from source, will be NULL: %s", missing)

            return target
        
        columns_checked = match_columns.expand(target=file_info)
        
        insert_delete_task = BigQueryInsertJobOperator.partial(
                task_id="bq_insert_and_prune",
                gcp_conn_id=GCP_CONN_ID,
            ).expand_kwargs(
                file_info.map(lambda t: {
                    "configuration": {
                        "query": {
                            "query": build_insert_delete_sql(
                                t, 
                                Variable.get("GCP_PROJECT"), 
                                Variable.get("GCP_DATASET"), 
                                TABLE_NAME
                                ),
                            "useLegacySql": False,
                        }
                    }
                })
            )
            
        @task(outlets=[BQ_LOADED[colour]])
        def file_uploaded(target, *, outlet_events):
            outlet_events[BQ_LOADED[colour]].extra = {"path": target["path"]}
            return target
        
        
        
        file_info >> upload_task >> bq_external_table >> insert_delete_task
        bq_target_table >> columns_checked >> insert_delete_task
        
        insert_delete_task >> file_uploaded(columns_checked)

    return local_workflow()


for colour  in COLOURS:
    generate_dag = make_dag(colour)
    globals()["dag_" + colour] = generate_dag
