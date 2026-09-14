"""Viewport-driven reading layout; permissions remain enforced by the normal views."""
MOBILE_PAGES = {'feed', 'read', 'authors', 'author', 'login', 'signup', 'account', 'invite-landing', 'account-merge'}


def mobile_context(request):
    match = request.resolver_match
    name = match.url_name if match else None
    return {'mobile_desktop_page': name not in MOBILE_PAGES, 'mobile_page_name': name or ''}
