from .security import write_audit_log


class AuditLogMiddleware:
    """Simple audit trail for authenticated write actions."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if request.method in {"POST", "PUT", "PATCH", "DELETE"} and request.user.is_authenticated:
            # Keep this lightweight and avoid logging static/admin noise.
            path = request.path or ""
            if not path.startswith("/static/"):
                write_audit_log(
                    user=request.user,
                    action=f"http_{request.method.lower()}",
                    path=path,
                    method=request.method,
                    metadata={"status_code": response.status_code},
                )
        return response
