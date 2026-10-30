// UbiFleet — Paramètres › Carburant › Historique des prix
//
// Un prix entré en vigueur n'est jamais modifié : on ajoute un nouveau prix
// avec sa date d'effet. Seuls les prix futurs (pas encore en vigueur) se suppriment.
import {
  Component, ChangeDetectionStrategy, OnInit, computed, inject, input, signal,
} from '@angular/core';
import { DatePipe, DecimalPipe } from '@angular/common';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { CarburantApiService } from '../../../core/services/api.service';

@Component({
  selector: 'ubi-param-prix-carburant',
  standalone: true,
  imports: [ReactiveFormsModule, DecimalPipe, DatePipe],
  templateUrl: './prix-carburant.component.html',
  styleUrls: ['./prix-carburant.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class PrixCarburantComponent implements OnInit {
  private api = inject(CarburantApiService);
  private fb  = inject(FormBuilder);

  ecriture = input(false);

  readonly types = [
    { value: 'diesel', label: 'Diesel' }, { value: 'essence', label: 'Essence' },
    { value: 'gpl', label: 'GPL' }, { value: 'hybride', label: 'Hybride' },
    { value: 'electrique', label: 'Électrique' },
  ];
  readonly aujourdhui = new Date().toISOString().split('T')[0];

  prix       = signal<any[]>([]);
  typeFiltre = signal('diesel');
  chargement = signal(true);
  notice     = signal<{ type: 'ok' | 'err'; texte: string } | null>(null);
  ajoutOuvert = signal(false);

  /** Historique du type choisi, le plus récent en premier, avec le statut de chaque prix. */
  historique = computed(() => {
    const liste = this.prix().filter(p => p.type_carburant === this.typeFiltre());
    const enVigueur = liste.find(p => p.date_effet <= this.aujourdhui);
    return liste.map(p => ({
      ...p,
      statut: p.date_effet > this.aujourdhui ? 'futur' : (p.id === enVigueur?.id ? 'en_vigueur' : 'passe'),
    }));
  });

  /** Prix actuel de chaque type (cartes de synthèse). */
  actuels = computed(() => this.types.map(t => {
    const p = this.prix().filter(x => x.type_carburant === t.value && x.date_effet <= this.aujourdhui)[0];
    return { ...t, prix: p?.prix ?? null, depuis: p?.date_effet ?? null };
  }).filter(t => t.prix !== null || t.value === this.typeFiltre()));

  form = this.fb.group({
    prix:        [null as number | null, [Validators.required, Validators.min(1)]],
    date_effet:  [this.aujourdhui, Validators.required],
    commentaire: [''],
  });

  ngOnInit(): void { this.charger(); }

  charger(): void {
    this.chargement.set(true);
    this.api.getPrix().subscribe({
      next: l => { this.prix.set(l); this.chargement.set(false); },
      error: () => { this.chargement.set(false); this.notice.set({ type: 'err', texte: 'Impossible de charger les prix.' }); },
    });
  }

  ouvrirAjout(): void {
    this.form.reset({ prix: null, date_effet: this.aujourdhui, commentaire: '' });
    this.ajoutOuvert.set(true);
  }

  ajouter(): void {
    if (this.form.invalid) return;
    this.api.createPrix({ ...this.form.value, type_carburant: this.typeFiltre() }).subscribe({
      next: () => {
        this.ajoutOuvert.set(false);
        this.notice.set({ type: 'ok', texte: 'Nouveau prix enregistré.' });
        this.charger();
      },
      error: (err: any) => this.notice.set({
        type: 'err',
        texte: err?.error?.detail
          ?? (err?.error?.non_field_errors ? 'Un prix existe déjà à cette date pour ce carburant.' : "Erreur lors de l'enregistrement."),
      }),
    });
  }

  supprimer(p: any): void {
    if (!confirm(`Supprimer le prix prévu au ${p.date_effet} ?`)) return;
    this.api.deletePrix(p.id).subscribe({
      next: () => this.charger(),
      error: (err: any) => this.notice.set({ type: 'err', texte: err?.error?.detail ?? 'Suppression impossible.' }),
    });
  }
}
