"""Blueprint registration.

All routes keep the same URL paths and response shapes as the legacy app.py.
"""

from __future__ import annotations


def register_blueprints(app):
    # Import locally to avoid import-time side effects / circular imports.
    from .home import bp as home_bp
    from .files import bp as files_bp
    from .personal import bp as personal_bp
    from .group import bp as group_bp
    from .network import bp as network_bp
    from .compare import bp as compare_bp
    from .ai import bp as ai_bp
    from .analysis_cache import bp as analysis_cache_bp
    from .preview import bp as preview_bp
    from .export import bp as export_bp
    from .hotwords import bp as hotwords_bp
    from .system import bp as system_bp

    app.register_blueprint(home_bp)
    app.register_blueprint(files_bp)
    app.register_blueprint(personal_bp)
    app.register_blueprint(group_bp)
    app.register_blueprint(network_bp)
    app.register_blueprint(compare_bp)
    app.register_blueprint(ai_bp)
    app.register_blueprint(analysis_cache_bp)
    app.register_blueprint(preview_bp)
    app.register_blueprint(export_bp)
    app.register_blueprint(hotwords_bp)
    app.register_blueprint(system_bp)
