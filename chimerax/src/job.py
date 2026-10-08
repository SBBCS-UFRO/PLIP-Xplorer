"""Keep calculation off the UI thread; all model and Qt operations run on completion."""
import threading
from chimerax.core.tasks import Task
from .backend import run_engine


class AnalysisJob(Task):
    SESSION_SAVE = False

    def __init__(self, session, python, directory, position, no_hydro=False, callback=None, source=None):
        super().__init__(session)
        self.python = python
        self.directory = directory
        self.position = position
        self.no_hydro = no_hydro
        self.callback = callback
        self.source = source
        self.cancel_event = threading.Event()
        self.result = None
        self.error = None

    def run(self):
        try:
            self.result = run_engine(self.python, self.directory / 'input.pdb', self.directory,
                                     no_hydro=self.no_hydro, cancelled=self.cancel_event.is_set)
        except Exception as err:
            self.error = str(err)

    def cancel(self):
        self.cancel_event.set()

    def terminate(self):
        self.cancel()
        super().terminate()

    def on_finish(self):
        result = None
        if self.cancel_event.is_set():
            self.error = 'PLIP analysis cancelled.'
        if not self.error:
            from .commands import show_results
            try:
                result = show_results(self.session, self.result, self.directory, self.position)
                if self.source is not None and not self.source.deleted:
                    self.source.display = False
            except Exception as err:
                self.error = str(err)
        if self.error:
            self.session.logger.warning(self.error)
        if self.callback:
            self.callback(result, self.error)
