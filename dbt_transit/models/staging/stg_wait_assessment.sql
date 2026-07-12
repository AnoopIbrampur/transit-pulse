-- Wait assessment (share of timepoints meeting headway targets), deduplicated
-- on (line, month, day_type, period). wait_assessment is a 0-1 fraction.
with source as (
    select * from {{ source('raw', 'wait_assessment') }}
),

deduped as (
    select
        *,
        row_number() over (
            partition by line, month, day_type, period
            order by _loaded_at desc
        ) as _rn
    from source
    where wait_assessment is not null
)

select
    line                                    as line_name,
    division,
    month                                   as period,
    extract(year from month)                as period_year,
    extract(month from month)               as period_month,
    day_type,
    case when day_type = 1 then 'weekday' else 'weekend' end as day_type_label,
    period                                  as time_period,
    num_timepoints_passing_wait_assessment,
    num_sched_timepoints,
    wait_assessment                         as wait_assessment_fraction,
    round(wait_assessment * 100, 2)         as wait_assessment_pct
from deduped
where _rn = 1
