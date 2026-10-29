// UbiFleet — Budget & Comptabilité Component (Angular 18)
import { Component, inject, signal, OnInit, ChangeDetectionStrategy } from '@angular/core';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'ubi-budget',
  standalone: true,
  imports: [RouterLink],
  templateUrl: './budget.component.html',
  styleUrls: ['./budget.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class BudgetComponent implements OnInit {
  loading = signal(false);

  ngOnInit(): void {
    // Charger les données depuis l'API
  }
}
