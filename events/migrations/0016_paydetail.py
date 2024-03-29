# Generated by Django 4.0.8 on 2023-03-20 13:39

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0015_participant_counted_routes'),
    ]

    operations = [
        migrations.CreateModel(
            name='PayDetail',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('datetime', models.DateTimeField(auto_now_add=True)),
                ('amount', models.FloatField(default=0)),
                ('operation_id', models.CharField(max_length=100)),
                ('event', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='PayDetail', to='events.event')),
                ('participant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='PayDetail', to='events.participant')),
                ('promo_code', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='PayDetail', to='events.promocode')),
                ('wallet', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='PayDetail', to='events.wallet')),
            ],
        ),
    ]
