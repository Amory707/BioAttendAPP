import random
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import Role, RoleUtilisateur
from attendance.models import Pointage


class Command(BaseCommand):
    help = "Genere de faux pointages pour tester l'application."

    def add_arguments(self, parser):
        parser.add_argument(
            "--users",
            type=int,
            default=5,
            help="Nombre d'employes a creer si necessaire.",
        )
        parser.add_argument(
            "--days",
            type=int,
            default=7,
            help="Nombre de jours de pointage a generer par employe.",
        )
        parser.add_argument(
            "--seed",
            type=int,
            default=42,
            help="Graine aleatoire pour obtenir des donnees reproductibles.",
        )
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Supprime d'abord les pointages deja generes par cette commande.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        user_count = max(options["users"], 1)
        day_count = max(options["days"], 1)
        random.seed(options["seed"])

        User = get_user_model()
        employee_role, _ = Role.objects.get_or_create(nom="employé")

        if options["reset"]:
            deleted_count, _ = Pointage.objects.filter(
                utilisateur__username__startswith="fake-employee-"
            ).delete()
            self.stdout.write(
                self.style.WARNING(f"{deleted_count} faux pointages supprimes.")
            )

        created_users = 0
        created_pointages = 0
        today = timezone.localdate()

        for index in range(1, user_count + 1):
            username = f"fake-employee-{index:02d}"
            defaults = {
                "email": f"{username}@example.com",
                "first_name": f"Employe{index}",
                "last_name": "Test",
            }
            user, user_created = User.objects.get_or_create(
                username=username,
                defaults=defaults,
            )

            if user_created:
                user.set_password("test-pass-123")
                user.save(update_fields=["password"])
                created_users += 1
            else:
                fields_to_update = []
                for field, value in defaults.items():
                    if getattr(user, field) != value:
                        setattr(user, field, value)
                        fields_to_update.append(field)
                if fields_to_update:
                    user.save(update_fields=fields_to_update)

            RoleUtilisateur.objects.get_or_create(utilisateur=user, role=employee_role)

            existing_dates = set(
                Pointage.objects.filter(utilisateur=user)
                .values_list("horodatage__date", flat=True)
            )

            new_pointages = []
            for day_offset in range(day_count):
                current_date = today - timedelta(days=day_offset)
                if current_date in existing_dates:
                    continue

                entree_time = timezone.make_aware(
                    timezone.datetime.combine(
                        current_date,
                        timezone.datetime.min.time(),
                    )
                ) + timedelta(hours=8, minutes=random.randint(0, 35))
                sortie_time = entree_time + timedelta(
                    hours=8,
                    minutes=random.randint(0, 45),
                )

                statut_entree = "VALIDE" if random.random() > 0.15 else "NON_VALIDE"
                statut_sortie = "VALIDE" if random.random() > 0.10 else "NON_VALIDE"

                new_pointages.append(
                    Pointage(
                        utilisateur=user,
                        statut=statut_entree,
                        horodatage=entree_time,
                        type="ENTREE",
                        score_confiance=self._build_score(statut_entree),
                        origine=Pointage.ORIGINE_POINTEUSE,
                    )
                )
                new_pointages.append(
                    Pointage(
                        utilisateur=user,
                        statut=statut_sortie,
                        horodatage=sortie_time,
                        type="SORTIE",
                        score_confiance=self._build_score(statut_sortie),
                        origine=Pointage.ORIGINE_POINTEUSE,
                    )
                )

            if new_pointages:
                Pointage.objects.bulk_create(new_pointages)
                created_pointages += len(new_pointages)

        self.stdout.write(
            self.style.SUCCESS(
                f"{created_users} employe(s) crees, {created_pointages} pointage(s) genere(s)."
            )
        )

    def _build_score(self, statut):
        if statut == "VALIDE":
            return round(random.uniform(0.82, 0.99), 2)
        return round(random.uniform(0.35, 0.69), 2)