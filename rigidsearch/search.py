# -*- coding: utf-8 -*-
import os
import errno
import hashlib
from whoosh import index
from whoosh.fields import Schema, TEXT, ID, STORED
from whoosh.qparser import QueryParser
from whoosh.query import Term, And
from whoosh.highlight import HtmlFormatter, ContextFragmenter

from flask import current_app

from rigidsearch.utils import normalize_text


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


def get_index(index_path=None, app=None):
    if index_path is None:
        if app is None:
            app = current_app._get_current_object()
        schema = make_schema()
        index_path = app.config['SEARCH_INDEX_PATH']
    if os.path.exists(index_path):
        idx = index.open_dir(index_path)
    else:
        os.makedirs(index_path)
        idx = index.create_in(index_path, schema)
    return Index(index_path, idx, schema)


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
