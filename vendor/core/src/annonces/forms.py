from django import forms

from .models import Annonce

MIN_PHOTOS = 3
MAX_PHOTOS = 4
# Doit rester alignée avec DATA_UPLOAD_MAX_MEMORY_SIZE/FILE_UPLOAD_MAX_MEMORY_SIZE
# (core/settings.py) et client_max_body_size (nginx, site vendor.djona.tech) —
# ces deux-là bornent la taille TOTALE de la requête (MAX_PHOTOS * MAX_PHOTO_SIZE
# + marge), pas la taille par fichier. La limite par image, elle, ne vit qu'ici.
MAX_PHOTO_SIZE = 4 * 1024 * 1024  # 4 Mo par image


class AnnonceForm(forms.ModelForm):
    class Meta:
        model = Annonce
        fields = [
            'marque', 'modele', 'annee', 'type_annonce', 'prix', 'prix_jour', 'prix_semaine', 'prix_mois', 'caution',
            'kilometrage', 'carburant', 'boite_vitesses', 'couleur',
            'etat', 'ville', 'description',
        ]

    def __init__(self, *args, exiger_photos_minimum=False, nb_photos_conservees=0, **kwargs):
        # exiger_photos_minimum : True quand l'annonce part directement en
        # validation (action=soumettre), à la création comme à la modification.
        # nb_photos_conservees : photos déjà enregistrées que la modification
        # garde — elles comptent dans les bornes MIN_PHOTOS / MAX_PHOTOS.
        self.exiger_photos_minimum = exiger_photos_minimum
        self.nb_photos_conservees = nb_photos_conservees
        super().__init__(*args, **kwargs)
        self.fields['etat'].required = True
        self.fields['ville'].required = True
        # Le prix de vente n'est exigé que pour une vente ; une location demande
        # au moins un tarif (jour, semaine ou mois), au choix du vendeur.
        self.fields['prix'].required = False
        self.fields['type_annonce'].required = False

    def clean(self):
        cleaned_data = super().clean()
        errors = []
        self.valider_tarifs(cleaned_data)

        photos = self.files.getlist('photos')
        total = self.nb_photos_conservees + len(photos)
        if self.exiger_photos_minimum and total < MIN_PHOTOS:
            errors.append(f"Ajoutez au moins {MIN_PHOTOS} photos pour soumettre votre annonce à validation.")

        if total > MAX_PHOTOS:
            errors.append(f"Une annonce ne peut pas avoir plus de {MAX_PHOTOS} photos.")
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
                    continue

                if photo.size > MAX_PHOTO_SIZE:
                    taille_mo = photo.size / (1024 * 1024)
                    errors.append(
                        f"« {photo.name} » fait {taille_mo:.1f} Mo — chaque image doit faire 4 Mo maximum."
                    )

        if errors:
            raise forms.ValidationError(errors)

        return cleaned_data

    def valider_tarifs(self, cleaned_data):
        """Vente : prix de vente obligatoire. Location : au moins un tarif ; le prix
        de vente vaut alors 0 et la caution est facultative."""
        type_annonce = cleaned_data.get('type_annonce') or Annonce.TypeAnnonce.VENTE
        cleaned_data['type_annonce'] = type_annonce
        champs_location = ('prix_jour', 'prix_semaine', 'prix_mois', 'caution')
        if type_annonce == Annonce.TypeAnnonce.LOCATION:
            for nom in champs_location:
                if cleaned_data.get(nom) == 0:
                    self.add_error(nom, 'Indiquez un montant supérieur à 0, ou laissez vide.')
            if not any(cleaned_data.get(nom) for nom in ('prix_jour', 'prix_semaine', 'prix_mois')):
                self.add_error('prix_jour', 'Indiquez au moins un tarif : par jour, par semaine ou par mois.')
            cleaned_data['prix'] = 0
        else:
            if not cleaned_data.get('prix'):
                self.add_error('prix', 'Indiquez le prix de vente.')
            for nom in champs_location:
                cleaned_data[nom] = None
