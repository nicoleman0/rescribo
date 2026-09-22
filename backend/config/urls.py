from django.contrib import admin
from django.urls import path
from drf_spectacular.views import SpectacularAPIView

from accounts.views import (
    CsrfView,
    InvitationCreateView,
    InvitationRevokeView,
    InviteAcceptView,
    InvitePreviewView,
    LoginView,
    LogoutView,
    MembershipListView,
    MembershipPasswordResetView,
    MembershipRevokeView,
    MembershipRoleView,
    PasswordResetPreviewView,
    PasswordResetRedeemView,
    SessionView,
)
from health.views import LiveView, ReadyView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/live/", LiveView.as_view(), name="health-live"),
    path("api/health/ready/", ReadyView.as_view(), name="health-ready"),
    path("api/auth/login/", LoginView.as_view(), name="auth-login"),
    path("api/auth/csrf/", CsrfView.as_view(), name="auth-csrf"),
    path("api/auth/logout/", LogoutView.as_view(), name="auth-logout"),
    path("api/auth/session/", SessionView.as_view(), name="auth-session"),
    path("api/invitations/preview/", InvitePreviewView.as_view(), name="invitation-preview"),
    path("api/invitations/accept/", InviteAcceptView.as_view(), name="invitation-accept"),
    path(
        "api/password-resets/preview/",
        PasswordResetPreviewView.as_view(),
        name="password-reset-preview",
    ),
    path(
        "api/password-resets/redeem/",
        PasswordResetRedeemView.as_view(),
        name="password-reset-redeem",
    ),
    path(
        "api/workspaces/<uuid:workspace_id>/invitations/",
        InvitationCreateView.as_view(),
        name="invitation-create",
    ),
    path(
        "api/workspaces/<uuid:workspace_id>/invitations/<uuid:invitation_id>/revoke/",
        InvitationRevokeView.as_view(),
        name="invitation-revoke",
    ),
    path(
        "api/workspaces/<uuid:workspace_id>/memberships/",
        MembershipListView.as_view(),
        name="membership-list",
    ),
    path(
        "api/workspaces/<uuid:workspace_id>/memberships/<uuid:membership_id>/revoke/",
        MembershipRevokeView.as_view(),
        name="membership-revoke",
    ),
    path(
        "api/workspaces/<uuid:workspace_id>/memberships/<uuid:membership_id>/role/",
        MembershipRoleView.as_view(),
        name="membership-role",
    ),
    path(
        "api/workspaces/<uuid:workspace_id>/memberships/<uuid:membership_id>/password-reset/",
        MembershipPasswordResetView.as_view(),
        name="membership-password-reset",
    ),
    path("api/schema/", SpectacularAPIView.as_view(authentication_classes=[]), name="schema"),
]
