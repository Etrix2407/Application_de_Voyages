"""Trace anonyme des comptes clients supprimés (voir DeletedClientAccount)."""

from accounts.models import DeletedClientAccount, User


def record_deleted_client(user: User) -> None:
    """Enregistre la trace d'un compte client confirmé, juste avant sa suppression.

    Un compte du personnel ou un compte client jamais confirmé n'est pas tracé.
    """
    if not user.is_client or user.email_confirmed_at is None:
        return
    # Relation inverse déclarée par orders (related_name="orders"), sans importer cette application :
    # accounts ne dépend pas de orders (ordre des applications). Appelée depuis un signal pre_delete :
    # les demandes sont encore liées au compte, la base ne les détache qu'après ces signaux.
    DeletedClientAccount.objects.create(date_joined=user.date_joined, had_orders=user.orders.exists())
