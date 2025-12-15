import logging

from flask import render_template


logger = logging.getLogger(__name__)
def index():
    """主页"""
    return render_template('index.html')
