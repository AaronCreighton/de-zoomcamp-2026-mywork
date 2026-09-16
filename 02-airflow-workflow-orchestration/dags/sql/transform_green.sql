CREATE TABLE IF NOT EXISTS {{ params.final_table }} (
    unique_row_id          uuid PRIMARY KEY,
    filename               text,
    vendor_id              bigint,
    lpep_pickup_datetime   timestamp,
    lpep_dropoff_datetime  timestamp,
    passenger_count        integer,
    trip_distance          double precision,
    ratecode_id            bigint,
    store_and_fwd_flag     text,
    pu_location_id         bigint,
    do_location_id         bigint,
    payment_type           integer,
    fare_amount            double precision,
    extra                  double precision,
    mta_tax                double precision,
    tip_amount             double precision,
    tolls_amount           double precision,
    improvement_surcharge  double precision,
    total_amount           double precision,
    congestion_surcharge   double precision,
    ehail_fee              double precision,
    trip_type              integer
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
    unique_row_id, filename, vendor_id, lpep_pickup_datetime, lpep_dropoff_datetime,
    passenger_count, trip_distance, ratecode_id, store_and_fwd_flag, pu_location_id,
    do_location_id, payment_type, fare_amount, extra, mta_tax, tip_amount, tolls_amount,
    improvement_surcharge, total_amount, congestion_surcharge, ehail_fee, trip_type
  )
  VALUES (
    S.unique_row_id, S.filename, S."VendorID", S.lpep_pickup_datetime, S.lpep_dropoff_datetime,
    S.passenger_count, S.trip_distance, S."RatecodeID", S.store_and_fwd_flag, S."PULocationID",
    S."DOLocationID", S.payment_type, S.fare_amount, S.extra, S.mta_tax, S.tip_amount, S.tolls_amount,
    S.improvement_surcharge, S.total_amount, S.congestion_surcharge, S.ehail_fee, S.trip_type
  );