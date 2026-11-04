"""Thin HTTP boundary for account lifecycle."""

from urllib.parse import urlparse

from django.conf import settings
from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied, ValidationError
from rest_framework.generics import GenericAPIView, RetrieveUpdateAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from .serializers import LoginSerializer, LogoutSerializer, RegisterSerializer, UserSerializer
from .services import login_user


def _check_cookie_origin(request):
    origin = request.headers.get("Origin")
    if not origin:
        return
    parsed = urlparse(origin)
    allowed = {f"{request.scheme}://{request.get_host()}", *settings.CORS_ALLOWED_ORIGINS}
    if parsed.scheme not in {"http", "https"} or origin not in allowed:
        raise PermissionDenied("Origin không được phép.")


def _set_refresh_cookie(response, token):
    response.set_cookie(
        settings.REFRESH_COOKIE_NAME,
        str(token),
        max_age=7 * 24 * 60 * 60,
        httponly=True,
        secure=settings.REFRESH_COOKIE_SECURE,
        samesite=settings.REFRESH_COOKIE_SAMESITE,
        path=settings.REFRESH_COOKIE_PATH,
    )


def _session_response(user, *, status_code=status.HTTP_200_OK):
    refresh = RefreshToken.for_user(user)
    response = Response(
        {"access": str(refresh.access_token), "user": UserSerializer(user).data},
        status=status_code,
    )
    _set_refresh_cookie(response, refresh)
    return response


class RegisterView(GenericAPIView):
    permission_classes = (AllowAny,)
    serializer_class = RegisterSerializer
    throttle_scope = "register"

    def post(self, request):
        _check_cookie_origin(request)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return _session_response(serializer.save(), status_code=status.HTTP_201_CREATED)


class LoginView(GenericAPIView):
    permission_classes = (AllowAny,)
    serializer_class = LoginSerializer
    throttle_scope = "login"

    def post(self, request):
        _check_cookie_origin(request)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = login_user(**serializer.validated_data)
        return _session_response(user)


class RefreshView(GenericAPIView):
    permission_classes = (AllowAny,)
    serializer_class = TokenRefreshSerializer
    throttle_scope = "refresh"

    def post(self, request):
        _check_cookie_origin(request)
        raw = request.COOKIES.get(settings.REFRESH_COOKIE_NAME)
        if not raw:
            raise ValidationError({"refresh": "Phiên đăng nhập không hợp lệ."})
        serializer = self.get_serializer(data={"refresh": raw})
        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as exc:
            raise AuthenticationFailed("Phiên đăng nhập không hợp lệ.") from exc
        response = Response({"access": serializer.validated_data["access"]})
        if "refresh" in serializer.validated_data:
            _set_refresh_cookie(response, serializer.validated_data["refresh"])
        return response


class LogoutView(GenericAPIView):
    permission_classes = (AllowAny,)
    serializer_class = LogoutSerializer
    throttle_scope = "logout"

    def post(self, request):
        _check_cookie_origin(request)
        raw = request.COOKIES.get(settings.REFRESH_COOKIE_NAME)
        if raw:
            try:
                RefreshToken(raw).blacklist()
            except TokenError:
                pass
        response = Response(status=status.HTTP_204_NO_CONTENT)
        response.delete_cookie(settings.REFRESH_COOKIE_NAME, path=settings.REFRESH_COOKIE_PATH)
        return response


class MeView(RetrieveUpdateAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user
