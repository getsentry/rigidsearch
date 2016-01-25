# coding: utf-8
import os
import json
import click

from werkzeug.utils import cached_property


class Context(object):

    def __init__(self):
        self.config_filename = os.environ.get('RIGIDSEARCH_CONFIG')

    @cached_property
    def app(self):
        from rigidsearch.app import create_app
        return create_app(self.config_filename)


pass_ctx = click.make_pass_decorator(Context, ensure=True)


@click.group()
@click.option('--config', type=click.Path(),
              help='Path to the config file.')
@pass_ctx
def cli(ctx, config):
    if config is not None:
        ctx.config_filename = os.path.abspath(config)


@cli.command('index-folder')
@click.argument('config', type=click.File('rb'))
@click.option('--index-path', type=click.Path(),
              help='Where to write the index to other than config default.')
@click.option('--save-zip', type=click.File('wb'),
              help='Optional a zip file the index should be stored at '
              'instead of modifying the index in-place.')
@pass_ctx
def index_folder_cmd(ctx, config, index_path, save_zip):
    """Indexes a path."""
    from rigidsearch.search import index_tree, get_index_path
    index_path = get_index_path(index_path=index_path, app=ctx.app)
    for event in index_tree(json.load(config), index_zip=save_zip,
                            index_path=index_path):
        click.echo(event)


@cli.command('search')
@click.argument('query')
@click.option('--section', default='generic')
@click.option('--index-path', help='Path to the search index.')
@pass_ctx
def search_cmd(ctx, query, section, index_path):
    """Triggers a search from the command line."""
    from rigidsearch.search import get_index, get_index_path

    index_path = get_index_path(app=ctx.app)
    index = get_index(index_path)
    results = index.search(query, section=section)
    for result in results['items']:
        click.echo('%s (%s)' % (
            result['path'],
            result['title']
        ))


@cli.command('devserver')
@click.option('--bind', '-b', default='127.0.0.1:5001')
@pass_ctx
def devserver_cmd(ctx, bind):
    """Runs a local development server."""
    parts = bind.split(':', 1)
    if len(parts) == 2:
        addr, port = parts
    elif len(parts) == 1:
        addr, port = bind, '5001'
    if addr == '':
        addr = '127.0.0.1'
    ctx.app.run(addr, int(port), debug=True)


@cli.command('run')
@click.option('--bind', '-b', default='127.0.0.1:5001')
@click.option('--workers', '-w', default=1)
@click.option('--timeout', '-t', default=30)
@click.option('--loglevel', default='info')
@click.option('--accesslog', default='-')
@click.option('--errorlog', default='-')
@pass_ctx
def run_cmd(ctx, **options):
    """Runs the http web server."""
    from rigidsearch.app import make_production_server
    make_production_server(app=ctx.app, options=options).run()


def main():
    cli(auto_envvar_prefix='RIGIDSEARCH')
