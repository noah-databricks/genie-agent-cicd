-- Synthetic accounts (stand-in for platform gold data). Deterministic: same rows every run.
select
  concat('A', lpad(cast(id as string), 6, '0'))                                   as account_id,
  element_at(array('Individual','Joint','SMSF','Trust','Company','Super','Pension'),
             cast(pmod(xxhash64(id, 'type'), 7) as int) + 1)                     as account_type,
  element_at(array('Platform Choice','Platform Core','Platform Super'),
             cast(pmod(xxhash64(id, 'prod'), 3) as int) + 1)                     as product,
  element_at(array('NSW','VIC','QLD','WA','SA','TAS','ACT','NT'),
             cast(pmod(xxhash64(id, 'state'), 8) as int) + 1)                    as state,
  date_add(date'2018-01-01', cast(pmod(xxhash64(id, 'open'), 2900) as int))       as open_date,
  case when pmod(xxhash64(id, 'closed'), 25) = 0 then 'Closed' else 'Open' end     as status
from range(1, 3001) as t(id)
