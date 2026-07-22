{% for section, categories in sections.items() %}
{% for category, entries in categories.items() if entries %}
### {{ definitions[category]["name"] }}

{% for text, issues in entries.items() -%}
- {{ text }}{% if issues %} ({{ issues | join(", ") }}){% endif %}
{% endfor %}

{% endfor %}
{% endfor %}
