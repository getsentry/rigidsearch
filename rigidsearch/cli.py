# coding: utf-8
import os
import click
import shutil
import tempfile

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
@click.option('--ignore', '-i', multiple=True,
              help='Adds a CSS selector to be ignored for indexing.')
@click.option('--no-default-ignores', is_flag=True,
              help='Removes the default ignores.')
@click.option('--content-selector', '-c', multiple=True,
              help='Adds a content CSS selector.')
@click.option('--title-cleanup-regex', '-T',
              help='A regular expression for cleaning up the HTML title. The '
              'group with index 1 is used for the final title.')
@click.option('--skip-document', '-s',
              help='Adds a document path that should be ignored.')
@click.option('--index-path', help='Where to put the index.')
@click.option('--save-zip', type=click.File('wb'),
              help='Optional a zip file the index should be stored at.')
@pass_ctx
def index_folder_cmd(ctx, path, section, ignore, no_default_ignores,
                     content_selector, title_cleanup_regex,
                     skip_document, index_path, save_zip):
    """Indexes a path."""
    from rigidsearch.search import get_index, zip_up_index
    from rigidsearch.fs import find_all_documents, file_changed
    from rigidsearch.htmlprocessor import Processor

    try:
        if save_zip is not None:
            index_path = tempfile.mkdtemp()

        index = get_index(index_path, ctx.app)

        processor = Processor(
            title_cleanup_regex=title_cleanup_regex,
            content_selectors=content_selector,
            ignore=ignore,
            no_default_ignores=no_default_ignores
        )

        all_docs = find_all_documents(path, ignore=skip_document)
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
                t.index_document(processor, path, source_file, section=section)
            for path in to_delete:
                click.echo('Removing %s' % path)
                t.remove_document(path, section=section)

        if save_zip:
            click.echo('Dumping index to zip file')
            zip_up_index(save_zip, index_path)

    finally:
        if save_zip:
            try:
                shutil.rmtree(index_path)
            except (OSError, IOError):
                pass


@cli.command('search')
@click.argument('query')
@click.option('--section', default='generic')
@click.option('--index-path', help='Path to the search index.')
@pass_ctx
def search_cmd(ctx, query, section, index_path):
    """Triggers a search from the command line."""
    from rigidsearch.search import get_index

    index = get_index(index_path, ctx.app)
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
    from rigidsearch.app import RigidsearchServer
    RigidsearchServer(app=ctx.app, options=options).run()


def main():
    cli(auto_envvar_prefix='RIGIDSEARCH')
