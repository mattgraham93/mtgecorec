{{
  config(
    materialized='view',
    tags=['staging', 'daily']
  )
}}

/*
  Staging: Load raw pricing data from Databricks staging table
  
  Source: card_pricing_daily_staging (Databricks/Delta Lake)
  
  Current schema (ALREADY PIVOTED):
    - One row per card per date
    - Example: Sol Ring on 2026-02-03 has 1 row with all prices in columns
  
  This staging model:
    - Loads pivoted data from staging table
    - Passes data through with minimal transformations
    - Prepares for additional transformations in intermediate step
*/

WITH raw_pricing AS (
  SELECT
    scryfall_id,
    card_name,
    ds,
    usd,
    usd_foil,
    usd_etched,
    eur,
    eur_foil,
    tix,
    CURRENT_TIMESTAMP() as loaded_at
  FROM {{ source('staging', 'card_pricing_daily_staging') }}
  WHERE 
    -- Filter out invalid records
    scryfall_id IS NOT NULL
    AND card_name IS NOT NULL
    AND ds IS NOT NULL
    
    -- Optional: Filter by date range for testing
    {% if var('test_mode', False) %}
    AND ds >= '{{ var('test_start_date', '2026-02-01') }}'
    {% endif %}
)

SELECT * FROM raw_pricing
