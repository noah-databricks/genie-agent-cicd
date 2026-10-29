{{ config(materialized='metric_view') }}

version: 1.1
comment: Monthly platform fee revenue for the Portfolio Reporting agent.
source: {{ ref('fct_fees') }}
joins:
  - name: account
    source: {{ ref('dim_account') }}
    on: source.account_id = account.account_id
dimensions:
  - name: Month End
    expr: source.month_end_date
  - name: Fee Type
    expr: source.fee_type
  - name: Account Type
    expr: account.account_type
  - name: Product
    expr: account.product
measures:
  - name: Fee Revenue
    expr: SUM(source.fee_amount)
    synonyms: [fees, revenue, platform fees]
