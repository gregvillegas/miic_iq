from django.conf import settings


class EmbedPolicyMiddleware:
    """
    Allows the app to be embedded (CRM widget iframe) only from EMBED_ALLOWED_ORIGINS.
    With no origins configured the default same-origin policy stays in force.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        origins = getattr(settings, 'EMBED_ALLOWED_ORIGINS', [])
        if origins:
            response.headers.pop('X-Frame-Options', None)
            response.headers['Content-Security-Policy'] = "frame-ancestors 'self' " + ' '.join(origins)
        return response
