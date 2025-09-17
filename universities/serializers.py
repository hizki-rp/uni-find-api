from rest_framework import serializers
from .models import University, UserDashboard
from django.contrib.auth.models import User, Group
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer


class UserSerializer(serializers.ModelSerializer):
    # Add the email field so the serializer will accept it
    email = serializers.EmailField(required=True)
    first_name = serializers.CharField(required=True, max_length=150)
    last_name = serializers.CharField(required=True, max_length=150)
    phone_number = serializers.CharField(write_only=True, required=False, allow_blank=True, max_length=20)

    class Meta:
        model = User
        # Add 'email' to the list of fields
        fields = ["id", "username", "email", "password", "first_name", "last_name", "phone_number"]
        extra_kwargs = {"password": {"write_only": True}}

    def create(self, validated_data):
        phone_number = validated_data.pop('phone_number', '')
        # Use create_user to properly hash the password
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data['first_name'],
            last_name=validated_data['last_name']
        )
        # The post_save signal creates the dashboard, now we update it.
        if hasattr(user, 'dashboard'):
            user.dashboard.phone_number = phone_number
            user.dashboard.save()
        # Add user to the 'user' group by default on registration
        try:
            user_group = Group.objects.get(name='user')
            user.groups.add(user_group)
        except Group.DoesNotExist:
            # In a production app, you would ensure this group exists
            # via a migration or a management command.
            pass
        return user

class SafeDashboardField(serializers.Field):
    """
    A custom field to safely serialize the dashboard,
    handling cases where it might not exist for a user.
    """
    def to_representation(self, user_instance):
        try:
            dashboard = user_instance.dashboard
            return DashboardAdminSerializer(dashboard).data
        except ObjectDoesNotExist:
            # Catching the generic ObjectDoesNotExist will handle both
            # UserDashboard.DoesNotExist and the RelatedObjectDoesNotExist
            # that is raised when accessing user.dashboard for a user without one.
            return None

    def to_internal_value(self, data):
        return data

class DashboardAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserDashboard
        fields = ['subscription_status', 'subscription_end_date']

class GroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = ['id', 'name']

class UserDetailSerializer(serializers.ModelSerializer):
    """Serializer for admins to view and edit user details, including subscriptions."""
    dashboard = SafeDashboardField(source='*', required=False)
    groups = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Group.objects.all()
     )

    class Meta:
        model = User
        fields = ["id", "username", "email", "groups", "is_staff", "is_active", "date_joined", "dashboard"]
        read_only_fields = ["id", "username", "email", "date_joined", "is_staff"]
    
    def update(self, instance, validated_data):
        dashboard_data = validated_data.pop('dashboard', None)

        # Update user fields
        instance.is_active = validated_data.get('is_active', instance.is_active)
        if 'groups' in validated_data:
            instance.groups.set(validated_data.get('groups'))
        instance.save()

        # Update nested dashboard subscription fields
        if dashboard_data:
            dashboard, _ = UserDashboard.objects.get_or_create(user=instance)
            dashboard.subscription_status = dashboard_data.get('subscription_status', dashboard.subscription_status)
            dashboard.subscription_end_date = dashboard_data.get('subscription_end_date', dashboard.subscription_end_date)
            dashboard.save()
            instance.refresh_from_db()

        return instance

class UniversitySerializer(serializers.ModelSerializer):
    class Meta:
        model = University
        fields = '__all__'

class DashboardUniversitySerializer(serializers.ModelSerializer):
    class Meta:
        model = University
        fields = ['id', 'name']

class UserDashboardSerializer(serializers.ModelSerializer):
    favorites = DashboardUniversitySerializer(many=True, read_only=True)
    planning_to_apply = DashboardUniversitySerializer(many=True, read_only=True)
    applied = DashboardUniversitySerializer(many=True, read_only=True)
    accepted = DashboardUniversitySerializer(many=True, read_only=True)
    visa_approved = DashboardUniversitySerializer(many=True, read_only=True)
    first_name = serializers.CharField(source='user.first_name', read_only=True)
    last_name = serializers.CharField(source='user.last_name', read_only=True)

    class Meta:
        model = UserDashboard
        fields = ['first_name', 'last_name', 'phone_number', 'favorites', 'planning_to_apply', 'applied', 'accepted', 'visa_approved', 'subscription_status', 'subscription_end_date']

class UserProfileUpdateSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=150, required=False)
    last_name = serializers.CharField(max_length=150, required=False)
    phone_number = serializers.CharField(max_length=20, required=False, allow_blank=True)

    def update(self, instance, validated_data):
        # instance here is the user
        instance.first_name = validated_data.get('first_name', instance.first_name)
        instance.last_name = validated_data.get('last_name', instance.last_name)
        instance.save()

        if 'phone_number' in validated_data:
            dashboard, _ = UserDashboard.objects.get_or_create(user=instance)
            dashboard.phone_number = validated_data.get('phone_number')
            dashboard.save()
        
        return instance

class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        # Add custom claims
        token['username'] = user.username
        token['is_staff'] = user.is_staff
        token['groups'] = list(user.groups.values_list('name', flat=True))
        return token