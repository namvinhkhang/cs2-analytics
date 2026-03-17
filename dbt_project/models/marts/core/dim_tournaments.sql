-- Dimension: tournaments from Liquipedia data.
-- Currently a placeholder structure for Phase 4 enrichment.
-- Tournament metadata was count-only in Phase 1 (no canonical schema for tournaments).
-- Will be enriched in a future phase when tournament metadata gets proper S3 persistence.
select
    {{ dbt_utils.generate_surrogate_key(["'placeholder'"]) }} as tournament_sk,
    'unknown'           as tournament_id,
    'Unknown Tournament' as tournament_name,
    null                as tier,
    null                as start_date,
    null                as end_date
