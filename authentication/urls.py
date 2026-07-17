from django.urls import path
from django.contrib.auth.views import LogoutView
from . import views

urlpatterns = [
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('activate/<uidb64>/<token>/<str:action>/', views.activate_account, name='activate'),
    path('waiting-room/', views.waiting_room, name='waiting_room'),
    path('check-login-status/', views.check_login_status, name='check_login_status'),
]