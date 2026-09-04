import shutil
from pathlib import Path

from decouple import config
from django.conf import settings
from django.core.management.base import BaseCommand

from apps.catalog.models import Seller, Vehicle, VehicleImage
from apps.vendor_sync.models import AnnonceMirror, AnnoncePhotoMirror, ProfilMirror

# Le schéma `annonces` (djona_vendor) n'a pas encore de champ ville/état — voir
# discussion avec le projet vendor. Valeurs par défaut en attendant.
DEFAULT_CITY = 'Abidjan'
DEFAULT_CONDITION = Vehicle.Condition.OCCASION

VENDOR_MEDIA_ROOT = config('VENDOR_MEDIA_ROOT', default='')


class Command(BaseCommand):
    help = "Synchronise les annonces validées (statut='publiee') depuis djona_vendor vers le catalogue public, photos et vendeur inclus."

    def handle(self, *args, **options):
        annonces = AnnonceMirror.objects.using('vendor_db').filter(
            statut=AnnonceMirror.Statut.PUBLIEE,
        ).select_related('vendeur')

        created, updated, photos_synced = 0, 0, 0
        for annonce in annonces:
            seller = self._sync_seller(annonce.vendeur)

            description = annonce.description
            if annonce.couleur:
                description = f'{description}\n\nCouleur : {annonce.couleur}'.strip()

            # 'publish' est volontairement absent de defaults : sur update, on ne
            # touche jamais à la visibilité marketplace décidée par l'admin (voir
            # moderation.views côté admin, toggle indépendant du statut) — sur
            # create, le champ prend son défaut de modèle (True). Seule la
            # dépublication automatique ci-dessous (annonce plus publiee) prime
            # sur ce choix admin.
            vehicle, was_created = Vehicle.objects.update_or_create(
                source_annonce_id=annonce.id,
                defaults={
                    'brand': annonce.marque,
                    'model_name': annonce.modele,
                    'year': annonce.annee,
                    'price': annonce.prix,
                    'mileage': annonce.kilometrage,
                    'fuel_type': annonce.carburant,
                    'transmission': annonce.boite_vitesses,
                    'description': description,
                    'city': DEFAULT_CITY,
                    'condition': DEFAULT_CONDITION,
                    'seller': seller,
                },
            )
            created += was_created
            updated += not was_created

            photos_synced += self._sync_photos(annonce, vehicle)

        # Une annonce redevenue non publiée (refusée/dépubliée après une synchro
        # précédente) ne doit plus apparaître sur le site.
        valid_ids = list(annonces.values_list('id', flat=True))
        unpublished = (
            Vehicle.objects.filter(source_annonce_id__isnull=False)
            .exclude(source_annonce_id__in=valid_ids)
            .update(publish=False)
        )

        self.stdout.write(self.style.SUCCESS(
            f'{created} créée(s), {updated} mise(s) à jour, {photos_synced} photo(s) copiée(s), '
            f'{unpublished} dépubliée(s).'
        ))

    def _sync_seller(self, vendeur):
        profil = ProfilMirror.objects.using('vendor_db').filter(user_id=vendeur.pk).first()

        seller, _ = Seller.objects.update_or_create(
            source_vendeur_id=vendeur.pk,
            defaults={
                'first_name': vendeur.prenom,
                'last_name': vendeur.nom,
                'phone': vendeur.telephone,
                'type_compte': vendeur.type_compte,
                'company_name': profil.raison_sociale if profil else '',
                'city': profil.ville if profil else '',
                'member_since': vendeur.date_joined,
            },
        )

        if profil and profil.avatar:
            self._sync_logo(profil, seller)

        return seller

    def _sync_logo(self, profil, seller):
        if not VENDOR_MEDIA_ROOT:
            return

        filename = Path(profil.avatar.name).name
        dest_relative = f'sellers/{seller.source_vendeur_id}/{filename}'
        if seller.logo and seller.logo.name == dest_relative:
            return  # déjà synchronisé, rien à refaire

        source_path = Path(VENDOR_MEDIA_ROOT) / profil.avatar.name
        if not source_path.exists():
            self.stderr.write(self.style.WARNING(f'Logo introuvable sur disque, ignoré : {source_path}'))
            return

        dest_dir = Path(settings.MEDIA_ROOT) / 'sellers' / str(seller.source_vendeur_id)
        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, dest_dir / filename)
        seller.logo = dest_relative
        seller.save(update_fields=['logo'])

    def _sync_photos(self, annonce, vehicle):
        if not VENDOR_MEDIA_ROOT:
            return 0

        vendor_media_root = Path(VENDOR_MEDIA_ROOT)
        dest_dir = Path(settings.MEDIA_ROOT) / 'vehicles' / f'annonce-{annonce.id}'
        existing = set(vehicle.images.values_list('image', flat=True))

        synced = 0
        photos = AnnoncePhotoMirror.objects.using('vendor_db').filter(annonce_id=annonce.id).order_by('ordre')
        for photo in photos:
            filename = Path(photo.image.name).name
            dest_relative = f'vehicles/annonce-{annonce.id}/{filename}'
            if dest_relative in existing:
                continue

            source_path = vendor_media_root / photo.image.name
            if not source_path.exists():
                self.stderr.write(self.style.WARNING(f'Photo introuvable sur disque, ignorée : {source_path}'))
                continue

            dest_dir.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source_path, dest_dir / filename)
            VehicleImage.objects.create(vehicle=vehicle, image=dest_relative, order=photo.ordre)
            synced += 1

        return synced
