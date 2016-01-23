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
