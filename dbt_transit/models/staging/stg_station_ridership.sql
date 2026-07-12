-- Monthly ridership by station complex, deduplicated on (station_complex_id, month).
with source as (
    select * from {{ source('raw', 'station_ridership') }}
),

deduped as (
    select
        *,
        row_number() over (
            partition by station_complex_id, month
            order by _loaded_at desc
        ) as _rn
    from source
    where ridership is not null
)

select
    station_complex_id,
    station_complex,
    borough,
    month                                   as period,
    extract(year from month)                as period_year,
    extract(month from month)               as period_month,
    ridership,
    transfers,
    latitude,
    longitude
from deduped
where _rn = 1
