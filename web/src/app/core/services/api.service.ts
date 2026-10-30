// UbiFleet — API Services
import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable, map } from 'rxjs';
import { environment } from '@env/environment';
import {
  Vehicule, VehiculeDetail, ReleveKilometrage, AffectationVehicule, UbiUser, Role, HistoriqueImmatriculation, PleinCarburant, DotationCarburant, Station,
  Intervention, Prestataire, SuiviPneus, Sinistre, ContratAssurance, Assureur,
  Chauffeur, BudgetAnnuel, Depense, Alerte, DashboardData,
  PaginatedResponse, Agence, User
} from '../models';

const API = environment.apiUrl;

// ── Base Service ──
@Injectable({ providedIn: 'root' })
export class ApiBaseService {
  protected http = inject(HttpClient);

  protected buildParams(filters: Record<string, any>): HttpParams {
    let params = new HttpParams();
    Object.entries(filters).forEach(([key, val]) => {
      if (val !== null && val !== undefined && val !== '') {
        params = params.set(key, String(val));
      }
    });
    return params;
  }
}

// ── Grand Livre API ──
@Injectable({ providedIn: 'root' })
export class GrandLivreApiService extends ApiBaseService {
  upload(formData: FormData): Observable<any> {
    return this.http.post<any>(`${API}/grand-livre/imports/upload/`, formData, {
      reportProgress: true,
      observe: 'events',
    });
  }

  getHistorique(filters?: Record<string, any>): Observable<any> {
    const params = filters ? this.buildParams(filters) : undefined;
    return this.http.get<any>(`${API}/grand-livre/imports/`, { params });
  }

  getLignes(filters?: Record<string, any>): Observable<any> {
    const params = filters ? this.buildParams(filters) : undefined;
    return this.http.get<any>(`${API}/grand-livre/lignes/`, { params });
  }

  getStats(filters?: Record<string, any>): Observable<any> {
    const params = filters ? this.buildParams(filters) : undefined;
    return this.http.get<any>(`${API}/grand-livre/lignes/stats/`, { params });
  }

  getTotaux(filters?: Record<string, any>): Observable<any> {
    const params = filters ? this.buildParams(filters) : undefined;
    return this.http.get<any>(`${API}/grand-livre/lignes/stats/`, { params });
  }
}

// ── Auth API ──
@Injectable({ providedIn: 'root' })
export class RoleApiService extends ApiBaseService {
  getAll(): Observable<Role[]> {
    return this.http.get<any>(`${API}/auth/roles/`).pipe(
      map(res => Array.isArray(res) ? res : (res.results ?? []))
    );
  }
  getById(id: string): Observable<Role> {
    return this.http.get<Role>(`${API}/auth/roles/${id}/`);
  }
  create(data: Partial<Role>): Observable<Role> {
    return this.http.post<Role>(`${API}/auth/roles/`, data);
  }
  update(id: string, data: Partial<Role>): Observable<Role> {
    return this.http.patch<Role>(`${API}/auth/roles/${id}/`, data);
  }
  delete(id: string): Observable<any> {
    return this.http.delete(`${API}/auth/roles/${id}/`);
  }
}

@Injectable({ providedIn: 'root' })
export class AgenceApiService extends ApiBaseService {
  getAll(filters?: Record<string, any>): Observable<any> {
    const params = filters ? this.buildParams(filters) : undefined;
    return this.http.get<any>(`${API}/auth/agences/`, { params }).pipe(
      map(res => Array.isArray(res) ? res : (res.results ?? []))
    );
  }
  getById(id: string): Observable<Agence> {
    return this.http.get<Agence>(`${API}/auth/agences/${id}/`);
  }
  create(data: Partial<Agence>): Observable<Agence> {
    return this.http.post<Agence>(`${API}/auth/agences/`, data);
  }
  update(id: string, data: Partial<Agence>): Observable<Agence> {
    return this.http.patch<Agence>(`${API}/auth/agences/${id}/`, data);
  }
  delete(id: string): Observable<any> {
    return this.http.delete(`${API}/auth/agences/${id}/`);
  }
}

@Injectable({ providedIn: 'root' })
export class UserApiService extends ApiBaseService {
  getAll(filters?: Record<string, any>): Observable<PaginatedResponse<User>> {
    const params = filters ? this.buildParams(filters) : undefined;
    return this.http.get<PaginatedResponse<User>>(`${API}/auth/users/`, { params });
  }
  getById(id: string): Observable<User> {
    return this.http.get<User>(`${API}/auth/users/${id}/`);
  }
  getMe(): Observable<User> {
    return this.http.get<User>(`${API}/auth/me/`);
  }
  updateMe(data: Partial<User>): Observable<any> {
    return this.http.patch(`${API}/auth/me/profile/`, data);
  }
  create(data: any): Observable<User> {
    return this.http.post<User>(`${API}/auth/users/`, data);
  }
  update(id: string, data: Partial<User>): Observable<User> {
    return this.http.patch<User>(`${API}/auth/users/${id}/`, data);
  }
  delete(id: string): Observable<any> {
    return this.http.delete(`${API}/auth/users/${id}/`);
  }
  toggleActive(id: string): Observable<any> {
    return this.http.post(`${API}/auth/users/${id}/toggle_active/`, {});
  }
  resetPassword(id: string, newPassword: string): Observable<any> {
    return this.http.post(`${API}/auth/users/${id}/reset_password/`, { new_password: newPassword });
  }
  getRoles(): Observable<{ value: string; label: string }[]> {
    return this.http.get<{ value: string; label: string }[]>(`${API}/auth/users/roles/`);
  }
  changePassword(data: { old_password: string; new_password: string }): Observable<any> {
    return this.http.put(`${API}/auth/me/password/`, data);
  }
  getPermissions(filters?: Record<string, any>): Observable<any> {
    const params = filters ? this.buildParams(filters) : undefined;
    return this.http.get(`${API}/auth/permissions/`, { params });
  }
  getPermissionsMeta(): Observable<any> {
    return this.http.get(`${API}/auth/permissions/meta/`);
  }
  bulkUpdatePermissions(data: any[]): Observable<any> {
    return this.http.post(`${API}/auth/permissions/bulk/`, data);
  }
  updatePermission(id: string, data: any): Observable<any> {
    return this.http.patch(`${API}/auth/permissions/${id}/`, data);
  }
}

// ── Véhicules API ──
@Injectable({ providedIn: 'root' })
export class VehiculeApiService extends ApiBaseService {
  getAll(filters?: Record<string, any>): Observable<PaginatedResponse<Vehicule>> {
    const params = filters ? this.buildParams(filters) : undefined;
    return this.http.get<PaginatedResponse<Vehicule>>(`${API}/vehicules/`, { params });
  }
  getById(id: string): Observable<VehiculeDetail> {
    return this.http.get<VehiculeDetail>(`${API}/vehicules/${id}/`);
  }
  create(data: Partial<Vehicule>): Observable<Vehicule> {
    return this.http.post<Vehicule>(`${API}/vehicules/`, data);
  }
  update(id: string, data: Partial<Vehicule>): Observable<Vehicule> {
    return this.http.patch<Vehicule>(`${API}/vehicules/${id}/`, data);
  }
  delete(id: string): Observable<any> {
    return this.http.delete(`${API}/vehicules/${id}/`);
  }
  updateKilometrage(id: string, data: {
    kilometrage: number;
    date_releve: string;
    type_mouvement?: string;
    chauffeur?: string;
    tournee?: string;
    notes?: string;
    photo_tableau_bord?: File | null;
  }): Observable<any> {
    const fd = new FormData();
    fd.append('kilometrage',    String(data.kilometrage));
    fd.append('date_releve',    data.date_releve);
    if (data.type_mouvement)    fd.append('type_mouvement', data.type_mouvement);
    if (data.chauffeur)         fd.append('chauffeur',      data.chauffeur);
    if (data.tournee)           fd.append('tournee',        data.tournee);
    if (data.notes)             fd.append('notes',          data.notes);
    if (data.photo_tableau_bord) fd.append('photo_tableau_bord', data.photo_tableau_bord);
    return this.http.post(`${API}/vehicules/${id}/kilometrage/`, fd);
  }
  changerImmatriculation(id: string, data: {
    nouvelle_immatriculation: string;
    date_changement?: string;
    motif?: string;
  }): Observable<any> {
    return this.http.post(`${API}/vehicules/${id}/changer_immatriculation/`, data);
  }

  getHistoriqueStatuts(vehiculeId: string): Observable<any[]> {
    return this.http.get<any[]>(
      `${API}/vehicules/${vehiculeId}/historique-statuts/`
    ).pipe(map(res => Array.isArray(res) ? res : (res as any).results ?? []));
  }
  createHistoriqueStatut(vehiculeId: string, data: any): Observable<any> {
    return this.http.post(`${API}/vehicules/${vehiculeId}/historique-statuts/`, data);
  }

  getHistoriqueImmat(vehiculeId: string): Observable<HistoriqueImmatriculation[]> {
    return this.http.get<HistoriqueImmatriculation[]>(
      `${API}/vehicules/historique-immat/?vehicule=${vehiculeId}`
    );
  }

  getTypesDocument(actif?: boolean): Observable<any[]> {
    const params = actif !== undefined ? this.buildParams({ actif }) : undefined;
    return this.http.get<any[]>(`${API}/vehicules/types-document/`, { params });
  }
  createTypeDocument(data: any): Observable<any> {
    return this.http.post<any>(`${API}/vehicules/types-document/`, data);
  }
  updateTypeDocument(id: number, data: any): Observable<any> {
    return this.http.patch<any>(`${API}/vehicules/types-document/${id}/`, data);
  }
  deleteTypeDocument(id: number): Observable<any> {
    return this.http.delete(`${API}/vehicules/types-document/${id}/`);
  }

  getConsommationKm(params: Record<string, any>): Observable<any> {
    const p = this.buildParams(params);
    return this.http.get<any>(`${API}/vehicules/consommation-km/`, { params: p });
  }

  getEtatParc(filters?: Record<string, any>): Observable<any> {
    const params = filters ? this.buildParams(filters) : undefined;
    return this.http.get<any>(`${API}/vehicules/etat_parc/`, { params });
  }

  getAffectations(filters?: Record<string, any>): Observable<PaginatedResponse<AffectationVehicule>> {
    const params = filters ? this.buildParams(filters) : undefined;
    return this.http.get<PaginatedResponse<AffectationVehicule>>(
      `${API}/vehicules/affectations/`, { params }
    );
  }
  createAffectation(data: Partial<AffectationVehicule>): Observable<AffectationVehicule> {
    return this.http.post<AffectationVehicule>(`${API}/vehicules/affectations/`, data);
  }
  updateAffectation(id: string, data: Partial<AffectationVehicule>): Observable<AffectationVehicule> {
    return this.http.patch<AffectationVehicule>(`${API}/vehicules/affectations/${id}/`, data);
  }
  deleteAffectation(id: string): Observable<any> {
    return this.http.delete(`${API}/vehicules/affectations/${id}/`);
  }

  getRelevesKm(filters?: Record<string, any>): Observable<PaginatedResponse<ReleveKilometrage>> {
    const params = filters ? this.buildParams(filters) : undefined;
    return this.http.get<PaginatedResponse<ReleveKilometrage>>(
      `${API}/vehicules/releves-km/`, { params }
    );
  }
  createReleveKm(data: Partial<ReleveKilometrage> & { photo_tableau_bord?: File | null }): Observable<ReleveKilometrage> {
    const fd = new FormData();
    Object.entries(data).forEach(([k, val]) => {
      if (val === null || val === undefined) return;
      const v: any = val;
      if (v instanceof File) fd.append(k, v);
      else fd.append(k, String(v));
    });
    return this.http.post<ReleveKilometrage>(`${API}/vehicules/releves-km/`, fd);
  }
  deleteReleveKm(id: string): Observable<any> {
    return this.http.delete(`${API}/vehicules/releves-km/${id}/`);
  }
  getHistorique(id: string): Observable<any> {
    return this.http.get(`${API}/vehicules/${id}/historique/`);
  }
  getStats(): Observable<any> {
    return this.http.get(`${API}/vehicules/stats/`);
  }
  getAssurancesExpirant(): Observable<Vehicule[]> {
    return this.http.get<Vehicule[]>(`${API}/vehicules/assurances_expirant/`);
  }
  getDocuments(vehiculeId: string): Observable<any[]> {
    return this.http.get<any[]>(`${API}/vehicules/${vehiculeId}/documents/`);
  }
  uploadDocument(vehiculeId: string, data: FormData): Observable<any> {
    return this.http.post(`${API}/vehicules/${vehiculeId}/documents/`, data);
  }
  updateDocument(vehiculeId: string, docId: string, data: FormData): Observable<any> {
    return this.http.patch(`${API}/vehicules/${vehiculeId}/documents/${docId}/`, data);
  }
  deleteDocument(vehiculeId: string, docId: string): Observable<any> {
    return this.http.delete(`${API}/vehicules/${vehiculeId}/documents/${docId}/`);
  }
}

// ── Carburant API ──
@Injectable({ providedIn: 'root' })
export class CarburantApiService extends ApiBaseService {
  getPleinsVehicule(vehiculeId: string, filters?: Record<string, any>): Observable<PaginatedResponse<PleinCarburant>> {
    const params = this.buildParams({ vehicule: vehiculeId, ...filters });
    return this.http.get<PaginatedResponse<PleinCarburant>>(`${API}/carburant/pleins/`, { params });
  }
  getPleins(filters?: Record<string, any>): Observable<PaginatedResponse<PleinCarburant>> {
    const params = filters ? this.buildParams(filters) : undefined;
    return this.http.get<PaginatedResponse<PleinCarburant>>(`${API}/carburant/pleins/`, { params });
  }
  createPlein(data: Partial<PleinCarburant> | FormData): Observable<PleinCarburant> {
    return this.http.post<PleinCarburant>(`${API}/carburant/pleins/`, data);
  }
  updatePlein(id: string, data: Partial<PleinCarburant> | FormData): Observable<PleinCarburant> {
    return this.http.patch<PleinCarburant>(`${API}/carburant/pleins/${id}/`, data);
  }
  validerPlein(id: string, data: { statut: string; motif?: string } = { statut: 'valide' }): Observable<any> {
    return this.http.post(`${API}/carburant/pleins/${id}/valider/`, data);
  }
  getAnomalies(): Observable<any> {
    return this.http.get(`${API}/carburant/pleins/anomalies/`);
  }
  getStats(params?: Record<string, any>): Observable<any> {
    const p = params ? this.buildParams(params) : undefined;
    return this.http.get(`${API}/carburant/pleins/stats/`, { params: p });
  }
  getConsommation(params?: Record<string, any>): Observable<any> {
    const p = params ? this.buildParams(params) : undefined;
    return this.http.get<any>(`${API}/carburant/pleins/consommation/`, { params: p });
  }
  getConsommationMoyennePeriode(params: Record<string, any>): Observable<any> {
    const p = this.buildParams(params);
    return this.http.get<any>(`${API}/carburant/pleins/consommation_moyenne_periode/`, { params: p });
  }
  getEvolutionAgences(params: Record<string, any>): Observable<any> {
    const p = this.buildParams(params);
    return this.http.get<any>(`${API}/carburant/pleins/evolution_agences/`, { params: p });
  }
  getSuiviTournees(filters?: Record<string, any>): Observable<any> {
    const p = filters ? this.buildParams(filters) : undefined;
    return this.http.get<any>(`${API}/carburant/pleins/suivi_tournees/`, { params: p });
  }

  getComparaisonTotal(params: Record<string, any>): Observable<any> {
    const p = this.buildParams(params);
    return this.http.get<any>(`${API}/carburant/pleins/comparaison_total/`, { params: p });
  }
  getDotations(filters?: Record<string, any>): Observable<PaginatedResponse<DotationCarburant>> {
    const params = filters ? this.buildParams(filters) : undefined;
    return this.http.get<PaginatedResponse<DotationCarburant>>(`${API}/carburant/dotations/`, { params });
  }
  createDotation(data: Partial<DotationCarburant>): Observable<DotationCarburant> {
    return this.http.post<DotationCarburant>(`${API}/carburant/dotations/`, data);
  }
  getStations(filters?: Record<string, any>): Observable<PaginatedResponse<Station>> {
    const params = filters ? this.buildParams(filters) : undefined;
    return this.http.get<PaginatedResponse<Station>>(`${API}/carburant/stations/`, { params });
  }
  createStation(data: any): Observable<any> {
    return this.http.post(`${API}/carburant/stations/`, data);
  }
  updateStation(id: string, data: any): Observable<any> {
    return this.http.patch(`${API}/carburant/stations/${id}/`, data);
  }
  deleteStation(id: string): Observable<any> {
    return this.http.delete(`${API}/carburant/stations/${id}/`);
  }
  // Historique des prix du carburant
  getPrix(filters?: Record<string, any>): Observable<any[]> {
    const params = filters ? this.buildParams(filters) : undefined;
    return this.http.get<any[]>(`${API}/carburant/prix/`, { params });
  }
  createPrix(data: any): Observable<any> {
    return this.http.post(`${API}/carburant/prix/`, data);
  }
  deletePrix(id: number): Observable<any> {
    return this.http.delete(`${API}/carburant/prix/${id}/`);
  }
  /** Prix en vigueur à une date, pour un véhicule (son carburant) ou un type de carburant. */
  prixEnVigueur(params: { vehicule?: string; type_carburant?: string; date?: string }): Observable<any> {
    return this.http.get(`${API}/carburant/prix/en_vigueur/`, { params: this.buildParams(params) });
  }
  getRapprochements(filters?: Record<string, any>): Observable<PaginatedResponse<any>> {
    const params = filters ? this.buildParams(filters) : undefined;
    return this.http.get<PaginatedResponse<any>>(`${API}/carburant/rapprochements/`, { params });
  }
}

// ── Entretien API ──
@Injectable({ providedIn: 'root' })
export class EntretienApiService extends ApiBaseService {
  getByVehicule(vehiculeId: string, filters?: Record<string, any>): Observable<PaginatedResponse<Intervention>> {
    const params = this.buildParams({ vehicule: vehiculeId, ...filters });
    return this.http.get<PaginatedResponse<Intervention>>(`${API}/entretien/interventions/`, { params });
  }
  getInterventions(filters?: Record<string, any>): Observable<PaginatedResponse<Intervention>> {
    const params = filters ? this.buildParams(filters) : undefined;
    return this.http.get<PaginatedResponse<Intervention>>(`${API}/entretien/interventions/`, { params });
  }
  getById(id: string): Observable<Intervention> {
    return this.http.get<Intervention>(`${API}/entretien/interventions/${id}/`);
  }
  create(data: Partial<Intervention>): Observable<Intervention> {
    return this.http.post<Intervention>(`${API}/entretien/interventions/`, data);
  }
  update(id: string, data: Partial<Intervention>): Observable<Intervention> {
    return this.http.patch<Intervention>(`${API}/entretien/interventions/${id}/`, data);
  }
  demarrer(id: string, data: { date_debut?: string } = {}): Observable<any> {
    return this.http.post(`${API}/entretien/interventions/${id}/demarrer/`, data);
  }
  terminer(id: string, data: { cout_reel?: number; rapport?: string; prochain_km?: number }): Observable<any> {
    return this.http.post(`${API}/entretien/interventions/${id}/terminer/`, data);
  }

  // Documents
  getDocuments(interventionId: string, typeDoc?: string): Observable<any[]> {
    const params: any = { intervention: interventionId };
    if (typeDoc) params['type_doc'] = typeDoc;
    return this.http.get<any[]>(`${API}/entretien/documents/`, { params });
  }
  uploadDocument(interventionId: string, fichier: File, typeDoc: string, nom?: string): Observable<any> {
    const fd = new FormData();
    fd.append('intervention', interventionId);
    fd.append('fichier', fichier, fichier.name);
    fd.append('type_doc', typeDoc);
    if (nom) fd.append('nom', nom);
    return this.http.post(`${API}/entretien/documents/`, fd);
  }
  deleteDocument(id: string): Observable<any> {
    return this.http.delete(`${API}/entretien/documents/${id}/`);
  }
  getPlanifiees(): Observable<Intervention[]> {
    return this.http.get<Intervention[]>(`${API}/entretien/interventions/planifiees/`);
  }
  getStats(params?: Record<string, any>): Observable<any> {
    const p = params ? this.buildParams(params) : undefined;
    return this.http.get(`${API}/entretien/interventions/stats/`, { params: p });
  }
  getTypes(filters?: Record<string, any>): Observable<any[]> {
    const params = filters ? this.buildParams(filters) : undefined;
    return this.http.get<any[] | PaginatedResponse<any>>(`${API}/entretien/types/`, { params }).pipe(
      map(res => Array.isArray(res) ? res : res.results ?? [])
    );
  }
  createType(data: any): Observable<any> {
    return this.http.post(`${API}/entretien/types/`, data);
  }
  updateType(id: string, data: any): Observable<any> {
    return this.http.patch(`${API}/entretien/types/${id}/`, data);
  }
  deleteType(id: string): Observable<any> {
    return this.http.delete(`${API}/entretien/types/${id}/`);
  }
  getPrestataires(filters?: Record<string, any>): Observable<PaginatedResponse<Prestataire>> {
    const params = filters ? this.buildParams(filters) : undefined;
    return this.http.get<PaginatedResponse<Prestataire>>(`${API}/entretien/prestataires/`, { params });
  }
  createPrestataire(data: Partial<Prestataire>): Observable<Prestataire> {
    return this.http.post<Prestataire>(`${API}/entretien/prestataires/`, data);
  }
  updatePrestataire(id: string, data: Partial<Prestataire>): Observable<Prestataire> {
    return this.http.patch<Prestataire>(`${API}/entretien/prestataires/${id}/`, data);
  }
  deletePrestataire(id: string): Observable<any> {
    return this.http.delete(`${API}/entretien/prestataires/${id}/`);
  }
  getPneus(filters?: Record<string, any>): Observable<PaginatedResponse<SuiviPneus>> {
    const params = filters ? this.buildParams(filters) : undefined;
    return this.http.get<PaginatedResponse<SuiviPneus>>(`${API}/entretien/pneus/`, { params });
  }
  getPneusAChanger(): Observable<SuiviPneus[]> {
    return this.http.get<SuiviPneus[]>(`${API}/entretien/pneus/a_changer/`);
  }
}

// ── Sinistres API ──
@Injectable({ providedIn: 'root' })
export class SinistreApiService extends ApiBaseService {
  getSinistres(filters?: Record<string, any>): Observable<PaginatedResponse<Sinistre>> {
    const params = filters ? this.buildParams(filters) : undefined;
    return this.http.get<PaginatedResponse<Sinistre>>(`${API}/sinistres/sinistres/`, { params });
  }
  getById(id: string): Observable<Sinistre> {
    return this.http.get<Sinistre>(`${API}/sinistres/sinistres/${id}/`);
  }
  create(data: Partial<Sinistre>): Observable<Sinistre> {
    return this.http.post<Sinistre>(`${API}/sinistres/sinistres/`, data);
  }
  update(id: string, data: Partial<Sinistre>): Observable<Sinistre> {
    return this.http.patch<Sinistre>(`${API}/sinistres/sinistres/${id}/`, data);
  }
  changerStatut(id: string, statut: string): Observable<any> {
    return this.http.post(`${API}/sinistres/sinistres/${id}/changer_statut/`, { statut });
  }
  getStats(params?: Record<string, any>): Observable<any> {
    const p = params ? this.buildParams(params) : undefined;
    return this.http.get(`${API}/sinistres/sinistres/stats/`, { params: p });
  }
  getContrats(filters?: Record<string, any>): Observable<PaginatedResponse<ContratAssurance>> {
    const params = filters ? this.buildParams(filters) : undefined;
    return this.http.get<PaginatedResponse<ContratAssurance>>(`${API}/sinistres/contrats/`, { params });
  }
  getContratsExpirant(): Observable<ContratAssurance[]> {
    return this.http.get<ContratAssurance[]>(`${API}/sinistres/contrats/expirant_bientot/`);
  }
  getContratsExpires(): Observable<ContratAssurance[]> {
    return this.http.get<ContratAssurance[]>(`${API}/sinistres/contrats/expires/`);
  }
  createContrat(data: Partial<ContratAssurance>): Observable<ContratAssurance> {
    return this.http.post<ContratAssurance>(`${API}/sinistres/contrats/`, data);
  }
  updateContrat(id: string, data: Partial<ContratAssurance>): Observable<ContratAssurance> {
    return this.http.patch<ContratAssurance>(`${API}/sinistres/contrats/${id}/`, data);
  }
  deleteContrat(id: string): Observable<any> {
    return this.http.delete(`${API}/sinistres/contrats/${id}/`);
  }
  getContratsByVehicule(vehiculeId: string): Observable<PaginatedResponse<ContratAssurance>> {
    const params = this.buildParams({ vehicule: vehiculeId, page_size: 20 });
    return this.http.get<PaginatedResponse<ContratAssurance>>(
      `${API}/sinistres/contrats/`, { params }
    );
  }
  getAssureurs(filters?: Record<string, any>): Observable<any[]> {
    const params = filters ? this.buildParams(filters) : undefined;
    return this.http.get<any[] | PaginatedResponse<any>>(`${API}/sinistres/assureurs/`, { params }).pipe(
      map(res => Array.isArray(res) ? res : res.results ?? [])
    );
  }
  createAssureur(data: Partial<Assureur>): Observable<Assureur> {
    return this.http.post<Assureur>(`${API}/sinistres/assureurs/`, data);
  }
  updateAssureur(id: string, data: Partial<Assureur>): Observable<Assureur> {
    return this.http.patch<Assureur>(`${API}/sinistres/assureurs/${id}/`, data);
  }
  deleteAssureur(id: string): Observable<any> {
    return this.http.delete(`${API}/sinistres/assureurs/${id}/`);
  }
}

// ── Chauffeurs API ──
@Injectable({ providedIn: 'root' })
export class ChauffeurApiService extends ApiBaseService {
  getAll(filters?: Record<string, any>): Observable<PaginatedResponse<Chauffeur>> {
    const params = filters ? this.buildParams(filters) : undefined;
    return this.http.get<PaginatedResponse<Chauffeur>>(`${API}/chauffeurs/`, { params });
  }
  getById(id: string): Observable<Chauffeur> {
    return this.http.get<Chauffeur>(`${API}/chauffeurs/${id}/`);
  }
  create(data: Partial<Chauffeur>): Observable<Chauffeur> {
    return this.http.post<Chauffeur>(`${API}/chauffeurs/`, data);
  }
  update(id: string, data: Partial<Chauffeur>): Observable<Chauffeur> {
    return this.http.patch<Chauffeur>(`${API}/chauffeurs/${id}/`, data);
  }
  getPermisExpirant(): Observable<Chauffeur[]> {
    return this.http.get<Chauffeur[]>(`${API}/chauffeurs/permis_expirant/`);
  }
  getHistoriqueCond(id: string): Observable<any> {
    return this.http.get(`${API}/chauffeurs/${id}/historique_conduite/`);
  }
}

// ── Budget API ──
@Injectable({ providedIn: 'root' })
export class BudgetApiService extends ApiBaseService {
  getBudgets(filters?: Record<string, any>): Observable<PaginatedResponse<BudgetAnnuel>> {
    const params = filters ? this.buildParams(filters) : undefined;
    return this.http.get<PaginatedResponse<BudgetAnnuel>>(`${API}/budget/budgets/`, { params });
  }
  createBudget(data: Partial<BudgetAnnuel>): Observable<BudgetAnnuel> {
    return this.http.post<BudgetAnnuel>(`${API}/budget/budgets/`, data);
  }
  updateBudget(id: string, data: Partial<BudgetAnnuel>): Observable<BudgetAnnuel> {
    return this.http.patch<BudgetAnnuel>(`${API}/budget/budgets/${id}/`, data);
  }
  getTableauDeBord(params?: Record<string, any>): Observable<any> {
    const p = params ? this.buildParams(params) : undefined;
    return this.http.get(`${API}/budget/budgets/tableau_de_bord/`, { params: p });
  }
  getDepenses(filters?: Record<string, any>): Observable<PaginatedResponse<Depense>> {
    const params = filters ? this.buildParams(filters) : undefined;
    return this.http.get<PaginatedResponse<Depense>>(`${API}/budget/depenses/`, { params });
  }
  createDepense(data: Partial<Depense>): Observable<Depense> {
    return this.http.post<Depense>(`${API}/budget/depenses/`, data);
  }
  updateDepense(id: string, data: Partial<Depense>): Observable<Depense> {
    return this.http.patch<Depense>(`${API}/budget/depenses/${id}/`, data);
  }
  deleteDepense(id: string): Observable<any> {
    return this.http.delete(`${API}/budget/depenses/${id}/`);
  }
  getDepensesByVehicule(vehiculeId: string): Observable<PaginatedResponse<Depense>> {
    const params = this.buildParams({ vehicule: vehiculeId, page_size: 20 });
    return this.http.get<PaginatedResponse<Depense>>(`${API}/budget/depenses/`, { params });
  }
}

// ── Contrôle Véhicule API ──
@Injectable({ providedIn: 'root' })
export class ControleApiService extends ApiBaseService {
  getElements(params?: Record<string, any>): Observable<any[]> {
    const p = params ? this.buildParams(params) : undefined;
    return this.http.get<any[]>(`${API}/controle/elements/`, { params: p }).pipe(
      map(res => Array.isArray(res) ? res : (res as any).results ?? [])
    );
  }
  createElement(data: any): Observable<any> {
    return this.http.post(`${API}/controle/elements/`, data);
  }
  updateElement(id: number, data: any): Observable<any> {
    return this.http.patch(`${API}/controle/elements/${id}/`, data);
  }
  deleteElement(id: number): Observable<any> {
    return this.http.delete(`${API}/controle/elements/${id}/`);
  }
  getFiches(params?: Record<string, any>): Observable<any> {
    const p = params ? this.buildParams(params) : undefined;
    return this.http.get<any>(`${API}/controle/fiches/`, { params: p });
  }
  getFiche(id: string): Observable<any> {
    return this.http.get(`${API}/controle/fiches/${id}/`);
  }
  createFiche(data: any): Observable<any> {
    return this.http.post(`${API}/controle/fiches/`, data);
  }
  validerFiche(id: string): Observable<any> {
    return this.http.post(`${API}/controle/fiches/${id}/valider/`, {});
  }
  getRapportFiche(id: string): Observable<any> {
    return this.http.get(`${API}/controle/fiches/${id}/rapport/`);
  }
  getStatsFiches(): Observable<any> {
    return this.http.get(`${API}/controle/fiches/stats/`);
  }
  bulkSavePoints(ficheId: string, points: any[]): Observable<any> {
    return this.http.post(`${API}/controle/points/bulk_save/`, { fiche_id: ficheId, points });
  }
  uploadPhoto(ficheId: string, formData: FormData): Observable<any> {
    return this.http.post(`${API}/controle/photos/`, formData);
  }
  deletePhoto(id: string): Observable<any> {
    return this.http.delete(`${API}/controle/photos/${id}/`);
  }
}

// ── Demandes API ──
@Injectable({ providedIn: 'root' })
export class DemandesApiService extends ApiBaseService {
  getLignes(demandeId: string): Observable<any[]> {
    return this.http.get<any[]>(`${API}/demandes/lignes/`, {
      params: this.buildParams({ demande: demandeId })
    }).pipe(map(res => Array.isArray(res) ? res : (res as any).results ?? []));
  }
  bulkSaveLignes(demandeId: string, lignes: any[]): Observable<any> {
    return this.http.post(`${API}/demandes/lignes/bulk_save/`, {
      demande_id: demandeId, lignes
    });
  }
  deleteLigne(id: number): Observable<any> {
    return this.http.delete(`${API}/demandes/lignes/${id}/`);
  }
  getNiveaux(typeDemandeId: string | number): Observable<any[]> {
    return this.http.get<any[]>(`${API}/demandes/niveaux/`, {
      params: this.buildParams({ type_demande: typeDemandeId })
    }).pipe(map(res => Array.isArray(res) ? res : (res as any).results ?? []));
  }
  createNiveau(data: any): Observable<any> {
    return this.http.post(`${API}/demandes/niveaux/`, data);
  }
  updateNiveau(id: number, data: any): Observable<any> {
    return this.http.patch(`${API}/demandes/niveaux/${id}/`, data);
  }
  deleteNiveau(id: number): Observable<any> {
    return this.http.delete(`${API}/demandes/niveaux/${id}/`);
  }
  getTypesDemande(actif?: boolean): Observable<any[]> {
    const p = actif !== undefined ? this.buildParams({ actif }) : undefined;
    return this.http.get<any[]>(`${API}/demandes/types/`, { params: p }).pipe(
      map(res => Array.isArray(res) ? res : (res as any).results ?? [])
    );
  }
  createTypeDemande(data: any): Observable<any> {
    return this.http.post(`${API}/demandes/types/`, data);
  }
  updateTypeDemande(id: string, data: any): Observable<any> {
    return this.http.patch(`${API}/demandes/types/${id}/`, data);
  }
  getDemandes(params?: Record<string, any>): Observable<any> {
    const p = params ? this.buildParams(params) : undefined;
    return this.http.get<any>(`${API}/demandes/`, { params: p });
  }
  getDemande(id: string): Observable<any> {
    return this.http.get(`${API}/demandes/${id}/`);
  }
  createDemande(data: any): Observable<any> {
    return this.http.post(`${API}/demandes/`, data);
  }
  updateDemande(id: string, data: any): Observable<any> {
    return this.http.patch(`${API}/demandes/${id}/`, data);
  }
  soumettre(id: string): Observable<any> {
    return this.http.post(`${API}/demandes/${id}/soumettre/`, {});
  }
  valider(id: string, commentaire?: string): Observable<any> {
    return this.http.post(`${API}/demandes/${id}/valider/`, { commentaire: commentaire ?? '' });
  }
  rejeter(id: string, commentaire: string): Observable<any> {
    return this.http.post(`${API}/demandes/${id}/rejeter/`, { commentaire });
  }
  annuler(id: string): Observable<any> {
    return this.http.post(`${API}/demandes/${id}/annuler/`, {});
  }
  getStats(vue?: string): Observable<any> {
    const p = vue ? this.buildParams({ vue }) : undefined;
    return this.http.get(`${API}/demandes/stats/`, { params: p });
  }
  getAValider(): Observable<any[]> {
    return this.http.get<any[]>(`${API}/demandes/a_valider/`).pipe(
      map(res => Array.isArray(res) ? res : (res as any).results ?? [])
    );
  }
}

// ── Alertes API ──
@Injectable({ providedIn: 'root' })
export class AlerteApiService extends ApiBaseService {
  getAll(filters?: Record<string, any>): Observable<PaginatedResponse<Alerte>> {
    const params = filters ? this.buildParams(filters) : undefined;
    return this.http.get<PaginatedResponse<Alerte>>(`${API}/alertes/`, { params });
  }
  traiter(id: string, notes?: string): Observable<any> {
    return this.http.post(`${API}/alertes/${id}/traiter/`, { notes: notes ?? '' });
  }
  ignorer(id: string): Observable<any> {
    return this.http.post(`${API}/alertes/${id}/ignorer/`, {});
  }
  marquerToutesLues(): Observable<any> {
    return this.http.post(`${API}/alertes/marquer_toutes_lues/`, {});
  }
  getResume(): Observable<any> {
    return this.http.get(`${API}/alertes/resume/`);
  }
  generer(): Observable<any> {
    return this.http.post(`${API}/alertes/generer/`, {});
  }
}

// ── Rapports API ──
@Injectable({ providedIn: 'root' })
export class RapportApiService extends ApiBaseService {
  getDashboard(params?: Record<string, any>): Observable<DashboardData> {
    const p = params ? this.buildParams(params) : undefined;
    return this.http.get<DashboardData>(`${API}/rapports/dashboard/`, { params: p });
  }
  getCarburant(params?: Record<string, any>): Observable<any> {
    const p = params ? this.buildParams(params) : undefined;
    return this.http.get(`${API}/rapports/carburant/`, { params: p });
  }
  getCouts(params?: Record<string, any>): Observable<any> {
    const p = params ? this.buildParams(params) : undefined;
    return this.http.get(`${API}/rapports/couts/`, { params: p });
  }
  getMultiAgences(params?: Record<string, any>): Observable<any> {
    const p = params ? this.buildParams(params) : undefined;
    return this.http.get(`${API}/rapports/multi-agences/`, { params: p });
  }
  getSinistres(params?: Record<string, any>): Observable<any> {
    const p = params ? this.buildParams(params) : undefined;
    return this.http.get(`${API}/rapports/sinistres/`, { params: p });
  }
  getInterventions(params?: Record<string, any>): Observable<any> {
    const p = params ? this.buildParams(params) : undefined;
    return this.http.get(`${API}/rapports/interventions/`, { params: p });
  }
  getPneus(params?: Record<string, any>): Observable<any> {
    const p = params ? this.buildParams(params) : undefined;
    return this.http.get(`${API}/rapports/pneus/`, { params: p });
  }
  getEffectifParc(params?: Record<string, any>): Observable<any> {
    const p = params ? this.buildParams(params) : undefined;
    return this.http.get(`${API}/rapports/effectif-parc/`, { params: p });
  }
}

// ── Paramétrage API ──
@Injectable({ providedIn: 'root' })
export class ParametrageApiService extends ApiBaseService {
  getAll(categorie?: string): Observable<any[]> {
    const params = categorie ? this.buildParams({ categorie }) : undefined;
    return this.http.get<any[] | PaginatedResponse<any>>(`${API}/parametrage/`, { params }).pipe(
      map(res => Array.isArray(res) ? res : res.results ?? [])
    );
  }
  update(id: number, valeur: string): Observable<any> {
    return this.http.patch(`${API}/parametrage/${id}/`, { valeur });
  }
  bulkUpdate(items: { cle: string; valeur: string }[]): Observable<any> {
    return this.http.post(`${API}/parametrage/bulk_update/`, items);
  }
  byCategorie(): Observable<Record<string, any[]>> {
    return this.http.get<Record<string, any[]>>(`${API}/parametrage/by_categorie/`);
  }
  // Affectations / Usages
  getAffectations(): Observable<any[]> {
    return this.http.get<any[]>(`${API}/parametrage/affectations/`).pipe(
      map(res => Array.isArray(res) ? res : (res as any).results ?? [])
    );
  }
  createAffectation(data: any): Observable<any> {
    return this.http.post(`${API}/parametrage/affectations/`, data);
  }
  updateAffectation(id: number, data: any): Observable<any> {
    return this.http.patch(`${API}/parametrage/affectations/${id}/`, data);
  }
  deleteAffectation(id: number): Observable<any> {
    return this.http.delete(`${API}/parametrage/affectations/${id}/`);
  }

  // Statuts véhicule
  getStatutsVehicule(): Observable<any[]> {
    return this.http.get<any[]>(`${API}/parametrage/statuts/`).pipe(
      map(res => Array.isArray(res) ? res : (res as any).results ?? [])
    );
  }
  createStatutVehicule(data: any): Observable<any> {
    return this.http.post(`${API}/parametrage/statuts/`, data);
  }
  updateStatutVehicule(id: number, data: any): Observable<any> {
    return this.http.patch(`${API}/parametrage/statuts/${id}/`, data);
  }
  deleteStatutVehicule(id: number): Observable<any> {
    return this.http.delete(`${API}/parametrage/statuts/${id}/`);
  }

  // Marques véhicule
  getMarques(actif?: boolean): Observable<any[]> {
    const p = actif !== undefined ? this.buildParams({ actif }) : undefined;
    return this.http.get<any[]>(`${API}/parametrage/marques/`, { params: p }).pipe(
      map(res => Array.isArray(res) ? res : (res as any).results ?? [])
    );
  }
  createMarque(data: any): Observable<any> {
    return this.http.post(`${API}/parametrage/marques/`, data);
  }
  updateMarque(id: number, data: any): Observable<any> {
    return this.http.patch(`${API}/parametrage/marques/${id}/`, data);
  }
  deleteMarque(id: number): Observable<any> {
    return this.http.delete(`${API}/parametrage/marques/${id}/`);
  }

  // Modèles véhicule
  getModeles(filters?: { actif?: boolean; marque?: number }): Observable<any[]> {
    const p = filters ? this.buildParams(filters) : undefined;
    return this.http.get<any[]>(`${API}/parametrage/modeles/`, { params: p }).pipe(
      map(res => Array.isArray(res) ? res : (res as any).results ?? [])
    );
  }
  createModele(data: any): Observable<any> {
    return this.http.post(`${API}/parametrage/modeles/`, data);
  }
  updateModele(id: number, data: any): Observable<any> {
    return this.http.patch(`${API}/parametrage/modeles/${id}/`, data);
  }
  deleteModele(id: number): Observable<any> {
    return this.http.delete(`${API}/parametrage/modeles/${id}/`);
  }

  // Tournées
  getTournees(filters?: { actif?: boolean; agence?: string }): Observable<any[]> {
    const p = filters ? this.buildParams(filters) : undefined;
    return this.http.get<any[]>(`${API}/parametrage/tournees/`, { params: p }).pipe(
      map(res => Array.isArray(res) ? res : (res as any).results ?? [])
    );
  }
  createTournee(data: any): Observable<any> {
    return this.http.post(`${API}/parametrage/tournees/`, data);
  }
  updateTournee(id: number, data: any): Observable<any> {
    return this.http.patch(`${API}/parametrage/tournees/${id}/`, data);
  }
  importTourneesExcel(fichier: File): Observable<any> {
    const fd = new FormData();
    fd.append('fichier', fichier, fichier.name);
    return this.http.post(`${API}/parametrage/tournees/import_excel/`, fd);
  }
  deleteTournee(id: number): Observable<any> {
    return this.http.delete(`${API}/parametrage/tournees/${id}/`);
  }
  demanderDotation(id: number, data: { nouvelle_dotation: number; motif: string }): Observable<any> {
    return this.http.post(`${API}/parametrage/tournees/${id}/demander_dotation/`, data);
  }
  historiqueDotation(id: number): Observable<any[]> {
    return this.http.get<any[]>(`${API}/parametrage/tournees/${id}/historique_dotation/`);
  }
  // Types de mouvement (relevés kilométriques)
  getTypesMouvement(filters?: { actif?: boolean }): Observable<any[]> {
    const params = filters ? this.buildParams(filters) : undefined;
    return this.http.get<any[]>(`${API}/parametrage/types-mouvement/`, { params });
  }
  createTypeMouvement(data: any): Observable<any> {
    return this.http.post(`${API}/parametrage/types-mouvement/`, data);
  }
  updateTypeMouvement(id: number, data: any): Observable<any> {
    return this.http.patch(`${API}/parametrage/types-mouvement/${id}/`, data);
  }
  deleteTypeMouvement(id: number): Observable<any> {
    return this.http.delete(`${API}/parametrage/types-mouvement/${id}/`);
  }
}

// ── Faits marquants API ──
@Injectable({ providedIn: 'root' })
export class FaitsMarquantsApiService extends ApiBaseService {
  getAll(filters?: Record<string, any>): Observable<PaginatedResponse<any>> {
    const params = filters ? this.buildParams(filters) : undefined;
    return this.http.get<PaginatedResponse<any>>(`${API}/faits-marquants/`, { params });
  }
  create(data: FormData): Observable<any> {
    return this.http.post(`${API}/faits-marquants/`, data);
  }
  update(id: string, data: FormData): Observable<any> {
    return this.http.patch(`${API}/faits-marquants/${id}/`, data);
  }
  delete(id: string): Observable<any> {
    return this.http.delete(`${API}/faits-marquants/${id}/`);
  }
}
// ── Total Import API ──
@Injectable({ providedIn: 'root' })
export class TotalImportApiService extends ApiBaseService {
  upload(formData: FormData): Observable<any> {
    return this.http.post<any>(`${API}/total-import/historique/upload/`, formData, {
      reportProgress: true,
      observe: 'events',
    });
  }

  getHistorique(filters?: Record<string, any>): Observable<any> {
    const params = filters ? this.buildParams(filters) : undefined;
    return this.http.get<any>(`${API}/total-import/historique/`, { params });
  }

  getTransactions(filters?: Record<string, any>): Observable<any> {
    const params = filters ? this.buildParams(filters) : undefined;
    return this.http.get<any>(`${API}/total-import/transactions/`, { params });
  }

  getStats(filters?: Record<string, any>): Observable<any> {
    const params = filters ? this.buildParams(filters) : undefined;
    return this.http.get<any>(`${API}/total-import/transactions/stats/`, { params });
  }

  getConsommation(filters: Record<string, string>): Observable<any> {
    const params = this.buildParams(filters);
    return this.http.get<any>(`${API}/total-import/transactions/consommation/`, { params });
  }

  getEvolutionAgences(filters: Record<string, string>): Observable<any> {
    const params = this.buildParams(filters);
    return this.http.get<any>(`${API}/total-import/transactions/evolution_agences/`, { params });
  }

  getReconciliation(filters: Record<string, any>): Observable<any> {
    const params = this.buildParams(filters);
    return this.http.get<any>(`${API}/total-import/reconciliation/comparer/`, { params });
  }
}
