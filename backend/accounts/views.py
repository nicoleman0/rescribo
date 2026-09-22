"""Thin HTTP adapters for account use cases."""

from typing import Any

from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView, exception_handler

from accounts.models import Invitation, Membership
from accounts.permissions import IsWorkspaceMember, IsWorkspaceOwner
from accounts.services import (
    LastActiveOwner,
    accept_invitation,
    change_membership_role,
    create_invitation,
    create_password_reset,
    describe_session,
    preview_invitation,
    preview_password_reset,
    redeem_password_reset,
    revoke_invitation,
    revoke_membership,
)
from accounts.session import bind_session_generation
from accounts.throttling import (
    InvitationCreationThrottle,
    LoginAddressThrottle,
    LoginIdentityThrottle,
    TokenRedemptionThrottle,
)


class ErrorSerializer(serializers.Serializer):
    detail = serializers.CharField()
    reason = serializers.CharField()
    field_errors = serializers.DictField(required=False)


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class TokenSerializer(serializers.Serializer):
    token = serializers.CharField()


class SessionSerializer(serializers.Serializer):
    user = serializers.DictField()
    memberships = serializers.ListField(child=serializers.DictField())


class EmptySerializer(serializers.Serializer):
    pass


class InvitationOutputSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    email = serializers.EmailField()
    accept_url = serializers.URLField()


class InvitationListItemSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    email = serializers.EmailField()
    role = serializers.CharField()
    created_at = serializers.DateTimeField()
    expires_at = serializers.DateTimeField()


class MembershipOutputSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    email = serializers.EmailField()
    full_name = serializers.CharField()
    role = serializers.CharField()


class TokenPreviewSerializer(serializers.Serializer):
    status = serializers.CharField()
    workspace_name = serializers.CharField(required=False)


class PasswordResetOutputSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    reset_url = serializers.URLField()


def error_response(error: Exception) -> Response:
    reason = getattr(error, "reason", "request_failed")
    detail = "The request could not be completed."
    code = status.HTTP_400_BAD_REQUEST
    if reason == "last_active_owner":
        detail = "At least one active owner must remain in the workspace."
    if reason == "password_rejected":
        detail = "Choose a stronger password."
        return Response(
            {
                "detail": detail,
                "reason": reason,
                "field_errors": {"password": getattr(error, "messages", [])},
            },
            status=400,
        )
    return Response({"detail": detail, "reason": reason, "field_errors": {}}, status=code)


def session_payload(user: Any) -> dict[str, Any]:
    data = describe_session(user=user)
    return {
        "user": {"id": data.user_id, "email": data.email, "full_name": data.full_name},
        "memberships": [
            {
                "membership_id": item.membership_id,
                "role": item.role,
                "workspace": {
                    "id": item.workspace_id,
                    "name": item.workspace_name,
                    "slug": item.workspace_slug,
                },
            }
            for item in data.memberships
        ],
    }


def csrf_failure(request: Any, reason: str = "") -> JsonResponse:
    return JsonResponse(
        {
            "detail": "Your request could not be verified. Refresh and try again.",
            "reason": "csrf_failed",
            "field_errors": {},
        },
        status=403,
    )


def api_exception_handler(error: Exception, context: dict[str, Any]) -> Response | None:
    response = exception_handler(error, context)
    if response is None:
        return None
    payload = response.data
    detail = (
        str(payload.get("detail", "The request could not be completed."))
        if isinstance(payload, dict)
        else "The request could not be completed."
    )
    if response.status_code == 400 and isinstance(payload, dict) and "detail" not in payload:
        return Response(
            {
                "detail": "Check the submitted fields.",
                "reason": "invalid_request",
                "field_errors": payload,
            },
            status=response.status_code,
        )
    reason = getattr(error, "default_code", "request_failed")
    return Response(
        {"detail": detail, "reason": reason, "field_errors": {}},
        status=response.status_code,
        headers=response.headers,
    )


@method_decorator(csrf_protect, name="dispatch")
class LoginView(APIView):
    authentication_classes: list = []
    permission_classes = [AllowAny]
    throttle_classes = [LoginIdentityThrottle, LoginAddressThrottle]

    @extend_schema(
        request=LoginSerializer,
        responses={
            200: SessionSerializer,
            400: ErrorSerializer,
            401: ErrorSerializer,
            429: ErrorSerializer,
        },
        auth=[],
    )
    def post(self, request: Request) -> Response:
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    "detail": "Check the submitted fields.",
                    "reason": "invalid_request",
                    "field_errors": serializer.errors,
                },
                status=400,
            )
        user = authenticate(
            request,
            username=serializer.validated_data["email"].lower(),
            password=serializer.validated_data["password"],
        )
        if user is None or not user.memberships.filter(is_active=True).exists():
            return Response(
                {
                    "detail": "Email or password is incorrect.",
                    "reason": "invalid_credentials",
                    "field_errors": {},
                },
                status=401,
            )
        login(request, user)
        bind_session_generation(request=request, user=user)
        return Response(session_payload(user))


class SessionView(APIView):
    @extend_schema(responses={200: SessionSerializer, 401: ErrorSerializer})
    def get(self, request: Request) -> Response:
        return Response(session_payload(request.user))


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfView(APIView):
    authentication_classes: list = []
    permission_classes = [AllowAny]

    @extend_schema(responses={204: None}, auth=[])
    def get(self, request: Request) -> Response:
        return Response(status=204)


@method_decorator(csrf_protect, name="dispatch")
class LogoutView(APIView):
    @extend_schema(request=EmptySerializer, responses={204: None, 401: ErrorSerializer})
    def post(self, request: Request) -> Response:
        logout(request)
        return Response(status=204)


class WorkspaceView(APIView):
    permission_classes = [IsAuthenticated, IsWorkspaceMember]
    membership: Membership


class OwnerWorkspaceView(WorkspaceView):
    permission_classes = [IsAuthenticated, IsWorkspaceMember, IsWorkspaceOwner]


class InvitationCreateSerializer(serializers.Serializer):
    email = serializers.EmailField()
    role = serializers.ChoiceField(choices=[Membership.Role.MEMBER])


class InvitationCreateView(OwnerWorkspaceView):
    def get_throttles(self) -> list[Any]:
        return [InvitationCreationThrottle()] if self.request.method == "POST" else []

    @extend_schema(
        responses={
            200: InvitationListItemSerializer(many=True),
            401: ErrorSerializer,
            403: ErrorSerializer,
            404: ErrorSerializer,
        }
    )
    def get(self, request: Request, workspace_id: str) -> Response:
        rows = Invitation.objects.filter(
            workspace_id=workspace_id, used_at__isnull=True, revoked_at__isnull=True
        ).values("id", "email", "role", "created_at", "expires_at")
        return Response(list(rows))

    @extend_schema(
        request=InvitationCreateSerializer,
        responses={
            201: InvitationOutputSerializer,
            400: ErrorSerializer,
            401: ErrorSerializer,
            403: ErrorSerializer,
            404: ErrorSerializer,
            429: ErrorSerializer,
        },
    )
    def post(self, request: Request, workspace_id: str) -> Response:
        serializer = InvitationCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    "detail": "Check the submitted fields.",
                    "reason": "invalid_request",
                    "field_errors": serializer.errors,
                },
                status=400,
            )
        invitation, secret = create_invitation(actor=self.membership, **serializer.validated_data)
        return Response(
            {
                "id": str(invitation.pk),
                "email": invitation.email,
                "accept_url": f"{settings.RESCRIBO_PUBLIC_BASE_URL}/invite/{secret}",
            },
            status=201,
        )


@method_decorator(csrf_protect, name="dispatch")
class PublicTokenView(APIView):
    permission_classes = [AllowAny]


@method_decorator(csrf_protect, name="dispatch")
class InvitePreviewView(PublicTokenView):
    throttle_classes: list = []

    @extend_schema(
        request=TokenSerializer,
        responses={200: TokenPreviewSerializer, 400: ErrorSerializer},
        auth=[],
    )
    def post(self, request: Request) -> Response:
        payload = request.data
        if not isinstance(payload, dict):
            return Response(
                {"detail": "Expected an object.", "reason": "invalid_request", "field_errors": {}},
                status=400,
            )
        secret = str(payload.get("token", ""))
        return Response(preview_invitation(secret=secret))


class InvitationAcceptSerializer(serializers.Serializer):
    token = serializers.CharField()
    full_name = serializers.CharField(required=False, allow_blank=True)
    password = serializers.CharField(required=False, write_only=True, allow_blank=True)


@method_decorator(csrf_protect, name="dispatch")
class InviteAcceptView(PublicTokenView):
    throttle_classes = [TokenRedemptionThrottle]

    @extend_schema(
        request=InvitationAcceptSerializer,
        responses={
            200: SessionSerializer,
            400: ErrorSerializer,
            401: ErrorSerializer,
            429: ErrorSerializer,
        },
        auth=[],
    )
    def post(self, request: Request) -> Response:
        data = InvitationAcceptSerializer(data=request.data)
        if not data.is_valid():
            return Response(
                {
                    "detail": "Check the submitted fields.",
                    "reason": "invalid_request",
                    "field_errors": data.errors,
                },
                status=400,
            )
        try:
            user = accept_invitation(
                secret=data.validated_data["token"],
                full_name=data.validated_data.get("full_name", ""),
                password=data.validated_data.get("password", ""),
                authenticated_user=request.user if request.user.is_authenticated else None,
            )
        except Exception as error:
            if hasattr(error, "reason"):
                return error_response(error)
            raise
        login(request, user)
        bind_session_generation(request=request, user=user)
        return Response(session_payload(user))


class MembershipListView(OwnerWorkspaceView):
    @extend_schema(
        responses={
            200: MembershipOutputSerializer(many=True),
            401: ErrorSerializer,
            403: ErrorSerializer,
            404: ErrorSerializer,
        }
    )
    def get(self, request: Request, workspace_id: str) -> Response:
        rows = Membership.objects.filter(workspace_id=workspace_id, is_active=True).select_related(
            "user"
        )
        return Response(
            [
                {
                    "id": str(row.pk),
                    "email": row.user.email,
                    "full_name": row.user.full_name,
                    "role": row.role,
                }
                for row in rows
            ]
        )


@method_decorator(csrf_protect, name="dispatch")
class InvitationRevokeView(OwnerWorkspaceView):
    @extend_schema(
        request=EmptySerializer,
        responses={204: None, 401: ErrorSerializer, 403: ErrorSerializer, 404: ErrorSerializer},
    )
    def post(self, request: Request, workspace_id: str, invitation_id: str) -> Response:
        try:
            revoke_invitation(workspace_id=workspace_id, invitation_id=invitation_id)
        except LookupError:
            from rest_framework.exceptions import NotFound

            raise NotFound() from None
        return Response(status=204)


@method_decorator(csrf_protect, name="dispatch")
class MembershipRevokeView(OwnerWorkspaceView):
    @extend_schema(
        request=EmptySerializer,
        responses={
            204: None,
            400: ErrorSerializer,
            401: ErrorSerializer,
            403: ErrorSerializer,
            404: ErrorSerializer,
        },
    )
    def post(self, request: Request, workspace_id: str, membership_id: str) -> Response:
        target = Membership.objects.filter(pk=membership_id, workspace_id=workspace_id).first()
        if target is None:
            from rest_framework.exceptions import NotFound

            raise NotFound()
        try:
            revoke_membership(actor=self.membership, target=target)
        except LastActiveOwner as error:
            return error_response(error)
        return Response(status=204)


class RoleSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=Membership.Role.choices)


@method_decorator(csrf_protect, name="dispatch")
class MembershipRoleView(OwnerWorkspaceView):
    @extend_schema(
        request=RoleSerializer,
        responses={
            200: MembershipOutputSerializer,
            400: ErrorSerializer,
            401: ErrorSerializer,
            403: ErrorSerializer,
            404: ErrorSerializer,
        },
    )
    def post(self, request: Request, workspace_id: str, membership_id: str) -> Response:
        target = Membership.objects.filter(pk=membership_id, workspace_id=workspace_id).first()
        if target is None:
            from rest_framework.exceptions import NotFound

            raise NotFound()
        data = RoleSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            change_membership_role(actor=self.membership, target=target, **data.validated_data)
        except LastActiveOwner as error:
            return error_response(error)
        return Response(
            {
                "id": str(target.pk),
                "email": target.user.email,
                "full_name": target.user.full_name,
                "role": data.validated_data["role"],
            }
        )


@method_decorator(csrf_protect, name="dispatch")
class MembershipPasswordResetView(OwnerWorkspaceView):
    @extend_schema(
        request=EmptySerializer,
        responses={
            201: PasswordResetOutputSerializer,
            401: ErrorSerializer,
            403: ErrorSerializer,
            404: ErrorSerializer,
        },
    )
    def post(self, request: Request, workspace_id: str, membership_id: str) -> Response:
        target = (
            Membership.objects.filter(pk=membership_id, workspace_id=workspace_id, is_active=True)
            .select_related("user")
            .first()
        )
        if target is None:
            from rest_framework.exceptions import NotFound

            raise NotFound()
        try:
            reset, secret = create_password_reset(actor=self.membership, target=target)
        except LookupError as error:
            from rest_framework.exceptions import NotFound

            raise NotFound() from error
        return Response(
            {
                "id": str(reset.pk),
                "reset_url": f"{settings.RESCRIBO_PUBLIC_BASE_URL}/reset-password/{secret}",
            },
            status=201,
        )


class PasswordResetPreviewView(PublicTokenView):
    throttle_classes: list = []

    @extend_schema(
        request=TokenSerializer,
        responses={200: TokenPreviewSerializer, 400: ErrorSerializer},
        auth=[],
    )
    def post(self, request: Request) -> Response:
        payload = request.data
        if not isinstance(payload, dict):
            return Response(
                {"detail": "Expected an object.", "reason": "invalid_request", "field_errors": {}},
                status=400,
            )
        return Response(preview_password_reset(secret=str(payload.get("token", ""))))


class PasswordResetRedeemSerializer(serializers.Serializer):
    token = serializers.CharField()
    password = serializers.CharField(write_only=True)


@method_decorator(csrf_protect, name="dispatch")
class PasswordResetRedeemView(PublicTokenView):
    throttle_classes = [TokenRedemptionThrottle]

    @extend_schema(
        request=PasswordResetRedeemSerializer,
        responses={200: SessionSerializer, 400: ErrorSerializer, 429: ErrorSerializer},
        auth=[],
    )
    def post(self, request: Request) -> Response:
        data = PasswordResetRedeemSerializer(data=request.data)
        if not data.is_valid():
            return Response(
                {
                    "detail": "Check the submitted fields.",
                    "reason": "invalid_request",
                    "field_errors": data.errors,
                },
                status=400,
            )
        try:
            user = redeem_password_reset(
                secret=data.validated_data["token"], password=data.validated_data["password"]
            )
        except Exception as error:
            if hasattr(error, "reason"):
                return error_response(error)
            raise
        login(request, user)
        bind_session_generation(request=request, user=user)
        return Response(session_payload(user))
