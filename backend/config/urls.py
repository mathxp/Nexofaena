from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from django.urls import path, include
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)


# ======================
# URLS
# ======================
urlpatterns = [

    # ======================
    # ADMIN
    # ======================
    path('admin/', admin.site.urls),
    path("api/", include("nexofaena.urls")),
    # ======================
    # AUTENTICACIÓN
    # ======================
    path('login/', auth_views.LoginView.as_view(template_name='auth/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),

    # Endpoints de Login con JWT (Sprint 1)
    path('api/login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]
# ======================
# STATIC FILES (DESARROLLO)
# ======================
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])