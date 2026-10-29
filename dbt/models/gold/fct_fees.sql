select month_end_date, account_id, fee_type, fee_amount
from {{ ref('src_fees') }}
