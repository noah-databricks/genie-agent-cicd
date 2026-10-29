select security_code, security_name, asset_class
from {{ ref('src_securities') }}
