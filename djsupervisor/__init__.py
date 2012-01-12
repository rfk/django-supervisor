"""

djsupervisor:  easy integration between django and supervisord
==============================================================


Django-supervisor combines the process-management awesomeness of supervisord
with the convenience of Django's management scripts.


Rationale
---------

Running a Django project these days often entails much more than just starting
up a webserver.  You might need to have Django running under FCGI or CherryPy,
with background tasks being managed by celeryd, periodic tasks scheduled by
celerybeat, and any number of other processes all cooperating to keep the
project up and running.

When you're just developing or debugging, it's a pain having to start and
stop all these different processes by hand.

When you're deploying, it's a pain to make sure that each process is hooked
into the system startup scripts with the correct configuration.

Django-supervisor provides a convenient bridge between your Django project
and the supervisord process control system.  It makes starting all the
processes required by your project as simple as::

    $ python myproject/manage.py supervisor


Advantages
----------

Django-supervisor is admittedly quite a thin layer on top of the wonderful
functionality provided by supervisord.  But by integrating tightly with
Django's management scripts you gain several advantages:

    * manage.py remains the single point of control for running your project.
    * Running all those processes is just as easy in development as it
      is in production.
    * You get auto-reloading for *all* processes when running in debug mode.
    * Process configuration can depend on Django settings and environment
      variables, and have paths relative to your project and/or apps.
    * Apps can provide default process configurations, which projects can
      then tweak or override as needed.



Configuration
-------------

Django-supervisor is a wrapper around supervisord, so it uses the same
configuration file format.  Basically, you write an ini-style config file
where each section defines a process to be launched.  Some examples can be
found below, but you'll want to refer to the supervisord docs for all the
finer details:

    http://www.supervisord.org


To get started, just include "djsupervisor" in your INSTALLED_APPS and drop
a "supervisord.conf" file in your project directory, right next to the main
manage.py script.

A simple example config might run both the Django development server and the
Celery task daemon::

    [program:webserver]
    command={{ PYTHON }} {{ PROJECT_DIR }}/manage.py runserver --noreload
 
    [program:celeryd]
    command={{ PYTHON }} {{ PROJECT_DIR }}/manage.py celeryd -l info


Now when you run the "supervisor" management command, it will detect this
file and start the two processes for you.

Notice that the config file is interpreted using Django's templating engine.
This lets you do fun things like locate files relative to the project root
directory.

Better yet, you can make parts of the config conditional based on project
settings or on the environment.  For example, you might start the development
server when debugging but run under FCGI in production::

    [program:webserver]
    {% if settings.DEBUG %}
    command={{ PYTHON }} {{ PROJECT_DIR }}/manage.py runserver
    {% else %}
    command={{ PYTHON }} {{ PROJECT_DIR }}/manage.py runfcgi host=127.0.0.1 port=8025
    {% endif %}
 

For more flexibility, django-supervisor also supports per-application config
files.  For each application in INSTALLED_APPS, it will search for config
files in the following locations:

   * <app directory>/management/supervisord.conf
   * djsupervisor/contrib/<app name>/supervisord.conf

Any files so found will be merged together, and then merged with your project
configuration to produce the final supervisord config.  This allows you to
include basic process management definitions as part of a reusable Django
application, and tweak or override them on a per-project basis.


Usage
-----

Django-supervisor provides a new Django manangement command named "supervisor"
which allows you to control all of the processes belonging to your project.

When run without arguments, it will spawn supervisord to launch and monitor
all the configured processs.  Here's some example output using the config
file shown in the previous section::

    $ python myproject/manage.py supervisor
    2011-06-07 23:46:45,253 INFO RPC interface 'supervisor' initialized
    2011-06-07 23:46:45,253 INFO supervisord started with pid 4787
    2011-06-07 23:46:46,258 INFO spawned: 'celeryd' with pid 4799
    2011-06-07 23:46:46,275 INFO spawned: 'webserver' with pid 4801
    2011-06-07 23:46:47,456 INFO success: webserver entered RUNNING state, process has stayed up for > than 1 seconds (startsecs)
    2011-06-07 23:46:56,512 INFO success: celeryd entered RUNNING state, process has stayed up for > than 10 seconds (startsecs)

By default the "supervisor" command will stay in the foreground and print
status updates to the console.  Pass the --daemonize option to have it 
run in the background.  You can also tweak its behaviour using all of
supervisord's standard options in the config file.

Once the supervisor is up and running, you can interact with it to control the
running processes.  Running "manage.py supervisor shell" will launch the
interactive supervisorctl command shell.  From here you can view process
status and start/stop/restart individual processes::

    $ python myproject/manage.py supervisor shell
    celeryd                          RUNNING    pid 4799, uptime 0:03:17
    webserver                        RUNNING    pid 4801, uptime 0:03:17
    supervisor> 
    supervisor> help

    default commands (type help <topic>):
    =====================================
    add   clear fg       open quit   remove restart  start  stop update 
    avail exit  maintail pid  reload reread shutdown status tail version

    supervisor> 
    supervisor> stop celeryd
    celeryd: stopped
    supervisor> 
    supervisor> status
    celeryd                          STOPPED    Jun 07 11:51 PM
    webserver                        RUNNING    pid 4801, uptime 0:04:45
    supervisor> 


You can also issue individual process-manangement commands directly on the 
command-line::

    $ python myproject/manage.py supervisor start celeryd
    celeryd: started
    $
    $ python myproject/manage.py supervisor status
    celeryd                          RUNNING    pid 4937, uptime 0:00:55
    webserver                        RUNNING    pid 4801, uptime 0:09:05
    $
    $ python myproject/manage.py supervisor shutdown
    Shut down
    $


For details of all the available management commands, consult the supervisord
documentation.


Command-Line Options
~~~~~~~~~~~~~~~~~~~~

The "supervisor" command accepts the following options:

  --daemonize             run the supervisord process in the background
  --pidfile               store PID of supervisord process in this file
  --loggile               write supervisord logs to this file
  --project-dir           use this as the django project directory
  --launch=program        launch program automatically at supervisor startup
  --nolaunch=program      don't launch program automatically at startup
  --exclude=program       remove program from the supervisord config
  --include=program       include program in the supervisord config
  --autoreload=program    restart program when code files change
  --noreload              don't restart programs when code files change


Extra Goodies
-------------

Django-supervisor provides some extra niceties on top of the configuration
language of supervisord.


Templating
~~~~~~~~~~

All supervisord.conf files are rendered through Django's templating system.
This allows you to interpolate values from the settings or environment, and
conditionally switch processes on or off.  The template context for each
configuration file contains the following variables::

    PROJECT_DIR          the top-level directory of your project (i.e. the
                         directory containing your manage.py script).

    APP_DIR              for app-provided config files, the top-level
                         directory containing the application code.

    PYTHON               full path to the current python interpreter.

    SUPERVISOR_OPTIONS   the command-line options passed to manage.py. 
 
    settings             the Django settings module, as seen by your code.

    environ              the os.environ dict, as seen by your code.



Defaults, Overrides and Excludes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Django-supervisor recognises some special config-file options that are useful
when merging multiple app-specific and project-specific configuration files.

The [program:__defaults__] section can be used to provide default options
for all other [program] sections.  These options will only be used if none
of the config files found by django-supervisor provide that option for
a specific program.

The [program:__overrides__] section can be used to override options for all
configured programs.  These options will be applied to all processes regardless
of what any other config file has to say.

Finally, you can completely disable a [program] section by setting the option
"exclude" to true.  This is mostly useful for disabling process definitions
provided by a third-party application.

Here's an example config file that shows them all in action::

    ; We want all programs to redirect stderr by default,
    ; unless specifically configured otherwise.
    [program:__defaults__]
    redirect_stderr=true

    ; We force all programs to run as user "nobody"
    [program:__overrides__]
    user=nobody

    ; Django-supervisord ships with a default configuration for celerybeat.
    ; We don't use it, so remove it from the config.
    [program:celerybeat]
    exclude=true



Automatic Control Socket Config
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The supervisord and supervisorctl programs interact with each other via an
XML-RPC control socket.  This provides a great deal of flexibility and control
over security, but you have to configure it just so or things won't work.

For convenience during development, django-supervisor provides automatic
control socket configuration.  By default it binds the server to localhost
on a fixed-but-randomish port, and sets up a username and password based on
settings.SECRET_KEY.

For production deployment, you might like to reconfigure this by setting up
the [inet_http_server] or [unix_http_server] sections.  Django-supervisor
will honour any such settings you provide.



Autoreload
~~~~~~~~~~

When running in debug mode, django-supervisor automatically defines a process
named "autoreload".  This is very similar to the auto-reloading feature of
the Django development server, but works across all configured processes.
For example, this will let you automatically restart both the dev server and
celeryd whenever your code changes.

To prevent an individual program from being auto-reloaded, set its "autoreload"
option to false::

    [program:non-python-related]
    autoreload=false

To switch off the autoreload process entirely, you can pass the --noreload 
option to supervisor or just exclude it in your project config file like so::

    [program:autoreload]
    exclude=true



More Info
---------

There aren't any more docs online yet.  Sorry.  I'm working on a little tutorial
and some examples, but I need to actually *use* the project a little more
first to make sure it all fits together the way I want...

"""

__ver_major__ = 0
__ver_minor__ = 2
__ver_patch__ = 4
__ver_sub__ = ""
__version__ = "%d.%d.%d%s" % (__ver_major__,__ver_minor__,__ver_patch__,__ver_sub__)


