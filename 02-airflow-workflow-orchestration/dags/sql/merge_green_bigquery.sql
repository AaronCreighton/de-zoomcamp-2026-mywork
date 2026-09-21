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
        unique_row_id, filename, vendor_id, lpep_pickup_datetime, lpep_dropoff_datetime,
        store_and_fwd_flag, ratecode_id, pu_location_id, do_location_id, passenger_count,
        trip_distance, fare_amount, extra, mta_tax, tip_amount, tolls_amount, ehail_fee,
        improvement_surcharge, total_amount, payment_type, trip_type, congestion_surcharge
    )
    VALUES (
        S.unique_row_id, S.filename, S.VendorID, S.lpep_pickup_datetime, S.lpep_dropoff_datetime,
        S.store_and_fwd_flag, S.RatecodeID, S.PULocationID, S.DOLocationID, S.passenger_count,
        S.trip_distance, S.fare_amount, S.extra, S.mta_tax, S.tip_amount, S.tolls_amount, S.ehail_fee,
        S.improvement_surcharge, S.total_amount, S.payment_type, S.trip_type, S.congestion_surcharge
    );