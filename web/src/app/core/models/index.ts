// ═══════════════════════════════════════════════
//  UbiFleet — Core Models / Interfaces TypeScript
// ═══════════════════════════════════════════════

// ── Auth ──
export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginResponse {
  access: string;
  refresh: string;
  user: User;
}

export interface User {
  id: string;
  email: string;
  username: string;
  first_name: string;
  last_name: string;
  full_name: string;
  role: UserRole;
  role_display: string;
  agence: string | null;
  agence_detail: Agence | null;
  telephone: string;
  avatar: string | null;
  is_active: boolean;
  date_joined: string;
}



// ── Agence ──
export interface Agence {
  id: string;
  nom: string;
  code: string;
  ville: string;
  adresse: string;
  telephone: string;
  responsable_nom: string;
  nb_vehicules: number;
  is_active: boolean;
  created_at: string;
}

// ── Véhicule ──
export type StatutVehicule = 'en_service' | 'en_revision' | 'immobilise' | 'vendu' | 'en_panne' | string;
export type TypeCarburant  = 'diesel' | 'essence' | 'hybride' | 'electrique' | 'gpl';
export type TypeVehicule   = string;   // code d'un type de véhicule (Paramètres › Types de véhicule)

export interface Vehicule {
  id: string;
  immatriculation: string;
  marque: number | null;
  marque_libelle: string | null;
  modele: number | null;
  modele_libelle: string | null;
  annee: number;
  couleur: string;
  designation: string;
  type_vehicule: TypeVehicule;
  type_vehicule_display: string;
  type_carburant: TypeCarburant;
  type_carburant_display: string;
  nombre_places: number;
  statut: number | null;
  statut_display: string;
  statut_couleur: string;
  agence: string;
  agence_detail: Agence;
  affectation: number | null;
  affectation_libelle: string | null;
  chauffeur_attitré: string | null;
  chauffeur_nom: string | null;
  kilometrage_actuel: number;
  conso_theorique_origine: number;
  numero_carte_carburant?: string;
  kilometrage_revision: number;
  revision_due: boolean;
  dotation_carburant_mensuelle: number;
  consommation_moyenne: number | null;
  date_mise_en_service: string | null;
  photo: string | null;
  is_active: boolean;
  created_at: string;
  immatriculation_provisoire: string | null;
  est_immatriculation_provisoire: boolean;
  date_immatriculation_definitive: string | null;
}

export interface VehiculeDetail extends Vehicule {
  indicateurs_carburant?: {
    periode_jours: number; conso_3_mois: number | null; km_3_mois: number | null; conso_reference: number | null;
    ecart_pct: number | null; cout_km: number | null; nb_prises: number; nb_anomalies: number;
  };
  numero_chassis: string;
  date_acquisition: string | null;
  valeur_acquisition: number | null;
  notes: string;
  documents: DocumentVehicule[];
}

export interface DocumentVehicule {
  id: string;
  type_document: string;
  type_display: string;
  numero: string;
  date_emission: string | null;
  date_expiration: string | null;
  fichier: string;
  est_expire: boolean;
  notes: string;
  created_at: string;
}

// ── Carburant ──
export type StatutValidation = 'en_attente' | 'valide' | 'anomalie' | 'rejete';

export interface PleinCarburant {
  id: string;
  // Fenêtre de saisie : figé pour l'utilisateur courant, trace hors délai
  verrouille?: boolean;
  hors_fenetre?: boolean;   // date sortie de la fenêtre : motif obligatoire pour corriger
  modifiable?: boolean;     // l'utilisateur courant peut modifier / supprimer
  supprimable?: boolean;
  saisie_hors_delai?: boolean;
  hors_delai_par_nom?: string | null;
  hors_delai_le?: string | null;
  vehicule: string;
  vehicule_immat: string;
  vehicule_designation: string;
  chauffeur: string | null;
  chauffeur_nom: string | null;
  station: string | null;
  station_nom: string | null;
  tournee?: number | null;
  tournee_code?: string | null;
  type_mouvement?: string;
  type_display?: string;
  tournee_effectuee?: string | null;
  tournee_effectuee_numero?: string | null;
  tournee_effectuee_statut?: string | null;
  tournee_libelle?: string | null;
  date_plein: string;
  heure_plein: string | null;
  volume_litres: number;
  prix_litre: number | null;
  montant_fcfa: number;
  kilometrage_releve: number;
  consommation_calculee: number | null;
  bon_carburant: string;
  photo_bon: string | null;
  photo_tableau_bord: string | null;
  statut_validation: StatutValidation;
  statut_display: string;
  motif_anomalie: string;
  notes: string;
  agence: string;
  agence_nom: string;
  created_at: string;
}

export interface Station {
  id: string;
  nom: string;
  ville: string;
  agence: string | null;
  est_partenaire: boolean;
}

// ── Entretien ──
export type StatutIntervention = 'planifie' | 'en_cours' | 'termine' | 'annule' | 'attente_piece';
export type PrioriteIntervention = 'critique' | 'haute' | 'normale' | 'basse';

export interface Intervention {
  id: string;
  vehicule: string;
  vehicule_immat: string;
  vehicule_designation: string;
  type_intervention: string;
  type_nom: string;
  type_categorie: string;
  prestataire: string | null;
  prestataire_nom: string | null;
  date_planifiee: string;
  date_debut: string | null;
  date_fin: string | null;
  kilometrage_intervention: number | null;
  prochain_km: number | null;
  cout_estime: number;
  cout_reel: number | null;
  statut: StatutIntervention;
  statut_display: string;
  priorite: PrioriteIntervention;
  priorite_display: string;
  description: string;
  rapport_intervention: string;
  agence: string;
  agence_nom: string;
  created_at: string;
}

export interface Prestataire {
  id: string;
  nom: string;
  specialite: string;
  telephone: string;
  email: string;
  ville: string;
  adresse: string;
  note_qualite: number | null;
}

export interface SuiviPneus {
  id: string;
  vehicule: string;
  vehicule_immat: string;
  position: string;
  position_display: string;
  marque: string;
  dimension: string;
  date_montage: string;
  kilometrage_montage: number;
  kilometrage_remplacement: number | null;
  statut: string;
  statut_display: string;
  cout: number;
  usure_pct: number | null;
  kilometrage_utilise: number;
}

// ── Sinistres ──
/** Code de Paramètres › Types de sinistre. */
export type TypeSinistre = string;
export type StatutSinistre = 'declare' | 'en_instruction' | 'expertise' | 'reparation' | 'indemnise' | 'clos' | 'conteste';

export interface Sinistre {
  id: string;
  numero_dossier: string;
  vehicule: string;
  vehicule_immat: string;
  vehicule_designation: string;
  chauffeur: string | null;
  chauffeur_nom: string | null;
  type_sinistre: TypeSinistre;
  type_display: string;
  statut: StatutSinistre;
  statut_display: string;
  date_sinistre: string;
  lieu: string;
  description: string;
  dommages_estimes: number;
  cout_reparation: number | null;
  indemnisation_recue: number | null;
  agence: string;
  agence_nom: string;
  created_at: string;
}

export interface ContratAssurance {
  id: string;
  vehicule: string;
  vehicule_immat: string;
  assureur: string;
  assureur_nom: string;
  numero_police: string;
  type_contrat: string;
  type_display: string;
  date_debut: string;
  date_fin: string;
  prime_annuelle: number;
  franchise: number;
  is_active: boolean;
  est_expire: boolean;
  jours_restants: number;
}

// ── Chauffeur ──
export interface Chauffeur {
  id: string;
  matricule: string;
  nom: string;
  prenom: string;
  nom_complet: string;
  telephone: string;
  email: string;
  numero_permis: string;
  categories_permis: string;
  date_expiration_permis: string | null;
  permis_expire: boolean;
  jours_expiration_permis: number | null;
  date_naissance: string | null;
  adresse: string;
  date_obtention_permis: string | null;
  notes: string;
  agence: string;
  agence_nom: string;
  statut: string;
  statut_display: string;
  vehicule_actuel: { id: string; immatriculation: string; designation: string } | null;
  photo: string | null;
}

// ── Budget ──
export interface BudgetAnnuel {
  id: string;
  agence: string;
  agence_nom: string;
  annee: number;
  budget_carburant: number;
  budget_entretien: number;
  budget_reparations: number;
  budget_assurances: number;
  budget_pneumatiques: number;
  budget_divers: number;
  budget_total: number;
  realise: Record<string, number>;
  notes: string;
}

export interface Depense {
  id: string;
  vehicule: string;
  vehicule_immat: string;
  agence: string;
  agence_nom: string;
  categorie: string;
  categorie_display: string;
  date_depense: string;
  montant: number;
  description: string;
  fournisseur: string;
  numero_facture: string;
  /** Dépense reportée depuis une prise de carburant (modifiable seulement par la prise). */
  automatique?: boolean;
  ref_objet_id?: string | null;
  ref_objet_type?: string;
  /** Prise de carburant, Intervention, Pneu, Contrat d'assurance, Sinistre ou Saisie manuelle. */
  origine?: string;
}

// ── Alertes ──
export type TypeAlerte =
  | 'revision_due' | 'assurance_exp' | 'assurance_expiree'
  | 'conso_anormale' | 'ct_exp' | 'ct_expiree'
  | 'permis_exp' | 'permis_expire'
  | 'budget_depasse' | 'pneu_usure' | 'plein_anomalie' | 'sinistre_ouvert';

export type PrioriteAlerte = 'critique' | 'haute' | 'normale' | 'basse';
export type StatutAlerte   = 'active' | 'lue' | 'traitee' | 'ignoree';

export interface Alerte {
  id: string;
  type_alerte: TypeAlerte;
  type_display: string;
  priorite: PrioriteAlerte;
  priorite_display: string;
  statut: StatutAlerte;
  statut_display: string;
  titre: string;
  message: string;
  vehicule: string | null;
  vehicule_immat: string | null;
  chauffeur: string | null;
  chauffeur_nom: string | null;
  agence: string;
  agence_nom: string;
  /** Prise de carburant à l'origine d'une alerte « Consommation anormale ». */
  plein?: string | null;
  date_echeance: string | null;
  created_at: string;
}

// ── Dashboard ──
export interface DashboardData {
  periode: { mois: number; annee: number };
  parc: { total: number; en_service: number; en_revision: number; immobilises: number };
  carburant: {
    volume: number; montant: number; nb_pleins: number;
    conso_moy: number; anomalies: number;
  };
  entretien: { planifiees: number; terminees: number; en_cours: number; cout: number };
  sinistres: { en_cours: number; annee: number };
  alertes: { total: number; critiques: number; hautes: number };
  cout_mensuel: { mois: number; annee: number; total: number }[];
  top_consommation: any[];
  top_ecart_conso?: { vehicule__immatriculation: string; vehicule__marque: string; vehicule__modele: string; conso: number; reference: number; ecart_pct: number; litres: number }[];
  repartition_couts: { categorie: string; label: string; montant: number }[];
  assurances_critiques: number;
}

// ── API Pagination ──
export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

// ── API Error ──
export interface ApiError {
  detail?: string;
  [key: string]: any;
}

/** Code d'un type de mouvement paramétrable (Paramètres › Types de mouvement). */
export type TypeMouvement = string;

export interface ReleveKilometrage {
  id: string;
  // Fenêtre de saisie : figé pour l'utilisateur courant, trace hors délai
  verrouille?: boolean;
  hors_fenetre?: boolean;   // date sortie de la fenêtre : motif obligatoire pour corriger
  modifiable?: boolean;     // l'utilisateur courant peut modifier / supprimer
  supprimable?: boolean;
  saisie_hors_delai?: boolean;
  hors_delai_par_nom?: string | null;
  hors_delai_le?: string | null;
  vehicule: string;
  vehicule_immat: string;
  vehicule_designation: string;
  kilometrage: number;
  date_releve: string;
  heure_releve: string | null;   // HH:MM:SS ; null pour les relevés antérieurs
  type_mouvement: TypeMouvement;
  type_display: string;
  chauffeur: string | null;
  chauffeur_nom: string | null;
  chauffeur_matricule?: string | null;
  tournee: number | null;         // référentiel Tournée ; renseignée pour le type « tournée »
  tournee_code?: string | null;
  tournee_libelle?: string | null;
  notes: string;
  photo_tableau_bord: string | null;
  photo_tableau_bord_url: string | null;
  created_by: string | null;
  created_by_nom: string | null;
  created_at: string;
}

export interface HistoriqueImmatriculation {
  id: string;
  vehicule: string;
  ancienne_immatriculation: string;
  nouvelle_immatriculation: string;
  date_changement: string;
  motif: string;
  created_by: string | null;
  created_by_nom: string | null;
  created_at: string;
}

export interface Assureur {
  id: string;
  nom: string;
  telephone: string;
  email: string;
  adresse: string;
  contact_sinistre: string;
  is_active: boolean;
}

export interface AffectationVehicule {
  id: string;
  vehicule: string;
  vehicule_immat: string;
  vehicule_designation: string;
  chauffeur: string;
  chauffeur_nom: string;
  date_debut: string;
  date_fin: string | null;
  notes: string;
  est_active: boolean;
  created_by: string | null;
  created_by_nom: string | null;
  created_at: string;
  updated_at: string;
}

// Rôles dynamiques — viennent de la DB
export interface Role {
  id: string;
  code: string;
  nom: string;
  description: string;
  niveau: number;
  is_active: boolean;
  is_system: boolean;
  nb_utilisateurs: number;
  created_at: string;
  updated_at: string;
}

export interface UbiUser {
  id: string;
  email: string;
  username: string;
  first_name: string;
  last_name: string;
  full_name: string;
  role: string | null;            // UUID du rôle
  role_detail?: Role | null;      // Rôle complet (objet, optionnel selon l'endpoint)
  role_display?: string;          // Nom du rôle (rétrocompatibilité)
  agence: string | null;
  agence_detail: { id: string; nom: string; code: string } | null;
  telephone: string;
  avatar: string | null;
  is_active: boolean;
  date_joined: string;
}

// Gardé pour rétrocompatibilité dans les composants
export type UserRole = string;
