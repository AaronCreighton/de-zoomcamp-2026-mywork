from airflow.sdk import Asset

TAXI_GZ = {
    colour: Asset(name=f"{colour}_tripdata_gz", uri=f"taxi://{colour}_tripdata_gz")
    for colour in ("yellow", "green")
}