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
from connections.views import (
    CallbackView,
    ChannelView,
    ConnectionListView,
    DisconnectView,
    RefreshView,
    ReportDeleteView,
    SetupView,
    WorkspaceDeleteView,
)
from feedback.views import (
    MemberDirectoryView,
    ProblemActivityListView,
    ProblemDetailView,
    ProblemEditView,
    ProblemListView,
    ProblemOwnerView,
    ProblemReportListView,
    ReportAssignView,
    ReportCreateProblemView,
    ReportDetailView,
    ReportDismissView,
    ReportLinkView,
    ReportListView,
    ReportRestoreView,
    ReportUnlinkView,
)
from health.views import LiveView, ReadyView

urlpatterns = [
    path("api/workspaces/<uuid:workspace_id>/connections/", ConnectionListView.as_view()),
    path(
        "api/workspaces/<uuid:workspace_id>/connections/<str:provider>/setup/", SetupView.as_view()
    ),
    path(
        "api/workspaces/<uuid:workspace_id>/connections/<str:provider>/callback/",
        CallbackView.as_view(),
    ),
    path(
        "api/workspaces/<uuid:workspace_id>/connections/<str:provider>/disconnect/",
        DisconnectView.as_view(),
    ),
    path(
        "api/workspaces/<uuid:workspace_id>/connections/<str:provider>/refresh/",
        RefreshView.as_view(),
    ),
    path("api/workspaces/<uuid:workspace_id>/channels/", ChannelView.as_view()),
    path("api/workspaces/<uuid:workspace_id>/delete/", WorkspaceDeleteView.as_view()),
    path(
        "api/workspaces/<uuid:workspace_id>/reports/<uuid:report_id>/delete/",
        ReportDeleteView.as_view(),
    ),
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
    path(
        "api/workspaces/<uuid:workspace_id>/members/",
        MemberDirectoryView.as_view(),
        name="member-directory",
    ),
    path(
        "api/workspaces/<uuid:workspace_id>/reports/",
        ReportListView.as_view(),
        name="report-list",
    ),
    path(
        "api/workspaces/<uuid:workspace_id>/reports/<uuid:report_id>/",
        ReportDetailView.as_view(),
        name="report-detail",
    ),
    *[
        path(
            f"api/workspaces/<uuid:workspace_id>/reports/<uuid:report_id>/{action}/",
            view,
            name=name,
        )
        for action, view, name in (
            ("link", ReportLinkView.as_view(), "report-link"),
            ("create-problem", ReportCreateProblemView.as_view(), "report-create-problem"),
            ("unlink", ReportUnlinkView.as_view(), "report-unlink"),
            ("dismiss", ReportDismissView.as_view(), "report-dismiss"),
            ("restore", ReportRestoreView.as_view(), "report-restore"),
            ("assign", ReportAssignView.as_view(), "report-assign"),
        )
    ],
    path(
        "api/workspaces/<uuid:workspace_id>/problems/",
        ProblemListView.as_view(),
        name="problem-list",
    ),
    path(
        "api/workspaces/<uuid:workspace_id>/problems/<uuid:problem_id>/",
        ProblemDetailView.as_view(),
        name="problem-detail",
    ),
    path(
        "api/workspaces/<uuid:workspace_id>/problems/<uuid:problem_id>/reports/",
        ProblemReportListView.as_view(),
        name="problem-reports",
    ),
    path(
        "api/workspaces/<uuid:workspace_id>/problems/<uuid:problem_id>/activity/",
        ProblemActivityListView.as_view(),
        name="problem-activity",
    ),
    path(
        "api/workspaces/<uuid:workspace_id>/problems/<uuid:problem_id>/edit/",
        ProblemEditView.as_view(),
        name="problem-edit",
    ),
    path(
        "api/workspaces/<uuid:workspace_id>/problems/<uuid:problem_id>/assign-owner/",
        ProblemOwnerView.as_view(),
        name="problem-assign-owner",
    ),
    path("api/schema/", SpectacularAPIView.as_view(authentication_classes=[]), name="schema"),
]
