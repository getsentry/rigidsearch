import html5lib
import warnings
from lxml.cssselect import CSSSelector
from html5lib.ihatexml import DataLossWarning
from StringIO import StringIO


# the ihatexml module emits data loss warnings.  This in our case is okay
# because we are willing to accept the data loss that happens on the way
# from HTML to XML as we never go in reverse direction.  In particular the
# problem is XML namespaces which are not supported in HTML.
warnings.filterwarnings('ignore', category=DataLossWarning)


class ProcessingError(Exception):
    pass


XHTML_NAMESPACE = 'http://www.w3.org/1999/xhtml'
namespaces = {
    'html': XHTML_NAMESPACE
}


def compile_selector(sel):
    return CSSSelector(sel, namespaces=namespaces, translator='html')


def qname(tag):
    if '{' in tag:
        return tag
    return '{%s}%s' % (XHTML_NAMESPACE, tag)


tree_walker = html5lib.getTreeWalker('lxml')


def make_processor_from_config(config):
    return Processor(
        title_cleanup_func=config.get('PROCESSOR_TITLE_CLEANUP_FUNC'),
        content_selectors=config.get('PROCESSOR_CONTENT_SELECTORS'),
        ignore=config.get('PROCESSOR_IGNORE'),
        ignored_tags=config.get('PROCESSOR_IGNORED_TAGS'),
    )


class Processor(object):

    def __init__(self, title_cleanup_func=None,
                 content_selectors=None,
                 ignore=None,
                 ignored_tags=None):
        self.content_selectors = [compile_selector(sel) for sel in
                                  content_selectors or ('html|body',)]
        self.title_cleanup_func = title_cleanup_func
        self.ignore = [compile_selector(sel) for sel
                       in ignore or ('.nocontent',)]
        self.ignored_tags = [qname(x) for x in ignored_tags
                             or ('script', 'noscript', 'style', 'head')]

    def is_ignored(self, node):
        if node.tag in self.ignored_tags:
            return True
        for sel in self.ignore:
            xpath = sel.path.replace('descendant-or-self::', 'self::')
            matches = node.xpath(xpath, namespaces=namespaces)
            if matches and matches[0] is node:
                return True
        return False

    def process_document(self, document):
        if isinstance(document, basestring):
            document = StringIO(document)
        doc = html5lib.parse(document, treebuilder='lxml')
        return self.process_tree(doc)

    def process_title_tag(self, title):
        if title is None:
            return None
        text = title.text
        if self.title_cleanup_func is not None:
            text = self.title_cleanup_func(text)
        return text

    def process_content_tag(self, body):
        if body is None:
            return u''

        buf = []

        def _walk(node):
            if self.is_ignored(node):
                return

            if node.text:
                buf.append(node.text)
            for child in node:
                _walk(child)
            if node.tail:
                buf.append(node.tail)

        _walk(body)

        return u''.join(buf)

    def process_tree(self, tree):
        rv = {}

        root = tree.getroot()
        head = root.find(qname('head'))
        if head is None:
            raise ProcessingError('Document does not parse correctly.')

        title = head.find(qname('title'))
        rv['title'] = self.process_title_tag(title)

        buf = []
        for sel in self.content_selectors:
            for el in sel(root):
                buf.append(self.process_content_tag(el))

        rv['text'] = u''.join(buf).rstrip()
        return rv
