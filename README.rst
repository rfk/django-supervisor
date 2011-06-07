

djsupervisor:  easy integration between django and supervisord
==============================================================


Django-supervisor combines the process-managment awesomness of supervisord
with the convenience of Django's management scripts.


Why?
----

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
    command={{ PROJECT_DIR }}/manage.py runserver --noreload
    autostart=true
    autorestart=true
 
    [program:celeryd]
    command={{ PROJECT_DIR }}/manage.py celeryd -l info
    autostart=true
    autorestart=true


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
    command={{ PROJECT_DIR }}/manage.py runserver
    {% else %}
    command={{ PROJECT_DIR }}/manage.py runfcgi host=127.0.0.1 port=8025
    {% endif %}
    autostart=true
    autorestart=true
 

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

Django-supervisor provides a new Django manangement command named "supervise"
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
run in the background.

Once the supervisor is up and running, you can interact with it to control the
running processes.  Running "manage.py supervisor shell" will launch the
interactive supervisorctl command shell.  From here you can view process
status, and start/stop individual processes::

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



Advantages
----------

Django-supervisor is admittedly quite a thin layer on top of the wonderful
functionality provided by supervisord.  But by integrating tightly with
Django's management scripts you gain several advantages:

    * manage.py remains the single point of control for running your project.
    * Process configuration lives and is managed inside your project directory.
    * Process configuration can depend on Django settings and environment
      variables, and have paths relative to your project and/or apps.
    * Apps can provide default process configurations, which projects can
      then tweak or override as needed.
    * Running all those processes is just as easy in development as it
      is in production.


