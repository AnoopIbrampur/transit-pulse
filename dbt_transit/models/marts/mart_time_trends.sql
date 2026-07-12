-- Time-trend feed for the dashboard heatmap and peak/weekend comparisons.
-- One row per line/month with weekday vs weekend OTP, peak vs off-peak customer
-- journey time, and a rolling 3-month OTP average.
with otp_by_daytype as (
    select
        line_name,
        period,
        period_year,
        period_month,
        avg(case when day_type = 1 then otp_pct end) as weekday_otp_pct,
        avg(case when day_type = 2 then otp_pct end) as weekend_otp_pct,
        avg(otp_pct) as overall_otp_pct
    from {{ ref('stg_terminal_otp') }}
    group by 1, 2, 3, 4
),

cjt_by_period as (
    select
        line_name,
        period,
        avg(case when time_period = 'peak' then cjt_pct end) as peak_cjt_pct,
        avg(case when time_period = 'offpeak' then cjt_pct end) as offpeak_cjt_pct
    from {{ ref('stg_customer_journey') }}
    group by 1, 2
)

select
    o.line_name,
    o.period,
    o.period_year,
    o.period_month,
    round(o.weekday_otp_pct, 2) as weekday_otp_pct,
    round(o.weekend_otp_pct, 2) as weekend_otp_pct,
    round(o.overall_otp_pct, 2) as overall_otp_pct,
    round(
        avg(o.overall_otp_pct) over (
            partition by o.line_name
            order by o.period
            rows between 2 preceding and current row
        ),
        2
    ) as rolling_3mo_otp_pct,
    round(c.peak_cjt_pct, 2) as peak_cjt_pct,
    round(c.offpeak_cjt_pct, 2) as offpeak_cjt_pct
from otp_by_daytype o
left join cjt_by_period c
    on o.line_name = c.line_name and o.period = c.period
