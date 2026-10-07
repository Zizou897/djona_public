def espace_vendeur(request):
    """Expose le type d'espace (particulier / pro) et le rôle de l'utilisateur
    à la navigation partagée (`app/includes/sidebar_vendeur.html`)."""
    user = getattr(request, 'user', None)
    if user is None or not user.is_authenticated:
        return {}

    rattachement = getattr(user, 'rattachement_pro', None)
    est_membre = bool(rattachement and rattachement.actif)
    role = rattachement.role if est_membre else ''
    return {
        'espace_vendeur': {
            'est_pro': user.is_pro_ou_membre,
            'est_membre': est_membre,
            'role_libelle': rattachement.get_role_display() if est_membre else '',
            'lecture_seule': role == 'lecture_seule',
            'compte_pro_nom': rattachement.compte_pro.get_full_name() if est_membre else '',
        }
    }
