from django.urls import path
from .views import (
    RegisterView, LoginView, LogoutView, 
    ChangePasswordView, ProfileView, ForgotPasswordView, ActiveSessionsView,ResetPasswordConfirmView,CustomTokenRefreshView,PasswordResetRequestList

)
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('change-password/', ChangePasswordView.as_view(), name='change-password'),
    path('profile/', ProfileView.as_view(), name='profile'),
    path('forgot-password/', ForgotPasswordView.as_view(), name='forgot-password'),
    path('reset-password-confirm/<str:uid>/<str:token>/', ResetPasswordConfirmView.as_view(), name='reset-password-confirm'),
    path('token/refresh/', CustomTokenRefreshView.as_view(), name='token-refresh'),
    path('sessions/', ActiveSessionsView.as_view(), name='active-sessions'),
    path("password-reset-requests/", PasswordResetRequestList.as_view()),
    path("password-reset-requests/<int:pk>/", PasswordResetRequestList.as_view()),

]