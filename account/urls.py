from django.urls import path,include
from rest_framework_simplejwt.views import TokenRefreshView
from .views import SendPasswordResetEmailView, UserChangePassword, UserLoginView, UserPasswordResetView, UserProfileView, UserRegistrationView

urlpatterns = [
    path('register/',UserRegistrationView.as_view(),name='register'),
    path('login/',UserLoginView.as_view(),name='login'),
    path('refresh_token/',TokenRefreshView.as_view(),name='refresh_token'),
    path('profile/',UserProfileView.as_view(),name='profile'),
    path('changepassword/',UserChangePassword.as_view(),name='change_password'),
    path('send-reset-password-email/',SendPasswordResetEmailView.as_view(),name='send-reset-password-email'),
    path('reset-password/<uid>/<token>/',UserPasswordResetView.as_view(),name='reset-password'),
]

# www.abc.com/account/login/