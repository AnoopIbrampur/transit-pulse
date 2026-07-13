-- Ridership recovery by station complex. Compares recent ridership against the
-- 2019 pre-pandemic baseline to show which parts of the network came back and
-- which did not. Includes coordinates for the geospatial view.
with baseline as (
    -- Average monthly ridership in 2019 (last full pre-pandemic year).
    select
        station_complex_id,
        any_value(station_complex) as station_complex,
        any_value(borough) as borough,
        avg(ridership) as baseline_2019
    from {{ ref('stg_station_ridership') }}
    where period_year = 2019
    group by station_complex_id
),

recent as (
    -- Average monthly ridership over the trailing 12 months.
    select
        station_complex_id,
        avg(ridership) as recent_ridership,
        any_value(latitude) as latitude,
        any_value(longitude) as longitude
    from {{ ref('stg_station_ridership') }}
    where period >= date_sub(
        (select max(period) from {{ ref('stg_station_ridership') }}),
        interval 12 month
    )
    group by station_complex_id
)

select
    b.station_complex_id,
    b.station_complex,
    b.borough,
    r.latitude,
    r.longitude,
    round(b.baseline_2019, 0) as baseline_2019,
    round(r.recent_ridership, 0) as recent_ridership,
    round(safe_divide(r.recent_ridership, b.baseline_2019) * 100, 1) as recovery_pct,
    case
        when safe_divide(r.recent_ridership, b.baseline_2019) >= 1.0 then 'fully_recovered'
        when safe_divide(r.recent_ridership, b.baseline_2019) >= 0.85 then 'nearly_recovered'
        when safe_divide(r.recent_ridership, b.baseline_2019) >= 0.70 then 'lagging'
        else 'depressed'
    end as recovery_tier
from baseline b
join recent r using (station_complex_id)
where b.baseline_2019 > 0
