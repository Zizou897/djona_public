import re

from django import forms

from .models import SiteContactMirror

PHONE_RE = re.compile(r'^\+?[\d\s.\-]{8,20}$')


class SiteContactForm(forms.ModelForm):
    class Meta:
        model = SiteContactMirror
        fields = ['phone', 'whatsapp', 'email', 'address', 'city']
        help_texts = {
            'phone': 'Format conseillé : +225 01 41 60 27 53',
            'whatsapp': "Numéro utilisé pour le bouton « Écrire sur WhatsApp », avec l'indicatif pays.",
            'address': 'Ex : Angré 9ème tranche, non loin de CGK',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'w-full px-4 py-3 rounded bg-surface-container outline-none focus:ring-2 focus:ring-primary'

    def _clean_number(self, name):
        value = self.cleaned_data[name].strip()
        if not PHONE_RE.match(value) or sum(ch.isdigit() for ch in value) < 8:
            raise forms.ValidationError('Numéro invalide : chiffres, espaces et « + » uniquement.')
        return value

    def clean_phone(self):
        return self._clean_number('phone')

    def clean_whatsapp(self):
        value = self._clean_number('whatsapp')
        if not value.startswith('+'):
            raise forms.ValidationError("Indiquez l'indicatif pays (ex : +225 …) pour que le lien WhatsApp fonctionne.")
        return value
