from rest_framework.routers import DefaultRouter

from .views import EndpointViewSet

router = DefaultRouter()
router.register("endpoints", EndpointViewSet, basename="endpoint")

urlpatterns = router.urls
