"""E-mails de marque Djona : la version texte reste celle écrite par l'appelant, la version HTML
(gabarits templates/emails/) y est ajoutée pour les clients mail qui l'affichent."""
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string


def admin_url(path):
    """Lien absolu vers une page du back-office (« /pieces/commandes/12/ »)."""
    return f'{settings.ADMIN_SITE_URL}{path}'


def send_branded_email(subject, text_body, template, context, recipients):
    """Envoie `text_body` avec une alternative HTML rendue depuis `template`.

    N'échoue jamais bruyamment (fail_silently) : les appelants enregistrent déjà la demande en base."""
    html = render_to_string(template, {
        'subject': subject,
        'site_url': settings.SITE_URL,
        **context,
    })
    message = EmailMultiAlternatives(subject, text_body, None, list(recipients))
    message.attach_alternative(html, 'text/html')
    message.send(fail_silently=True)
