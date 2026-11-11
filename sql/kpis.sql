-- Campaign KPI layer on the Facebook "Sales Conversion Optimization" data.
-- Source table: facebook_ads (loaded by src/kpis.py from the raw CSV).
--
-- Definitions (also in the KPI dictionary):
--   conversions   = Approved_Conversion (the stricter, purchase-approved count)
--   CTR           = clicks / impressions                    (undefined at 0 impressions)
--   CPM           = spend / impressions * 1000              (noisy at small impressions)
--   CPC           = spend / clicks                          (undefined at 0 clicks)
--   CVR           = conversions / clicks  -- base is CLICKS, stated everywhere
--   CPA           = spend / conversions                     (undefined at 0 conversions, never 0)
--   ROAS          = conversions * @value_per_conversion / spend  -- the value is an ASSUMPTION
--
-- Every division is guarded with NULLIF so an undefined metric is NULL, never 0.

-- ---------------------------------------------------------------- ad_kpis
-- Per-ad KPIs. SQL skills: CTE, NULLIF guards, CASE.
CREATE OR REPLACE VIEW ad_kpis AS
WITH base AS (
    SELECT
        ad_id,
        xyz_campaign_id                         AS campaign_id,
        age, gender, interest,
        Impressions                             AS impressions,
        Clicks                                  AS clicks,
        Spent                                   AS spend,
        Approved_Conversion                     AS conversions
    FROM facebook_ads
)
SELECT
    *,
    clicks / NULLIF(impressions, 0)::DOUBLE                 AS ctr,
    spend  / NULLIF(impressions, 0)::DOUBLE * 1000          AS cpm,
    spend  / NULLIF(clicks, 0)::DOUBLE                      AS cpc,
    conversions / NULLIF(clicks, 0)::DOUBLE                 AS cvr,
    spend  / NULLIF(conversions, 0)::DOUBLE                 AS cpa
FROM base;

-- --------------------------------------------------------- campaign_rollup
-- Same KPIs per campaign, recomputed from SUMS (never averaged from ad-level
-- ratios: a mean of ratios weights a 100-impression ad like a 1M one).
CREATE OR REPLACE VIEW campaign_rollup AS
SELECT
    campaign_id,
    COUNT(*)                                                AS ads,
    SUM(impressions)                                        AS impressions,
    SUM(clicks)                                             AS clicks,
    SUM(spend)                                              AS spend,
    SUM(conversions)                                        AS conversions,
    SUM(clicks)      / NULLIF(SUM(impressions), 0)::DOUBLE  AS ctr,
    SUM(spend)       / NULLIF(SUM(impressions), 0)::DOUBLE * 1000 AS cpm,
    SUM(spend)       / NULLIF(SUM(clicks), 0)::DOUBLE       AS cpc,
    SUM(conversions) / NULLIF(SUM(clicks), 0)::DOUBLE       AS cvr,
    SUM(spend)       / NULLIF(SUM(conversions), 0)::DOUBLE  AS cpa
FROM ad_kpis
GROUP BY campaign_id;

-- ----------------------------------------------------- ad_rank_in_campaign
-- Rank ads by CPA inside each campaign. Ads with no conversions rank last.
-- SQL skill: RANK() OVER (PARTITION BY ...), NULLS LAST.
CREATE OR REPLACE VIEW ad_rank_in_campaign AS
SELECT
    campaign_id,
    ad_id,
    spend,
    conversions,
    cpa,
    RANK() OVER (
        PARTITION BY campaign_id
        ORDER BY cpa ASC NULLS LAST
    ) AS cpa_rank,
    RANK() OVER (
        PARTITION BY campaign_id, age, gender
        ORDER BY cpa ASC NULLS LAST
    ) AS cpa_rank_in_age_gender
FROM ad_kpis;

-- ------------------------------------------------------------ running_spend
-- Cumulative spend by ad within each campaign (ordered by ad_id as a proxy
-- for creation order; the data carries no dates).
-- SQL skill: SUM() OVER (... ORDER BY ...).
CREATE OR REPLACE VIEW running_spend AS
SELECT
    campaign_id,
    ad_id,
    spend,
    SUM(spend) OVER (
        PARTITION BY campaign_id
        ORDER BY ad_id
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) AS cumulative_spend,
    SUM(spend) OVER (PARTITION BY campaign_id) AS campaign_spend
FROM ad_kpis;

-- ------------------------------------------------------------- segment_cuts
-- KPIs by age, gender and interest; segments too small to trust are flagged,
-- not hidden. SQL skills: GROUPING SETS-style cuts via UNION ALL, HAVING-free
-- flagging (we keep every row and mark it instead of filtering).
CREATE OR REPLACE VIEW segment_cuts AS
WITH cuts AS (
    SELECT 'age' AS dimension, age AS segment,
           SUM(impressions) AS impressions, SUM(clicks) AS clicks,
           SUM(spend) AS spend, SUM(conversions) AS conversions
    FROM ad_kpis GROUP BY age
    UNION ALL
    SELECT 'gender', gender,
           SUM(impressions), SUM(clicks), SUM(spend), SUM(conversions)
    FROM ad_kpis GROUP BY gender
    UNION ALL
    SELECT 'interest', interest::VARCHAR,
           SUM(impressions), SUM(clicks), SUM(spend), SUM(conversions)
    FROM ad_kpis GROUP BY interest
)
SELECT
    dimension, segment, impressions, clicks, spend, conversions,
    clicks      / NULLIF(impressions, 0)::DOUBLE        AS ctr,
    spend       / NULLIF(impressions, 0)::DOUBLE * 1000 AS cpm,
    spend       / NULLIF(clicks, 0)::DOUBLE             AS cpc,
    conversions / NULLIF(clicks, 0)::DOUBLE             AS cvr,
    spend       / NULLIF(conversions, 0)::DOUBLE        AS cpa,
    impressions < 100000                                AS low_volume_flag
FROM cuts;
