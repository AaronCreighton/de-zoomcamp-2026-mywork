# Update the ingest_data_local DAG (2022) to match 04_postgres_taxi (2026) from Kestra. 



import os
from datetime import datetime


from airflow.sdk import dag, Variable

from airflow.providers.standard.operators.bash import BashOperator
from airflow.providers.google.cloud.transfers.local_to_gcs import LocalFilesystemToGCSOperator
from airflow.providers.google.cloud.operators.bigquery import BigQueryInsertJobOperator


AIRFLOW_HOME = os.environ.get("AIRFLOW_HOME", "/opt/airflow/")
CHUNKSIZE=100000


# GCP variables
GCP_CONN_ID = "gcp_zoomcamp"


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
    OUTPUT_FILE_TEMPLATE = AIRFLOW_HOME + "/" + COlOUR_DATE + ".csv"
    
    # GCP variables
    GCS_OBJECT_PREFIX = "taxi/raw/" + TAXI_COLOUR + "_tripdata/{{ logical_date.strftime(\"%Y/%m\") }}.csv"
    
    # table names for external and staging tables in BigQuery
    TABLE_NAME= 'tripdata_' + TAXI_COLOUR  #+ "_tripdata_{{ logical_date.strftime(\'%Y_%m\') }}"
    #EXTERNAL_TABLE=  TAXI_COLOUR + "_tripdata_{{ logical_date.strftime(\'%Y_%m\') }}" + '_ext'
    #STAGING_TABLE=  TAXI_COLOUR + "_tripdata_{{ logical_date.strftime(\'%Y_%m\') }}" + '_staging'
    
     
    # newer Taskflow API, of Airflow Dag factory function, compared to postgres dag.
    @dag(
        dag_id="08_gcp_taxi_"+TAXI_COLOUR+"_dag",
        start_date=datetime(2021, 1, 1),
        schedule=CONFIG.get("schedule"),
    )
    def local_workflow():   

        extract_task = BashOperator(
            task_id="extract_task",
            bash_command="wget -qO- " + URL_TEMPLATE + " | gunzip > " + OUTPUT_FILE_TEMPLATE
        )
        
        upload_task = LocalFilesystemToGCSOperator(
            task_id="upload_to_gcs",
            gcp_conn_id=GCP_CONN_ID,
            src=OUTPUT_FILE_TEMPLATE,
            dst=GCS_OBJECT_PREFIX,
            bucket=Variable.get("GCP_BUCKET"),
        )
        
        
        bq_external_table = BigQueryInsertJobOperator(
            task_id="bq_create_external_table",
            gcp_conn_id=GCP_CONN_ID,
            configuration={
                "query": {
                    "query": "{% include 'sql/external_table_" + colour + "_bigquery.sql' %}",
                    "useLegacySql": False,
                }
            },
            params={
                "project": Variable.get("GCP_PROJECT"),
                "dataset": Variable.get("GCP_DATASET"),
                "table": TABLE_NAME,
                "bucket": Variable.get("GCP_BUCKET"),
                "gcs_object": GCS_OBJECT_PREFIX,
            },
        )
        
        bq_staging_table = BigQueryInsertJobOperator(
                    task_id="bq_create_staging_table",
                    gcp_conn_id=GCP_CONN_ID,
                    configuration={
                        "query": {
                            "query": "{% include 'sql/staging_table_" + colour + "_bigquery.sql' %}",
                            "useLegacySql": False,
                        }
                    },
                    params={
                        "project": Variable.get("GCP_PROJECT"),
                        "dataset": Variable.get("GCP_DATASET"),
                        "table": TABLE_NAME,
                        "filename": TAXI_COLOUR + "_tripdata_.csv",
                    },
                )
                
        #cleanup = BashOperator(
            #task_id="cleanup",
            #bash_command="rm -f " + OUTPUT_FILE_TEMPLATE,
            # trigger_rule="all_done",  # enable once failures are handled elsewhere —
            # skips cleanup on failure by default, which keeps the file for inspection
        #)
        
        extract_task >> upload_task >> bq_external_table >> bq_staging_table #>> cleanup

    return local_workflow()


for colour, config in DATASETS.items():
    generate_dag = make_dag(colour, config)
    globals()["dag_" + colour] = generate_dag
