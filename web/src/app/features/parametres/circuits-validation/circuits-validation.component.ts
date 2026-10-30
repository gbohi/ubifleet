// UbiFleet — Paramètres › Workflows › Circuits de validation des demandes
//
// Types de demande et niveaux de validation (qui valide à chaque étape).
// Un niveau sans rôle validateur n'est validable que par le super admin.
import {
  Component, ChangeDetectionStrategy, OnInit, computed, inject, input, signal,
} from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { DemandesApiService, RoleApiService } from '../../../core/services/api.service';

@Component({
  selector: 'ubi-param-circuits',
  standalone: true,
  imports: [ReactiveFormsModule],
  templateUrl: './circuits-validation.component.html',
  styleUrls: ['./circuits-validation.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CircuitsValidationComponent implements OnInit {
  private api     = inject(DemandesApiService);
  private roleApi = inject(RoleApiService);
  private fb      = inject(FormBuilder);

  ecriture = input(false);

  readonly formulaires = [
    { value: 'vehicule',  label: 'Véhicule / mission (véhicule + chauffeur)' },
    { value: 'entretien', label: 'Entretien (véhicule)' },
    { value: 'carburant', label: 'Carburant (véhicule)' },
    { value: 'achat',     label: 'Achat (lignes de matériel, montant)' },
    { value: 'autre',     label: 'Simple (titre + description)' },
  ];

  types      = signal<any[]>([]);
  roles      = signal<any[]>([]);
  chargement = signal(true);
  notice     = signal<{ type: 'ok' | 'err'; texte: string } | null>(null);

  niveauxSansRole = computed(() =>
    this.types().filter(t => t.actif).flatMap(t => (t.niveaux ?? []).filter((n: any) => !n.role_min)).length
  );

  // Fenêtre type de demande
  typeEdite   = signal<any | null | undefined>(undefined);   // undefined = fermée, null = création
  typeErreur  = signal('');
  typeForm = this.fb.group({
    code:                ['autre', Validators.required],
    nom:                 ['', Validators.required],
    nb_niveaux:          [2, [Validators.required, Validators.min(1), Validators.max(4)]],
    delai_reponse_jours: [3, [Validators.required, Validators.min(1)]],
    actif:               [true],
  });

  // Ajout d'un niveau (type ciblé)
  ajoutPour    = signal<any | null>(null);
  niveauForm = this.fb.group({
    libelle:  ['', Validators.required],
    role_min: [''],
  });

  ngOnInit(): void {
    this.charger();
    this.roleApi.getAll().subscribe({ next: r => this.roles.set(r.filter((x: any) => x.is_active !== false)), error: () => {} });
  }

  charger(): void {
    this.chargement.set(true);
    this.api.getTypesDemande().subscribe({
      next: l => { this.types.set(l); this.chargement.set(false); },
      error: () => { this.chargement.set(false); this.erreur('Impossible de charger les circuits.'); },
    });
  }

  libelleFormulaire(code: string): string {
    return this.formulaires.find(f => f.value === code)?.label ?? code;
  }

  // ── Types ─────────────────────────────────────────────────────────
  ouvrirType(t: any | null): void {
    this.typeErreur.set('');
    this.typeForm.reset(t
      ? { code: t.code, nom: t.nom, nb_niveaux: t.nb_niveaux, delai_reponse_jours: t.delai_reponse_jours, actif: t.actif }
      : { code: 'autre', nom: '', nb_niveaux: 2, delai_reponse_jours: 3, actif: true });
    this.typeEdite.set(t);
  }

  enregistrerType(): void {
    if (this.typeForm.invalid) return;
    const t = this.typeEdite();
    const req = t ? this.api.updateTypeDemande(t.id, this.typeForm.value)
                  : this.api.createTypeDemande(this.typeForm.value);
    req.subscribe({
      next: () => { this.typeEdite.set(undefined); this.ok(t ? 'Type modifié.' : 'Type créé.'); this.charger(); },
      error: (err: any) => this.typeErreur.set(err?.error?.detail ?? "Erreur lors de l'enregistrement."),
    });
  }

  basculerType(t: any): void {
    this.api.updateTypeDemande(t.id, { actif: !t.actif }).subscribe({
      next: () => this.charger(),
      error: (err: any) => this.erreur(err?.error?.detail ?? 'Modification impossible.'),
    });
  }

  // ── Niveaux ───────────────────────────────────────────────────────
  changerRole(n: any, roleId: string): void {
    this.api.updateNiveau(n.id, { role_min: roleId || null }).subscribe({
      next: () => { this.ok('Rôle validateur mis à jour.'); this.charger(); },
      error: (err: any) => this.erreur(err?.error?.detail ?? 'Modification impossible.'),
    });
  }

  ouvrirAjout(t: any): void {
    this.niveauForm.reset({ libelle: '', role_min: '' });
    this.ajoutPour.set(t);
  }

  ajouterNiveau(): void {
    const t = this.ajoutPour();
    if (!t || this.niveauForm.invalid) return;
    const v = this.niveauForm.value;
    this.api.createNiveau({
      type_demande: t.id,
      niveau: Math.max(0, ...(t.niveaux ?? []).map((n: any) => n.niveau)) + 1,
      libelle: v.libelle,
      ...(v.role_min ? { role_min: v.role_min } : {}),
    }).subscribe({
      next: () => { this.ajoutPour.set(null); this.ok('Niveau ajouté.'); this.charger(); },
      error: (err: any) => this.erreur(err?.error?.detail ?? "Impossible d'ajouter le niveau."),
    });
  }

  supprimerNiveau(n: any): void {
    if (!confirm(`Supprimer le niveau ${n.niveau} « ${n.libelle} » ?`)) return;
    this.api.deleteNiveau(n.id).subscribe({
      next: () => this.charger(),
      error: (err: any) => this.erreur(err?.error?.detail ?? 'Suppression impossible.'),
    });
  }

  private ok(texte: string): void { this.notice.set({ type: 'ok', texte }); }
  private erreur(texte: string): void { this.notice.set({ type: 'err', texte }); }
}
