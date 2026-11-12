from django import forms
from django.utils import timezone

from .models import Interest
from .rental import rental_days


class InterestForm(forms.ModelForm):
    """« Je suis intéressé » / « Acheter avec Djona » / « Louer avec Djona ».

    Pour un véhicule à louer, les dates de début et de retour sont obligatoires et contrôlées ;
    pour une vente, elles sont ignorées (jamais enregistrées)."""

    class Meta:
        model = Interest
        fields = ['name', 'phone', 'message', 'rental_start', 'rental_end']

    def __init__(self, *args, vehicle=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.vehicle = vehicle
        self.fields['message'].required = False
        for name in ('rental_start', 'rental_end'):
            self.fields[name].required = False

    @property
    def is_rental(self):
        return bool(self.vehicle and self.vehicle.is_rental)

    def clean(self):
        cleaned = super().clean()
        if not self.is_rental:
            cleaned['rental_start'] = cleaned['rental_end'] = None
            return cleaned

        start, end = cleaned.get('rental_start'), cleaned.get('rental_end')
        if 'rental_start' in self.errors or 'rental_end' in self.errors:
            return cleaned  # format de date invalide : déjà signalé par le champ
        if not start or not end:
            raise forms.ValidationError('Indiquez la date de début et la date de retour de la location.', code='dates_required')
        if start < timezone.localdate():
            raise forms.ValidationError('La date de début ne peut pas être dans le passé.', code='start_past')
        if rental_days(start, end) < 1:
            raise forms.ValidationError('La date de retour doit être postérieure à la date de début.', code='end_before_start')
        return cleaned
