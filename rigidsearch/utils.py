import re
from datetime import timedelta
from functools import update_wrapper
from flask import make_response, current_app, request


_ws_re = re.compile(r'(\s+)')


def chop_tail(base, tail):
    if not base.endswith(tail):
        return base, False
    return base[:-len(tail)], True


def normalize_text(text):
    def _handle_match(match):
        ws = match.group()
        nl = ws.count('\n')
        if nl >= 2:
            return u'\n\n'
        elif nl == 1:
            return u'\n'
        return u' '
    return _ws_re.sub(_handle_match, text).strip('\n')


def cors(origin=None, methods=None, headers=None, max_age=21600,
         attach_to_all=True, automatic_options=True):
    if methods is not None:
        methods = ', '.join(sorted(x.upper() for x in methods))
    if headers is not None and not isinstance(headers, basestring):
        headers = ', '.join(x.upper() for x in headers)
    if not isinstance(origin, basestring):
        origin = ', '.join(origin or ('*',))
    if isinstance(max_age, timedelta):
        max_age = max_age.total_seconds()

    def get_methods():
        if methods is not None:
            return methods

        options_resp = current_app.make_default_options_response()
        return options_resp.headers['allow']

    def decorator(f):
        def wrapped_function(*args, **kwargs):
            if automatic_options and request.method == 'OPTIONS':
                resp = current_app.make_default_options_response()
            else:
                resp = make_response(f(*args, **kwargs))
            if not attach_to_all and request.method != 'OPTIONS':
                return resp

            h = resp.headers

            h['Access-Control-Allow-Origin'] = origin
            h['Access-Control-Allow-Methods'] = get_methods()
            h['Access-Control-Max-Age'] = str(max_age)
            if headers is not None:
                h['Access-Control-Allow-Headers'] = headers
            return resp

        f.provide_automatic_options = False
        return update_wrapper(wrapped_function, f)
    return decorator
