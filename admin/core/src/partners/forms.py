from django import forms

from .models import PartnerMirror


class PartnerForm(forms.ModelForm):
    class Meta:
        model = PartnerMirror
        fields = ['name', 'logo', 'website_url', 'order', 'publish']
