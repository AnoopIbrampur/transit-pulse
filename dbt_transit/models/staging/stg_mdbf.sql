-- Mean distance between failures, deduplicated on (car_class, month).
-- Grain is car class (NOT line); division (A/B) is the only link to lines.
with source as (
    select * from {{ source('raw', 'mdbf') }}
),

deduped as (
    select
        *,
        row_number() over (
            partition by car_class, month
            order by _loaded_at desc
        ) as _rn
    from source
    where mdbf is not null
)

select
    car_class,
    division,
    month                                   as period,
    extract(year from month)                as period_year,
    extract(month from month)               as period_month,
    total_miles,
    number_of_failures,
    number_of_cars,
    mdbf,
    _12_month_average_mdbf                  as mdbf_12mo_avg
from deduped
where _rn = 1
