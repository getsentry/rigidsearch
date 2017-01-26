# -*- coding: utf-8 -*-
import os
import sys
import uuid
import errno
import shutil
import zipfile
import hashlib
import tempfile
from contextlib import contextmanager
from whoosh import index, sorting, columns
from whoosh.fields import Schema, TEXT, ID, STORED, COLUMN
from whoosh.qparser import MultifieldParser
from whoosh.query import Term, And
from whoosh.highlight import HtmlFormatter, ContextFragmenter, \
     SentenceFragmenter
from whoosh.analysis import StandardAnalyzer

from flask import current_app

from rigidsearch.utils import normalize_text
from rigidsearch.htmlprocessor import Processor
from rigidsearch.fs import find_all_documents, file_changed


def make_fragmenter_and_analyzer(type=None, maxchars=None, surround=None):
    type = type or 'context'
    if type == 'context':
        return ContextFragmenter(
            maxchars=maxchars or 300,
            surround=surround or 60,
        ), None
    elif type == 'sentence':
        return SentenceFragmenter(
            maxchars=maxchars or 300
        ), StandardAnalyzer(stoplist=None)
    return None, None


def make_html_formatter():
    # the html formatter cannot be shared between searches easily, thus
    # we create it in a factory.
    return HtmlFormatter(
        tagname='strong',
        between=u' <span class="elipsis">…</span> '
    )


def make_schema():
    return Schema(
        title=TEXT(stored=True, sortable=True),
        path=ID(stored=True, sortable=True),
        section=ID(stored=True),
        checksum=STORED,
        content=TEXT,
        priority=COLUMN(columns.NumericColumn("i"))
    )


def create_index_version(index_path, copy=False):
    path = os.path.join(index_path, uuid.uuid4().hex)
    if copy:
        try:
            os.makedirs(os.path.dirname(path))
        except OSError:
            pass
        cur = os.path.join(index_path, os.readlink(
            os.path.join(index_path, 'cur')))
        shutil.copytree(cur, path)
    else:
        os.makedirs(path)
    return path


def get_index_path(index_path=None, app=None):
    if index_path is None:
        if app is None:
            app = current_app._get_current_object()
        index_path = app.config['SEARCH_INDEX_PATH']
    return index_path


def get_index(index_path=None, resolve_cur=True):
    schema = make_schema()

    def _ensure_index(path):
        try:
            return index.open_dir(path)
        except index.EmptyIndexError:
            return index.create_in(path, schema)

    if not resolve_cur:
        return Index(index_path, _ensure_index(index_path), schema)

    cur_idx = os.path.join(index_path, 'cur')

    if not os.path.exists(cur_idx):
        real_idx = create_index_version(index_path)
        os.symlink(os.path.basename(real_idx), cur_idx)
    idx = _ensure_index(cur_idx)
    return Index(cur_idx, idx, schema)


@contextmanager
def place_new_index(index_path, copy=True):
    # Ensure the index exists
    get_index(index_path)

    cur_idx = os.path.join(index_path, 'cur')
    index_name = os.path.join(index_path, os.readlink(cur_idx))

    try:
        new_idx = create_index_version(index_path, copy=copy)
        yield new_idx
    finally:
        if sys.exc_info()[2] is None:
            os.remove(cur_idx)
            os.symlink(os.path.basename(new_idx), cur_idx)
            to_remove = index_name
        else:
            to_remove = new_idx
        try:
            shutil.rmtree(to_remove)
        except OSError:
            pass


def put_index(index_path, stream):
    """Replaces the index with a new version from a zip file that is
    provided as file stream.
    """
    with place_new_index(index_path, copy=False) as new_idx:
        with zipfile.ZipFile(stream, 'r') as zip:
            zip.extractall(new_idx)


def zip_up_index(stream, base_dir):
    with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as zip:
        for dirpath, dirnames, filenames in os.walk(base_dir):
            for name in filenames:
                path = os.path.join(dirpath, name)
                arcname = path[len(base_dir) + 1:]
                zip.write(path, arcname)


def index_tree(config, index_zip=None, base_dir=None, index_path=None,
               from_zip=None):
    if from_zip is not None:
        source_tmp = tempfile.mkdtemp()
        with zipfile.ZipFile(from_zip, 'r') as zip:
            zip.extractall(source_tmp)
            base_dir = source_tmp
    try:
        indexer = TreeIndexer(config, base_dir)
        for evt in indexer.index_tree(index_path, index_zip):
            yield evt
        yield u'Done!'
    finally:
        if from_zip is not None:
            try:
                shutil.rmtree(source_tmp)
            except (OSError, IOError):
                pass


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

        docs = processor.process_document(contents, path)
        self.remove_document(path, section)
        for doc in docs:
            self._writer.add_document(
                path=doc['path'],
                title=doc['title'],
                content=doc['title'] + '\n\n' + doc['text'],
                section=unicode(section),
                checksum=unicode(h.hexdigest()),
                priority=doc['priority']
            )

            content_fn = self._index.get_content_filename(doc['path'], section)
            try:
                os.makedirs(os.path.dirname(content_fn))
            except OSError:
                pass
            with open(content_fn, 'wb') as f:
                f.write(doc['text'].encode('utf-8'))

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
                    'checksum': fields['checksum'],
                    'priority': fields['priority']
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

    def search(self, query, section=None, page=1, per_page=20,
               excerpt_fragmenter=None, excerpt_maxchars=None,
               excerpt_surround=None):
        qp = MultifieldParser(['title', 'content'], self.schema)
        q = qp.parse(unicode(query))
        mf = sorting.MultiFacet()
        mf.add_field("priority", reverse=True)
        mf.add_field("path", reverse=True)

        if section is not None:
            q = And([q, Term('section', unicode(section))])

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
            rv = searcher.search_page(q, page, sortedby=mf, pagelen=per_page)
            frag, anal = make_fragmenter_and_analyzer(
                excerpt_fragmenter, excerpt_maxchars, excerpt_surround)
            rv.results.formatter = make_html_formatter()
            if frag is not None:
                rv.results.fragmenter = frag
            if anal is not None:
                rv.results.analyzer = anal
            return {
                'items': [_make_item(x) for x in rv.results],
                'pages': rv.pagecount,
                'page': page,
                'per_page': per_page
            }


class TreeIndexer(object):

    def __init__(self, config, base_dir=None):
        if base_dir is None:
            base_dir = os.getcwd()
        self.configurations = config['configurations']
        self.base_dir = base_dir

    def iter_sources(self):
        for conf in self.configurations:
            for source in conf['sources']:
                d = dict(source)
                d.update(conf)
                d.pop('sources', None)
                section = d.pop('section', None)
                path = os.path.join(self.base_dir, d.pop('path', None))
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
                yield 'Indexing %s (%s)' % (path, section)
                t.index_document(processor, path, source_file, section=section)
            for path in to_delete:
                yield 'Removing %s (%s)' % (path, section)
                t.remove_document(path, section=section)

    @contextmanager
    def _process(self, index_path, index_zip):
        if index_zip is None:
            with place_new_index(index_path, copy=True) as path:
                yield path
            return
        try:
            index_path = tempfile.mkdtemp()
            get_index(index_path, resolve_cur=False)
            yield index_path
        finally:
            if sys.exc_info()[2] is None:
                zip_up_index(index_zip, index_path)
            try:
                shutil.rmtree(index_path)
            except (OSError, IOError):
                pass

    def index_tree(self, index_path=None, index_zip=None):
        with self._process(index_path, index_zip) as load_path:
            index = get_index(load_path, resolve_cur=False)
            for section, path, config in self.iter_sources():
                for evt in self.index_source(index, section, path, config):
                    yield evt
