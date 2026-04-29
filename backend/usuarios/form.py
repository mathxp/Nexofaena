from django import forms
from django.contrib.auth.models import User, Group
from .models import Perfil

class UsuarioForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput)

    telefono = forms.CharField()
    rut = forms.CharField()

    grupo = forms.ModelChoiceField(
        queryset=Group.objects.all(),
        required=True,
        label="Rol"
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'first_name', 'last_name']


class UsuarioEditarForm(forms.ModelForm):
    telefono = forms.CharField()
    rut = forms.CharField()

    grupo = forms.ModelChoiceField(
        queryset=Group.objects.all(),
        required=True,
        label="Rol"
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name']