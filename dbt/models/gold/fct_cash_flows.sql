select transaction_id, account_id, transaction_date, flow_type, amount,
       case when flow_type in ('Contribution', 'Transfer In') then amount else -amount end as signed_amount
from {{ ref('src_cash_flows') }}
