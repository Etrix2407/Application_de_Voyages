"""RGPD (portabilité) : informations du compte d'un utilisateur, prêtes à être exportées."""

from accounts.models import User


def profile_data(user: User) -> dict:
    """Informations du compte, sans le mot de passe ni aucune donnée interne."""
    data = {
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.email,
        "date_joined": user.date_joined,
    }
    if user.is_client:
        data.update(
            {
                "phone": user.phone,
                "birth_date": user.birth_date,
                "consent_date": user.consent_date,
                "email_confirmed_at": user.email_confirmed_at,
            }
        )
    else:
        data["employee_number"] = user.employee_number
    return data
