from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm

from usuarios.models import Perfil


# =====================================================
# 🔐 LOGIN
# =====================================================

def login_view(request):
    """
    Permite login con:
    - Username tradicional
    - RUT (si existe en Perfil)
    """

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        # 🔥 Intentar login con RUT
        try:
            perfil = Perfil.objects.get(rut=username)
            username = perfil.user.username  # reemplaza por username real
        except Perfil.DoesNotExist:
            pass  # si no es RUT, sigue como username normal

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            return redirect('dashboard')  # puedes cambiar a home si quieres
        else:
            messages.error(request, "Usuario o contraseña incorrectos")

    return render(request, 'auth/login.html')


# =====================================================
# 📝 REGISTRO
# =====================================================

def registro(request):
    """
    Registro básico de usuario usando UserCreationForm
    """

    form = UserCreationForm(request.POST or None)

    if form.is_valid():
        form.save()
        messages.success(request, "Cuenta creada correctamente")
        return redirect('login')

    return render(request, 'auth/registro.html', {'form': form})


# =====================================================
# 🏠 HOME
# =====================================================

@login_required
def home(request):
    """
    Vista principal protegida
    """
    return render(request, 'home.html')