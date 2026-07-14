from django import forms
from django.core.exceptions import ValidationError

from core.models import Perfil, Curso
from core.services.acesso import validar_role_planos, get_academias_permitidas_para_role


class PerfilInlineForm(forms.ModelForm):
    class Meta:
        model = Perfil
        fields = '__all__'

    def clean(self):
        cleaned = super().clean()
        role = cleaned.get('role')
        if not role:
            return cleaned

        planos = cleaned.get('planos')
        if planos is not None:
            erro = validar_role_planos(role, planos)
            if erro:
                raise ValidationError(erro)

        return cleaned


class CursoAdminForm(forms.ModelForm):
    roles_extras = forms.MultipleChoiceField(
        choices=Perfil.ROLE_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label='Perfis extras com acesso',
        help_text='Além da academy principal, libere acesso para perfis específicos.',
    )

    class Meta:
        model = Curso
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and self.instance.roles_extras:
            self.initial['roles_extras'] = self.instance.roles_extras

    def clean(self):
        cleaned = super().clean()
        is_gratuito = cleaned.get('is_gratuito')
        ambiente = cleaned.get('ambiente')
        status = cleaned.get('status')

        if status == 'publicado' and not is_gratuito and not ambiente:
            raise ValidationError(
                'Cursos restritos publicados precisam de uma Academy vinculada '
                'ou ser marcados como gratuitos.'
            )
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.roles_extras = self.cleaned_data.get('roles_extras') or []
        if commit:
            instance.save()
            self.save_m2m()
        return instance
