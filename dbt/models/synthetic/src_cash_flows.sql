-- Synthetic contributions, withdrawals and transfers.
select
  concat('T', lpad(cast(id as string), 8, '0'))                                         as transaction_id,
  concat('A', lpad(cast(pmod(xxhash64(id, 'acct'), 3000) + 1 as string), 6, '0'))        as account_id,
  date_add(date'2024-10-01', cast(pmod(xxhash64(id, 'd'), 730) as int))                 as transaction_date,
  element_at(array('Contribution','Contribution','Withdrawal','Withdrawal','Transfer In','Transfer Out'),
             cast(pmod(xxhash64(id, 'f'), 6) as int) + 1)                               as flow_type,
  round(100 + pmod(xxhash64(id, 'amt'), 40000) / 1.0, 2)                               as amount
from range(1, 60001) as t(id)
