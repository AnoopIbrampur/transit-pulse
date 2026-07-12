-- Terminal on-time performance, cleaned and deduplicated on (line, month, day_type).
-- OTP arrives as a 0-1 fraction; expose both the fraction and a 0-100 percentage.
with source as (
    select * from {{ source('raw', 'terminal_otp') }}
),

deduped as (
    select
        *,
        row_number() over (
            partition by line, month, day_type
            order by _loaded_at desc
        ) as _rn
    from source
    where terminal_on_time_performance is not null
)

select
    line                                    as line_name,
    division,
    month                                   as period,
    extract(year from month)                as period_year,
    extract(month from month)               as period_month,
    -- day_type: 1 = weekday, 2 = weekend (MTA convention)
    day_type,
    case when day_type = 1 then 'weekday' else 'weekend' end as day_type_label,
    num_on_time_trips,
    num_sched_trips,
    terminal_on_time_performance            as otp_fraction,
    round(terminal_on_time_performance * 100, 2) as otp_pct
from deduped
where _rn = 1
