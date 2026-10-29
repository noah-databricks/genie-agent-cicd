-- Synthetic monthly fees per account.
select
  h.month_end_date,
  h.account_id,
  f.fee_type,
  round(sum(h.units * h.unit_price) * f.rate / 12, 2) as fee_amount
from {{ ref('src_holdings_monthly') }} h
cross join (select 'Administration' as fee_type, 0.0025 as rate
            union all select 'Investment', 0.0010) f
group by h.month_end_date, h.account_id, f.fee_type, f.rate
