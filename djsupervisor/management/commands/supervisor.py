"""

djsupervisor.management.commands.supervisor:  djsupervisor mangement command
----------------------------------------------------------------------------

This module defines the main management command for the djsupervisor app.
The "supervisor" command acts like a combination of the supervisord and
supervisorctl programs, allowing you to start up, shut down and manage all
of the proceses defined in your Django project.

The "supervisor" command suports three modes of operation:

    * called without arguments, it launches supervisord to spawn processes.
    * called with the single argument "autorestart", it watches for changes
      to python modules and restarts all processes if things change.
    * called with any other arguments, it passes them on the supervisorctl.

"""

from __future__ import absolute_import
from __future__ import with_statement

import sys
import os
import time
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
           With a command argument it lets you control the running processes.
           Available commands include:

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
        #  We basically just construct the supervisord.conf file and 
        #  forward it on to either supervisord or supervisorctl.
        cfg = get_merged_config(**options)
        #  Due to some very nice engineering on behalf of supervisord authors,
        #  you can pass it a StringIO instance for the "-c" command-line
        #  option.  Saves us having to write the config to a tempfile.
        cfg_file = StringIO(cfg)
        #  With no arguments, we launch the processes under supervisord.
        #  With argument "autorestart" we run the auto-restarter.
        #  With any other arguments, we pass them on to supervisorctl.
        if not args:
            return supervisord.main(("-c",cfg_file))
        elif args[0] == "autorestart":
            return self._handle_autorestart(*args[1:],**options)
        else:
            if args[0] == "shell":
                args = ("--interactive",) + args[1:]
            return supervisorctl.main(("-c",cfg_file) + args)

    def _handle_autorestart(self,*args,**options):
        """Watch python code files, restart processes if they change.

        This command provides a simulation of the Django dev server's
        auto-reloading mechanism that will restart all supervised processes.

        It uses django.util.autoreload under the hood, but it's not quite
        as accurate since it doesn't know what modules are being loaded
        by other processes.  Instead, it tries to watch all python files
        contained in each application directory.
        """
        if args:
            raise CommandError("supervisord autorestart takes no arguments")
        live_dirs = self._find_live_code_dirs()
        mtimes = {}
        while True:
            if self._code_has_changed(live_dirs,mtimes):
                #  Fork a subprocess to make the restart call.
                #  Otherwise supervisord might kill us and cancel the restart!
                if os.fork() == 0:
                    self.handle("restart","all",**options)
                return 0
            time.sleep(1)

    def _code_has_changed(self,live_dirs,mtimes):
        """Check whether code under the given directories has changed."""
        for filepath in self._find_live_code_files(live_dirs):
            try:
                stat = os.stat(filepath)
            except EnvironmentError:
                continue
            if filepath not in mtimes:
                mtimes[filepath] = stat.st_mtime
            else:
                if mtimes[filepath] != stat.st_mtime:
                    return True

    def _find_live_code_dirs(self):
        """Find all directories in which we might have live python code."""
        live_dirs = []
        for mod in sys.modules.values():
            #  Get the directory containing that module.
            #  This is deliberately casting a wide net.
            try:
                dirnm = os.path.dirname(mod.__file__)
            except AttributeError:
                continue
            #  Normalize it for comparison purposes.
            dirnm = os.path.realpath(os.path.abspath(dirnm))
            if not dirnm.endswith(os.sep):
                dirnm += os.sep
            #  Check that it's not an egg or some other wierdness
            if not os.path.isdir(dirnm):
                continue
            #  If it's a subdir of one we've already found, ignore it.
            for dirnm2 in live_dirs:
                if dirnm.startswith(dirnm2):
                    break
            else:
                #  Remove any one's we've found that are subdirs of it.
                live_dirs = [dirnm2 for dirnm2 in live_dirs\
                                    if not dirnm2.startswith(dirnm)]
                live_dirs.append(dirnm)
        return live_dirs

    def _find_live_code_files(self,live_dirs):
        """Find live python code files, that must be watched for changes.

        Given a pre-computed list of directories in which to search, this
        method finds all the python files under those directories and yields
        their full paths.
        """
        for dirnm in live_dirs:
            for (subdirnm,_,filenms) in os.walk(dirnm):
                for filenm in filenms:
                    try:
                        filebase,ext = filenm.rsplit(".",1)
                    except ValueError:
                        continue
                    if ext in ("py","pyc","pyo",):
                        yield os.path.join(subdirnm,filebase+".py")

