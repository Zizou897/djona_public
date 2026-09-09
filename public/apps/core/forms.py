from django import forms


class NewsletterForm(forms.Form):
    # Volontairement un forms.Form simple, pas un ModelForm : NewsletterSubscriber.email
    # est unique, et un ModelForm rejetterait une adresse déjà abonnée comme une erreur
    # de validation — alors que la vue doit pouvoir gérer ce cas elle-même (message
    # « déjà abonné » plutôt qu'une erreur).
    email = forms.EmailField()
