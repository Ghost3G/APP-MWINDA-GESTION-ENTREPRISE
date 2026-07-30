from .security import write_audit_log

# Endpoints à haute fréquence : on évite le bruit dans l'audit générique
_SKIP_AUDIT_PREFIXES = (
    '/static/',
    '/media/',
    '/projects/api/timer/',
    '/api/notifications/',
    '/messaging/api/csrf/',
)


class AuditLogMiddleware:
    """Simple audit trail for authenticated write actions."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if request.method in {"POST", "PUT", "PATCH", "DELETE"} and request.user.is_authenticated:
            path = request.path or ""
            if any(path.startswith(prefix) for prefix in _SKIP_AUDIT_PREFIXES):
                return response
            write_audit_log(
                user=request.user,
                action=f"http_{request.method.lower()}",
                path=path,
                method=request.method,
                metadata={"status_code": response.status_code},
            )
        return response
