from cStringIO import StringIO
from flask import Blueprint, jsonify, request, current_app, abort, json, \
     Response
from werkzeug.security import safe_str_cmp

from rigidsearch.search import get_index, put_index, index_tree, \
     get_index_path
from rigidsearch.utils import cors


bp = Blueprint('api', __name__, url_prefix='/api')


@bp.route('/search')
@cors()
def search():
    q = request.args.get('q') or u''
    page = request.args.get('page', type=int, default=1)
    per_page = request.args.get('per_page', type=int, default=20)
    section = request.args.get('section') or 'generic'

    index_path = get_index_path()
    return jsonify(get_index(index_path).search(
        q, section, page=page, per_page=per_page))


@bp.route('/index', methods=['PUT'])
def update_index():
    if not safe_str_cmp(request.form.get('secret', ''),
                        current_app.config['SEARCH_INDEX_SECRET']):
        abort(403)
    index_path = get_index_path()
    put_index(index_path, request.files['archive'])
    return jsonify(okay=True)


@bp.route('/index/sources', methods=['PUT'])
def process_zip_for_index():
    if not safe_str_cmp(request.form.get('secret', ''),
                        current_app.config['SEARCH_INDEX_SECRET']):
        abort(403)

    index_path = get_index_path()
    config = json.load(request.files['config'])

    f = request.files['archive']
    archive = f.stream
    f.stream = StringIO()

    def generate():
        for event in index_tree(config, from_zip=archive,
                                index_path=index_path):
            yield '%s\n' % event.encode('utf-8')
    return Response(generate(), direct_passthrough=True,
                    mimetype='text/plain')
