import os

from django import template
register = template.Library()

project_dir = None
ctx = None

@register.filter
def templated(template_path):
    if not template_path.endswith(".template"):
        raise Exception("templates must end with .template")

    full_path = os.path.join(project_dir, template_path)
    t = template.Template(open(full_path).read())
    c = template.Context(ctx)
    templated = t.render(c).encode('ascii')

    new_path = full_path.split(".template")[0]
    open(new_path, 'w').write(templated)
    return new_path
