"""En-têtes de sécurité HTTP (CSP, Permissions-Policy, etc.)."""
from django.conf import settings


class SecurityHeadersMiddleware:
    """Ajoute des en-têtes de défense navigateur sans changer le métier."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # CSP : 'unsafe-inline' conservé pour les scripts/styles déjà présents dans les templates
        csp = (
            "default-src 'self'; "
            "base-uri 'self'; "
            "object-src 'none'; "
            "frame-ancestors 'none'; "
            "form-action 'self'; "
            "img-src 'self' data: blob: https://res.cloudinary.com https://*.cloudinary.com; "
            "font-src 'self' data: https://fonts.gstatic.com; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "script-src 'self' 'unsafe-inline'; "
            "connect-src 'self'; "
            "media-src 'self' blob: https://res.cloudinary.com https://*.cloudinary.com; "
            "worker-src 'self' blob:"
        )
        if not settings.DEBUG:
            csp += "; upgrade-insecure-requests"

        response.setdefault('Content-Security-Policy', csp)
        response.setdefault('Permissions-Policy', 'geolocation=(), microphone=(), camera=(), payment=()')
        response.setdefault('Cross-Origin-Opener-Policy', 'same-origin')
        response.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
        response.setdefault('X-Content-Type-Options', 'nosniff')
        return response
