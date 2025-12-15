import logging

from flask import Blueprint, render_template


logger = logging.getLogger(__name__)

bp = Blueprint('home', __name__)


@bp.route('/')
def index():
    """主页"""
    return render_template('index.html')
