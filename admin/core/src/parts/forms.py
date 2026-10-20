from django import forms

from .importer import parse_compatibilities
from .models import PartCategoryMirror, PartMirror, PartRequestMirror

INPUT_CLASS = (
    'w-full px-4 py-3 rounded-lg border border-outline-variant bg-surface-container-lowest '
    'focus:border-primary focus:ring-2 focus:ring-primary/10 outline-none transition-all'
)
# Mêmes règles que les annonces de véhicules (moderation/forms.py) : 3 photos au minimum à la
# création (la pièce est publiée tout de suite), 4 au maximum, 4 Mo chacune.
MIN_PHOTOS = 3
MAX_PHOTOS = 4
MAX_PHOTO_BYTES = 4 * 1024 * 1024


def style(form):
    for field in form.fields.values():
        if isinstance(field.widget, (forms.CheckboxInput, forms.ClearableFileInput)):
            continue
        field.widget.attrs['class'] = INPUT_CLASS


class PartCategoryForm(forms.ModelForm):
    class Meta:
        model = PartCategoryMirror
        fields = ['name', 'icon', 'order']
        labels = {'name': 'Nom de la catégorie', 'icon': 'Icône', 'order': 'Ordre'}
        help_texts = {'icon': 'Nom Material Symbols (ex : speed, build, lightbulb).'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style(self)

    def validate_unique(self):
        pass  # contrôlé dans clean_name sur public_db

    def clean_name(self):
        name = self.cleaned_data['name'].strip()
        qs = PartCategoryMirror.objects.using('public_db').filter(name__iexact=name)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('Cette catégorie existe déjà.')
        return name

    def clean_icon(self):
        icon = self.cleaned_data['icon'].strip().lower()
        if not icon.replace('_', '').isalnum():
            raise forms.ValidationError("Nom d'icône invalide : lettres, chiffres et « _ » uniquement.")
        return icon


class PartForm(forms.ModelForm):
    compatibilities = forms.CharField(
        label='Véhicules compatibles', required=False,
        widget=forms.Textarea(attrs={'rows': 5, 'placeholder': 'Toyota / Corolla / 2014 / 2019 / 1.6 essence\nHyundai / Accent / 2012 / 2016\nPeugeot'}),
        help_text='Un véhicule par ligne : Marque / Modèle / Année début / Année fin / Motorisation. '
                  'Seule la marque est obligatoire ; un modèle vide = toute la marque.',
    )

    class Meta:
        model = PartMirror
        fields = ['reference', 'name', 'category', 'manufacturer_reference', 'brand', 'condition', 'price',
                  'availability', 'warranty', 'lead_time', 'description', 'is_featured', 'is_active']
        widgets = {'description': forms.Textarea(attrs={'rows': 4})}
        help_texts = {
            'reference': 'Identifiant unique de la pièce chez Djona.',
            'condition': "Laissez vide si l'état n'est pas connu : le site affichera « Non précisé ».",
            'price': 'Laissez vide pour afficher « Prix sur demande ».',
            'availability': "Ne choisissez « Disponible » que si la disponibilité est confirmée.",
            'lead_time': 'Uniquement si le délai est connu et fiable.',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].queryset = PartCategoryMirror.objects.using('public_db').all()
        self.fields['category'].empty_label = 'Choisir une catégorie'
        self.fields['condition'].choices = [('', 'Non précisé')] + list(PartMirror.Condition.choices)
        style(self)

    def validate_unique(self):
        pass  # contrôlé dans clean_reference sur public_db

    def clean_reference(self):
        reference = self.cleaned_data['reference'].strip()
        qs = PartMirror.objects.using('public_db').filter(reference__iexact=reference)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('Cette référence existe déjà.')
        return reference

    def clean_compatibilities(self):
        try:
            return parse_compatibilities(self.cleaned_data['compatibilities'])
        except ValueError as exc:
            raise forms.ValidationError(str(exc))


class PartRequestFollowUpForm(forms.ModelForm):
    class Meta:
        model = PartRequestMirror
        fields = ['status', 'proposed_price', 'proposed_lead_time', 'internal_note']
        labels = {
            'status': 'Statut', 'proposed_price': 'Prix proposé (FCFA)',
            'proposed_lead_time': 'Délai proposé', 'internal_note': 'Note interne',
        }
        widgets = {'internal_note': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Échanges avec le partenaire, rappels…'})}
        help_texts = {'internal_note': 'Visible uniquement par le staff.'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style(self)


class PartImportForm(forms.Form):
    file = forms.FileField(label='Fichier CSV', widget=forms.ClearableFileInput(attrs={'accept': '.csv,text/csv'}))

    def clean_file(self):
        upload = self.cleaned_data['file']
        if not upload.name.lower().endswith('.csv'):
            raise forms.ValidationError('Le fichier doit être au format CSV (.csv).')
        return upload
