# ======================
# DJANGO IMPORTS
# ======================
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User

# ======================
# FORMULARIOS
# ======================
from .form import UsuarioForm, UsuarioEditarForm

# ======================
# MODELOS
# ======================
from .models import Perfil


# =========================================================
# 📋 LISTAR USUARIOS
# =========================================================
@login_required
def lista_usuarios(request):
    usuarios = User.objects.all()
    return render(request, 'usuarios/lista.html', {'usuarios': usuarios})


# =========================================================
# ➕ CREAR USUARIO
# =========================================================
@login_required
def crear_usuario(request):

    form = UsuarioForm(request.POST or None)

    if form.is_valid():

        # ======================
        # CREAR USUARIO
        # ======================
        user = form.save(commit=False)
        user.set_password(form.cleaned_data['password'])
        user.save()

        # ======================
        # PERFIL (YA EXISTE POR SIGNAL)
        # ======================
        user.perfil.telefono = form.cleaned_data['telefono']
        user.perfil.rut = form.cleaned_data['rut']
        user.perfil.save()

        # ======================
        # ASIGNAR GRUPO
        # ======================
        grupo = form.cleaned_data['grupo']
        user.groups.add(grupo)

        # ======================
        # PERMISOS SEGÚN GRUPO
        # ======================
        if grupo.name == "Administrador":
            user.is_staff = True
            user.is_superuser = True

        elif grupo.name == "Bodega":
            user.is_staff = True
            user.is_superuser = False

        elif grupo.name == "Clinico":
            user.is_staff = False
            user.is_superuser = False

        user.save()

        return redirect('lista_usuarios')

    return render(request, 'usuarios/form.html', {'form': form})


# =========================================================
# ✏️ EDITAR USUARIO
# =========================================================
@login_required
def editar_usuario(request, id):

    usuario = get_object_or_404(User, id=id)
    perfil = usuario.perfil

    form = UsuarioEditarForm(request.POST or None, instance=usuario)

    # ======================
    # PRE-CARGA DE DATOS
    # ======================
    if request.method == 'GET':
        form.fields['telefono'].initial = perfil.telefono
        form.fields['rut'].initial = perfil.rut
        form.fields['grupo'].initial = usuario.groups.first()

    if form.is_valid():

        form.save()

        # ======================
        # ACTUALIZAR PERFIL
        # ======================
        perfil.telefono = form.cleaned_data['telefono']
        perfil.rut = form.cleaned_data['rut']
        perfil.save()

        # ======================
        # ACTUALIZAR GRUPO
        # ======================
        usuario.groups.clear()
        usuario.groups.add(form.cleaned_data['grupo'])

        return redirect('lista_usuarios')

    return render(request, 'usuarios/form.html', {'form': form})


# =========================================================
# ❌ ELIMINAR USUARIO
# =========================================================
@login_required
def eliminar_usuario(request, id):

    usuario = get_object_or_404(User, id=id)
    usuario.delete()

    return redirect('lista_usuarios')