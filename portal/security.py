"""Request guards: optional HTTP Basic auth, same-origin writes and response headers."""

import hmac
from urllib.parse import urlsplit

from flask import Response, current_app, request

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def require_login():
    password = current_app.config.get("PORTAL_PASSWORD")
    if not password or request.endpoint == "portal.health":
        return None
    auth = request.authorization
    expected_user = current_app.config.get("PORTAL_USERNAME") or "admin"
    if (
        auth
        and auth.type == "basic"
        and hmac.compare_digest((auth.username or "").encode(), expected_user.encode())
        and hmac.compare_digest((auth.password or "").encode(), password.encode())
    ):
        return None
    return Response(
        "Sign-in required", 401, {"WWW-Authenticate": 'Basic realm="Client Report Portal", charset="UTF-8"'}
    )


def reject_cross_site_writes():
    """CSRF guard for the JSON API.

    Browsers label cross-site requests with Origin and Sec-Fetch-Site, so a
    write is refused unless it comes from this host (or from a non-browser
    client that sends neither header).
    """
    if request.method not in UNSAFE_METHODS:
        return None
    if request.headers.get("Sec-Fetch-Site") not in (None, "same-origin", "none"):
        return Response("Cross-site request refused", 403)
    origin = request.headers.get("Origin")
    if origin and urlsplit(origin).netloc != request.host:
        return Response("Cross-site request refused", 403)
    return None


def set_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    if request.path.startswith("/api/"):
        # Client balances and identifiers should not linger in shared caches.
        response.headers["Cache-Control"] = "no-store"
    return response


def init_app(app):
    app.before_request(require_login)
    app.before_request(reject_cross_site_writes)
    app.after_request(set_headers)
