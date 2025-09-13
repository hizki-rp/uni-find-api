from rest_framework import serializers
from .models import University
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError


class UserSerializer(serializers.ModelSerializer):
    # Add the email field so the serializer will accept it
    email = serializers.EmailField(required=True)

    class Meta:
        model = User
        # Add 'email' to the list of fields
        fields = ["id", "username", "email", "password"]
        extra_kwargs = {"password": {"write_only": True}}

    def create(self, validated_data):
        # Use create_user to properly hash the password
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password']
        )
        return user

class UniversitySerializer(serializers.ModelSerializer):
    class Meta:
        model = University
        fields = '__all__'