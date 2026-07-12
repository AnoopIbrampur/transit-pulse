-- Station dimension: one row per GTFS stop, with a normalized borough name and
-- the first daytime route (used to map stations onto lines for the map).
with source as (
    select * from {{ source('raw', 'stations') }}
),

deduped as (
    select
        *,
        row_number() over (
            partition by gtfs_stop_id
            order by _loaded_at desc
        ) as _rn
    from source
    where gtfs_latitude is not null and gtfs_longitude is not null
)

select
    gtfs_stop_id,
    station_id,
    complex_id,
    division,
    stop_name,
    borough                                 as borough_code,
    case borough
        when 'M' then 'Manhattan'
        when 'Bk' then 'Brooklyn'
        when 'Bx' then 'Bronx'
        when 'Q' then 'Queens'
        when 'SI' then 'Staten Island'
        else borough
    end                                     as borough,
    daytime_routes,
    -- primary_route: first space-separated route, used to color the map by line
    split(daytime_routes, ' ')[safe_offset(0)] as primary_route,
    structure,
    gtfs_latitude                           as latitude,
    gtfs_longitude                          as longitude,
    safe_cast(ada as int64)                 as ada
from deduped
where _rn = 1
