from django import forms
from django.contrib.auth import password_validation

from annonces.models import Annonce
from app.models import Utilisateur, telephone_validator

from .models import MembreEquipe, Prospect


class MembreEquipeForm(forms.Form):
    prenom = forms.CharField(max_length=100, label='Prénom')
    nom = forms.CharField(max_length=100, label='Nom')
    email = forms.EmailField(label='Email')
    telephone = forms.CharField(max_length=10, validators=[telephone_validator], label='Téléphone')
    role = forms.ChoiceField(choices=MembreEquipe.Role.choices, label='Rôle')
    password = forms.CharField(widget=forms.PasswordInput, label='Mot de passe temporaire')

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if Utilisateur.objects.filter(email=email).exists():
            raise forms.ValidationError('Un compte existe déjà avec cet email.')
        return email

    def clean_password(self):
        password = self.cleaned_data['password']
        candidat = Utilisateur(
            email=self.cleaned_data.get('email', ''),
            nom=self.cleaned_data.get('nom', ''),
            prenom=self.cleaned_data.get('prenom', ''),
        )
        password_validation.validate_password(password, user=candidat)
        return password

    def save(self, compte_pro):
        membre = Utilisateur.objects.create_user(
            email=self.cleaned_data['email'],
            password=self.cleaned_data['password'],
            nom=self.cleaned_data['nom'],
            prenom=self.cleaned_data['prenom'],
            telephone=self.cleaned_data['telephone'],
            type_compte=Utilisateur.TypeCompte.PARTICULIER,
            statut_compte=Utilisateur.StatutCompte.ACTIF,
        )
        return MembreEquipe.objects.create(
            compte_pro=compte_pro, membre=membre, role=self.cleaned_data['role'],
        )


class ProspectForm(forms.ModelForm):
    class Meta:
        model = Prospect
        fields = ['nom', 'telephone', 'email', 'annonce', 'notes']

    def __init__(self, *args, compte_pro=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['telephone'].required = False
        self.fields['email'].required = False
        self.fields['annonce'].required = False
        self.fields['notes'].required = False
        self.fields['annonce'].queryset = Annonce.objects.filter(
            vendeur=compte_pro,
        ) if compte_pro else Annonce.objects.none()

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data.get('telephone') and not cleaned_data.get('email'):
            raise forms.ValidationError('Indiquez au moins un téléphone ou un email pour recontacter ce prospect.')
        return cleaned_data
