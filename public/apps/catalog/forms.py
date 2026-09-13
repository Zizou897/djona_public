from django import forms

from .models import Interest


class InterestForm(forms.ModelForm):
    class Meta:
        model = Interest
        fields = ['name', 'phone', 'message']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['message'].required = False
