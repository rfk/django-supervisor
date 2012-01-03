"""

djsupervisor.management.commands.supervisor:  djsupervisor mangement command
----------------------------------------------------------------------------

This module defines the main management command for the djsupervisor app.
The "supervisor" command acts like a combination of the supervisord and
supervisorctl programs, allowing you to start up, shut down and manage all
of the proceses defined in your Django project.

The "supervisor" command suports several modes of operation:

    * called without arguments, it launches supervisord to spawn processes.

    * called with the single argument "getconfig", is prints the merged
      supervisord config to stdout.

    * called with the single argument "autoreload", it watches for changes
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
from ConfigParser import RawConfigParser, NoOptionError
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
            help="daemonize before launching subprocessess"
        ),
        make_option("--pidfile",None,
            action="store",
            dest="pidfile",
            help="store daemon PID in this file"
        ),
        make_option("--logfile",None,
            action="store",
            dest="logfile",
            help="write logging output to this file"
        ),
        make_option("--project-dir",None,
            action="store",
            dest="project_dir",
            help="the root directory for the django project"
                 " (by default this is guessed from the location"
                 " of manage.py)"
        ),
        make_option("--launch","-l",
            metavar="PROG",
            action="append",
            dest="launch",
            help="launch program automatically at supervisor startup"
        ),
        make_option("--nolaunch","-n",
            metavar="PROG",
            action="append",
            dest="nolaunch",
            help="don't launch program automatically at supervisor startup"
        ),
        make_option("--exclude","-x",
            metavar="PROG",
            action="append",
            dest="exclude",
            help="exclude program from supervisor config"
        ),
        make_option("--include","-i",
            metavar="PROG",
            action="append",
            dest="include",
            help="don't exclude program from supervisor config"
        ),
        make_option("--autoreload","-r",
            metavar="PROG",
            action="append",
            dest="autoreload",
            help="restart program automatically when code files change"
                 " (debug mode only;"
                 " if not set then all programs are autoreloaded)"
        ),
        make_option("--noreload",
            action="store_true",
            dest="noreload",
            help="don't restart processes when code files change"
        ),
    )

    def run_from_argv(self,argv):
        #  Customize option handling so that it doesn't choke on any
        #  options that are being passed straight on to supervisorctl.
        #  Basically, we insert "--" before the supervisorctl command.
        #
        #  For example, automatically turn this:
        #      manage.py supervisor -l celeryd tail -f celeryd
        #  Into this:
        #      manage.py supervisor -l celeryd -- tail -f celeryd
        #
        i = 2
        while i < len(argv):
            arg = argv[i]
            if arg == "--":
                break
            elif arg.startswith("--"):
                i += 1
            elif arg.startswith("-"):
                i += 2
            else:
                argv = argv[:i] + ["--"] + argv[i:]
                break
        return super(Command,self).run_from_argv(argv)

    def handle(self, *args, **options):
        #  We basically just construct the merged supervisord.conf file
        #  and forward it on to either supervisord or supervisorctl.
        cfg = get_merged_config(**options)
        #  Due to some very nice engineering on behalf of supervisord authors,
        #  you can pass it a StringIO instance for the "-c" command-line
        #  option.  Saves us having to write the config to a tempfile.
        cfg_file = StringIO(cfg)
        #  With no arguments, we launch the processes under supervisord.
        if not args:
            return supervisord.main(("-c",cfg_file))
        #  With arguments, the first arg specifies the sub-command
        #  Some commands we implement ourself with _handle_<command>.
        #  The rest we just pass on to supervisorctl.
        assert args[0].isalnum()
        methname = "_handle_%s" % (args[0],)
        try:
            method = getattr(self,methname)
        except AttributeError:
            return supervisorctl.main(("-c",cfg_file) + args)
        else:
            return method(cfg_file,*args[1:],**options)

    #
    #  The following methods implement custom sub-commands.
    #

    def _handle_shell(self,cfg_file,*args,**options):
        """Command 'supervisord shell' runs the interactive command shell."""
        args = ("--interactive",) + args
        return supervisorctl.main(("-c",cfg_file) + args)

    def _handle_getconfig(self,cfg_file,*args,**options):
        """Command 'supervisor getconfig' prints merged config to stdout."""
        if args:
            raise CommandError("supervisor getconfig takes no arguments")
        print cfg_file.getvalue()
        return 0

    def _handle_autoreload(self,cfg_file,*args,**options):
        """Command 'supervisor autoreload' watches for code changes.

        This command provides a simulation of the Django dev server's
        auto-reloading mechanism that will restart all supervised processes.

        It's not quite as accurate as Django's autoreloader because it runs
        in a separate process, so it doesn't know the precise set of modules
        that have been loaded. Instead, it tries to watch all python files
        that are "nearby" the files loaded at startup by Django.
        """
        if args:
            raise CommandError("supervisor autoreload takes no arguments")
        live_dirs = self._find_live_code_dirs()
        mtimes = {}
        reload_progs = self._get_autoreload_programs(cfg_file)
        while True:
            if self._code_has_changed(live_dirs,mtimes):
                #  Fork a subprocess to make the restart call.
                #  Otherwise supervisord might kill us and cancel the restart!
                if os.fork() == 0:
                    self.handle("restart",*reload_progs,**options)
                return 0
            time.sleep(1)

    def _get_autoreload_programs(self,cfg_file):
        """Get the set of programs to auto-reload when code changes.

        Such programs will have autoreload=true in their config section.
        This can be affected by config file sections or command-line
        arguments, so we need to read it out of the merged config.
        """
        cfg = RawConfigParser()
        cfg.readfp(cfg_file)
        reload_progs = []
        for section in cfg.sections():
            if section.startswith("program:"):
                try:
                    if cfg.getboolean(section,"autoreload"):
                        reload_progs.append(section.split(":",1)[1])
                except NoOptionError:
                    pass
        return reload_progs

    def _code_has_changed(self,live_dirs,mtimes):
        """Check whether code under the given directories has changed.

        This is a simple check based on file mtime.  New or deleted files
        don't count as code changes.
        """
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
        """Find all directories in which we might have live python code.

        This walks all of the currently-imported modules and adds their
        containing directory to the list of live dirs.  After normalization
        and de-duplication, we get a pretty good approximation of the 
        directories on sys.path that are actively in use.
        """
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
                #  Remove any ones we've found that are subdirs of it.
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

