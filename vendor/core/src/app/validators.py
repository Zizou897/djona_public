import re
from django.core.exceptions import ValidationError


class ComplexiteMotDePasseValidator:
    """Impose une majuscule et un chiffre, promis par le formulaire d'inscription."""

    def validate(self, password, user=None):
        if not re.search(r'[A-Z]', password):
            raise ValidationError(
                'Le mot de passe doit contenir au moins une majuscule.',
                code='password_no_upper',
            )
        if not re.search(r'\d', password):
            raise ValidationError(
                'Le mot de passe doit contenir au moins un chiffre.',
                code='password_no_digit',
            )

    def get_help_text(self):
        return 'Le mot de passe doit contenir au moins une majuscule et un chiffre.'
