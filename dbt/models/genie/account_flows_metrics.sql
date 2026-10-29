{{ config(materialized='metric_view') }}

version: 1.1
comment: Contributions, withdrawals and transfers for the Portfolio Reporting agent. Flows are additive over time.
source: {{ ref('fct_cash_flows') }}
joins:
  - name: account
    source: {{ ref('dim_account') }}
    on: source.account_id = account.account_id
dimensions:
  - name: Transaction Month
    expr: DATE_TRUNC('MONTH', source.transaction_date)
  - name: Transaction Date
    expr: source.transaction_date
  - name: Flow Type
    expr: source.flow_type
  - name: Account Type
    expr: account.account_type
  - name: Product
    expr: account.product
  - name: State
    expr: account.state
measures:
  - name: Net Flows
    expr: SUM(source.signed_amount)
    comment: Inflows minus outflows in AUD.
    synonyms: [net flow, net inflows]
  - name: Gross Inflows
    expr: SUM(source.amount) FILTER (WHERE source.flow_type IN ('Contribution', 'Transfer In'))
  - name: Gross Outflows
    expr: SUM(source.amount) FILTER (WHERE source.flow_type IN ('Withdrawal', 'Transfer Out'))
  - name: Transaction Count
    expr: COUNT(1)
