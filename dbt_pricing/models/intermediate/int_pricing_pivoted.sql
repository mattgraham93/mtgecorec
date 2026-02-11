{{
  config(
    materialized='view',
    tags=['intermediate', 'transformation']
  )
}}

/*
  Intermediate: Enrich pivoted pricing data with derived fields
  
  Input:
    - Data already pivoted (1 row per card per date)
    - Columns: scryfall_id, card_name, ds, usd, usd_foil, usd_etched, eur, eur_foil, tix
  
  Transformations:
    - Calculate foil premium percentage
    - Find cheapest price across all formats
    - Add data quality flags
    - Add processing timestamp
  
  Example:
    INPUT:
      scryfall_id | ds         | usd  | usd_foil | eur
      abc123      | 2026-02-03 | 2.50 | 5.00     | 2.30
      
    OUTPUT:
      scryfall_id | ds         | usd  | usd_foil | eur | foil_premium_pct | usd_cheapest
      abc123      | 2026-02-03 | 2.50 | 5.00     | 2.30| 100.00          | 2.30
*/

WITH enriched AS (
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
    
    -- Cheapest price (for budget players)
    LEAST(
      COALESCE(usd, 999999),
      COALESCE(usd_foil, 999999),
      COALESCE(usd_etched, 999999)
    ) as usd_cheapest,
    
    -- Price availability flags
    (usd IS NOT NULL) as has_usd_price,
    (eur IS NOT NULL) as has_eur_price,
    (tix IS NOT NULL) as has_tix_price,
    
    -- Foil premium calculation
    CASE 
      WHEN usd IS NOT NULL AND usd_foil IS NOT NULL AND usd > 0
      THEN ROUND((usd_foil - usd) / usd * 100, 2)
      ELSE NULL
    END as foil_premium_pct,
    
    -- Current timestamp for tracking
    CURRENT_TIMESTAMP() as dbt_updated_at
    
  FROM {{ ref('stg_pricing_raw') }}
)

SELECT * FROM enriched
