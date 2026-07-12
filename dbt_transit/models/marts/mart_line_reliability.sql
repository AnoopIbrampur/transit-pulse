-- Composite line-health feed. Per line/month, blends on-time performance, wait
-- assessment, and customer journey time into a single health score, carries
-- ridership for weighting, and attaches division-level fleet MDBF as context.
--
-- MDBF is reported by car class, not line, so it is aggregated to the division
-- (A/B) and joined on division — treat it as fleet reliability context.
with otp as (
    select line_name, period, division, avg(otp_pct) as otp_pct
    from {{ ref('stg_terminal_otp') }}
    where day_type = 1
    group by 1, 2, 3
),

wait as (
    select line_name, period, avg(wait_assessment_pct) as wait_pct
    from {{ ref('stg_wait_assessment') }}
    where day_type = 1
    group by 1, 2
),

journey as (
    select
        line_name,
        period,
        avg(cjt_pct) as cjt_pct,
        sum(num_passengers) as total_passengers
    from {{ ref('stg_customer_journey') }}
    group by 1, 2
),

fleet_mdbf as (
    -- Division-level fleet reliability (mean of car-class MDBF that month).
    select
        -- stg_mdbf.division is 'A'/'B'; OTP division is 'A DIVISION'/'B DIVISION'
        case when division = 'A' then 'A DIVISION' else 'B DIVISION' end as division,
        period,
        avg(mdbf) as avg_fleet_mdbf
    from {{ ref('stg_mdbf') }}
    group by 1, 2
)

select
    o.line_name,
    o.period,
    extract(year from o.period)  as period_year,
    extract(month from o.period) as period_month,
    o.division,
    round(o.otp_pct, 2)   as otp_pct,
    round(w.wait_pct, 2)  as wait_assessment_pct,
    round(j.cjt_pct, 2)   as cjt_pct,
    j.total_passengers,
    round(f.avg_fleet_mdbf, 0) as avg_fleet_mdbf,
    -- Composite health score: weighted blend of the three service metrics.
    -- OTP 50%, wait assessment 30%, customer journey time 20%.
    round(
        0.50 * o.otp_pct
        + 0.30 * coalesce(w.wait_pct, o.otp_pct)
        + 0.20 * coalesce(j.cjt_pct, o.otp_pct),
        2
    ) as line_health_score,
    case
        when o.otp_pct >= 90 then 'reliable'
        when o.otp_pct >= 80 then 'at_risk'
        else 'poor'
    end as reliability_tier
from otp o
left join wait w    on o.line_name = w.line_name and o.period = w.period
left join journey j on o.line_name = j.line_name and o.period = j.period
left join fleet_mdbf f on o.division = f.division and o.period = f.period
