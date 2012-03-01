from watchdog.events import PatternMatchingEventHandler


class CallbackModifiedHandler(PatternMatchingEventHandler):
    """
    A pattern matching event handler that calls the provided
    callback when a file is modified.
    """
    def __init__(self, callback, *args, **kwargs):
        self.callback = callback
        super(CallbackModifiedHandler, self).__init__(*args, **kwargs)

    def on_modified(self, event):
        super(CallbackModifiedHandler, self).on_modified(event)
        if not event.is_directory:
            self.callback()
