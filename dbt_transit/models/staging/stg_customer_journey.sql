-- Customer journey-focused metrics, deduplicated on (line, month, period).
-- customer_journey_time is a 0-1 fraction (share of journeys within expected time).
with source as (
    select * from {{ source('raw', 'customer_journey') }}
),

deduped as (
    select
        *,
        row_number() over (
            partition by line, month, period
            order by _loaded_at desc
        ) as _rn
    from source
    where customer_journey_time is not null
)

select
    line                                    as line_name,
    division,
    month                                   as period,
    extract(year from month)                as period_year,
    extract(month from month)               as period_month,
    -- period is 'peak' or 'offpeak'
    period                                  as time_period,
    num_passengers,
    additional_platform_time,
    additional_train_time,
    total_apt,
    total_att,
    over_five_mins,
    over_five_mins_perc,
    customer_journey_time                   as cjt_fraction,
    round(customer_journey_time * 100, 2)   as cjt_pct
from deduped
where _rn = 1
