from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import UserViewSet, ApplicationViewSet, ProgramViewSet, DepartmentViewSet

router = DefaultRouter()
router.register(r'users', UserViewSet, basename='user')
router.register(r'applications', ApplicationViewSet, basename='application')
router.register(r'programs', ProgramViewSet, basename='program')
router.register(r'departments', DepartmentViewSet, basename='department')

urlpatterns = [
    path('', include(router.urls)),
]
