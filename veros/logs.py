import logging

from . import runtime_state

TRACE = 5


class MyLogger(logging.getLoggerClass()):
        def __init__(self, name, level=logging.NOTSET):
            super(MyLogger, self).__init__(name, level)

            logging.addLevelName(TRACE, "TRACE")

        def trace(self, msg, *args, **kwargs):
            if self.isEnabledFor(TRACE):
                self._log(TRACE, msg, args, **kwargs)


logging.setLoggerClass(MyLogger)


def setup_logging(loglevel="info", logfile=None):
    if runtime_state.proc_rank != 0:
        return

    try: # python 2
        logging.basicConfig(logfile=logfile, filemode="w",
                            level=loglevel.upper(),
                            format="%(message)s")
    except ValueError: # python 3
        logging.basicConfig(filename=logfile, filemode="w",
                            level=loglevel.upper(),
                            format="%(message)s")
