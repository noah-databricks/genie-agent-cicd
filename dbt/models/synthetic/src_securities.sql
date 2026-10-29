-- Synthetic security master.
with base as (
  select id,
    element_at(array('Australian Equities','International Equities','Fixed Income','Cash',
                     'Property','Managed Funds','ETFs'),
               cast(pmod(id, 7) as int) + 1) as asset_class
  from range(1, 81) as t(id)
)
select
  concat(upper(substr(replace(asset_class, ' ', ''), 1, 3)), lpad(cast(id as string), 3, '0')) as security_code,
  concat(asset_class, ' Holding ', id)                                                       as security_name,
  asset_class,
  case when asset_class = 'Cash' then 1.0
       else round(5 + pmod(xxhash64(id, 'px'), 9500) / 100.0, 4) end                       as base_price
from base
