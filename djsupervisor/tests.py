"""

djsupervisor.tests:  testcases for djsupervisor
-----------------------------------------------

These are just some simple tests for the moment, more to come...

"""

import os
import sys
import difflib
import unittest

import djsupervisor


class TestDJSupervisorDocs(unittest.TestCase):

    def test_readme_matches_docstring(self):
        """Ensure that the README is in sync with the docstring.

        This test should always pass; if the README is out of sync it just
        updates it with the contents of djsupervisor.__doc__.
        """
        dirname = os.path.dirname
        readme = os.path.join(dirname(dirname(__file__)),"README.rst")
        if not os.path.isfile(readme):
            f = open(readme,"wb")
            f.write(djsupervisor.__doc__.encode())
            f.close()
        else:
            f = open(readme,"rb")
            if f.read() != djsupervisor.__doc__:
                f.close()
                f = open(readme,"wb")
                f.write(djsupervisor.__doc__.encode())
                f.close()


