"""
Migration : création du modèle Role + nettoyage tables auth inutiles.
"""
from django.db import migrations, models
import uuid
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
        ('auth', '0012_alter_user_first_name_max_length'),
        ('contenttypes', '0002_remove_content_type_name'),
    ]

    operations = [
        # 1. Créer le modèle Role
        migrations.CreateModel(
            name='Role',
            fields=[
                ('id',          models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)),
                ('code',        models.SlugField(max_length=50, unique=True)),
                ('nom',         models.CharField(max_length=100, verbose_name='Nom du rôle')),
                ('description', models.TextField(blank=True)),
                ('niveau',      models.PositiveSmallIntegerField(default=1)),
                ('is_active',   models.BooleanField(default=True)),
                ('is_system',   models.BooleanField(default=False)),
                ('created_at',  models.DateTimeField(auto_now_add=True)),
                ('updated_at',  models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Rôle',
                'verbose_name_plural': 'Rôles',
                'ordering': ['-niveau', 'nom'],
            },
        ),

        # 2. Ajouter role FK sur User (nullable pendant la transition)
        migrations.AddField(
            model_name='user',
            name='role_fk',
            field=models.ForeignKey(
                'accounts.Role', null=True, blank=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='utilisateurs', verbose_name='Rôle',
            ),
        ),

        # 3. Modifier PermissionRole.role de CharField → ForeignKey
        migrations.AddField(
            model_name='permissionrole',
            name='role_fk',
            field=models.ForeignKey(
                'accounts.Role', null=True, blank=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='permissions', verbose_name='Rôle',
            ),
        ),

        # 4. Vider les tables auth inutiles.
        #    Les tables de liaison M2M de User (groups / user_permissions)
        #    n'existent que si le modèle les déclarait : on les traite
        #    séparément et de façon tolérante.
        migrations.RunSQL(
            sql="""
                DELETE FROM auth_group_permissions;
                DELETE FROM auth_permission;
                DELETE FROM auth_group;
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            sql="""
                DO $$
                BEGIN
                    IF to_regclass('public.accounts_user_user_permissions') IS NOT NULL THEN
                        EXECUTE 'DROP TABLE accounts_user_user_permissions';
                    END IF;
                    IF to_regclass('public.accounts_user_groups') IS NOT NULL THEN
                        EXECUTE 'DROP TABLE accounts_user_groups';
                    END IF;
                END $$;
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
        # Note : le modèle User déclare « groups = None » et
        # « user_permissions = None ». Ces champs sont donc absents dès la
        # migration initiale ; aucun RemoveField n'est nécessaire (il
        # provoquerait un KeyError au calcul de l'état).
    ]
