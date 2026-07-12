-- Trains delayed by line/month/day_type/cause, deduplicated on the full grain.
with source as (
    select * from {{ source('raw', 'trains_delayed') }}
),

deduped as (
    select
        *,
        row_number() over (
            partition by line, month, day_type, reporting_category
            order by _loaded_at desc
        ) as _rn
    from source
    where line is not null
)

select
    line                                    as line_name,
    division,
    month                                   as period,
    extract(year from month)                as period_year,
    extract(month from month)               as period_month,
    day_type,
    case when day_type = 1 then 'weekday' else 'weekend' end as day_type_label,
    reporting_category,
    coalesce(delays, 0)                     as delays
from deduped
where _rn = 1
