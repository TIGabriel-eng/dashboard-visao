from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.forms.widgets import CheckboxSelectMultiple
from django.utils.html import format_html

from core.models import Perfil, Curso, Plano, Trilha
from core.services.acesso import validar_role_planos, get_academias_permitidas_para_role

EMPRESA_PADRAO = 'Orcoma-Org. Comercial e Serviços'


class ImportarUsuariosForm(forms.Form):
    arquivo = forms.FileField(
        label='Arquivo Excel (.xlsx)',
        help_text='Selecione o arquivo Excel com os dados dos usuários.',
        widget=forms.FileInput(attrs={'accept': '.xlsx'}),
    )

    def clean_arquivo(self):
        arquivo = self.cleaned_data.get('arquivo')
        if arquivo:
            if not arquivo.name.endswith('.xlsx'):
                raise ValidationError('O arquivo deve ter extensão .xlsx')
            if arquivo.size > 10 * 1024 * 1024:
                raise ValidationError('O arquivo é muito grande. Tamanho máximo: 10MB.')
        return arquivo


class MembroOrcomaAddForm(UserCreationForm):
    first_name = forms.CharField(label='Primeiro Nome', max_length=30)
    last_name = forms.CharField(label='Último Nome', max_length=30)
    email = forms.EmailField(label='Endereço de Email')
    empresa = forms.CharField(
        label='Empresa',
        initial=EMPRESA_PADRAO,
        widget=forms.TextInput(attrs={'readonly': 'readonly', 'class': 'disabled'}),
    )
    unidade = forms.ChoiceField(
        label='Unidade',
        choices=Perfil.UNIDADE_CHOICES,
        required=True,
    )
    cargo = forms.CharField(
        label='Cargo',
        max_length=200,
        required=False,
        help_text='Exemplo: Analista de Customer',
    )
    telefone = forms.CharField(
        label='Telefone',
        max_length=20,
        required=False,
        help_text='Não obrigatório',
    )

    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'password1', 'password2')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].label = 'Usuário'
        self.fields['password1'].label = 'Senha'
        self.fields['password2'].label = 'Confirme a Senha'

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email and User.objects.filter(email=email).exists():
            raise ValidationError('Este endereço de email já está em uso.')
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.email = self.cleaned_data['email']
        user.is_staff = True
        user.is_superuser = True
        if commit:
            user.save()
            Perfil.objects.update_or_create(
                usuario=user,
                defaults={
                    'empresa': self.cleaned_data.get('empresa', EMPRESA_PADRAO),
                    'unidade': self.cleaned_data.get('unidade', ''),
                    'role': 'admin',
                    'cargo': self.cleaned_data.get('cargo', ''),
                    'telefone': self.cleaned_data.get('telefone', ''),
                },
            )
        return user


CLIENTE_ROLE_CHOICES = [c for c in Perfil.ROLE_CHOICES if c[0] in ('cliente_vex', 'cliente_premium', 'empresário', 'cliente_equipe', 'visitor')]


class ClienteAddForm(UserCreationForm):
    first_name = forms.CharField(label='Primeiro Nome', max_length=30)
    last_name = forms.CharField(label='Último Nome', max_length=30)
    email = forms.EmailField(label='Endereço de Email')
    is_empresario = forms.TypedChoiceField(
        label='É Empresário?',
        choices=[('True', 'Sim'), ('False', 'Não')],
        coerce=lambda x: x == 'True',
        initial='False',
        widget=forms.RadioSelect,
    )
    empresa = forms.CharField(label='Empresa', max_length=200, required=False)
    cnpj = forms.CharField(label='CNPJ', max_length=18, required=False)
    regime_federal = forms.ChoiceField(
        label='Regime Federal',
        choices=Perfil.REGIME_FEDERAL_CHOICES,
        required=False,
    )
    telefone = forms.CharField(label='Telefone Corporativo', max_length=20, required=False)
    role = forms.ChoiceField(
        label='Perfil',
        choices=CLIENTE_ROLE_CHOICES,
        initial='cliente_vex',
    )
    planos = forms.ModelMultipleChoiceField(
        label='Planos',
        queryset=Plano.objects.filter(ativo=True),
        required=False,
    )

    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'password1', 'password2')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].label = 'Usuário'
        self.fields['password1'].label = 'Senha'
        self.fields['password2'].label = 'Confirme a Senha'

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email and User.objects.filter(email=email).exists():
            raise ValidationError('Este endereço de email já está em uso.')
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
            Perfil.objects.update_or_create(
                usuario=user,
                defaults={
                    'empresa': self.cleaned_data.get('empresa', ''),
                    'is_empresario': self.cleaned_data.get('is_empresario', False),
                    'cnpj': self.cleaned_data.get('cnpj', ''),
                    'regime_federal': self.cleaned_data.get('regime_federal', ''),
                    'role': self.cleaned_data.get('role', 'cliente_vex'),
                    'telefone': self.cleaned_data.get('telefone', ''),
                },
            )
            perfil = user.perfil
            planos = self.cleaned_data.get('planos')
            if planos:
                perfil.planos.set(planos)
        return user


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


class CursoCardCheckboxSelectMultiple(CheckboxSelectMultiple):
    """CheckboxSelectMultiple que renderiza cada curso como um card com imagem e dados."""

    def __init__(self, attrs=None):
        super().__init__(attrs)
        self._cursos = {}

    def set_cursos(self, cursos):
        self._cursos = {str(c.pk): c for c in cursos}

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        curso = self._cursos.get(str(value))
        if curso is None:
            return option

        if curso.thumbnail:
            thumb = format_html(
                '<img class="cc-thumb" src="{}" alt="{}" loading="lazy">',
                curso.thumbnail.url,
                curso.titulo,
            )
        else:
            thumb = format_html(
                '<div class="cc-thumb cc-thumb--ph"><i class="fa-solid fa-video"></i></div>'
            )

        option['attrs']['class'] = 'cc-input'
        option['attrs']['data-status'] = curso.status
        option['label'] = format_html(
            '<div class="cc-card">'
            '{thumb}'
            '<span class="cc-check"><i class="fa-solid fa-check"></i></span>'
            '<span class="cc-tipo">{tipo}</span>'
            '<div class="cc-body">'
            '<span class="cc-title">{titulo}</span>'
            '<span class="cc-academy"><i class="fa-solid fa-building-columns"></i> {academy}</span>'
            '<span class="cc-status cc-status--{status}"><i class="fa-solid fa-circle"></i> {status_label}</span>'
            '</div>'
            '</div>',
            thumb=thumb,
            tipo=curso.get_tipo_display(),
            titulo=curso.titulo,
            academy=curso.ambiente.nome if curso.ambiente else 'Sem Academy',
            status=curso.status,
            status_label=curso.get_status_display(),
        )
        return option

    class Media:
        css = {'all': ('admin/css/trilha_cursos.css',)}


class TrilhaAdminForm(forms.ModelForm):
    class Meta:
        model = Trilha
        fields = '__all__'
        widgets = {'cursos': CursoCardCheckboxSelectMultiple}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        qs = self.fields['cursos'].queryset.select_related('ambiente')
        widget = self.fields['cursos'].widget
        # No admin o campo vira um RelatedFieldWidgetWrapper; o widget real fica em .widget
        if hasattr(widget, 'widget'):
            widget = widget.widget
        if hasattr(widget, 'set_cursos'):
            widget.set_cursos(qs)
