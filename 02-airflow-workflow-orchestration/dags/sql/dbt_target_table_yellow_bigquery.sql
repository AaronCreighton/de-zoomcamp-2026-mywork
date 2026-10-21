CREATE TABLE IF NOT EXISTS `{{params.project}}.{{ params.dataset }}.{{params.table}}`
    (
        filename STRING,     
        VendorID STRING, 
        tpep_pickup_datetime STRING,
        tpep_dropoff_datetime STRING, 
        passenger_count STRING,
        trip_distance STRING,
        RatecodeID STRING, 
        store_and_fwd_flag STRING, 
        PULocationID STRING, 
        DOLocationID STRING,
        payment_type STRING, 
        fare_amount STRING, 
        extra STRING,
        mta_tax STRING,
        tip_amount STRING,
        tolls_amount STRING,
        improvement_surcharge STRING, 
        total_amount STRING,
        congestion_surcharge STRING,
        ingestion_timestamp TIMESTAMP OPTIONS (description = 'The timestamp when the record was ingested into the data warehouse.')
    )
    PARTITION BY DATE(ingestion_timestamp)
    CLUSTER BY filename;