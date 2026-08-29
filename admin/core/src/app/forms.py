from django import forms

from .models import Profil


class UtilisateurInfoForm(forms.Form):
    nom_complet = forms.CharField(max_length=150, label='Nom complet')
    email = forms.EmailField(label='Email')

    def save(self, user):
        nom_complet = self.cleaned_data['nom_complet'].strip()
        prenom, _, nom = nom_complet.partition(' ')
        user.first_name = prenom
        user.last_name = nom
        user.email = self.cleaned_data['email']
        user.save(update_fields=['first_name', 'last_name', 'email'])


class ProfilForm(forms.ModelForm):
    class Meta:
        model = Profil
        fields = [
            'telephone', 'ville', 'avatar',
            'two_factor_enabled', 'langue', 'notif_email', 'notif_whatsapp',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # `langue` has a model-level default but no `blank=True`, so Django's
        # ModelForm would otherwise mark it required. Treat it like the other
        # profile fields: optional in the form, falling back to the default.
        self.fields['langue'].required = False

    def clean_langue(self):
        return self.cleaned_data.get('langue') or Profil.Langue.FRANCAIS
