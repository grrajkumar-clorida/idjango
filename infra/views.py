# infra/views.py
import logging

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import redirect, render

from coredata.utils.breeze_session import (
    is_valid_session_token,
    session_status,
    set_breeze_session,
)

logger = logging.getLogger(__name__)


def home(request):
    """
    ICICI Breeze login redirect lands here with ?apisession=<session_token>.
    Example: https://idjango.rbynex.in/?apisession=56456543
    We store the token in AppSettings/Redis and redirect to a clean URL
    so the token is not left in the browser address bar.
    """
    # Real ICICI param is apisession; keep id as a legacy alias.
    session_token = (
        request.GET.get("apisession") or request.GET.get("id") or ""
    ).strip()
    if session_token:
        if not is_valid_session_token(session_token):
            logger.warning("Rejected invalid Breeze apisession token format")
            messages.error(request, "Invalid Breeze session token in redirect URL.")
            return redirect(f"{request.path}?breeze_session=invalid")

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

    return render(request, "home.html")


def user_login(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect("home")
        messages.error(request, "Invalid username or password.")
    return render(request, "login.html")


def user_logout(request):
    logout(request)
    return redirect("login")


def about_us(request):
    return render(request, "about_us.html")
