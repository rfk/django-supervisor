"""

djsupervisor.management.commands.supervisor:  djsupervisor mangement command
----------------------------------------------------------------------------

This module defines the main management command for the djsupervisor app.
The "supervise" command acts like a combination of the supervisord and
supervisorctl programs, allowing you to start up, shut down and manage all
of the proceses defined in your Django project.

"""

from __future__ import absolute_import

from supervisor import supervisord, supervisorctl

from django.core.management.base import BaseCommand, CommandError

from djsupervisor.config import get_merged_supervisord_config


class Command(BaseCommand):

    args = "[<command> [<process>, ...]]"

    help = "Manage processes with supervisord"

    def handle(self, *args, **options):
        #  With no arguments, we launch the processes under supervisord.
        #  With arguments, we pass them on to supervisorctl.
        if not args:
            return self._handle_launch(**options)
        else:
            return self._handle_control(args,**options)

    def _handle_launch(self,**options):
        cfg = get_merged_supervisord_config(**options)
        return supervisord.main(["-c",cfg,])

    def _handle_control(self,args,**options):
        cfg = get_merged_supervisord_config(**options)
        return supervisorctl.main(("-c",cfg) + args)


