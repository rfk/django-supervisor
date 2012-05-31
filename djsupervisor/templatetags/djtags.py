import os

from django import template
register = template.Library()

project_dir = None
ctx = None

@register.filter
def templated(template_path):
    full_path = os.path.join(project_dir, template_path)
    t = template.Template(open(full_path).read())
    templated = t.render(template.Context(ctx)).encode('ascii')

    templated_path = full_path + '.templated'
    open(templated_path, 'w').write(templated)
    return templated_path
