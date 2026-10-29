{{ config(materialized='metric_view') }}

version: 1.1
comment: >-
  Month-end portfolio holdings for the Portfolio Reporting agent. Funds under
  administration (FUA) is a point-in-time balance: always filter or group by Month End.
source: {{ ref('fct_holdings_monthly') }}
joins:
  - name: account
    source: {{ ref('dim_account') }}
    on: source.account_id = account.account_id
  - name: security
    source: {{ ref('dim_security') }}
    on: source.security_code = security.security_code
dimensions:
  - name: Month End
    expr: source.month_end_date
    comment: Month-end reporting date.
  - name: Account Type
    expr: account.account_type
    synonyms: [account structure, entity type]
  - name: Product
    expr: account.product
  - name: State
    expr: account.state
  - name: Account Status
    expr: account.status
  - name: Asset Class
    expr: security.asset_class
    synonyms: [sector, investment type]
  - name: Security
    expr: security.security_name
measures:
  - name: Funds Under Administration
    expr: SUM(source.market_value)
    comment: Total market value in AUD. Point-in-time, so do not sum across months.
    synonyms: [FUA, FUM, balance, assets]
  - name: Account Count
    expr: COUNT(DISTINCT source.account_id)
  - name: Average Account Balance
    expr: SUM(source.market_value) / COUNT(DISTINCT source.account_id)
    synonyms: [average balance]
