# Diagrammes corriges - AgroVision Olive AI

Ce dossier contient les versions PlantUML corrigees des diagrammes du rapport.

Regle importante :

- Les diagrammes de cas d'utilisation montrent uniquement les acteurs et les objectifs fonctionnels.
- Les axes de vie apparaissent uniquement dans les diagrammes de sequence.
- Les traitements internes apparaissent dans les diagrammes d'activite, de sequence ou de pipeline, pas dans les cas d'utilisation.
- Les services externes, comme Open-Meteo, sont modelises comme services secondaires et seulement connectes aux cas qui consomment leurs donnees.

Sources de syntaxe utilisees :

- PlantUML, Use case diagram syntax : https://plantuml.com/use-case-diagram
- PlantUML, Sequence diagram syntax : https://plantuml.com/sequence-diagram
- PlantUML, Class diagram syntax : https://plantuml.com/class-diagram
- PlantUML, Activity diagram syntax : https://plantuml.com/activity-diagram-beta

## Correspondance avec le rapport

| Diagramme du rapport | Fichier PlantUML corrige | Image Prism a remplacer |
| --- | --- | --- |
| Cas d'utilisation global | `01_usecase_global.puml` | `prism-uploads/use case.png` |
| Gantt | `02_gantt.puml` | `prism-uploads/gantt-agrovision.png` |
| Architecture logique | `03_architecture_logique.puml` | `prism-uploads/Capture d'écran 2026-05-15 224708_2.png` |
| Architecture physique | `04_architecture_physique.puml` | `prism-uploads/Capture d'écran 2026-05-15 233952.png` |
| Cas d'utilisation Sprint 1 | `05_usecase_lot1_ferme.puml` | `prism-uploads/di.png` |
| Classes Sprint 1 | `06_classes_lot1_ferme.puml` | `prism-uploads/classe sp1.png` |
| Sequence ferme | `07_sequence_lot1_ferme.puml` | `prism-uploads/seq sp1.png` |
| Cas d'utilisation Sprint 2 | `08_usecase_lot2_maladies.puml` | `prism-uploads/use case sp2.png` |
| Pipeline maladies | `09_activity_pipeline_maladies.puml` | `prism-uploads/pip.png` |
| Sequence maladies | `10_sequence_lot2_maladies.puml` | `prism-uploads/seq sp2.png` |
| Cas d'utilisation Sprint 3 | `11_usecase_lot3_recolte.puml` | `prism-uploads/Capture d'écran 2026-05-17 164007.png` |
| Activite recolte | `12_activity_lot3_recolte.puml` | `prism-uploads/Capture d'écran 2026-05-17 160816_2.png` |
| Sequence recolte | `13_sequence_lot3_recolte.puml` | `prism-uploads/Capture d'écran 2026-05-17 160655.png` |
| Cas d'utilisation Sprint 4 | `14_usecase_lot4_synthese.puml` | `prism-uploads/Capture d'écran 2026-05-17 220416.png` |
| Sequence tableau de bord | `15_sequence_tableau_bord.puml` | `prism-uploads/Capture d'écran 2026-05-17 221635.png` |
| Sequence production | `16_sequence_production.puml` | `prism-uploads/Capture d'écran 2026-05-17 222638.png` |
| Sequence assistant | `17_sequence_assistant.puml` | `prism-uploads/Capture d'écran 2026-05-17 224543.png` |
| Classes globales | `18_classes_globales.puml` | `prism-uploads/Capture d'écran 2026-05-17 234726.png` |

