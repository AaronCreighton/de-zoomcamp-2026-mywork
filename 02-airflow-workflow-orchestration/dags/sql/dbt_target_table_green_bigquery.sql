CREATE TABLE IF NOT EXISTS `{{params.project}}.{{ params.dataset }}.{{params.table}}`
    (
        filename STRING, 
        lpep_pickup_datetime STRING, 
        lpep_dropoff_datetime STRING, 
        store_and_fwd_flag STRING, 
        RatecodeID STRING, 
        PULocationID STRING, 
        DOLocationID STRING, 
        passenger_count STRING, 
        trip_distance STRING, 
        fare_amount STRING, 
        extra STRING, 
        mta_tax STRING, 
        tip_amount STRING, 
        tolls_amount STRING, 
        ehail_fee STRING,
        improvement_surcharge STRING, 
        total_amount STRING, 
        payment_type STRING, 
        trip_type STRING,
        ingestion_timestamp TIMESTAMP OPTIONS (description = 'The timestamp when the record was ingested into the data warehouse.')
    ) 
    PARTITION BY DATE(ingestion_timestamp)
    CLUSTER BY filename;
