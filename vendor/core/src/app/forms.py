from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.forms import AuthenticationForm

from .models import Profil, Utilisateur, telephone_validator


class InscriptionForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput, label='Mot de passe')
    consentement = forms.BooleanField(
        label="J'accepte les conditions d'utilisation et la politique de confidentialité.",
        error_messages={'required': "Vous devez accepter les conditions d'utilisation pour continuer."},
    )

    class Meta:
        model = Utilisateur
        fields = ['nom', 'prenom', 'email', 'telephone', 'type_compte']

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if Utilisateur.objects.filter(email=email).exists():
            raise forms.ValidationError('Un compte existe déjà avec cet email.')
        return email

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        if password:
            # La similarité mot de passe / attributs utilisateur nécessite une
            # instance : on en construit une transitoire (non sauvegardée)
            # avec les champs déjà validés.
            candidat = Utilisateur(
                email=cleaned_data.get('email', ''),
                nom=cleaned_data.get('nom', ''),
                prenom=cleaned_data.get('prenom', ''),
            )
            try:
                password_validation.validate_password(password, user=candidat)
            except forms.ValidationError as error:
                self.add_error('password', error)
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
        return user


class ConnexionForm(AuthenticationForm):
    error_messages = {
        **AuthenticationForm.error_messages,
        'invalid_login': 'Email ou mot de passe incorrect.',
        'inactive': 'Ce compte est désactivé.',
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget = forms.EmailInput()
        self.fields['username'].label = 'Adresse email'


class UtilisateurInfoForm(forms.Form):
    nom_complet = forms.CharField(max_length=150, label='Nom complet')
    email = forms.EmailField(label='Email')
    telephone = forms.CharField(
        max_length=10,
        validators=[telephone_validator],
        label='Numéro de téléphone',
    )
    type_compte = forms.ChoiceField(
        choices=Utilisateur.TypeCompte.choices,
        label='Type de compte',
        required=False,
    )

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        query = Utilisateur.objects.filter(email=email)
        if self.user:
            query = query.exclude(pk=self.user.pk)
        if query.exists():
            raise forms.ValidationError('Un compte existe déjà avec cet email.')
        return email

    def save(self, user):
        nom_complet = self.cleaned_data['nom_complet'].strip()
        prenom, _, nom = nom_complet.partition(' ')
        user.prenom = prenom
        user.nom = nom
        user.email = self.cleaned_data['email']
        user.telephone = self.cleaned_data['telephone']
        if self.cleaned_data.get('type_compte'):
            user.type_compte = self.cleaned_data['type_compte']
        user.save(update_fields=['prenom', 'nom', 'email', 'telephone', 'type_compte'])


class ProfilForm(forms.ModelForm):
    class Meta:
        model = Profil
        fields = [
            'ville', 'avatar',
            'two_factor_enabled', 'langue', 'notif_email', 'notif_whatsapp',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['langue'].required = False
        self.fields['ville'].required = False

    def clean_langue(self):
        return self.cleaned_data.get('langue') or Profil.Langue.FRANCAIS

