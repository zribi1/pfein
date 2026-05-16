"""V2 tooling — period-aware identity, per-label models, bootstrap CIs.

V2 réutilise les couches `raw` et `clean` de V1 telles quelles, à l'exception
d'une nouvelle table `clean/company_identity_periodic` reconstruite depuis
`raw/insee/bulk/stock_unite_legale_historique`. Voir `docs/v2/` pour le plan.
"""
