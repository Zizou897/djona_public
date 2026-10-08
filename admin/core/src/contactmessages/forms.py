import re
from urllib.parse import urlparse

from django import forms

from .models import SiteContactMirror

PHONE_RE = re.compile(r'^\+?[\d\s.\-]{8,20}$')
SOCIAL_DOMAINS = {
    'facebook_url': ('facebook.com', 'fb.com', 'fb.me'),
    'instagram_url': ('instagram.com',),
    'tiktok_url': ('tiktok.com',),
    'linkedin_url': ('linkedin.com',),
}


class SiteContactForm(forms.ModelForm):
    class Meta:
        model = SiteContactMirror
        fields = ['phone', 'whatsapp', 'email', 'address', 'city',
                  'facebook_url', 'instagram_url', 'tiktok_url', 'linkedin_url']
        help_texts = {
            'phone': 'Format conseillé : +225 01 41 60 27 53',
            'whatsapp': "Numéro utilisé pour le bouton « Écrire sur WhatsApp », avec l'indicatif pays.",
            'address': 'Ex : Angré 9ème tranche, non loin de CGK',
            'facebook_url': 'Ex : https://www.facebook.com/djonagroup — laisser vide pour masquer.',
            'instagram_url': 'Ex : https://www.instagram.com/djonagroup — laisser vide pour masquer.',
            'tiktok_url': 'Ex : https://www.tiktok.com/@djonagroup — laisser vide pour masquer.',
            'linkedin_url': 'Ex : https://www.linkedin.com/company/djonagroup — laisser vide pour masquer.',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = (
                'w-full px-4 py-3 rounded-lg border border-outline-variant bg-surface-container-lowest '
                'focus:border-primary focus:ring-2 focus:ring-primary/10 outline-none transition-all'
            )

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

    def _clean_social(self, name):
        value = self.cleaned_data[name].strip()
        if not value:
            return ''
        host = (urlparse(value).hostname or '').lower()
        if not any(host == d or host.endswith('.' + d) for d in SOCIAL_DOMAINS[name]):
            raise forms.ValidationError(f'Ce lien doit pointer vers {SOCIAL_DOMAINS[name][0]}.')
        return value

    def clean_facebook_url(self):
        return self._clean_social('facebook_url')

    def clean_instagram_url(self):
        return self._clean_social('instagram_url')

    def clean_tiktok_url(self):
        return self._clean_social('tiktok_url')

    def clean_linkedin_url(self):
        return self._clean_social('linkedin_url')
