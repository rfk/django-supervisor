

from StringIO import StringIO

def get_merged_supervisord_config(**options):
    return StringIO("""
[supervisord]
nodaemon=true
""")
