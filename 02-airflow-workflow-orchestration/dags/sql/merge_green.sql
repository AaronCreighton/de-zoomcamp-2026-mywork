CREATE TABLE IF NOT EXISTS {{ params.final_table }} (
    unique_row_id          uuid,
    filename               text,
    VendorID               text,
    lpep_pickup_datetime   timestamp,
    lpep_dropoff_datetime  timestamp,
    store_and_fwd_flag     text,
    RatecodeID             text,
    PULocationID           text,
    DOLocationID           text,
    passenger_count        integer,
    trip_distance          double precision,
    fare_amount            double precision,
    extra                  double precision,
    mta_tax                double precision,
    tip_amount             double precision,
    tolls_amount           double precision,
    ehail_fee              double precision,
    improvement_surcharge  double precision,
    total_amount           double precision,
    payment_type           integer,
    trip_type              integer,
    congestion_surcharge   double precision,
    --ingestion_timestamp TIMESTAMP, (description = 'The timestamp when the record was ingested into the data warehouse. research timestamp type for postgres)')
);


ALTER TABLE {{ params.staging_table }}
  ADD COLUMN IF NOT EXISTS unique_row_id uuid,
  ADD COLUMN IF NOT EXISTS filename text;

 UPDATE {{params.staging_table}}
          SET 
            unique_row_id = md5(
              COALESCE(CAST("VendorID" AS text), '') ||
              COALESCE(CAST("lpep_pickup_datetime" AS text), '') || 
              COALESCE(CAST("lpep_dropoff_datetime" AS text), '') || 
              COALESCE(CAST("PULocationID" AS text), '') || 
              COALESCE(CAST("DOLocationID" AS text), '') || 
              COALESCE(CAST("fare_amount" AS text), '') || 
              COALESCE(CAST("trip_distance" AS text), '')      
            )::uuid,
            filename = '{{ params.taxi_colour }}_tripdata_{{ logical_date.strftime("%Y-%m") }}.csv.gz';


MERGE INTO {{params.final_table}} AS T
USING {{params.staging_table}} AS S
ON T.unique_row_id = S.unique_row_id
WHEN NOT MATCHED THEN
  INSERT (
  unique_row_id, filename, VendorID, lpep_pickup_datetime, lpep_dropoff_datetime,
  store_and_fwd_flag, RatecodeID, PULocationID, DOLocationID, passenger_count,
  trip_distance, fare_amount, extra, mta_tax, tip_amount, tolls_amount, ehail_fee,
  improvement_surcharge, total_amount, payment_type, trip_type, congestion_surcharge
)
VALUES (
  S.unique_row_id, S.filename, S."VendorID", S.lpep_pickup_datetime, S.lpep_dropoff_datetime,
  S.store_and_fwd_flag, S."RatecodeID", S."PULocationID", S."DOLocationID", S.passenger_count,
  S.trip_distance, S.fare_amount, S.extra, S.mta_tax, S.tip_amount, S.tolls_amount, S.ehail_fee,
  S.improvement_surcharge, S.total_amount, S.payment_type, S.trip_type, S.congestion_surcharge
);
