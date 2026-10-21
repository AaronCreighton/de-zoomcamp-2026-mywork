from airflow.sdk import Asset
from utils.config import COLOURS

TAXI_GZ = {
    colour: Asset(name=f"{colour}_tripdata_gz", uri=f"taxi://{colour}_tripdata_gz")
    for colour in COLOURS
}


BQ_LOADED = {
    colour: Asset(name=f"{colour}_loaded_bq", uri=f"taxi://{colour}_loaded_bq")
    for colour in COLOURS
}