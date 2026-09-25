from django import forms

from .models import TransportVehicleTypeMirror


class TransportVehicleTypeForm(forms.ModelForm):
    class Meta:
        model = TransportVehicleTypeMirror
        fields = ['name', 'order']
        labels = {'name': 'Nom du type de véhicule', 'order': 'Ordre'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'px-4 py-3 rounded bg-surface-container outline-none focus:ring-2 focus:ring-primary'

    def validate_unique(self):
        # Le contrôle par défaut interrogerait l'alias 'default' au lieu de
        # 'public_db' ; clean_name() couvre l'unicité, la contrainte SQL en dernier recours.
        pass

    def clean_name(self):
        name = self.cleaned_data['name'].strip()
        qs = TransportVehicleTypeMirror.objects.using('public_db').filter(name__iexact=name)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('Ce type existe déjà.')
        return name
