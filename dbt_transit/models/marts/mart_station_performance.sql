-- Station-level performance feed for the Folium map. Each station carries its
-- coordinates, its primary line's most-recent weekday OTP (and reliability
-- tier), and recent monthly ridership for marker sizing.
--
-- Joins:
--   stations.primary_route  -> line OTP (latest weekday month per line)
--   stations.complex_id     -> station_ridership.station_complex_id (avg last 12 mo)
with latest_otp_month as (
    select max(period) as max_period from {{ ref('stg_terminal_otp') }}
),

line_otp as (
    -- Most recent weekday OTP per line.
    select
        line_name,
        otp_fraction,
        otp_pct
    from {{ ref('stg_terminal_otp') }}
    where day_type = 1
      and period = (select max_period from latest_otp_month)
),

recent_ridership as (
    -- Average monthly ridership over the trailing 12 months, per complex.
    select
        station_complex_id,
        avg(ridership) as avg_monthly_ridership
    from {{ ref('stg_station_ridership') }}
    where period >= date_sub(
        (select max(period) from {{ ref('stg_station_ridership') }}),
        interval 12 month
    )
    group by 1
)

select
    s.gtfs_stop_id,
    s.stop_name,
    s.borough,
    s.division,
    s.primary_route,
    s.daytime_routes,
    s.latitude,
    s.longitude,
    s.ada,
    o.otp_fraction,
    o.otp_pct,
    case
        when o.otp_pct is null then 'unknown'
        when o.otp_pct >= 90 then 'reliable'
        when o.otp_pct >= 80 then 'at_risk'
        else 'poor'
    end as reliability_tier,
    r.avg_monthly_ridership
from {{ ref('stg_stations') }} s
left join line_otp o
    on s.primary_route = o.line_name
left join recent_ridership r
    on cast(s.complex_id as string) = r.station_complex_id
