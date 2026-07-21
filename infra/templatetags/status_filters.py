# # infra/templatetags/status_filters.py

# from django import template

# register = template.Library()

# STATUS_DICT = {
#     0: "Invalid",
#     1: "Over Value",
#     2: "Stoploss",
#     3: "Completed",
#     4: "New",
#     5: "Update",
#     6: "Entry",
#     7: "Confirmation",
#     8: "Order",
#     9: "Target 1",
#     10: "Target 2",
#     11: "Target 3",
#     12: "Above T3",
#     13: "Altra",
# }


# @register.simple_tag
# def status_list(output_type="keys"):
#     """
#     Usage: {% status_list 'options' %}
#     Options:
#         'options' -> returns HTML select <option>
#         'list'    -> returns HTML unordered <ul>
#         'keys'    -> returns only keys list
#     """
#     if output_type == "options":

#         items = "".join(
#             [f'<option value="{k}">{v}</option>' for k, v in STATUS_DICT.items()]
#         )
#         return f"<select>{items}</select>"

#     elif output_type == "list":
#         items = "".join([f"<li>{k} - {v}</li>" for k, v in STATUS_DICT.items()])
#         return f"<ul>{items}</ul>"

#     elif output_type == "keys":
#         return list(STATUS_DICT.keys())

#     return ""

# infra/templatetags/status_filters.py
from django import template
from django.utils.safestring import mark_safe
from django.utils.html import format_html_join, format_html

register = template.Library()

STATUS = [
    (0, "Invalid"),
    (1, "Over Value"),
    (2, "Stoploss"),
    (3, "Completed"),
    (4, "New"),
    (5, "Update"),
    (6, "Entry"),
    (7, "Confirmation"),
    (8, "Order"),
    (9, "Target 1"),
    (10, "Target 2"),
    (11, "Target 3"),
    (12, "Above T3"),
    (13, "Altra"),
]

@register.simple_tag
def status_list(output_type="keys"):
    if output_type == "options":
        return format_html_join(
            "\n",
            '<option value="{}">{}</option>',
            STATUS,
        )
    elif output_type == "list":
        lis = format_html_join("\n", "<li>{} - {}</li>", STATUS)
        return mark_safe(f"<ul>\n{lis}\n</ul>")
    elif output_type == "keys":
        return [k for k, _ in STATUS]
    return ""
