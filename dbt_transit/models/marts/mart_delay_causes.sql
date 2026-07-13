-- Delay root-cause analysis. Per line / month / reporting category: total delays,
-- the category's share of that line-month's delays, and a systemwide monthly share
-- so the shifting mix of causes over time is queryable directly.
with base as (
    select
        line_name,
        period,
        period_year,
        period_month,
        reporting_category,
        sum(delays) as delays
    from {{ ref('stg_trains_delayed') }}
    group by 1, 2, 3, 4, 5
),

line_month_totals as (
    select line_name, period, sum(delays) as line_month_delays
    from base
    group by 1, 2
),

system_month as (
    select period, reporting_category, sum(delays) as system_delays
    from base
    group by 1, 2
),

system_month_totals as (
    select period, sum(delays) as system_month_delays
    from base
    group by 1
)

select
    b.line_name,
    b.period,
    b.period_year,
    b.period_month,
    b.reporting_category,
    b.delays,
    round(safe_divide(b.delays, t.line_month_delays) * 100, 1) as pct_of_line_month,
    round(safe_divide(s.system_delays, st.system_month_delays) * 100, 1) as pct_of_system_month
from base b
join line_month_totals t
    on b.line_name = t.line_name and b.period = t.period
join system_month s
    on b.period = s.period and b.reporting_category = s.reporting_category
join system_month_totals st
    on b.period = st.period
