select account_id, account_type, product, state, open_date, status
from {{ ref('src_accounts') }}
