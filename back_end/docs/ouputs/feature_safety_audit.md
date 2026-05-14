# Feature Safety Audit

| Élément | Valeur |
|---|---|
| Généré le | `2026-05-14T04:27:35.254362+00:00` |
| Data lake | `/content/drive/MyDrive/PFE ML Data/pfe_data/data-lake` |

## Objectif

Ce rapport classe chaque feature selon son niveau de sécurité historique et indique les champs qui nécessitent une vérification.

## Registre Des Features

| feature | source | status | present | note |
| --- | --- | --- | --- | --- |
| siren | technical_key | excluded | True | Identifiant de jointure, exclu de l'entraînement pour éviter la mémorisation. |
| prediction_year | temporal_key | safe_historical | True | Année d'observation utilisée pour construire la date de coupure. |
| prediction_date | temporal_key | excluded | True | Date de coupure utile pour l'audit, exclue du modèle. |
| company_name | INSEE | excluded_or_display_only | True | Nom utile pour l'affichage et l'audit, pas un signal ML robuste. |
| activity_code | INSEE | needs_verification | True | Code d'activité conservé depuis l'identité; vérifier la validité historique si l'activité change. |
| legal_category_code | INSEE | needs_verification | True | Catégorie juridique potentiellement évolutive; vérifier l'historique source. |
| employee_size_bracket | INSEE | needs_verification | True | Tranche d'effectif potentiellement datée; vérifier la source et l'année. |
| administrative_status_at_cutoff | INSEE | needs_verification | True | Doit provenir d'une période <= prediction_date; point sensible anti-leakage. |
| company_age_years | INSEE | safe_derived_from_historical_date | True | Calculé depuis creation_date et prediction_date. |
| legal_events_count_all | BODACC | safe_event_based | True | Événements filtrés avec event_date <= prediction_date. |
| legal_events_count_12m | BODACC | safe_event_based | True | Événements filtrés dans les 12 mois avant prediction_date. |
| legal_risk_events_count_all | BODACC | safe_event_based | True | Événements risqués passés uniquement. |
| legal_risk_events_count_12m | BODACC | safe_event_based | True | Événements risqués récents passés uniquement. |
| legal_distress_events_count_all | BODACC | safe_event_based | True | Historique passé de procédures collectives. |
| radiation_events_count_all | BODACC | safe_event_based | True | Radiations passées uniquement. |
| days_since_last_legal_event | BODACC | safe_derived_from_historical_date | True | Calculé depuis le dernier event_date passé et prediction_date. |
| formalities_count_all | INPI formalites | safe_event_based | True | Formalités passées uniquement. |
| formalities_count_12m | INPI formalites | safe_event_based | True | Formalités des 12 mois avant prediction_date. |
| cessation_formalities_count_all | INPI formalites | safe_event_based | True | Cessation/radiation/fermeture passées uniquement. |
| annual_accounts_count_all | INPI comptes annuels | safe_event_based | True | Dépôts passés uniquement. |
| annual_accounts_count_24m | INPI comptes annuels | safe_event_based | True | Dépôts des 24 mois avant prediction_date. |
| days_since_last_account_filing | INPI comptes annuels | safe_derived_from_historical_date | True | Calculé depuis le dernier dépôt passé. |
| latest_account_closing_year | INPI comptes annuels | safe_historical | True | Année de clôture max avec dépôt disponible avant prediction_date. |
| latest_revenue | financials | safe_historical | True | Dernière valeur avec financial_year <= prediction_year. |
| latest_net_result | financials | safe_historical | True | Dernière valeur avec financial_year <= prediction_year. |
| latest_equity | financials | safe_historical | True | Dernière valeur avec financial_year <= prediction_year. |
| latest_debt | financials | safe_historical | True | Dernière valeur avec financial_year <= prediction_year. |
| latest_total_assets | financials | safe_historical | True | Dernière valeur avec financial_year <= prediction_year. |
| latest_net_margin | financials | safe_historical | True | Ratio issu de la dernière année financière passée. |
| latest_debt_to_assets | financials | safe_historical | True | Ratio issu de la dernière année financière passée. |
| latest_equity_ratio | financials | safe_historical | True | Ratio issu de la dernière année financière passée. |
| latest_debt_to_equity | financials | safe_historical | True | Ratio issu de la dernière année financière passée. |
| has_negative_result_history | financials | safe_historical | True | Historique financier jusqu'à prediction_year. |
| has_negative_equity_history | financials | safe_historical | True | Historique financier jusqu'à prediction_year. |
| has_financial_data | financials | safe_derived | True | Indicateur de disponibilité, pas une valeur future. |
| financial_years_available | financials | safe_historical | True | Nombre d'années disponibles jusqu'à prediction_year. |
| latest_financial_year | financials | safe_historical | True | Doit être <= prediction_year. |
| years_since_last_financial_statement | financials | safe_derived_from_historical_date | True | Calculé avec prediction_year et latest_financial_year. |
| has_confidential_financials | financials | safe_historical | True | Indicateur de confidentialité observé dans l'historique. |
| revenue_growth_1y | financials | safe_historical | True | Compare latest_revenue à prediction_year - 1. |
| net_result_change_1y | financials | safe_historical | True | Compare latest_net_result à prediction_year - 1. |

## Features À Vérifier

| feature | source | status | present | note |
| --- | --- | --- | --- | --- |
| activity_code | INSEE | needs_verification | True | Code d'activité conservé depuis l'identité; vérifier la validité historique si l'activité change. |
| legal_category_code | INSEE | needs_verification | True | Catégorie juridique potentiellement évolutive; vérifier l'historique source. |
| employee_size_bracket | INSEE | needs_verification | True | Tranche d'effectif potentiellement datée; vérifier la source et l'année. |
| administrative_status_at_cutoff | INSEE | needs_verification | True | Doit provenir d'une période <= prediction_date; point sensible anti-leakage. |

## Colonnes Non Documentées

```json
[]
```
