from django import forms
from django.utils import timezone

from .models import TransportRequest, TransportVehicleType


class NewsletterForm(forms.Form):
    # Volontairement un forms.Form simple, pas un ModelForm : NewsletterSubscriber.email
    # est unique, et un ModelForm rejetterait une adresse déjà abonnée comme une erreur
    # de validation — alors que la vue doit pouvoir gérer ce cas elle-même (message
    # « déjà abonné » plutôt qu'une erreur).
    email = forms.EmailField()

QUANTITY_CHOICES = [('1', '1'), ('2', '2'), ('3', '3'), ('4', '4'), ('5', '5'), ('+5', '+5')]


class TransportRequestForm(forms.ModelForm):
    quantity = forms.ChoiceField(label='Nombre de véhicules souhaités', choices=QUANTITY_CHOICES)
    loading_date = forms.DateField(label='Date de chargement', widget=forms.DateInput(attrs={'type': 'date'}))

    class Meta:
        model = TransportRequest
        fields = [
            'last_name', 'first_name', 'phone', 'email', 'requester_type', 'company_name',
            'vehicle_type', 'quantity', 'loading_date', 'loading_place', 'delivery_place', 'message',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['vehicle_type'].queryset = TransportVehicleType.objects.filter(is_active=True)
        self.fields['vehicle_type'].empty_label = 'Sélectionnez un type de véhicule'
        self.fields['last_name'].widget.attrs['placeholder'] = 'Ex : Kouadio'
        self.fields['first_name'].widget.attrs['placeholder'] = 'Ex : Jean'
        self.fields['phone'].widget = forms.TextInput(attrs={'type': 'tel', 'placeholder': 'Ex : 07 00 00 00 00', 'autocomplete': 'tel'})
        self.fields['email'].widget.attrs['placeholder'] = 'jean@email.ci (facultatif)'
        self.fields['loading_place'].widget.attrs['placeholder'] = 'Ex : Abidjan – Yopougon'
        self.fields['delivery_place'].widget.attrs['placeholder'] = 'Ex : Bamako – Mali'
        self.fields['message'].widget = forms.Textarea(attrs={
            'rows': 5,
            'placeholder': 'Précisez ici toute information utile concernant votre transport : nature de la marchandise, contraintes particulières, horaires souhaités, etc.',
        })
        self.fields['requester_type'].label = 'Vous êtes'
        self.fields['loading_date'].widget.attrs['min'] = timezone.localdate().isoformat()
        for field in self.fields.values():
            is_select = isinstance(field.widget, forms.Select)
            field.widget.attrs['class'] = 'w-full px-4 py-3 rounded bg-surface-container text-on-surface outline-none focus:ring-2 focus:ring-primary transition-all' + (' appearance-none pr-10' if is_select else '')

    def clean_loading_date(self):
        value = self.cleaned_data['loading_date']
        if value < timezone.localdate():
            raise forms.ValidationError('La date de chargement ne peut pas être dans le passé.')
        return value

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('requester_type') == TransportRequest.RequesterType.COMPANY and not cleaned.get('company_name'):
            self.add_error('company_name', "Indiquez le nom de l'entreprise.")
        if cleaned.get('requester_type') != TransportRequest.RequesterType.COMPANY:
            cleaned['company_name'] = ''
        return cleaned
