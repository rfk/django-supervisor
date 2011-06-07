"""

djsupervisor.management.commands.supervisor:  djsupervisor mangement command
----------------------------------------------------------------------------

This module defines the main management command for the djsupervisor app.
The "supervise" command acts like a combination of the supervisord and
supervisorctl programs, allowing you to start up, shut down and manage all
of the proceses defined in your Django project.

"""

from __future__ import absolute_import
from __future__ import with_statement

from optparse import make_option
from textwrap import dedent
try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

from supervisor import supervisord, supervisorctl

from django.core.management.base import BaseCommand, CommandError

from djsupervisor.config import get_merged_config


class Command(BaseCommand):

    args = "[<command> [<process>, ...]]"

    help = dedent("""
           Manage processes with supervisord.

           With no arguments, this spawns the configured background processes.
           With a command argument it allows control the running processes.
           Available commands are:

               supervisor shell
               supervisor start <progname>
               supervisor stop <progname>
               supervisor restart <progname>

           """).strip()

    option_list = BaseCommand.option_list + (
        make_option("--daemonize","-d",
            action="store_true",
            dest="daemonize",
            default=False,
            help="daemonize before launching subprocessess"),
        make_option("--launch","-l",
            metavar="PROG",
            action="append",
            dest="launch",
            help="launch program automatically at supervisor startup"),
        make_option("--exclude","-x",
            metavar="PROG",
            action="append",
            dest="exclude",
            help="don't launch program automatically at supervisor startup"),
    )

    def handle(self, *args, **options):
        #  With no arguments, we launch the processes under supervisord.
        #  With arguments, we pass them on to supervisorctl.
        if not args:
            return self._handle_launch(**options)
        else:
            return self._handle_control(args,**options)

    def _handle_launch(self,**options):
        cfg = get_merged_config(**options)
        print cfg
        return supervisord.main(["-c",StringIO(cfg),])

    def _handle_control(self,args,**options):
        cfg = get_merged_config(**options)
        if args[0] == "shell":
            args = ("--interactive",) + args[1:]
        return supervisorctl.main(("-c",StringIO(cfg)) + args)


