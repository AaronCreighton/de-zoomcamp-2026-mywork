# Update the ingest_data_local DAG (2022) to match 04_postgres_taxi (2026) from Kestra.
# Then refined the DAG, so the output in BigQuery is simlar to the



import os
from datetime import datetime
from utils.config import COLOURS

from airflow.sdk import dag, task, Variable

from airflow.providers.google.cloud.transfers.local_to_gcs import LocalFilesystemToGCSOperator
from airflow.providers.google.cloud.operators.bigquery import BigQueryInsertJobOperator
from airflow.providers.google.cloud.hooks.bigquery import BigQueryHook
from airflow.exceptions import AirflowException


CHUNKSIZE=100000

# GCP variables
GCP_CONN_ID = "gcp_zoomcamp"


    
def make_dag(TAXI_COLOUR):
    
    # GCP variables
    GCS_FILE_PREFIX = "taxi/raw/" + TAXI_COLOUR + "_tripdata"
    
    
    # table names for external and staging tables in BigQuery
    TABLE_NAME=  TAXI_COLOUR + '_tripdata' 
    
         
    # newer Taskflow API, of Airflow Dag factory function, compared to postgres dag.
    @dag(
        dag_id="dbt_gcp_taxi_"+TAXI_COLOUR+"_dag",
        start_date=datetime(2019, 1, 1),
        catchup=False,
    )
    def local_workflow():   

        
        
        upload_task = LocalFilesystemToGCSOperator(
            task_id="upload_to_gcs",
            gcp_conn_id=GCP_CONN_ID,
            src=OUTPUT_FILE_TEMPLATE,
            dst=GCS_FILE_PREFIX + "/{{ logical_date.strftime(\"%Y/%m\") }}.csv",
            bucket=Variable.get("GCP_BUCKET"),
        )
        
        
        bq_external_table = BigQueryInsertJobOperator(
            task_id="bq_create_external_table",
            gcp_conn_id=GCP_CONN_ID,
            configuration={
                "query": {
                    "query": "{% include 'sql/dbt_external_table_" + colour + "_bigquery.sql' %}",
                    "useLegacySql": False,
                }
            },
            params={
                "project": Variable.get("GCP_PROJECT"),
                "dataset": Variable.get("GCP_DATASET"),
                "table": TABLE_NAME,
                "bucket": Variable.get("GCP_BUCKET"),
                "gcs_object": GCS_FILE_PREFIX,
            },
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
        def match_columns(dataset, target_table, ext_table):
            # Get the columns from the target table
            bq_hook = BigQueryHook(gcp_conn_id=GCP_CONN_ID)
            target_columns = bq_hook.get_schema(dataset_id=dataset, table_id=target_table)
            ext_columns = bq_hook.get_schema(dataset_id=dataset, table_id=ext_table)

            # Extract column names
            target_column_names = {col['name'] for col in target_columns}
            ext_column_names = {col['name'] for col in ext_columns}

            # Check if all columns in the external table are present in the target table
            missing_columns = ext_column_names - target_column_names
            if missing_columns:
                raise AirflowException(f"Missing columns in target table: {missing_columns}")

        bq_merge_task = BigQueryInsertJobOperator(
                            task_id="bq_merge_staging_to_main",
                            gcp_conn_id=GCP_CONN_ID,
                            configuration={
                                "query": {
                                    "query": "{% include 'sql/merge_" + colour + "_bigquery.sql' %}",
                                    "useLegacySql": False,
                                }
                            },
                            params={
                                "project": Variable.get("GCP_PROJECT"),
                                "dataset": Variable.get("GCP_DATASET"),
                                "table": TABLE_NAME,
                            },
                        )
                
    
        
        extract_task >> upload_task >> bq_external_table >>  bq_target_table >> bq_merge_task

    return local_workflow()


for colour  in COLOURS:
    generate_dag = make_dag(colour)
    globals()["dag_" + colour] = generate_dag
