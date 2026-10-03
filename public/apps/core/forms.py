from django import forms
from django.utils import timezone

from .models import ContactMessage, TransportRequest, TransportVehicleType

INPUT_CLASS = 'w-full px-4 py-3 rounded bg-surface-container border border-outline-variant/40 text-on-surface outline-none focus:ring-2 focus:ring-primary focus:border-primary transition-all'


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
            field.widget.attrs['class'] = INPUT_CLASS + (' appearance-none pr-10' if is_select else '')

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


class ContactMessageForm(forms.ModelForm):
    class Meta:
        model = ContactMessage
        fields = ['full_name', 'phone', 'email', 'subject', 'message']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['full_name'].widget.attrs.update({'placeholder': 'Ex : Jean Kouadio', 'autocomplete': 'name'})
        self.fields['phone'].widget = forms.TextInput(attrs={'type': 'tel', 'placeholder': 'Ex : 07 00 00 00 00', 'autocomplete': 'tel'})
        self.fields['email'].widget.attrs.update({'placeholder': 'jean@email.ci (facultatif)', 'autocomplete': 'email'})
        self.fields['message'].widget = forms.Textarea(attrs={'rows': 5, 'placeholder': 'Dites-nous comment nous pouvons vous aider…'})
        self.fields['subject'].choices = [c for c in self.fields['subject'].choices if c[0] != ContactMessage.Subject.QUESTION]
        for field in self.fields.values():
            is_select = isinstance(field.widget, forms.Select)
            field.widget.attrs['class'] = INPUT_CLASS + (' appearance-none pr-10' if is_select else ' resize-none' if isinstance(field.widget, forms.Textarea) else '')


class QuestionForm(forms.Form):
    """« Poser une question » (fenêtre de la section FAQ) — question + téléphone ivoirien."""

    question = forms.CharField(max_length=2000)
    phone = forms.CharField(max_length=30)
    page = forms.CharField(max_length=300, required=False)

    def clean_question(self):
        value = self.cleaned_data['question'].strip()
        if len(value) < 5:
            raise forms.ValidationError('Votre question est trop courte.')
        return value

    def clean_phone(self):
        digits = ''.join(ch for ch in self.cleaned_data['phone'] if ch.isdigit())
        if digits.startswith('225') and len(digits) > 10:
            digits = digits[3:]
        if not 8 <= len(digits) <= 10:
            raise forms.ValidationError('Numéro de téléphone invalide.')
        return f'+225 {digits}'
