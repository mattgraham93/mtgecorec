{{
  config(
    materialized='view',
    tags=['marts', 'production', 'latest']
  )
}}

/*
  Marts: Latest pricing view (most recent date)
  
  Use case:
    - Web application queries (current prices only)
    - Deck pricing calculations
    - "What's this card worth today?" queries
  
  Performance:
    - Lightweight view (no storage cost)
    - Fast queries (partition pruning to single date)
    - Always shows most recent available data
*/

WITH latest_date AS (
  SELECT MAX(ds) as max_ds
  FROM {{ ref('pricing_daily') }}
)

SELECT 
  p.*,
  ld.max_ds as latest_date
FROM {{ ref('pricing_daily') }} p
CROSS JOIN latest_date ld
WHERE p.ds = ld.max_ds
