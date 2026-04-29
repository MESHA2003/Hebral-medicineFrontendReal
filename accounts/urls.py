from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.RegisterUserView.as_view(), name='register'),
    path('users/', views.UserListView.as_view(), name='user-list'),
    path('login/', views.LoginView.as_view(), name='login'),
]