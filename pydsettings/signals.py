from pysignals import Signal

setting_changed = Signal(providing_args=["setting", "value", "enter"])
