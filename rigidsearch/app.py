from flask import Flask


def create_app(config_filename=None, config=None):
    app = Flask(__name__.split('.')[0])
    if config:
        app.config.update(config)
    if config_filename:
        app.config.from_pyfile(config_filename)

    from rigidsearch.api import bp as api_bp
    app.register_blueprint(api_bp)

    return app


def make_production_server(app, options):
    from gunicorn.app.base import Application

    class RigidsearchServer(Application):

        def __init__(self, app, options):
            # Non-optional gunicorn attributes
            self.usage = None
            self.prog = None
            self.cfg = None
            self.callable = None

            self._app = app
            self._options = options
            self.do_load_config()

        def init(self, *args):
            options = self._options.copy()
            options['worker_class'] = 'gevent'
            options['proc_name'] = 'rigidsearch'
            return options

        def load(self):
            return self._app

    return RigidsearchServer(app, options)
