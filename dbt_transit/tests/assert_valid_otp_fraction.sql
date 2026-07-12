-- On-time performance fractions must fall within [0, 1]. Any row outside that
-- range indicates a units bug (e.g. a 0-100 percentage leaking through).
select
    line_name,
    period,
    otp_fraction
from {{ ref('stg_terminal_otp') }}
where otp_fraction < 0 or otp_fraction > 1
