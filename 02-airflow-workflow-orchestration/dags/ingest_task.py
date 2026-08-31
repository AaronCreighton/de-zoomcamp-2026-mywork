import pandas as pd
from sqlalchemy import create_engine


dtype = {
    "VendorID": "Int64",
    "passenger_count": "Int64",
    "trip_distance": "float64",
    "RatecodeID": "Int64",
    "store_and_fwd_flag": "string",
    "PULocationID": "Int64",
    "DOLocationID": "Int64",
    "payment_type": "Int64",
    "fare_amount": "float64",
    "extra": "float64",
    "mta_tax": "float64",
    "tip_amount": "float64",
    "tolls_amount": "float64",
    "improvement_surcharge": "float64",
    "total_amount": "float64",
    "congestion_surcharge": "float64"
}



parse_dates = [
    "tpep_pickup_datetime",
    "tpep_dropoff_datetime"
]



def get_engine(pg_user, pg_pass, pg_host, pg_port, pg_db):
    """Create SQLAlchemy engine for PostgreSQL database."""
    return create_engine(f'postgresql+psycopg://{pg_user}:{pg_pass}@{pg_host}:{pg_port}/{pg_db}')


def ingest_taxi_data(year, month, target_table, chunksize, engine):
    """Ingest NYC taxi data into PostgreSQL database."""
    
    prefix = 'https://github.com/DataTalksClub/nyc-tlc-data/releases/download/yellow/'
    url = f'{prefix}/yellow_tripdata_{year}-{month:02d}.csv.gz'

    df_iter = pd.read_csv(
        url,
        dtype=dtype,
        parse_dates=parse_dates,
        iterator=True,
        chunksize=chunksize
    )

    first = True

    for df_chunk in df_iter:

        if first:
            # Create table schema (no data)
            df_chunk.head(0).to_sql(
                name=target_table,
                con=engine,
                if_exists="replace"
            )
            first = False
            #print("Table created")

        # Insert chunk
        df_chunk.to_sql(
            name=target_table,
            con=engine,
            if_exists="append"
        )

        #print("Inserted:", len(df_chunk))

def ingest_zone(engine):
    """Get taxi zone data and insert into PostgreSQL database."""
    zones_url = "https://d37ci6vzurychx.cloudfront.net/misc/taxi_zone_lookup.csv"
    zones_df = pd.read_csv(zones_url)
    zones_df.to_sql("taxi_zones", engine, if_exists="replace", index=False)
    
def ingest_callable(pg_user, pg_pass, pg_host, pg_port, pg_db, year, month, target_table, chunksize):
    print(f"Connecting to PostgreSQL database {pg_db} at {pg_host}:{pg_port} as user {pg_user}")
    
    """Run the data ingestion process."""
    engine = get_engine(pg_user, pg_pass, pg_host, pg_port, pg_db)
    engine.connect()
    #ingest_taxi_data(year, month, target_table, chunksize, engine)
    #ingest_zone(engine)  
