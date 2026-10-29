// UbiFleet — Entry Point
import { bootstrapApplication } from '@angular/platform-browser';
import { AppComponent } from './app/app.component';
import { appConfig } from './app/app.config';
import { registerLocaleData } from '@angular/common';
import localeFr from '@angular/common/locales/fr';

// Enregistrer la locale française AVANT bootstrap
// On enregistre sous 'fr-FR' (utilisé par LOCALE_ID dans app.config.ts)
registerLocaleData(localeFr, 'fr-FR');

bootstrapApplication(AppComponent, appConfig)
  .catch(err => console.error(err));
