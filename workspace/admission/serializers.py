from rest_framework import serializers
from .models import User, Application, Program, Department


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'email', 'role', 'created_at']
        extra_kwargs = {'password': {'write_only': True}}

    def create(self, validated_data):
        user = User(
            email=validated_data['email'],
            role=validated_data['role']
        )
        user.set_password(validated_data['password'])
        user.save()
        return user


class ApplicationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Application
        fields = ['id', 'user', 'program', 'department', 'status', 'submitted_at']
        read_only_fields = ['user', 'submitted_at']

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super(ApplicationSerializer, self).create(validated_data)


class ProgramSerializer(serializers.ModelSerializer):
    class Meta:
        model = Program
        fields = ['id', 'name', 'description', 'created_at']


class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ['id', 'name', 'description', 'created_at']
