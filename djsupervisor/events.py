
import time

from watchdog.events import PatternMatchingEventHandler


class CallbackModifiedHandler(PatternMatchingEventHandler):
    """
    A pattern matching event handler that calls the provided
    callback when a file is modified.
    """
    def __init__(self, callback, *args, **kwargs):
        self.callback = callback
        self.repeat_delay = kwargs.pop("repeat_delay", 0)
        self.last_fired_time = 0
        super(CallbackModifiedHandler, self).__init__(*args, **kwargs)

    def on_modified(self, event):
        super(CallbackModifiedHandler, self).on_modified(event)
        now = time.time()
        if self.last_fired_time + self.repeat_delay < now:
            if not event.is_directory:
                self.last_fired_time = now
                self.callback()
