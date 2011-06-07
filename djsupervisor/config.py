
import os

try:
    raise ImportError
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

from django import template
from django.conf import settings
from django.utils.importlib import import_module


def find_all_configs():
    """Generator yielding config file contents, in order.

    This function searches for supervisord config files within each of
    the installed apps as well as in the main project directory.  Each
    file is read, processed through the Django template system, and the
    resulting contents yielded as a string.
    """
    #  Find and load the containing project module.
    #  This is assumed to be the top-level package containing settings module.
    projmod = import_module(settings.SETTINGS_MODULE.split(".",1)[0])
    #  Get the path to our contrib directory.
    contribdir = os.path.join(os.path.dirname(__file__),"contrib")
    #  First we look for app-specific config files, in installed order.
    for appname in settings.INSTALLED_APPS:
        appmod = import_module(appname)
        if not hasattr(appmod,"__file__"):
            continue
        #  Look inside app managmenet directory
        appfile = os.path.join(os.path.dirname(appmod.__file__),
                               "management","supervisord.conf")
        if os.path.isfile(appfile):
            yield load_config_from_file(appfile,projmod,appmod)
        #  Look inside djsupervisor contrib directory
        appfile = os.path.join(contribdir,appname.replace(".",os.sep),
                               "supervisord.conf")
        if os.path.isfile(appfile):
            yield load_config_from_file(appfile,projmod,appmod)
    #  Then look for project-specific file.
    projfile = os.path.join(os.path.dirname(projmod.__file__),"supervisord.conf")
    if os.path.isfile(projfile):
        yield load_config_from_file(projfile,projmod,appmod)
    

def load_config_from_file(filename,proj,app):
    with open(filename,"r") as f:
        data = f.read()
    t = template.Template(data)    
    c = template.Context({
        "PROJECT_DIR": os.path.dirname(proj.__file__),
        "APP_DIR": None if app is None else os.path.dirname(app.__file__),
        "settings": settings,
        "environ": os.environ,
    })
    return t.render(c)
 

def get_merged_supervisord_config(**options):
    data = """
[supervisord]
nodaemon=true
"""
    for cfg in find_all_configs():
        data +=  cfg
    return StringIO(data)

