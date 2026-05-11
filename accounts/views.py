from rest_framework import viewsets, generics, permissions, status
from rest_framework.views import APIView
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser, AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.contrib.auth.hashers import check_password
from django.utils import timezone
from .models import User
from .serializers import UserSerializer, CreateUserSerializer

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAdminUser]

    @action(detail=True, methods=['post'], url_path='reset-password')
    def reset_password(self, request, pk=None):
        user = self.get_object()
        new_password = request.data.get('password')
        if not new_password:
            return Response({'error': 'Password required'}, status=400)
        user.set_password(new_password)
        user.last_password_change = timezone.now()
        user.save()
        return Response({'status': 'password updated'})

    @action(detail=True, methods=['post'], url_path='block')
    def block_user(self, request, pk=None):
        user = self.get_object()
        if user.id == request.user.id:
            return Response({'error': 'You cannot block yourself'}, status=400)
        user.is_blocked = True
        user.save()
        return Response({'status': f'User {user.username} blocked', 'is_blocked': True})

    @action(detail=True, methods=['post'], url_path='unblock')
    def unblock_user(self, request, pk=None):
        user = self.get_object()
        if user.id == request.user.id:
            return Response({'error': 'You cannot unblock yourself'}, status=400)
        user.is_blocked = False
        user.save()
        return Response({'status': f'User {user.username} unblocked', 'is_blocked': False})

class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        old_password = request.data.get('old_password')
        new_password = request.data.get('new_password')

        if not old_password or not new_password:
            return Response({'error': 'Both old_password and new_password are required'}, status=status.HTTP_400_BAD_REQUEST)

        if not check_password(old_password, user.password):
            return Response({'error': 'Current password is incorrect'}, status=status.HTTP_400_BAD_REQUEST)

        if len(new_password) < 6:
            return Response({'error': 'New password must be at least 6 characters'}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.last_password_change = timezone.now()
        user.save()

        return Response({'status': 'password changed successfully'})

class RegisterUserView(generics.CreateAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = CreateUserSerializer

class UserListView(generics.ListAPIView):
    permission_classes = [IsAdminUser]
    queryset = User.objects.all()
    serializer_class = UserSerializer

class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        if not username or not password:
            return Response({'error': 'Username and password required'}, status=400)
        user = authenticate(username=username, password=password)
        if not user:
            return Response({'error': 'Invalid credentials'}, status=400)
        if user.is_blocked:
            return Response({'error': 'Your account has been blocked. Contact administrator.'}, status=403)
        refresh = RefreshToken.for_user(user)
        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': UserSerializer(user).data
        })