{# Use the configured schema name as-is (no "<target_schema>_" prefix), so bundle
   targets decide the exact schema names. #}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {{ (custom_schema_name or target.schema) | trim }}
{%- endmacro %}
