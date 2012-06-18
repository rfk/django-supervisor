"""

djsupervisor.templatetags.djsupervisor_tags:  custom template tags
------------------------------------------------------------------

This module defines a custom template filter "templated" which can be used
to apply the djsupervisor templating logic to other config files in your
project.
"""

import os
import shutil

from django import template
register = template.Library()

import djsupervisor.config

current_context = None

@register.filter
def templated(template_path):
    # Interpret paths relative to the project directory.
    project_dir = current_context["PROJECT_DIR"]
    full_path = os.path.join(project_dir, template_path)
    templated_path = full_path + ".templated"
    # If the target file doesn't exist, we will copy over source file metadata.
    # Do so *after* writing the file, as the changed permissions might e.g.
    # affect our ability to write to it.
    created = not os.path.exists(templated_path)
    # Read and process the source file.
    with open(full_path, "r") as f:
        templated = djsupervisor.config.render_config(f.read(), current_context)
    # Write it out to the corresponding .templated file.
    with open(templated_path, "w") as f:
        f.write(templated)
    # Copy metadata if necessary.
    if created:
        try:
            info = os.stat(full_path)
            shutil.copystat(full_path, templated_path)
            os.chown(templated_path, info.st_uid, info.st_gid)
        except EnvironmentError:
            pass
    return templated_path
