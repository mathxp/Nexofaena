from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from nexofaena.models.usuario import Usuario


class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get("email")

        if not email:
            return Response(
                {"detail": "Debe ingresar un correo."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            usuario = Usuario.objects.get(email=email)
        except Usuario.DoesNotExist:
            return Response(
                {"success": True, "message": "Si el correo existe, se enviará un enlace."},
                status=status.HTTP_200_OK,
            )

        uid = urlsafe_base64_encode(force_bytes(usuario.pk))
        token = default_token_generator.make_token(usuario)

        reset_url = f"http://localhost:5173/reset-password/{uid}/{token}"
        
        print("\nLINK LIMPIO DE RECUPERACIÓN:")
        print(reset_url)
        print("\n")

        send_mail(
            subject="Recuperación de contraseña - NexoFaena SGI",
            message=f"Para restablecer tu contraseña, ingresa al siguiente enlace:\n\n{reset_url}",
            from_email=None,
            recipient_list=[usuario.email],
            fail_silently=False,
        )

        return Response(
            {"success": True, "message": "Si el correo existe, se enviará un enlace."},
            status=status.HTTP_200_OK,
        )


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        uidb64 = request.data.get("uid")
        token = request.data.get("token")
        password = request.data.get("password")

        if not uidb64 or not token or not password:
            return Response(
                {"detail": "Datos incompletos."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if len(password) < 6:
            return Response(
                {"detail": "La contraseña debe tener al menos 6 caracteres."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            usuario = Usuario.objects.get(pk=uid)
        except Exception:
            return Response(
                {"detail": "Enlace inválido."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not default_token_generator.check_token(usuario, token):
            return Response(
                {"detail": "Token inválido o expirado."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        usuario.set_password(password)
        usuario.save(update_fields=["password"])

        return Response(
            {"success": True, "message": "Contraseña actualizada correctamente."},
            status=status.HTTP_200_OK,
        )