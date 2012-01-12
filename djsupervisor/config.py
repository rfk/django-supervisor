"""

djsupervisor.config:  config loading and merging code for djsupervisor
----------------------------------------------------------------------

The code in this module is responsible for finding the supervisord.conf
files from all installed apps, merging them together with the config
files from your project and any options specified on the command-line,
and producing a final config file to control supervisord/supervisorctl.

"""

import sys
import os
import hashlib

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

from ConfigParser import RawConfigParser, NoSectionError, NoOptionError

from django import template
from django.conf import settings
from django.utils.importlib import import_module
 

CONFIG_FILE_NAME = "supervisord.conf"


def get_merged_config(**options):
    """Get the final merged configuration for supvervisord, as a string.

    This is the top-level function exported by this module.  It collects
    the various config files from installed applications and the main project,
    combines them together based on priority, and returns the resulting
    configuration as a string.
    """
    #  Find and load the containing project module.
    #  This can be specified explicity using the --project-dir option.
    #  Otherwise, we attempt to guess by looking for the manage.py file.
    project_dir = options.get("project_dir")
    if project_dir is None:
        project_dir = guess_project_dir()
    #  Build the default template context variables.
    #  This is mostly useful information about the project and environment.
    ctx = {
        "PROJECT_DIR": project_dir,
        "PYTHON": os.path.realpath(os.path.abspath(sys.executable)),
        "SUPERVISOR_OPTIONS": rerender_options(options),
        "settings": settings,
        "environ": os.environ,
    }
    #  Initialise the ConfigParser.
    #  Fortunately for us, ConfigParser has merge-multiple-config-files
    #  functionality built into it.  You just read each file in turn, and
    #  values from later files overwrite values from former.
    cfg = RawConfigParser()
    #  Start from the default configuration options.
    data = render_config(DEFAULT_CONFIG,ctx)
    cfg.readfp(StringIO(data))
    #  Add in each app-specific file in turn.
    for data in find_app_configs(ctx):
        cfg.readfp(StringIO(data))
    #  Add in the project-specific config file.
    projcfg = os.path.join(project_dir,CONFIG_FILE_NAME)
    if os.path.isfile(projcfg):
        with open(projcfg,"r") as f:
            data = render_config(f.read(),ctx)
        cfg.readfp(StringIO(data))
    #  Add in the options specified on the command-line.
    cfg.readfp(StringIO(get_config_from_options(**options)))
    #  Add options from [program:__defaults__] to each program section
    #  if it happens to be missing that option.
    PROG_DEFAULTS = "program:__defaults__"
    if cfg.has_section(PROG_DEFAULTS):
        for option in cfg.options(PROG_DEFAULTS):
            default = cfg.get(PROG_DEFAULTS,option)
            for section in cfg.sections():
                if section.startswith("program:"):
                    if not cfg.has_option(section,option):
                        cfg.set(section,option,default)
        cfg.remove_section(PROG_DEFAULTS)
    #  Add options from [program:__overrides__] to each program section
    #  regardless of whether they already have that option.
    PROG_OVERRIDES = "program:__overrides__"
    if cfg.has_section(PROG_OVERRIDES):
        for option in cfg.options(PROG_OVERRIDES):
            override = cfg.get(PROG_OVERRIDES,option)
            for section in cfg.sections():
                if section.startswith("program:"):
                    cfg.set(section,option,override)
        cfg.remove_section(PROG_OVERRIDES)
    #  Make sure we've got a port configured for supervisorctl to
    #  talk to supervisord.  It's passworded based on secret key.
    #  If they have configured a unix socket then use that, otherwise
    #  use an inet server on localhost at fixed-but-randomish port.
    username = hashlib.md5(settings.SECRET_KEY).hexdigest()[:7]
    password = hashlib.md5(username).hexdigest()
    if cfg.has_section("unix_http_server"):
        set_if_missing(cfg,"unix_http_server","username",username)
        set_if_missing(cfg,"unix_http_server","password",password)
        serverurl = "unix://" + cfg.get("unix_http_server","file")
    else:
        #  This picks a "random" port in the 9000 range to listen on.
        #  It's derived from the secret key, so it's stable for a given
        #  project but multiple projects are unlikely to collide.
        port = int(hashlib.md5(password).hexdigest()[:3],16) % 1000
        addr = "127.0.0.1:9%03d" % (port,)
        set_if_missing(cfg,"inet_http_server","port",addr)
        set_if_missing(cfg,"inet_http_server","username",username)
        set_if_missing(cfg,"inet_http_server","password",password)
        serverurl = "http://" + cfg.get("inet_http_server","port")
    set_if_missing(cfg,"supervisorctl","serverurl",serverurl)
    set_if_missing(cfg,"supervisorctl","username",username)
    set_if_missing(cfg,"supervisorctl","password",password)
    set_if_missing(cfg,"rpcinterface:supervisor",
                       "supervisor.rpcinterface_factory",
                       "supervisor.rpcinterface:make_main_rpcinterface")
    #  Remove any [program:] sections with exclude=true
    for section in cfg.sections():
        try:
            if cfg.getboolean(section,"exclude"):
                cfg.remove_section(section)
        except NoOptionError:
            pass
    #  Sanity-check to give better error messages.
    for section in cfg.sections():
        if section.startswith("program:"):
            if not cfg.has_option(section,"command"):
                msg = "Process name '%s' has no command configured"
                raise ValueError(msg % (section.split(":",1)[-1]))
    #  Write it out to a StringIO and return the data
    s = StringIO()
    cfg.write(s)
    return s.getvalue()


def render_config(data,ctx):
    """Render the given config data using Django's template system.

    This function takes a config data string and a dict of context variables,
    renders the data through Django's template system, and returns the result.
    """
    t = template.Template(data)
    c = template.Context(ctx)
    return t.render(c).encode("ascii")


def find_app_configs(ctx):
    """Generator yielding app-provided config file data.

    This function searches for supervisord config files within each of the
    installed apps, in the order they are listed in INSTALLED_APPS.  Each
    file found is rendered and the resulting contents yielded as a string.

    If the app ships with a management/supervisord.conf file, then that file
    is used.  Otherwise, we look for one under the djsupervisor "contrib"
    directory.  Only one of the two files is used, to prevent us from 
    clobbering settings specified by app authors.
    """
    contrib_dir = os.path.join(os.path.dirname(__file__),"contrib")
    for appname in settings.INSTALLED_APPS:
        appfile = None
        #  Look first in the application directory.
        appmod = import_module(appname)
        try:
            appdir = os.path.dirname(appmod.__file__)
        except AttributeError:
            pass
        else:
            appfile = os.path.join(appdir,"management",CONFIG_FILE_NAME)
            if not os.path.isfile(appfile):
                appfile = None
        #  If that didn't work, try the djsupervisor contrib directory
        if appfile is None:
            appdir = os.path.join(contrib_dir,appname.replace(".",os.sep))
            appfile = os.path.join(appdir,CONFIG_FILE_NAME)
            if not os.path.isfile(appfile):
                appfile = None
        #  If we found one, render and yield it.
        if appfile is not None:
            #  Add extra context info about the application.
            app_ctx = {
                "APP_DIR": os.path.dirname(appmod.__file__),
            }
            app_ctx.update(ctx)
            with open(appfile,"r") as f:
                yield render_config(f.read(),app_ctx)


def get_config_from_options(**options):
    """Get config file fragment reflecting command-line options."""
    data = []
    #  Set whether or not to daemonize.
    #  Unlike supervisord, our default is to stay in the foreground.
    data.append("[supervisord]\n")
    if options.get("daemonize",False):
        data.append("nodaemon=false\n")
    else:
        data.append("nodaemon=true\n")
    if options.get("pidfile",None):
        data.append("pidfile=%s\n" % (options["pidfile"],))
    if options.get("logfile",None):
        data.append("logfile=%s\n" % (options["logfile"],))
    #  Set which programs to launch automatically on startup.
    for progname in options.get("launch",None) or []:
        data.append("[program:%s]\nautostart=true\n" % (progname,))
    for progname in options.get("nolaunch",None) or []:
        data.append("[program:%s]\nautostart=false\n" % (progname,))
    #  Set which programs to include/exclude from the config
    for progname in options.get("include",None) or []:
        data.append("[program:%s]\nexclude=false\n" % (progname,))
    for progname in options.get("exclude",None) or []:
        data.append("[program:%s]\nexclude=true\n" % (progname,))
    #  Set which programs to autoreload when code changes.
    #  When this option is specified, the default for all other
    #  programs becomes autoreload=false.
    if options.get("autoreload",None):
        data.append("[program:autoreload]\nexclude=false\nautostart=true\n")
        data.append("[program:__defaults__]\nautoreload=false\n")
        for progname in options["autoreload"]:
            data.append("[program:%s]\nautoreload=true\n" % (progname,))
    #  Set whether to use the autoreloader at all.
    if options.get("noreload",False):
        data.append("[program:autoreload]\nexclude=true\n")
    return "".join(data)


def guess_project_dir():
    """Find the top-level Django project directory.

    This function guesses the top-level Django project directory based on
    the current environment.  It looks for module containing the currently-
    active settings module, in both pre-1.4 and post-1.4 layours.
    """
    projname = settings.SETTINGS_MODULE.split(".",1)[0]
    projmod = import_module(projname)
    projdir = os.path.dirname(projmod.__file__)

    # For Django 1.3 and earlier, the manage.py file was located
    # in the same directory as the settings file.
    if os.path.isfile(os.path.join(projdir,"manage.py")):
        return projdir

    # For Django 1.4 and later, the manage.py file is located in
    # the directory *containing* the settings file.
    projdir = os.path.abspath(os.path.join(projdir, os.path.pardir))
    if os.path.isfile(os.path.join(projdir,"manage.py")):
        return projdir

    msg = "Unable to determine the Django project directory;"\
          " use --project-dir to specify it"
    raise RuntimeError(msg)


def set_if_missing(cfg,section,option,value):
    """If the given option is missing, set to the given value."""
    try:
        cfg.get(section,option)
    except NoSectionError:
        cfg.add_section(section)
        cfg.set(section,option,value)
    except NoOptionError:
        cfg.set(section,option,value)


def rerender_options(options):
    """Helper function to re-render command-line options.

    This assumes that command-line options use the same name as their
    key in the options dictionary.
    """
    args = []
    for name,value in options.iteritems():
        name = name.replace("_","-")
        if value is None:
            pass
        elif isinstance(value,bool):
            if value:
                args.append("--%s" % (name,))
        elif isinstance(value,list):
            for item in value:
                args.append("--%s=%s" % (name,item))
        else:
            args.append("--%s=%s" % (name,value))
    return " ".join(args)


#  These are the default configuration options provided by djsupervisor.
#
DEFAULT_CONFIG = """

;  We always provide the 'runserver' process to run the dev server.
[program:runserver]
command={{ PYTHON }} {{ PROJECT_DIR }}/manage.py runserver --noreload

;  In debug mode, we watch for changes in the project directory and inside
;  any installed apps.  When something changes, restart all processes.
[program:autoreload]
command={{ PYTHON }} {{ PROJECT_DIR }}/manage.py supervisor {{ SUPERVISOR_OPTIONS }} autoreload
autoreload=true
{% if not settings.DEBUG %}
exclude=true
{% endif %}

;  All programs are auto-reloaded by default.
[program:__defaults__]
autoreload=true
redirect_stderr=true

[supervisord]
{% if settings.DEBUG %}
loglevel=debug
{% endif %}


"""

