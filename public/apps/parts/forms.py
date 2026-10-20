from django import forms
from django.utils import timezone

from .models import PartRequest

INPUT_CLASS = 'w-full px-4 py-3 rounded bg-surface-container border border-outline-variant/40 text-on-surface outline-none focus:ring-2 focus:ring-primary focus:border-primary transition-all'
MAX_PHOTO_BYTES = 5 * 1024 * 1024
FIRST_YEAR = 1960


class PartRequestForm(forms.ModelForm):
    """« Je ne trouve pas ma pièce » — champs et caractère obligatoire selon le
    cahier des charges Djona Parts (photo, motorisation et référence facultatifs)."""

    class Meta:
        model = PartRequest
        fields = ['full_name', 'phone', 'make', 'model', 'year', 'engine',
                  'part_name', 'part_reference', 'description', 'photo']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['full_name'].widget.attrs.update({'placeholder': 'Ex : Jean Kouadio', 'autocomplete': 'name'})
        self.fields['phone'].widget = forms.TextInput(attrs={'type': 'tel', 'placeholder': 'Ex : 07 00 00 00 00', 'autocomplete': 'tel'})
        self.fields['make'].widget.attrs.update({'placeholder': 'Ex : Toyota', 'list': 'parts-makes-list', 'autocomplete': 'off'})
        self.fields['model'].widget.attrs.update({'placeholder': 'Ex : Corolla', 'autocomplete': 'off'})
        self.fields['year'] = forms.IntegerField(
            label='Année', min_value=FIRST_YEAR, max_value=timezone.localdate().year + 1,
            widget=forms.NumberInput(attrs={'placeholder': 'Ex : 2015', 'inputmode': 'numeric'}),
        )
        self.fields['engine'].widget.attrs['placeholder'] = 'Ex : 1.6 essence (facultatif)'
        self.fields['part_name'].widget.attrs['placeholder'] = 'Ex : Plaquettes de frein avant'
        self.fields['part_reference'].widget.attrs['placeholder'] = 'Référence constructeur, si vous l’avez (facultatif)'
        self.fields['description'].widget = forms.Textarea(attrs={
            'rows': 4,
            'placeholder': 'Décrivez votre besoin : symptôme constaté, côté (avant/arrière, gauche/droite), quantité, etc.',
        })
        self.fields['photo'].widget = forms.ClearableFileInput(attrs={'accept': 'image/*'})
        self.fields['photo'].required = False
        for name in ('make', 'model', 'description'):
            self.fields[name].required = True  # facultatifs côté modèle (intérêt), obligatoires ici
        for name, field in self.fields.items():
            if name == 'photo':
                field.widget.attrs['class'] = 'block w-full text-sm text-on-surface-variant file:mr-4 file:rounded file:border-0 file:bg-primary/10 file:px-4 file:py-2.5 file:font-label-md file:text-primary hover:file:bg-primary/15'
                continue
            is_select = isinstance(field.widget, forms.Select)
            field.widget.attrs['class'] = INPUT_CLASS + (' appearance-none pr-10' if is_select else ' resize-none' if isinstance(field.widget, forms.Textarea) else '')

    def clean_phone(self):
        digits = ''.join(ch for ch in self.cleaned_data['phone'] if ch.isdigit())
        if digits.startswith('225') and len(digits) > 10:
            digits = digits[3:]
        if not 8 <= len(digits) <= 10:
            raise forms.ValidationError('Numéro de téléphone invalide.')
        return f'+225 {digits}'

    def clean_description(self):
        value = self.cleaned_data['description'].strip()
        if len(value) < 10:
            raise forms.ValidationError('Décrivez votre besoin en quelques mots (10 caractères minimum).')
        return value

    def clean_photo(self):
        photo = self.cleaned_data.get('photo')
        if photo and hasattr(photo, 'size') and photo.size > MAX_PHOTO_BYTES:
            raise forms.ValidationError('La photo ne doit pas dépasser 5 Mo.')
        return photo


class PartInterestForm(forms.Form):
    """« Je suis intéressé » sur une fiche pièce — même idée que pour un véhicule :
    nom + téléphone (+ message facultatif), pas de formulaire long."""

    name = forms.CharField(max_length=150)
    phone = forms.CharField(max_length=30)
    message = forms.CharField(max_length=1000, required=False)
    marque = forms.CharField(max_length=60, required=False)
    modele = forms.CharField(max_length=80, required=False)
    annee = forms.IntegerField(required=False, min_value=1950, max_value=2100)

    def clean_name(self):
        value = self.cleaned_data['name'].strip()
        if len(value) < 2:
            raise forms.ValidationError('Nom trop court.')
        return value

    def clean_phone(self):
        digits = ''.join(ch for ch in self.cleaned_data['phone'] if ch.isdigit())
        if digits.startswith('225') and len(digits) > 10:
            digits = digits[3:]
        if not 8 <= len(digits) <= 10:
            raise forms.ValidationError('Numéro de téléphone invalide.')
        return f'+225 {digits}'
