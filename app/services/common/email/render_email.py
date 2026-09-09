"""Template layer for outgoing e-mail.

Templates live in ``templates/`` next to this module and extend
``_base.html.jinja``, which carries the shared layout, header and footer.
Autoescaping is on, so anything a user typed (a display name, an app name) is
safe to interpolate into the HTML.
"""

from functools import lru_cache
from pathlib import Path

from jinja2 import Environment, FileSystemLoader


@lru_cache
def _environment() -> Environment:
    templates_dir = Path(__file__).parent / "templates"
    return Environment(loader=FileSystemLoader(templates_dir), autoescape=True)


def render_email(template_name: str, **context: object) -> str:
    """Render one e-mail template (e.g. ``password_reset.html.jinja``) to HTML."""
    return _environment().get_template(template_name).render(**context)
