{#
    Override dbt's default schema naming. By default dbt prefixes the target
    schema (e.g. "raw_staging"). We want models to land in the bare dataset
    named by each model's +schema config ("staging", "marts"), so custom
    schemas are used as-is.
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
