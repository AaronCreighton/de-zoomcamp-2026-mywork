CREATE OR REPLACE TABLE `{{params.project}}.{{ params.dataset }}.{{params.table}}_{{ logical_date.strftime("%Y_%m") }}_staging`
          AS
          SELECT
            MD5(CONCAT(
              COALESCE(CAST(VendorID AS STRING), ""),
              COALESCE(CAST(tpep_pickup_datetime AS STRING), ""),
              COALESCE(CAST(tpep_dropoff_datetime AS STRING), ""),
              COALESCE(CAST(PULocationID AS STRING), ""),
              COALESCE(CAST(DOLocationID AS STRING), "")
            )) AS unique_row_id,
            "{{params.filename}}" AS filename,
            *
          FROM `{{params.project}}.{{ params.dataset }}.{{params.table}}_{{ logical_date.strftime("%Y_%m") }}_ext`;