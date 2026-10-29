-- Synthetic month-end holdings: ~6 securities per open account over 24 month-ends.
with months as (
  select last_day(add_months(date'2024-10-01', m)) as month_end_date
  from range(0, 24) as t(m)
),
positions as (
  select a.account_id, a.open_date, s.security_code, s.asset_class, s.base_price,
         xxhash64(a.account_id, s.security_code) as seed
  from {{ ref('src_accounts') }} a
  cross join {{ ref('src_securities') }} s
  where pmod(xxhash64(a.account_id, s.security_code), 13) = 0
)
select
  m.month_end_date,
  p.account_id,
  p.security_code,
  round(10 + pmod(p.seed, 2000) * (1 + datediff(m.month_end_date, date'2024-10-31') / 1500.0), 2) as units,
  case when p.asset_class = 'Cash' then 1.0
       else round(p.base_price * (1 + 0.004 * months_between(m.month_end_date, date'2024-10-31')
                  + (pmod(xxhash64(p.security_code, m.month_end_date), 200) - 100) / 2500.0), 4) end as unit_price
from positions p
join months m on m.month_end_date >= p.open_date
