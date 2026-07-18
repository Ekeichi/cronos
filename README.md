# training_plan

Génération de plans d'entraînement trail : squelette hebdomadaire, assemblage
de macrocycle, et couche d'ajustement par readiness.

## Structure

```
domain/       modèles et enums partagés (dataclasses) : SessionSlot,
              SlotTemplate, MacrocycleBlock, ReadinessSignals,
              SessionFeedback, DecisionEvent, FeedbackEvent, Phase,
              SessionRole, Priority, ReadinessBand.

generation/   déterministe, stable. Construit le "plan idéal si tout va
              bien" à partir des templates de phase et des courbes de
              progression/taper. Ne connaît rien du readiness et n'a pas
              vocation à changer souvent — c'est la baseline sur laquelle
              le reste du système s'appuie.

readiness/    adaptatif, amené à évoluer plus vite que generation/. Prend
              une semaine déjà générée et la module selon des signaux de
              readiness (score, TSB, monotony, ACWR). Les règles ici sont
              volontairement simples aujourd'hui (v1) et seront probablement
              remplacées ou étendues (hystérésis, ML) sans toucher à
              generation/.

config/       paramètres calibrables sans redéploiement de code : templates
              de phase, courbes de décroissance du taper, seuils de
              readiness. Chargés et convertis en structures Python par
              config/loader.py — c'est le seul point du package qui connaît
              le format YAML sur disque.

persistence/  export du plan généré vers des formats externes (CSV), et
              journalisation append-only (JSONL) des décisions et feedbacks
              pour constituer un historique par athlète. Effet de bord
              explicite, appelé depuis l'extérieur de generation/ et
              readiness/ (jamais depuis ces couches elles-mêmes, qui
              restent pures). Nommé "persistence" et non "io" pour éviter
              la collision avec le module stdlib du même nom.

orchestration/ compose generation/, readiness/ et persistence/ pour un
              athlète et un jour donnés (run_daily_adjustment,
              record_session_feedback). Pas un scheduler de production —
              juste la logique de composition avec effets de bord (lecture
              du dernier band, du feedback récent, écriture du log),
              appelable telle quelle, prête à être branchée derrière un
              scheduler ou une API plus tard.

tests/        tests unitaires + non-régression (golden file capturé depuis
              l'ancien module monolithique, voir tests/fixtures/).
```

## Principe de séparation

- `generation/` ne doit jamais importer `readiness/`.
- `readiness/` peut importer `domain/` mais ne doit rien connaître de la
  façon dont `generation/` construit ses templates.
- Aucune valeur calibrable (ratios de templates, courbes de taper, seuils de
  readiness) n'est hardcodée dans le code Python : tout passe par
  `config/loader.py`, qui lit les fichiers YAML de `config/`.
- `generation/` et `readiness/` restent pures (aucune écriture disque) ; les
  effets de bord (lecture d'historique, logging) vivent exclusivement dans
  `orchestration/`, jamais à l'intérieur de ces deux couches.

## Note

Les modèles restent des `dataclasses` dans ce refactor (pas de migration
vers Pydantic — prévue dans une passe séparée).
