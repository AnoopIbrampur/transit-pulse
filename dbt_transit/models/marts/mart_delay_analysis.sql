-- Delay analysis by line and month: total delays, rolling 3-month average,
-- month-over-month percentage change, and per-month severity rank across lines.
with monthly as (
    select
        line_name,
        period,
        period_year,
        period_month,
        sum(delays) as total_delays
    from {{ ref('stg_trains_delayed') }}
    group by 1, 2, 3, 4
),

windowed as (
    select
        *,
        avg(total_delays) over (
            partition by line_name
            order by period
            rows between 2 preceding and current row
        ) as rolling_3mo_avg_delays,
        lag(total_delays) over (
            partition by line_name
            order by period
        ) as prev_month_delays,
        rank() over (
            partition by period
            order by total_delays desc
        ) as delay_severity_rank
    from monthly
)

select
    line_name,
    period,
    period_year,
    period_month,
    total_delays,
    round(rolling_3mo_avg_delays, 1) as rolling_3mo_avg_delays,
    prev_month_delays,
    case
        when prev_month_delays is null or prev_month_delays = 0 then null
        else round((total_delays - prev_month_delays) / prev_month_delays * 100, 1)
    end as mom_pct_change,
    delay_severity_rank
from windowed
