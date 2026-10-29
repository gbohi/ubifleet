"""UbiFleet — Accounts URLs"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from . import views

router = DefaultRouter()
router.register('users',       views.UserViewSet,           basename='user')
router.register('roles',       views.RoleViewSet,           basename='role')
router.register('agences',     views.AgenceViewSet,         basename='agence')
router.register('permissions', views.PermissionRoleViewSet, basename='permission-role')

urlpatterns = [
    path('login/',             views.LoginView.as_view(),           name='login'),
    path('logout/',            views.LogoutView.as_view(),          name='logout'),
    path('token/refresh/',     TokenRefreshView.as_view(),          name='token_refresh'),
    path('me/',                views.MeView.as_view(),              name='me'),
    path('me/password/',       views.ChangePasswordView.as_view(),  name='change_password'),
    path('me/profile/',        views.ResetProfileView.as_view(),    name='reset_profile'),
    path('permissions/meta/',  views.PermissionMetaView.as_view(),  name='permissions-meta'),
    path('permissions/bulk/',  views.PermissionBulkView.as_view(),  name='permissions-bulk'),
    path('', include(router.urls)),
]
