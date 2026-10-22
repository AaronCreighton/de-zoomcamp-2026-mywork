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

LOADED = (BQ_LOADED,)      # add DUCK_LOADED here when it exists

def loaded_assets(colour):
    """Every consumer's completion asset for one colour."""
    return [consumer[colour] for consumer in LOADED]