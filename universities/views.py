from django.shortcuts import render

from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Count
from rest_framework import generics, viewsets, status
from django.contrib.auth.models import User, Group
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAdminUser
from django.urls import reverse
from rest_framework.views import APIView
from django.utils import timezone
from datetime import timedelta
import os
import uuid
import requests
import json
import hmac
import hashlib

# Create your views here.

from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from .models import University, UserDashboard
from .permissions import HasActiveSubscription
from .serializers import UniversitySerializer, UserSerializer, UserDetailSerializer, UserDashboardSerializer, GroupSerializer, UserProfileUpdateSerializer

class CreateUserView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [AllowAny]

class UserViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows users to be viewed or edited by an admin.
    """
    queryset = User.objects.prefetch_related('groups', 'user_permissions').select_related('dashboard').all().order_by('-date_joined')
    permission_classes = [IsAdminUser]

    def get_serializer_class(self):
        if self.action == 'create':
            return UserSerializer
        return UserDetailSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        detail_serializer = UserDetailSerializer(user, context={'request': request})
        headers = self.get_success_headers(detail_serializer.data)
        return Response(detail_serializer.data, status=status.HTTP_201_CREATED, headers=headers)

@api_view(['POST'])
@permission_classes([IsAdminUser]) # Example: Only admins can create
def create_university(request):
    serializer = UniversitySerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['DELETE'])
@permission_classes([IsAdminUser])
def delete_university(request, pk):
    try:
        university = University.objects.get(id=pk)
        university.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    except University.DoesNotExist:
        return Response({'error': 'University not found'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
@permission_classes([IsAuthenticated, HasActiveSubscription])
def get_university_detail(request, pk):
    try:
        university = University.objects.get(id=pk)
        serializer = UniversitySerializer(university)
        return Response(serializer.data)
    except University.DoesNotExist:
        return Response({'error': 'University not found'}, status=status.HTTP_404_NOT_FOUND)

class DashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # get_or_create ensures a dashboard exists if the signal failed for some reason
        dashboard, created = UserDashboard.objects.get_or_create(user=request.user)
        serializer = UserDashboardSerializer(dashboard)
        return Response(serializer.data)

    def post(self, request):
        dashboard, created = UserDashboard.objects.get_or_create(user=request.user)
        university_id = request.data.get('university_id')
        list_name = request.data.get('list_name')

        if not university_id or not list_name:
            return Response({'error': 'university_id and list_name are required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            university = University.objects.get(id=university_id)
        except University.DoesNotExist:
            return Response({'error': 'University not found'}, status=status.HTTP_404_NOT_FOUND)

        valid_lists = ['favorites', 'planning_to_apply', 'applied', 'accepted', 'visa_approved']
        if list_name not in valid_lists:
            return Response({'error': f'Invalid list name: {list_name}'}, status=status.HTTP_400_BAD_REQUEST)

        list_to_modify = getattr(dashboard, list_name)
        list_to_modify.add(university)

        serializer = UserDashboardSerializer(dashboard)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request):
        serializer = UserProfileUpdateSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        # Return the complete, updated dashboard
        dashboard = request.user.dashboard
        final_serializer = UserDashboardSerializer(dashboard)
        return Response(final_serializer.data, status=status.HTTP_200_OK)

class UniversityList(generics.ListAPIView):
    queryset = University.objects.all()
    serializer_class = UniversitySerializer
    permission_classes = [IsAuthenticated, HasActiveSubscription]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['country', 'course_offered', 'tuition_fee', 'application_fee']

class InitializeChapaPaymentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        # For simplicity, we define a fixed amount for a 1-month subscription.
        # In a real app, this might come from a product model or settings.
        amount = "100"  # Example: 100 ETB for 1 month

        # Generate a unique transaction reference, embedding the user ID.
        tx_ref = f"unifinder-{user.id}-{uuid.uuid4()}"

        chapa_secret_key = os.environ.get("CHAPA_SECRET_KEY")
        if not chapa_secret_key:
            return Response(
                {"status": "error", "message": "Chapa secret key is not configured."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        headers = {
            "Authorization": f"Bearer {chapa_secret_key}",
            "Content-Type": "application/json"
        }

        # The backend URL is the webhook Chapa will call.
        # The frontend URL is where the user is redirected after payment.
        callback_url = request.build_absolute_uri(reverse('chapa_webhook'))
        return_url = "https://uni-frontend-lac.vercel.app/dashboard"

        payload = {
            "amount": amount,
            "currency": "ETB",
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "tx_ref": tx_ref,
            "callback_url": callback_url,
            "return_url": return_url,
            "customization[title]": "UNI-FINDER Subscription",
            "customization[description]": "1-Month Subscription Renewal",
        }

        try:
            chapa_init_url = "https://api.chapa.co/v1/transaction/initialize"
            response = requests.post(chapa_init_url, headers=headers, json=payload)
            response.raise_for_status()
            response_data = response.json()

            if response_data.get("status") == "success":
                return Response({
                    "status": "success",
                    "checkout_url": response_data.get("data", {}).get("checkout_url"),
                })
            else:
                return Response({
                    "status": "error",
                    "message": response_data.get("message", "Failed to initialize payment with Chapa.")
                }, status=status.HTTP_400_BAD_REQUEST)

        except requests.exceptions.RequestException as e:
            return Response({"status": "error", "message": f"Network error: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            return Response({"status": "error", "message": f"An unexpected error occurred: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class GroupList(generics.ListAPIView):
    queryset = Group.objects.all()
    serializer_class = GroupSerializer
    permission_classes = [IsAdminUser]


@api_view(['PUT'])
@permission_classes([IsAdminUser])
def update_university(request, pk):
    try:
        university = University.objects.get(id=pk)
    except University.DoesNotExist:
        return Response({'error': 'University not found'}, status=status.HTTP_404_NOT_FOUND)

    serializer = UniversitySerializer(university, data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class PaymentWebhookView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        # 1. Webhook Signature Verification
        chapa_webhook_secret = os.environ.get("CHAPA_WEBHOOK_SECRET")
        if not chapa_webhook_secret:
            print("Chapa webhook secret is not configured.")
            return Response({'status': 'error', 'message': 'Internal server error: Webhook secret not configured.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Chapa may send the signature in either of these headers. DRF headers are case-insensitive.
        signature = request.headers.get('Chapa-Signature') or request.headers.get('X-Chapa-Signature')
        if not signature:
            return Response({'status': 'error', 'message': 'Webhook signature not found.'}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            # The payload needs to be stringified in a compact, consistent way.
            # The Node.js example stringifies the parsed JSON, so we do the same with request.data.
            # Using separators=(',', ':') creates a compact JSON string without whitespace.
            payload_string = json.dumps(request.data, separators=(',', ':')).encode('utf-8')
            
            # Calculate the expected hash
            expected_hash = hmac.new(
                chapa_webhook_secret.encode('utf-8'),
                msg=payload_string,
                digestmod=hashlib.sha256
            ).hexdigest()

            # Compare signatures securely to prevent timing attacks
            if not hmac.compare_digest(signature, expected_hash):
                print(f"Signature mismatch. Expected: {expected_hash}, Received: {signature}")
                return Response({'status': 'error', 'message': 'Invalid webhook signature.'}, status=status.HTTP_401_UNAUTHORIZED)
        
        except Exception as e:
            print(f"Error during signature verification: {e}")
            return Response({'status': 'error', 'message': 'Internal server error during signature verification.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        print("✅ Webhook signature verified")

        # Signature is valid, now we can proceed with the existing logic.
        # Chapa sends the full transaction detail in the POST body.
        tx_ref = request.data.get('tx_ref')
        if not tx_ref:
            return Response({'status': 'error', 'message': 'Transaction reference not found in webhook payload.'}, status=status.HTTP_400_BAD_REQUEST)

        # 2. Verify the transaction with Chapa to ensure authenticity (this is a secondary check)
        chapa_secret_key = os.environ.get("CHAPA_SECRET_KEY")
        if not chapa_secret_key:
            print("Chapa secret key is not configured for webhook verification.")
            return Response({'status': 'error', 'message': 'Internal server error.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        headers = {
            "Authorization": f"Bearer {chapa_secret_key}",
        }
        verify_url = f"https://api.chapa.co/v1/transaction/verify/{tx_ref}"

        try:
            response = requests.get(verify_url, headers=headers)
            response.raise_for_status()
            verification_data = response.json()

            # Check if the transaction was successful
            if verification_data.get("data", {}).get("status") == "success":
                # 3. Process the payment
                try:
                    # tx_ref format: "unifinder-{user.id}-{uuid}"
                    user_id = int(tx_ref.split('-')[1])
                    user = User.objects.get(id=user_id)
                except (IndexError, ValueError, User.DoesNotExist):
                    print(f"Could not find user from tx_ref: {tx_ref}")
                    return Response({'status': 'error', 'message': 'Invalid transaction reference format.'}, status=status.HTTP_400_BAD_REQUEST)

                # 4. Update user's dashboard
                dashboard, _ = UserDashboard.objects.get_or_create(user=user)
                
                # Extend subscription by 30 days
                if dashboard.subscription_end_date and dashboard.subscription_end_date > timezone.now().date():
                    # If subscription is already active, extend from the end date
                    dashboard.subscription_end_date += timedelta(days=30)
                else:
                    # If expired or not set, extend from today
                    dashboard.subscription_end_date = timezone.now().date() + timedelta(days=30)
                
                dashboard.subscription_status = 'active'
                dashboard.save()

                print(f"Successfully processed payment for user {user.id}. New expiry: {dashboard.subscription_end_date}")
                
                # 5. Acknowledge receipt to Chapa
                return Response({'status': 'success'}, status=status.HTTP_200_OK)
            else:
                print(f"Chapa verification shows transaction not successful for tx_ref {tx_ref}: {verification_data.get('message')}")
                return Response({'status': 'error', 'message': 'Transaction not successful'}, status=status.HTTP_400_BAD_REQUEST)

        except requests.exceptions.RequestException as e:
            print(f"Network error during Chapa verification: {e}")
            return Response({'status': 'error', 'message': 'Network error during verification.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            print(f"An unexpected error occurred in Chapa webhook: {e}")
            # In a production environment, you would want to log this with more detail.
            return Response({'status': 'error', 'message': 'An internal server error occurred.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class AdminStatsView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        total_users = User.objects.count()
        
        # Users who have applied to at least one university
        applied_users = User.objects.annotate(applied_count=Count('dashboard__applied')).filter(applied_count__gt=0).count()
        
        # Users logged in within the last 30 days
        thirty_days_ago = timezone.now() - timedelta(days=30)
        active_logins = User.objects.filter(last_login__isnull=False, last_login__gte=thirty_days_ago).count()
        
        # Users marked as inactive
        inactive_accounts = User.objects.filter(is_active=False).count()

        # University and Subscription stats
        total_universities = University.objects.count()
        active_subscriptions = UserDashboard.objects.filter(subscription_status='active').count()
        expired_subscriptions = UserDashboard.objects.filter(subscription_status='expired').count()

        stats = {
            'total_users': total_users,
            'applied_users': applied_users,
            'recent_logins': active_logins,
            'inactive_accounts': inactive_accounts,
            'total_universities': total_universities,
            'active_subscriptions': active_subscriptions,
            'expired_subscriptions': expired_subscriptions,
        }
        return Response(stats)

class UniversityBulkCreate(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, *args, **kwargs):
        file = request.FILES.get('file')
        if not file:
            return Response({'error': 'No file provided'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            data = json.load(file)
            serializer = UniversitySerializer(data=data, many=True)
            if serializer.is_valid(raise_exception=True):
                serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
        except json.JSONDecodeError:
            return Response({'error': 'Invalid JSON format'}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)