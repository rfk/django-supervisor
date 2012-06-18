"""

djsupervisor.templatetags.djsupervisor_tags:  custom template tags
------------------------------------------------------------------

This module defines a custom template filter "templated" which can be used
to apply the djsupervisor templating logic to other config files in your
project.
"""

import os

from django import template
register = template.Library()

import djsupervisor.config

current_context = None

@register.filter
def templated(template_path):
    # Interpret paths relative to the project directory.
    project_dir = current_context["PROJECT_DIR"]
    full_path = os.path.join(project_dir, template_path)
    # Read and process the source file.
    with open(full_path, "r") as f:
        templated = djsupervisor.config.render_config(f.read(), current_context)
    # Write it out to the corresponding .templated file.
    templated_path = full_path + ".templated"
    with open(templated_path, "w") as f:
        f.write(templated)
    return templated_path
