from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from django.urls import path, include

from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
)

urlpatterns = [

    # =====================================
    # ADMIN
    # =====================================
    path("admin/", admin.site.urls),

    # =====================================
    # AUTENTICACIÓN DJANGO
    # =====================================
    path(
        "login/",
        auth_views.LoginView.as_view(
            template_name="auth/login.html"
        ),
        name="login",
    ),
    path(
        "logout/",
        auth_views.LogoutView.as_view(),
        name="logout",
    ),

    # =====================================
    # JWT
    # =====================================
    path(
        "api/login/",
        TokenObtainPairView.as_view(),
        name="token_obtain_pair",
    ),

    # ESTA ES LA RUTA QUE LE FALTABA AL FRONTEND
    path(
        "api/token/",
        TokenObtainPairView.as_view(),
        name="token_obtain_pair_api",
    ),

    path(
        "api/token/refresh/",
        TokenRefreshView.as_view(),
        name="token_refresh",
    ),

    # =====================================
    # API DEL PROYECTO
    # =====================================
    path(
        "api/",
        include("nexofaena.urls"),
    ),

    # =====================================
    # SWAGGER
    # =====================================
    path(
        "api/schema/",
        SpectacularAPIView.as_view(),
        name="schema",
    ),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(
            url_name="schema"
        ),
        name="swagger-ui",
    ),
]


# =====================================
# ARCHIVOS ESTÁTICOS (SOLO DESARROLLO)
# =====================================
if settings.DEBUG:
    urlpatterns += static(
        settings.STATIC_URL,
        document_root=settings.STATIC_ROOT,
    )