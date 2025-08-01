from django.urls import path
from .views import (
    RegisterView, LoginView, LogoutView, 
    ChangePasswordView, ProfileView, ForgotPasswordView, ActiveSessionsView,ResetPasswordConfirmView

)
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('change-password/', ChangePasswordView.as_view(), name='change-password'),
    path('profile/', ProfileView.as_view(), name='profile'),
    path('forgot-password/', ForgotPasswordView.as_view(), name='forgot-password'),
    path('reset-password-confirm/<uidb64>/<token>/', ResetPasswordConfirmView.as_view(), name='password_reset_confirm'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
    path('sessions/', ActiveSessionsView.as_view(), name='active-sessions'),

]
