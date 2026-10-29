select month_end_date, account_id, security_code, units, unit_price,
       round(units * unit_price, 2) as market_value
from {{ ref('src_holdings_monthly') }}
