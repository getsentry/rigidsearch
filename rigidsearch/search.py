# -*- coding: utf-8 -*-
import os
import uuid
import errno
import click
import shutil
import zipfile
import hashlib
import tempfile
from whoosh import index
from whoosh.fields import Schema, TEXT, ID, STORED
from whoosh.qparser import QueryParser
from whoosh.query import Term, And
from whoosh.highlight import HtmlFormatter, ContextFragmenter

from flask import current_app

from rigidsearch.utils import normalize_text
from rigidsearch.htmlprocessor import Processor
from rigidsearch.fs import find_all_documents, file_changed


context_fragmenter = ContextFragmenter(
    maxchars=300
)


def make_html_formatter():
    # the html formatter cannot be shared between searches easily, thus
    # we create it in a factory.
    return HtmlFormatter(
        tagname='strong',
        between=u' <span class="elipsis">…</span> '
    )


def make_schema():
    return Schema(
        title=TEXT(stored=True),
        path=ID(stored=True),
        section=ID(stored=True),
        checksum=STORED,
        content=TEXT
    )


def create_index_version(index_path):
    path = os.path.join(index_path, uuid.uuid4().hex)
    os.makedirs(path)
    return path


def get_index_path(index_path=None, app=None):
    if index_path is None:
        if app is None:
            app = current_app._get_current_object()
        index_path = app.config['SEARCH_INDEX_PATH']
    return index_path


def get_index(index_path=None, app=None):
    schema = make_schema()
    index_path = get_index_path(index_path, app)

    cur_idx = os.path.join(index_path, 'cur')

    if os.path.exists(cur_idx):
        idx = index.open_dir(cur_idx)
    else:
        real_idx = create_index_version(index_path)
        os.symlink(os.path.basename(real_idx), cur_idx)
        idx = index.create_in(cur_idx, schema)
    return Index(cur_idx, idx, schema)


def put_index(stream, index_path=None, app=None):
    """Replaces the index with a new version from a zip file that is
    provided as file stream.
    """
    index_path = get_index_path(index_path, app)
    cur_idx = os.path.join(index_path, 'cur')
    index_name = os.path.join(index_path, os.readlink(cur_idx))

    with zipfile.ZipFile(stream, 'r') as zip:
        new_idx = create_index_version(index_path)
        zip.extractall(new_idx)
        tmp_cur_idx = os.path.join(index_path, '.cur-' +
                                   os.path.basename(new_idx))
        os.symlink(os.path.basename(new_idx), tmp_cur_idx)
        os.rename(tmp_cur_idx, cur_idx)

    try:
        shutil.rmtree(index_name)
    except OSError:
        pass


def zip_up_index(stream, index_path=None, app=None):
    index_path = get_index_path(index_path, app)
    base_dir = os.path.join(
        index_path, os.readlink(os.path.join(index_path, 'cur')))

    with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as zip:
        for dirpath, dirnames, filenames in os.walk(base_dir):
            for name in filenames:
                path = os.path.join(dirpath, name)
                arcname = path[len(base_dir) + 1:]
                zip.write(path, arcname)


class IndexTransaction(object):

    def __init__(self, index):
        self._index = index
        self._writer = None

    def _get_writer(self):
        rv = self._writer
        if rv is not None:
            return rv
        raise RuntimeError('Tranaction was not started')

    def index_document(self, processor, path, source, section='generic'):
        buf = []
        h = hashlib.sha1()
        with open(source, 'rb') as f:
            while 1:
                chunk = f.read(16384)
                if not chunk:
                    break
                h.update(chunk)
                buf.append(chunk)
            contents = ''.join(buf)

        parts = processor.process_document(contents)
        self.remove_document(path, section)
        self._writer.add_document(
            path=path,
            title=parts['title'],
            content=parts['text'],
            section=unicode(section),
            checksum=unicode(h.hexdigest())
        )

        content_fn = self._index.get_content_filename(path, section)
        try:
            os.makedirs(os.path.dirname(content_fn))
        except OSError:
            pass
        with open(content_fn, 'wb') as f:
            f.write(parts['text'].encode('utf-8'))

    def remove_document(self, path, section='generic'):
        self._writer.delete_by_query(And([
            Term('path', path),
            Term('section', unicode(section)),
        ]))

        content_fn = self._index.get_content_filename(path, section)
        try:
            os.remove(content_fn)
        except OSError:
            pass

    def __enter__(self):
        if self._writer is not None:
            raise RuntimeError('Already entered transaction')
        self._writer = self._index.whoosh_index.writer()
        return self

    def __exit__(self, exc_type, exc_value, tb):
        self._writer.commit()


class Index(object):

    def __init__(self, index_path, whoosh_index, schema):
        self.index_path = index_path
        self.whoosh_index = whoosh_index
        self.schema = schema

    def transaction(self):
        return IndexTransaction(self)

    def iter(self, section=None):
        with self.whoosh_index.searcher() as searcher:
            for fields in searcher.all_stored_fields():
                if section is not None and \
                   fields['section'] != section:
                    continue
                yield {
                    'path': fields['path'],
                    'title': fields['title'],
                    'section': fields['section'],
                    'checksum': fields['checksum']
                }

    def get_content_filename(self, path, section):
        h = hashlib.sha1()
        h.update(path.encode('utf-8'))
        h.update('\x00')
        h.update(section.encode('utf-8'))
        fn = os.path.join(self.index_path, 'content', h.hexdigest())
        return fn

    def get_content(self, path, section, normalize=True):
        fn = self.get_content_filename(path, section)
        try:
            with open(fn, 'rb') as f:
                text = f.read().decode('utf-8')
                if normalize:
                    text = normalize_text(text)
                return text
        except OSError as e:
            if e.errno != errno.ENOENT:
                raise

    def search(self, query, section=None, page=1, per_page=20):
        qp = QueryParser('content', self.schema)
        q = qp.parse(unicode(query))
        filter = None
        if section is not None:
            filter = Term('section', unicode(section))

        def _make_item(hit):
            text = self.get_content(hit['path'], hit['section'])
            if text is not None:
                excerpt = hit.highlights('content', text=text)
            else:
                excerpt = None
            return {
                'path': hit['path'],
                'title': hit['title'],
                'excerpt': excerpt,
                'section': section,
            }

        with self.whoosh_index.searcher() as searcher:
            rv = searcher.search_page(q, page, filter=filter,
                                      pagelen=per_page)
            rv.results.formatter = make_html_formatter()
            rv.results.fragmenter = context_fragmenter
            return {
                'items': [_make_item(x) for x in rv.results],
                'pages': rv.pagecount,
                'page': page,
                'per_page': per_page
            }


class TreeIndexer(object):

    def __init__(self, config, log=False):
        self.configurations = config['configurations']
        self.log_output = log

    def log(self, message, *args):
        if self.log_output:
            click.echo(message % args)

    def iter_sources(self):
        for conf in self.configurations:
            for source in conf['sources']:
                d = dict(source)
                d.update(conf)
                d.pop('sources', None)
                section = d.pop('section', None)
                path = d.pop('path', None)
                yield section, path, d

    def index_source(self, index, section, path, config):
        processor = Processor.from_config(config)
        all_docs = find_all_documents(
            path, ignore=config.get('skip_docs') or None)
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
                self.log('Indexing %s (%s)' % (
                    click.style(path, fg='cyan'),
                    click.style(section, fg='yellow')))
                t.index_document(processor, path, source_file, section=section)
            for path in to_delete:
                self.log('Removing %s (%s)' % (
                    click.style(path, fg='cyan'),
                    click.style(section, fg='yellow')))
                t.remove_document(path, section=section)

    def index_tree(self, index_path=None, index_zip=None):
        if index_zip is not None:
            index_path = tempfile.mkdtemp()
        elif index_path is None:
            raise RuntimeError('Explicit index path must be provided')

        index = get_index(index_path)

        try:
            for section, path, config in self.iter_sources():
                self.index_source(index, section, path, config)
            if index_zip is not None:
                self.log('Dumping index into archive ...')
                zip_up_index(index_zip, index_path)
                self.log('Done')
        finally:
            if index_zip is not None:
                try:
                    shutil.rmtree(index_path)
                except (OSError, IOError):
                    pass
