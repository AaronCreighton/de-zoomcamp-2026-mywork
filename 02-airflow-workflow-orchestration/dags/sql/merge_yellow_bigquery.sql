IF (
  SELECT COUNT(*) FROM (
    SELECT unique_row_id FROM `{{params.project}}.{{ params.dataset }}.{{params.table}}_{{ logical_date.strftime("%Y_%m") }}_staging`
    GROUP BY unique_row_id HAVING COUNT(*) > 1
  )
) > 0 THEN
  RAISE USING MESSAGE = "Duplicate fingerprints in staging";
END IF;


MERGE INTO `{{params.project}}.{{ params.dataset }}.{{params.table}}` AS T
    USING `{{params.project}}.{{ params.dataset }}.{{params.table}}_{{ logical_date.strftime("%Y_%m") }}_staging` AS S
    ON T.unique_row_id = S.unique_row_id
    WHEN NOT MATCHED THEN
    INSERT (
        unique_row_id, filename, vendor_id, tpep_pickup_datetime, tpep_dropoff_datetime,
        passenger_count, trip_distance, ratecode_id, store_and_fwd_flag, pu_location_id,
        do_location_id, payment_type, fare_amount, extra, mta_tax, tip_amount, tolls_amount,
        improvement_surcharge, total_amount, congestion_surcharge
    )
    VALUES (
        S.unique_row_id, S.filename, S.VendorID, S.tpep_pickup_datetime, S.tpep_dropoff_datetime,
        S.passenger_count, S.trip_distance, S.RatecodeID, S.store_and_fwd_flag, S.PULocationID,
        S.DOLocationID, S.payment_type, S.fare_amount, S.extra, S.mta_tax, S.tip_amount, S.tolls_amount,
        S.improvement_surcharge, S.total_amount, S.congestion_surcharge
    );