"""

djsupervisor:  easy integration between django and supervisord
==============================================================


Django-supervisor combines the process-managment awesomness of supervisord
with the convenience of Django's management scripts.


Why?
----

Running a Django project these days often entails much more than just starting
up a webserver.  You might need to have Django running behind FCGI or CherryPy,
with background tasks being managed by celeryd, periodic tasks scheduled by
celerybeat, and any number of other processes all cooperating to keep the
project up and running.

When you're just developing or debugging, it's a pain having to start and
stop all these different processes by hand.

When you're deploying, it's a pain to make sure that each process is hooked
into the system startup scripts in the correct order.

Django-supervisor makes starting all the processes required by your project
as simple as::

    $ python myproject/manage.py supervisor


How?
----

To get started, just dump a "supervisord.conf" file in your project directory
and django-supervisor will pick up on it.  A simple example might run the
Django development server and the Celery task daemon::

    [program:webserver]
    command={{ PROJECT_DIR }}/manage.py runserver --noreload
    autostart=true
    autorestart=true
 
    [program:celeryd]
    command={{ PROJECT_DIR }}/manage.py celeryd -l info
    autostart=true
    autorestart=true


Now when you run `python myproject/manage.py supervisor`, it will detect this
file and start the two processes for you.

Notice the the config file is interpreted using Django's template engine.
This lets you do fun things like locate files relative to the project root
directory.

You can also make parts of the file conditional like so.  For example, you
might start the development server when debugging but run under fcgi in
production::

    [program:webserver]
    {% if settings.DEBUG %}
    command={{ PROJECT_DIR }}/manage.py runserver
    {% else %}
    command={{ PROJECT_DIR }}/manage.py runfcgi host=127.0.0.1 port=8025
    {% endif %}
    autostart=true
    autorestart=true
 

Django-supervisor also supports per-application configuration files.  For
example, if you have "djcelery" in your INSTALLED_APPS, it will automatically
pick up and merge in configuration files from the following directories:

   * djcelery/management/supervisord.conf
   * djsupervisor/contrib/djcelery/supervisord.conf


This allows you to make the specification of background processes a part of
your reusable applications, and they will be merged together with your
project configuration.


"""

__ver_major__ = 0
__ver_minor__ = 1
__ver_patch__ = 0
__ver_sub__ = ""
__version__ = "%d.%d.%d%s" % (__ver_major__,__ver_minor__,__ver_patch__,__ver_sub__)


