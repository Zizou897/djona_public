from django import forms

from .models import Annonce


class AnnonceForm(forms.ModelForm):
    class Meta:
        model = Annonce
        fields = [
            'marque', 'modele', 'annee', 'prix',
            'kilometrage', 'carburant', 'boite_vitesses', 'couleur',
            'description',
        ]

    def clean(self):
        cleaned_data = super().clean()
        errors = []

        photos = self.files.getlist('photos')
        if len(photos) > 8:
            errors.append("Vous ne pouvez pas ajouter plus de 8 photos.")
        else:
            # AnnoncePhoto est créé directement par la vue via .objects.create(),
            # sans passer par un ModelForm — donc sans la validation Pillow que
            # forms.ImageField apporte normalement. On la déclenche ici pour
            # rejeter les fichiers non-image avant la sauvegarde.
            image_field = forms.ImageField()
            for photo in photos:
                try:
                    image_field.clean(photo)
                except forms.ValidationError:
                    errors.append(f"« {photo.name} » n'est pas une image valide.")

        if errors:
            raise forms.ValidationError(errors)

        return cleaned_data
