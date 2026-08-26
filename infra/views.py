# infra/views.py
import logging

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from coredata.utils.breeze_session import (
    is_valid_session_token,
    session_status,
    set_breeze_session,
)

logger = logging.getLogger(__name__)

PENDING_BREEZE_SESSION_KEY = "pending_breeze_session"


def _safe_redirect_url(request, next_url, fallback="home"):
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return next_url
    return reverse(fallback)


def _consume_pending_breeze(request):
    token = request.session.pop(PENDING_BREEZE_SESSION_KEY, None)
    if not token or not request.user.is_authenticated:
        return
    if not is_valid_session_token(token):
        messages.error(request, "Invalid Breeze session token.")
        return
    try:
        set_breeze_session(token)
        messages.success(request, "Breeze session updated for today.")
    except Exception:
        logger.exception("Failed to store pending Breeze apisession token")
        messages.error(request, "Failed to store Breeze session token.")


def _store_breeze_token(request, session_token):
    if not is_valid_session_token(session_token):
        logger.warning("Rejected invalid Breeze apisession token format")
        messages.error(request, "Invalid Breeze session token in redirect URL.")
        return redirect(f"{request.path}?breeze_session=invalid")

    if not request.user.is_authenticated:
        request.session[PENDING_BREEZE_SESSION_KEY] = session_token
        request.session.modified = True
        login_url = reverse("login")
        return redirect(f"{login_url}?next={reverse('home')}")

    try:
        set_breeze_session(session_token)
        status = session_status()
        logger.info(
            "Breeze apisession stored (source=%s, preview=%s)",
            status.get("source"),
            status.get("preview"),
        )
        messages.success(
            request,
            "Breeze session updated for today. You can close this page.",
        )
        return redirect(f"{request.path}?breeze_session=ok")
    except Exception:
        logger.exception("Failed to store Breeze apisession token")
        messages.error(request, "Failed to store Breeze session token.")
        return redirect(f"{request.path}?breeze_session=error")


def home(request):
    """
    ICICI Breeze login redirect lands here with ?apisession=<session_token>.
    Guests cannot apply the token until they sign in; it is held in the
    Django session only. We then redirect to a clean URL so the token is
    not left in the browser address bar.
    """
    session_token = (
        request.GET.get("apisession") or request.GET.get("id") or ""
    ).strip()
    if session_token:
        return _store_breeze_token(request, session_token)

    if request.user.is_authenticated:
        _consume_pending_breeze(request)

    return render(request, "home.html")


def user_login(request):
    next_url = request.POST.get("next") or request.GET.get("next") or ""
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            _consume_pending_breeze(request)
            return redirect(_safe_redirect_url(request, next_url, "desk_review"))
        messages.error(request, "Invalid username or password.")
    return render(request, "login.html", {"next": next_url})


@require_POST
def user_logout(request):
    logout(request)
    return redirect("home")


def about_us(request):
    return render(request, "about.html")
