from flask import Blueprint, jsonify, request, current_app, abort
from werkzeug.security import safe_str_cmp

from rigidsearch.search import get_index, put_index
from rigidsearch.utils import cors


bp = Blueprint('api', __name__, url_prefix='/api')


@bp.route('/search')
@cors()
def search():
    q = request.args.get('q') or u''
    page = request.args.get('page', type=int, default=1)
    per_page = request.args.get('per_page', type=int, default=20)
    section = request.args.get('section') or 'generic'

    return jsonify(get_index().search(
        q, section, page=page, per_page=per_page))


@bp.route('/index', methods=['PUT'])
def update_index():
    if not safe_str_cmp(request.form.get('secret', ''), current_app.config['SEARCH_INDEX_SECRET']):
        abort(403)
    put_index(request.files['index'])
    return jsonify(okay=True)
