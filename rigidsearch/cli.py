# coding: utf-8
import os
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
@click.argument('path', type=click.Path())
@click.option('--section', default='generic')
@pass_ctx
def index_folder_cmd(ctx, path, section):
    """Indexes a path."""
    from rigidsearch.search import get_index
    from rigidsearch.fs import find_all_documents, file_changed
    index = get_index(ctx.app)
    to_ignore = set(ctx.app.config.get('INDEXER_DOCS_TO_IGNORE', ()))

    all_docs = find_all_documents(path, ignore=to_ignore)
    to_delete = set()
    to_index = {}
    seen = set()

    for doc in index.iter(section=section):
        source_file = all_docs.get(doc['path'])
        if source_file is None:
            to_delete.add(doc['path'])
        elif file_changed(source_file, doc['checksum']):
            to_index[doc['path']] = source_file
        seen.add(doc['path'])

    for path, source_file in all_docs.iteritems():
        if path not in seen:
            to_index[path] = source_file

    with index.transaction() as t:
        for path, source_file in to_index.iteritems():
            click.echo('Indexing %s' % path)
            t.index_document(path, source_file, section=section)
        for path in to_delete:
            click.echo('Removing %s' % path)
            t.remove_document(path, section=section)


@cli.command('search')
@click.argument('query')
@click.option('--section', default='generic')
@pass_ctx
def search_cmd(ctx, query, section):
    """Triggers a search from the command line."""
    from rigidsearch.search import get_index

    index = get_index(ctx.app)
    results = index.search(query, section=section)
    for result in results['items']:
        click.echo('%s (%s)' % (
            result['path'],
            result['title']
        ))


@cli.command('devserver')
@click.option('--bind', default='127.0.0.1')
@click.option('--port', default=5001)
@pass_ctx
def devserver_cmd(ctx, bind, port):
    """Runs the API server locally."""
    ctx.app.run(bind, port, debug=True)


main = cli
