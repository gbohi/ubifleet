// UbiFleet — Paramètres › Workflows › Éléments de contrôle véhicule
//
// Points vérifiés lors d'une fiche de contrôle, regroupés par catégorie.
import {
  Component, ChangeDetectionStrategy, OnInit, computed, inject, input, signal,
} from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ControleApiService } from '../../../core/services/api.service';

@Component({
  selector: 'ubi-param-elements-controle',
  standalone: true,
  imports: [ReactiveFormsModule],
  templateUrl: './elements-controle.component.html',
  styleUrls: ['./elements-controle.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ElementsControleComponent implements OnInit {
  private api = inject(ControleApiService);
  private fb  = inject(FormBuilder);

  ecriture = input(false);

  readonly categories = [
    { value: 'moteur',        label: 'Moteur' },
    { value: 'securite',      label: 'Sécurité' },
    { value: 'carrosserie',   label: 'Carrosserie' },
    { value: 'eclairage',     label: 'Éclairage' },
    { value: 'pneumatiques',  label: 'Pneumatiques' },
    { value: 'interieur',     label: 'Intérieur' },
    { value: 'administratif', label: 'Administratif' },
    { value: 'autre',         label: 'Autre' },
  ];

  elements   = signal<any[]>([]);
  chargement = signal(true);
  recherche  = signal('');
  notice     = signal<{ type: 'ok' | 'err'; texte: string } | null>(null);

  /** Catégories non vides, éléments triés par ordre puis nom. */
  groupes = computed(() => {
    const q = this.recherche().trim().toLowerCase();
    const liste = this.elements().filter(e => !q || e.nom.toLowerCase().includes(q));
    return this.categories
      .map(c => ({ ...c, elements: liste.filter(e => e.categorie === c.value) }))
      .filter(g => g.elements.length > 0);
  });

  elementEdite = signal<any | null | undefined>(undefined);   // undefined = fermé, null = création
  erreurForm   = signal('');
  form = this.fb.group({
    nom:         ['', Validators.required],
    categorie:   ['autre', Validators.required],
    description: [''],
    ordre:       [0, [Validators.min(0)]],
    obligatoire: [false],
    actif:       [true],
  });

  ngOnInit(): void { this.charger(); }

  charger(): void {
    this.chargement.set(true);
    this.api.getElements().subscribe({
      next: l => { this.elements.set(l); this.chargement.set(false); },
      error: () => { this.chargement.set(false); this.notice.set({ type: 'err', texte: 'Impossible de charger les éléments.' }); },
    });
  }

  ouvrir(e: any | null, categorie = 'autre'): void {
    this.erreurForm.set('');
    this.form.reset(e
      ? { nom: e.nom, categorie: e.categorie, description: e.description, ordre: e.ordre,
          obligatoire: e.obligatoire, actif: e.actif }
      : { nom: '', categorie, description: '', ordre: 0, obligatoire: false, actif: true });
    this.elementEdite.set(e);
  }

  enregistrer(): void {
    if (this.form.invalid) return;
    const e = this.elementEdite();
    const req = e ? this.api.updateElement(e.id, this.form.value) : this.api.createElement(this.form.value);
    req.subscribe({
      next: () => {
        this.elementEdite.set(undefined);
        this.notice.set({ type: 'ok', texte: e ? 'Élément modifié.' : 'Élément ajouté.' });
        this.charger();
      },
      error: (err: any) => this.erreurForm.set(err?.error?.detail ?? "Erreur lors de l'enregistrement."),
    });
  }

  basculer(e: any, champ: 'actif' | 'obligatoire'): void {
    this.api.updateElement(e.id, { [champ]: !e[champ] }).subscribe({
      next: () => this.charger(),
      error: (err: any) => this.notice.set({ type: 'err', texte: err?.error?.detail ?? 'Modification impossible.' }),
    });
  }

  supprimer(e: any): void {
    if (!confirm(`Supprimer « ${e.nom} » ? Désactivez-le plutôt s'il figure dans des fiches existantes.`)) return;
    this.api.deleteElement(e.id).subscribe({
      next: () => this.charger(),
      error: (err: any) => this.notice.set({ type: 'err', texte: err?.error?.detail ?? 'Suppression impossible : désactivez-le plutôt.' }),
    });
  }
}
