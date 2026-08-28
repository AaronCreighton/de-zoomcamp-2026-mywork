

from airflow import DAG

from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator

# Schedule_interval="0 6 2 * *" means the DAG will run at 6:00 AM on the 2nd day of every month.
# to update the schedule interval, you can use the cron expression from: https://crontab.guru/
local_workflow = DAG(
    dag_id="Hello_World",
    schedule="0 6 2 * *",
)


with local_workflow:
    
    wget_task = BashOperator(
        task_id="wget_task",
        bash_command='echo "Hello World"'
    )
    
    ingest_task = BashOperator(
        task_id="ingest_task",
        bash_command='echo "Ingesting data"'
    )
    
    wget_task >> ingest_task
    
    