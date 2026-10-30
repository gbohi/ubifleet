// UbiFleet — Historique Kilométrage (Angular 18)
import {
  Component, inject, OnInit, input,
  ChangeDetectionStrategy, signal
} from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { DatePipe, DecimalPipe } from '@angular/common';
import { FormBuilder, Validators, ReactiveFormsModule } from '@angular/forms';
import { VehiculeApiService, ChauffeurApiService } from '../../../core/services/api.service';
import { TypesMouvementService } from '../../../core/services/types-mouvement.service';
import { ReleveKilometrage, TypeMouvement } from '../../../core/models';

@Component({
  selector: 'ubi-vehicule-releves-km',
  standalone: true,
  imports: [RouterLink, DatePipe, DecimalPipe, ReactiveFormsModule],
  templateUrl: './vehicule-releves-km.component.html',
  styleUrls: ['./vehicule-releves-km.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class VehiculeRelevesKmComponent implements OnInit {
  id = input.required<string>();

  private router     = inject(Router);
  private fb         = inject(FormBuilder);
  private vehiculeApi  = inject(VehiculeApiService);
  private chauffeurApi = inject(ChauffeurApiService);

  releves     = signal<ReleveKilometrage[]>([]);
  total       = signal(0);
  page        = signal(1);
  loading     = signal(true);
  showForm    = signal(false);
  editId      = signal<string | null>(null);
  saving      = signal(false);
  error       = signal('');
  success     = signal('');
  deleteId    = signal<string | null>(null);
  vehiculeInfo = signal<{ immatriculation: string; designation: string; km: number } | null>(null);

  chauffeurs  = signal<{ id: string; nom_complet: string }[]>([]);
  photoFile   = signal<File | null>(null);
  photoPreview = signal<string | null>(null);
  photoLightbox = signal<string | null>(null);

  // Types de mouvement paramétrables (Paramètres › Types de mouvement)
  typesMvt = inject(TypesMouvementService);

  form = this.fb.group({
    kilometrage:    [null as number | null, [Validators.required, Validators.min(0)]],
    date_releve:    [new Date().toISOString().split('T')[0], Validators.required],
    type_mouvement: ['releve', Validators.required],
    tournee:        [''],
    chauffeur:      [''],
    notes:          [''],
  });

  get f() { return this.form.controls; }

  get totalPages(): number { return Math.ceil(this.total() / 20) || 1; }
  get pages(): number[] {
    const cur = this.page();
    const max = this.totalPages;
    const r: number[] = [];
    for (let i = Math.max(1, cur - 2); i <= Math.min(max, cur + 2); i++) r.push(i);
    return r;
  }

  ngOnInit(): void {
    this.typesMvt.charger();
    this.loadReleves();
    // Charger les infos du véhicule
    this.chauffeurApi.getAll({ page_size: 200, statut: 'actif' }).subscribe({
      next: (res) => this.chauffeurs.set(
        (res.results ?? []).map((c: any) => ({ id: c.id, nom_complet: c.nom_complet }))
      ),
      error: () => {},
    });
    this.vehiculeApi.getById(this.id()).subscribe({
      next: (v: any) => this.vehiculeInfo.set({
        immatriculation: v.immatriculation,
        designation:     v.designation,
        km:              v.kilometrage_actuel,
      }),
      error: () => {},
    });
  }

  loadReleves(): void {
    this.loading.set(true);
    this.vehiculeApi.getRelevesKm({ vehicule: this.id(), page: this.page() }).subscribe({
      next: (res) => {
        this.releves.set(res.results ?? []);
        this.total.set(res.count ?? 0);
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }

  openForm(releve?: ReleveKilometrage): void {
    this.error.set('');
    this.success.set('');
    if (releve) {
      this.editId.set(releve.id);
      this.form.patchValue({
        kilometrage:    releve.kilometrage,
        date_releve:    releve.date_releve,
        type_mouvement: releve.type_mouvement,
        chauffeur:      releve.chauffeur ?? '',
        tournee:        releve.tournee ?? '',
        notes:          releve.notes,
      });
    } else {
      this.editId.set(null);
      this.form.reset({
        date_releve: new Date().toISOString().split('T')[0],
        type_mouvement: 'releve',
      });
    }
    this.showForm.set(true);
  }

  closeForm(): void {
    this.showForm.set(false);
    this.photoFile.set(null);
    this.photoPreview.set(null);
  }

  onPhotoChange(event: Event): void {
    const file = (event.target as HTMLInputElement).files?.[0] ?? null;
    this.photoFile.set(file);
    if (file) {
      const reader = new FileReader();
      reader.onload = (e) => this.photoPreview.set(e.target?.result as string);
      reader.readAsDataURL(file);
    } else {
      this.photoPreview.set(null);
    }
  }

  openLightbox(url: string): void  { this.photoLightbox.set(url); }
  closeLightbox(): void             { this.photoLightbox.set(null); }

  saveReleve(): void {
    if (this.form.invalid || this.saving()) return;
    this.saving.set(true);
    this.error.set('');

    const raw = this.form.value;
    const payload: Record<string, any> = {
      vehicule:       this.id(),
      kilometrage:    raw.kilometrage,
      date_releve:    raw.date_releve,
      type_mouvement: raw.type_mouvement,
    };
    if (raw.chauffeur) payload['chauffeur'] = raw.chauffeur;
    if (raw.tournee)   payload['tournee']   = raw.tournee;
    if (raw.notes)     payload['notes']     = raw.notes;
    if (this.photoFile()) payload['photo_tableau_bord'] = this.photoFile()!

    // Toujours createReleveKm (on ne modifie pas l'historique, on corrige en ajoutant)
    this.vehiculeApi.createReleveKm(payload as any).subscribe({
      next: () => {
        this.saving.set(false);
        this.success.set('Relevé enregistré.');
        this.closeForm();
        this.loadReleves();
        // Recharger les infos véhicule (km actuel peut avoir changé)
        this.chauffeurApi.getAll({ page_size: 200, statut: 'actif' }).subscribe({
      next: (res) => this.chauffeurs.set(
        (res.results ?? []).map((c: any) => ({ id: c.id, nom_complet: c.nom_complet }))
      ),
      error: () => {},
    });
    this.vehiculeApi.getById(this.id()).subscribe({
          next: (v: any) => this.vehiculeInfo.set({
            immatriculation: v.immatriculation,
            designation: v.designation,
            km: v.kilometrage_actuel,
          }),
          error: () => {},
        });
      },
      error: (err) => {
        this.saving.set(false);
        this.error.set(err?.error?.detail ?? 'Erreur lors de l\'enregistrement.');
      },
    });
  }

  confirmDelete(id: string): void { this.deleteId.set(id); }
  cancelDelete(): void            { this.deleteId.set(null); }

  doDelete(id: string): void {
    this.vehiculeApi.deleteReleveKm(id).subscribe({
      next: () => { this.deleteId.set(null); this.loadReleves(); },
      error: () => this.deleteId.set(null),
    });
  }

  onPageChange(p: number): void { this.page.set(p); this.loadReleves(); }
  goBack(): void { this.router.navigate(['/vehicules', this.id()]); }

  typeMouvementClass(type: TypeMouvement): string {
    return this.typesMvt.classeBadge(type);
  }

  typeMouvementIcon(type: TypeMouvement): string {
    const map: Record<string, string> = {
      entree: 'fa-sign-in-alt', sortie: 'fa-sign-out-alt',
      releve: 'fa-tachometer-alt', tournee: 'fa-route',
    };
    return map[type] ?? 'fa-circle';
  }
}
