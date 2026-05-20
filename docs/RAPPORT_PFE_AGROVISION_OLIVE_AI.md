# Rapport PFE

## Conception et developpement d'une plateforme intelligente d'aide a la decision pour l'oleiculture en Tunisie

Auteur : `[Votre nom et prenom]`  
Niveau : `[Licence / Master / Specialite]`  
Etablissement : `Faculte des Sciences de Monastir (a adapter selon votre filiere)`  
Encadrant academique : `[Nom]`  
Encadrant professionnel : `[Nom]`  
Organisme d'accueil : `[Nom de l'entreprise / laboratoire]`  
Annee universitaire : `2025-2026`

---

## Remerciements

Je tiens a exprimer ma profonde gratitude a toutes les personnes qui ont contribue a la realisation de ce projet de fin d'etudes. Je remercie en premier lieu mes encadrants pour leur accompagnement, leurs conseils et leur disponibilite tout au long de la periode de conception et de developpement. Je remercie egalement l'equipe d'accueil pour l'environnement de travail offert, la confiance accordee et les echanges techniques qui ont enrichi ce travail.

Mes remerciements s'adressent aussi aux enseignants de ma formation pour les connaissances scientifiques et techniques transmises durant mon parcours universitaire. Enfin, j'exprime ma reconnaissance a ma famille et a mes proches pour leur soutien moral, leur patience et leurs encouragements permanents.

---

## Resume

Ce projet de fin d'etudes presente la conception et la realisation d'une plateforme web intelligente dediee au suivi des oliveraies, nommee **AgroVision Olive AI**. L'objectif principal est de proposer un outil d'aide a la decision destine aux producteurs d'olives, en combinant vision par ordinateur, donnees climatiques, regles agronomiques et visualisation de donnees dans une interface web moderne.

La plateforme repond a trois besoins majeurs de l'oleiculture : le diagnostic sanitaire de l'olivier, l'estimation du moment optimal de recolte et la prevision de la production de la saison suivante. Pour atteindre cet objectif, une architecture client-serveur a ete mise en place, avec un frontend developpe sous React et Vite, et un backend base sur FastAPI. Les traitements d'intelligence artificielle s'appuient principalement sur PyTorch, torchvision, YOLO et scikit-learn.

Le module **Disease Scan** exploite un pipeline hybride compose d'un routeur de partie vegetale, d'un modele specialise de classification des maladies foliaires et d'une couche experte chargee de limiter les faux positifs et de gerer les cas ambigus. Le module **Harvest Time** combine l'analyse visuelle de la maturite, les contraintes saisonnieres, les caracteristiques du cultivar, la localisation geographique et les donnees meteorologiques afin de produire une recommandation prudente sur l'etat de preparation a la recolte. Le module **Production Model** utilise un modele metier fonde sur l'historique des rendements, l'effet d'alternance, les conditions climatiques, la pression sanitaire, l'irrigation et l'age des arbres afin de projeter une fourchette de production.

Les resultats obtenus montrent qu'il est possible de concevoir une plateforme unifiee, claire et exploitable, capable de fournir des recommandations coherentes dans un contexte agricole reel. Le projet met particulierement l'accent sur la fiabilite des sorties, la reduction des affirmations excessives et l'explicabilite des decisions. Il constitue ainsi une base solide pour de futurs travaux portant sur l'amelioration des jeux de donnees, l'enrichissement des modeles et le deploiement a plus grande echelle dans le domaine de l'agriculture de precision en Tunisie.

**Mots-cles** : olivier, agriculture de precision, vision par ordinateur, detection de maladies, estimation de recolte, prediction de production, FastAPI, React, PyTorch, Tunisie.

---

## Abstract

This final-year project presents the design and implementation of an intelligent web platform dedicated to olive orchard monitoring, called **AgroVision Olive AI**. The main objective is to provide decision-support tools for olive growers by combining computer vision, climate data, agronomic rules, and data visualization within a modern web application.

The platform addresses three major olive-farming needs: plant health diagnosis, harvest timing estimation, and next-season production forecasting. To achieve this goal, a client-server architecture was implemented, with a React and Vite frontend and a FastAPI backend. The artificial intelligence components rely mainly on PyTorch, torchvision, YOLO, and scikit-learn.

The **Disease Scan** module uses a hybrid pipeline composed of a plant-part router, a dedicated leaf disease classifier, and an expert layer designed to reduce false positives and manage uncertain cases. The **Harvest Time** module combines visual maturity estimation, seasonal constraints, cultivar profile, farm location, and weather data in order to generate a careful harvest-readiness recommendation. The **Production Model** module uses a domain-specific forecasting formula based on yield history, alternate bearing effect, climate conditions, disease pressure, irrigation, and tree age to produce a production range for the next season.

The obtained results show that it is possible to build a unified, clear, and usable platform capable of providing coherent recommendations in a real agricultural context. The project places strong emphasis on reliability, cautious outputs, and explainability. It therefore represents a solid foundation for future work involving richer datasets, stronger models, and larger-scale deployment in precision agriculture for Tunisian olive farming.

**Keywords**: olive farming, precision agriculture, computer vision, disease detection, harvest estimation, production forecasting, FastAPI, React, PyTorch, Tunisia.

---

## Table des matieres

1. Introduction generale  
2. Chapitre 1 - Cadre general du projet  
3. Chapitre 2 - Etude de l'existant  
4. Chapitre 3 - Analyse des besoins et specification  
5. Chapitre 4 - Conception de la solution  
6. Chapitre 5 - Realisation et implementation  
7. Chapitre 6 - Validation et resultats  
8. Conclusion generale et perspectives  
9. Bibliographie et webographie  

---

## Introduction generale

L'oleiculture occupe une place centrale dans l'economie agricole tunisienne. L'olivier represente a la fois un patrimoine economique, social et environnemental, et joue un role important dans plusieurs regions du pays. Cependant, la gestion moderne d'une oliveraie exige des decisions de plus en plus precises concernant l'etat sanitaire des arbres, la periode optimale de recolte et l'estimation du rendement futur. Ces decisions influencent directement la qualite de l'huile, la sante du verger et la rentabilite de l'exploitation.

Dans les pratiques traditionnelles, ces choix reposent souvent sur l'observation visuelle du producteur, son experience personnelle et des estimations empiriques. Or, l'evolution recente des technologies d'intelligence artificielle, de vision par ordinateur et d'analyse de donnees rend possible le developpement de nouveaux outils capables d'assister l'agriculteur de maniere plus structuree, plus rapide et plus tracable.

Dans ce contexte, le projet **AgroVision Olive AI** a pour objectif de concevoir une plateforme web d'aide a la decision pour l'oleiculture, orientee vers le contexte tunisien. Cette plateforme doit permettre d'analyser des images, de croiser les donnees de la ferme avec des informations climatiques, de produire des recommandations agronomiques prudentes et de centraliser l'ensemble de ces informations dans un tableau de bord coherent.

La problematique principale de ce projet peut etre formulee comme suit : **comment concevoir une plateforme intelligente capable d'assister efficacement l'oleiculteur dans le suivi sanitaire, la planification de la recolte et l'estimation de la production, tout en garantissant des resultats interpretable et prudents ?**

Pour repondre a cette problematique, nous avons defini les objectifs suivants :

- developper une application web moderne et exploitable ;
- integrer un module de diagnostic sanitaire base sur l'image ;
- concevoir un module d'estimation de la recolte tenant compte de la maturite, de la saison, du cultivar et de la meteo ;
- ajouter un module de prevision de production base sur l'historique et les facteurs agronomiques ;
- mettre en place une architecture claire, modulaire et extensible.

Le present rapport est organise en six chapitres. Le premier chapitre presente le cadre general du projet. Le deuxieme etudie l'existant et positionne la solution proposee. Le troisieme expose l'analyse des besoins et la specification du systeme. Le quatrieme detaille la conception generale. Le cinquieme presente la realisation technique. Enfin, le sixieme chapitre est consacre a la validation, aux resultats obtenus et a la discussion des limites.

---

## Chapitre 1 - Cadre general du projet

### 1.1 Contexte du projet

Le present projet s'inscrit dans le cadre d'un projet de fin d'etudes realise dans le domaine de l'informatique appliquee a l'agriculture. Il repond a un besoin concret de numerisation et d'assistance a la decision dans la gestion des oliveraies, particulierement dans un contexte ou les ressources en eau, les risques sanitaires et les variations climatiques rendent les pratiques agricoles plus complexes.

Le choix de l'olivier comme culture cible est justifie par son importance en Tunisie. L'olivier est une culture strategique dont la surveillance sanitaire et la gestion de la recolte influencent directement la qualite finale du produit et la rentabilite de l'exploitation. De ce fait, le developpement d'outils intelligents capables d'aider le producteur dans ses decisions constitue une contribution pertinente sur les plans scientifique, technique et economique.

### 1.2 Problematique

Les oleiculteurs font face a plusieurs difficultes recurrentes :

- l'identification fiable des symptomes visibles sur feuilles, fruits ou rameaux ;
- la determination du bon moment de recolte en fonction de la maturite reelle du fruit ;
- l'anticipation de la production future en tenant compte des facteurs biologiques et climatiques ;
- la dispersion des informations entre observation terrain, intuition personnelle et donnees meteo.

Ces limites montrent la necessite d'un systeme integre capable de centraliser l'information, d'exploiter l'image et les donnees environnementales, et de fournir des recommandations intelligibles.

### 1.3 Objectifs du projet

#### 1.3.1 Objectif general

Concevoir et developper une plateforme web intelligente pour le suivi des oliveraies, capable de fournir des recommandations d'aide a la decision concernant la sante du verger, la fenetre de recolte et la prevision de production.

#### 1.3.2 Objectifs specifiques

- mettre en place une interface web moderne et responsive ;
- concevoir une base de donnees permettant de gerer les fermes, groupes d'arbres, scans et alertes ;
- developper un pipeline de diagnostic sanitaire base sur la vision par ordinateur ;
- developper un module de Harvest Time adapte au contexte tunisien ;
- concevoir un module de production forecast fonde sur l'historique et des facteurs agronomiques ;
- assurer une presentation claire, prudente et tracable des resultats.

### 1.4 Demarche adoptee

La demarche adoptee dans ce travail repose sur une approche iterative :

- analyse du besoin et du contexte agricole ;
- audit de l'existant et choix des technologies ;
- conception modulaire du systeme ;
- implementation progressive des modules ;
- integration frontend/backend ;
- validation experimentale et fonctionnelle.

### 1.5 Conclusion

Ce chapitre a permis de situer le contexte du projet, de preciser la problematique et de presenter les objectifs poursuivis. Le chapitre suivant s'interesse a l'etude de l'existant afin de positionner la solution proposee par rapport aux approches deja disponibles.

---

## Chapitre 2 - Etude de l'existant

### 2.1 Introduction

Avant de concevoir une nouvelle solution, il est essentiel d'analyser les approches existantes dans les domaines de la vision par ordinateur en agriculture, du diagnostic des maladies des plantes, de l'estimation de la recolte et de la prevision du rendement. Cette etude permet d'identifier les limites des solutions actuelles et de justifier les choix adoptes dans AgroVision Olive AI.

### 2.2 Outils existants pour le diagnostic des maladies

De nombreuses solutions de diagnostic vegetal reposent aujourd'hui sur des classifieurs d'images, souvent entraines sur des bases de donnees generales de feuilles. Ces systemes peuvent etre performants en laboratoire mais presentent plusieurs limites lorsqu'ils sont appliques en conditions reelles :

- sensibilite a l'eclairage et au cadrage ;
- confusion entre symptomes reels et artefacts visuels ;
- manque de specialisation sur les cultures locales ;
- tendance a produire des diagnostics trop affirmatifs.

Dans le cas de l'olivier, ces limites sont encore plus importantes, car les symptomes peuvent etre proches de certaines variations naturelles de couleur, de texture ou d'ombre. Une approche plus prudente et plus experte est donc necessaire.

### 2.3 Outils existants pour l'estimation de la recolte

Les approches de prediction de recolte sont generalement de deux types :

- des approches simples fondees sur la couleur ou la date calendaire ;
- des approches plus riches integrant la meteo, le cultivar, les indices de maturite et parfois les donnees historiques.

Les methodes purement visuelles sont insuffisantes lorsqu'elles ne tiennent pas pas compte du contexte agronomique. Inversement, les approches purement climatiques ne doivent pas annuler l'evidence visuelle du fruit. Une solution robuste doit donc fusionner ces deux dimensions.

### 2.4 Outils existants pour la prediction de production

La prediction de production est souvent etablie a partir de l'historique des rendements, de l'effet d'alternance, des conditions climatiques et de l'etat sanitaire. Dans de nombreux outils, ces facteurs ne sont pas structures dans une interface accessible au producteur. Il existe donc un interet pratique a integrer ces informations dans un tableau de bord agronomique.

### 2.5 Analyse critique de l'existant

L'etude de l'existant permet de degager plusieurs insuffisances :

- les outils sont souvent specialises sur une seule tache ;
- l'explicabilite des resultats est faible ;
- les cas ambigus sont mal geres ;
- l'integration des donnees meteo et de la localisation est souvent limitee ;
- les solutions sont rarement adaptees au contexte tunisien de l'oleiculture.

### 2.6 Positionnement de la solution proposee

AgroVision Olive AI se distingue par les caracteristiques suivantes :

- plateforme unifiee et non outil isole ;
- combinaison de vision par ordinateur et de regles expertes ;
- integration de la meteo, de la localisation et du cultivar ;
- orientation explicite vers les oliveraies tunisiennes ;
- presentation prudente des resultats avec niveaux de confiance ;
- stockage historique et suivi dans un dashboard.

### 2.7 Conclusion

L'etude de l'existant montre que les approches actuelles sont utiles mais souvent insuffisantes lorsqu'elles sont utilisees seules. La solution proposee cherche donc a combiner plusieurs sources d'information dans une architecture coherente afin d'offrir un systeme d'aide a la decision plus fiable.

---

## Chapitre 3 - Analyse des besoins et specification

### 3.1 Identification des acteurs

Le principal acteur du systeme est le **producteur d'olives** ou le gestionnaire de ferme. D'autres acteurs peuvent etre consideres de maniere indirecte :

- l'encadrant technique ou agronome ;
- l'administrateur de la plateforme ;
- le jury ou evaluateur dans le cadre du PFE.

### 3.2 Besoins fonctionnels

Les besoins fonctionnels identifies sont les suivants :

- creer et modifier le profil d'une ferme ;
- enregistrer la localisation geographique sur une carte ;
- definir le cultivar, les groupes d'arbres et les informations d'irrigation ;
- analyser une image pour estimer l'etat sanitaire ;
- analyser une image pour estimer la maturite et la periode de recolte ;
- consulter les conditions meteorologiques associees a la ferme ;
- obtenir une projection de production pour la saison suivante ;
- enregistrer les resultats dans un historique ;
- visualiser les syntheses, alertes et recommandations sur un dashboard.

### 3.3 Besoins non fonctionnels

Les besoins non fonctionnels sont tout aussi importants :

- **fiabilite** : limiter les fausses affirmations et gerer l'incertitude ;
- **ergonomie** : proposer une interface claire et moderne ;
- **maintenabilite** : assurer une architecture modulaire ;
- **extensibilite** : permettre l'ajout de nouveaux modeles ou services ;
- **performance** : repondre rapidement aux requetes usuelles ;
- **tracabilite** : conserver l'historique des analyses et decisions.

### 3.4 Cas d'utilisation principaux

#### Cas d'utilisation 1 : Configurer une ferme

L'utilisateur cree une nouvelle ferme, saisit son nom, sa localisation, le nombre d'arbres, les groupes varietaux et les notes climatiques. Les informations sont stockees dans la base de donnees et pourront etre reutilisees dans tous les modules.

#### Cas d'utilisation 2 : Scanner une maladie

L'utilisateur televerse une image. Le systeme verifie la qualite de l'image, identifie la partie vegetale principale, puis effectue le diagnostic si la situation est supportee. Le systeme retourne une maladie probable, un niveau de confiance et une action recommandee.

#### Cas d'utilisation 3 : Estimer la recolte

L'utilisateur fournit une image du fruit, la date, le cultivar et la localisation. Le systeme combine l'analyse visuelle et le contexte agronomique pour produire une estimation du niveau de preparation a la recolte.

#### Cas d'utilisation 4 : Prevoir la production

L'utilisateur saisit ou reutilise l'historique des rendements. Le systeme derive automatiquement plusieurs scores et calcule une fourchette de production future avec des explications.

### 3.5 Contraintes

Le projet est soumis a plusieurs contraintes :

- qualite variable des images fournies ;
- limites des jeux de donnees disponibles ;
- differences entre conditions de laboratoire et conditions reelles ;
- disponibilite partielle de certaines informations (irrigation, historique complet, etiquettes parfaites) ;
- besoin de conserver une interface simple malgre une logique technique complexe.

### 3.6 Conclusion

Ce chapitre a permis de transformer la problematique generale en besoins fonctionnels et non fonctionnels clairs. Ces besoins guident les choix de conception presentes dans le chapitre suivant.

---

## Chapitre 4 - Conception de la solution

### 4.1 Vue d'ensemble de l'architecture

La solution adopte une architecture client-serveur. Le frontend, developpe en React, assure l'interaction avec l'utilisateur et la presentation des resultats. Le backend, base sur FastAPI, centralise la logique metier, la gestion des donnees, les appels aux services meteorologiques et l'orchestration des modeles d'intelligence artificielle.

L'architecture peut etre decomposee en cinq couches :

- couche presentation ;
- couche API ;
- couche services metier ;
- couche modeles IA ;
- couche persistence.

### 4.2 Architecture frontend

Le frontend contient plusieurs pages principales :

- `LandingPage`
- `DashboardPage`
- `FarmSetupPage`
- `DiseaseScanPage`
- `HarvestTimePage`
- `ProductionModelPage`
- `AssistantPage`
- `SignInPage`, `SignUpPage`, `VerifyEmailPage`

Le point d'entree principal est gere dans `App.jsx`. Le frontend communique avec le backend via une couche API dediee. Il integre egalement la cartographie, l'affichage de graphiques et un tableau de bord orientee exploitation agricole.

### 4.3 Architecture backend

Le backend est expose via `backend/main.py`. Il fournit plusieurs categories de routes :

- routes de gestion de ferme ;
- routes d'analyse d'image ;
- routes de prediction climatique et de recolte ;
- routes de production forecast ;
- routes de chat et d'assistance ;
- routes d'historique et d'orchestration du verger.

La logique metier est segmentee en services, notamment :

- `vision_service.py`
- `scene_classifier_service.py`
- `disease_expert_service.py`
- `harvest_image_service.py`
- `harvest_time_service.py`
- `climate_weather_service.py`
- `climate_harvest_service.py`
- `olive_detection_service.py`

### 4.4 Conception de la persistence

Les donnees de l'application sont stockees dans une base SQLite. Les principales tables sont :

- `farm_profiles`
- `tree_groups`
- `farm_scan_records`
- `farm_alerts`
- `farm_notes`
- `analyses`
- `orchards`
- `observations`
- `analysis_results`
- `climate_predictions`

Cette structure permet de conserver les informations de la ferme, les historiques de scans, les notes de suivi et les resultats des differentes analyses.

### 4.5 Conception du module Disease Scan

Le module Disease Scan suit une architecture hybride en plusieurs etapes :

1. controle qualite de l'image ;
2. routage de la partie vegetale (`leaf`, `fruit`, `branch_twig`) ;
3. si la partie est `leaf`, appel au classifieur specialise ;
4. verification des symptomes via une couche experte ;
5. reduction des faux positifs et gestion de l'incertitude ;
6. retour final sous forme de diagnostic prudent.

Cette conception permet de traiter le diagnostic comme un systeme d'aide a la decision, et non comme un simple classifieur aveugle.

### 4.6 Conception du module Harvest Time

Le module Harvest Time repose sur un pipeline de fusion :

1. validation de la qualite de l'image ;
2. classification de scene ;
3. estimation visuelle du stade de maturite ;
4. determination du profil saisonnier selon cultivar et region ;
5. integration de la meteo recente ;
6. verification de coherence entre image et calendrier ;
7. production d'une recommandation finale.

Les sorties principales sont :

- le statut de recolte ;
- la fenetre recommandee ;
- la date estimee lorsque cela est pertinent ;
- le niveau de confiance ;
- une explication courte ;
- la prochaine action recommandee.

### 4.7 Conception du module Production Model

Le module de production est base sur une formule metier qui combine :

- l'historique des rendements ;
- l'effet d'alternance ;
- le score de pluie ;
- le score de stress thermique ;
- le score de cultivar ;
- le score d'irrigation ;
- le score de pression maladie ;
- le score d'age des arbres.

Le resultat est volontairement exprime sous forme de fourchette de production et non de valeur absolue certaine.

### 4.8 Conclusion

La conception adoptee permet de separer clairement les responsabilites des composants tout en maintenant une bonne coherente fonctionnelle. Cette modularite facilite la maintenance et les evolutions futures.

---

## Chapitre 5 - Realisation et implementation

### 5.1 Technologies utilisees

Le tableau suivant resume les principales technologies utilisees dans le projet.

| Categorie | Technologie | Role |
|---|---|---|
| Frontend | React + Vite | Construction de l'interface utilisateur |
| Navigation et UI | Framer Motion, Recharts, React Leaflet | Animation, graphiques, cartographie |
| Backend | FastAPI | Exposition des API et orchestration du systeme |
| IA / Vision | PyTorch, torchvision | Classification et traitement d'image |
| Detection | YOLO | Detection d'olives et region d'interet |
| ML classique | scikit-learn | Modeles de regression et prediction |
| Base de donnees | SQLite | Stockage local des donnees |
| Meteo | Open-Meteo | Recuperation des donnees historiques et de prevision |

### 5.2 Implementation du frontend

Le frontend a ete structure autour d'un composant principal `App.jsx`, responsable de la gestion de l'etat global de session, de navigation, de selection de ferme et de rechargement du dashboard. Chaque module metier dispose de sa propre page, ce qui permet de garder une structure lisible et modulaire.

Le dashboard constitue le point central de l'experience utilisateur. Il affiche la ferme active, la meteo, la simulation verger, les alertes, la recolte et la production projetee. La logique visuelle a ete orientee vers un style moderne et agritech afin de rendre l'application utilisable et presentable.

### 5.3 Implementation du backend

Le backend est organise autour d'un ensemble de services independants. Lors du demarrage, les bases de donnees sont initialisees et les composants principaux sont charges. Cette architecture permet de mutualiser les services entre plusieurs endpoints.

Les routes principales couvrent :

- la gestion des fermes ;
- le disease scan ;
- le harvest prediction ;
- la production forecast ;
- l'historique des analyses ;
- l'assistant conversationnel.

### 5.4 Implementation du module Disease Scan

Le module Disease Scan combine plusieurs briques techniques :

- un **plant-part router** charge de reconnaitre la partie dominante de l'image ;
- un modele specialise pour les maladies foliaires ;
- une couche experte pour valider la plausibilite du resultat.

Le routeur actif est un modele `EfficientNet-B0` charge depuis `models/curated/plant_part_router.pt`. Les classes prises en charge sont `branch_twig`, `fruit` et `leaf`.

Le modele foliaire actif est egalement base sur `EfficientNet-B0` et charge depuis `models/curated/leaf_disease_model.pt`. Les classes utilisees sont :

- `aculus_olearius`
- `healthy_leaf`
- `olive_peacock_spot`

Le systeme n'accepte pas aveuglement la prediction brute. Une logique experte intervient pour :

- verifier que la feuille est suffisamment visible ;
- detecter l'absence de symptome clair ;
- limiter les faux positifs ;
- retourner `Uncertain` lorsque l'evidence visuelle est insuffisante.

### 5.5 Implementation du module Harvest Time

Le module Harvest Time s'appuie sur `harvest_time_service.py`. Son objectif n'est pas d'estimer arbitrairement un taux d'huile a partir d'une simple photo, mais de produire une recommandation prudente sur l'etat de preparation a la recolte.

Le pipeline adopte integre :

- le stade de maturite estime a partir de l'image ;
- la date d'echantillonnage ;
- la fenetre saisonniere typique du cultivar ;
- la region ou la localisation GPS ;
- la meteo recente et la prevision ;
- des regles de coherence agronomique.

Les sorties du module sont volontairement interpretable :

- `Too early`
- `Not ready yet`
- `Approaching harvest`
- `Harvest now`
- `Outside current harvest season`
- `Data inconsistency`

Cette formulation permet de rendre le resultat utile sur le plan operationnel, tout en restant prudent.

### 5.6 Implementation du module Production Model

Le module Production Model a ete implemente dans le frontend via une librairie dediee, mais sur la base d'une logique metier explicite et documentee. Il derive automatiquement plusieurs scores a partir :

- de la meteo ;
- du cultivar et de la region ;
- des notes d'irrigation ;
- de l'etat sanitaire recent ;
- de l'age moyen des groupes d'arbres.

Les formules utilisent l'historique de rendement sur deux ou trois annees et un facteur d'alternance. Le resultat est exprime en kilogrammes avec equivalence en tonnes, ainsi qu'une fourchette basse et haute.

### 5.7 Jeux de donnees et curation

Le projet inclut egalement une demarche de curation semi-automatique des jeux d'images de maladies. Cette demarche comporte :

- l'audit des dossiers ;
- la detection de doublons ;
- la mise en quarantaine des fichiers corrompus ;
- un routage preliminaire par partie de plante ;
- une file de revue pour validation manuelle.

Cette etape est essentielle car la qualite des modeles depend directement de la qualite des donnees d'entrainement.

### 5.8 Conclusion

La realisation du projet montre que la combinaison d'une architecture web moderne, de services backend modulaires et d'une intelligence artificielle prudente permet de construire une plateforme fonctionnelle et extensible pour l'oleiculture.

---

## Chapitre 6 - Validation et resultats

### 6.1 Strategie de validation

La validation du systeme a porte sur deux dimensions :

- la validation fonctionnelle des modules et de leurs interactions ;
- la validation des modeles et des logiques de decision.

Des tests ont ete prevus sur les services critiques, en particulier pour les modules de disease scan et de harvest time. Cette approche permet de securiser les regressions et de verifier les cas limites.

### 6.2 Resultats du module Disease Scan

Les metriques disponibles pour le modele foliaire actif sont les suivantes :

| Metrique | Valeur |
|---|---|
| Accuracy | 0.977982 |
| Precision | 0.977992 |
| Recall | 0.977982 |
| F1-score | 0.977982 |

Ces metriques concernent le classifieur de maladies foliaires actif, base sur `EfficientNet-B0`, pour les classes `aculus_olearius`, `healthy_leaf` et `olive_peacock_spot`.

Pour le routeur de partie vegetale, les metriques disponibles sont :

| Metrique | Valeur |
|---|---|
| Accuracy | 0.889344 |
| Precision | 0.941485 |
| Recall | 0.889344 |
| F1-score | 0.904256 |

Ces resultats montrent que le routage est satisfaisant mais encore perfectible, ce qui justifie l'existence d'une couche experte supplementaire.

### 6.3 Analyse qualitative du Disease Scan

Le systeme donne de meilleurs resultats lorsqu'une feuille est visible clairement, bien eclairee et presente un symptome lisible. Les cas les plus delicats concernent :

- les feuilles saines avec ombres ou contrastes trompeurs ;
- les images ou la branche domine visuellement ;
- les images a faible resolution ;
- les symptomes tres faibles ou partiellement visibles.

Afin d'ameliorer la fiabilite, la couche experte privilegie un comportement prudent. Elle accepte plus facilement un resultat `Uncertain` plutot qu'un diagnostic faux mais confiant.

### 6.4 Analyse qualitative du Harvest Time

Le module Harvest Time a ete concu pour eviter deux types d'erreur :

- proposer une decision de recolte purement basee sur la couleur sans contexte ;
- generer une date precise trompeuse lorsque la saison ou les metadonnees ne sont pas coherentes.

La logique mise en place permet de :

- traiter les fruits verts hors saison comme relevant potentiellement du cycle suivant ;
- considerer une maturite avancee hors saison comme une incoherence de donnees ;
- utiliser la meteo comme ajustement secondaire et non comme autorite principale ;
- produire une decision courte et interpretable.

### 6.5 Resultats du Production Model

Le module de production ne vise pas une precision absolue, mais une estimation raisonnable et explicable. Son interet principal reside dans :

- l'integration automatique de plusieurs facteurs agronomiques ;
- la production d'une fourchette plutot que d'une seule valeur ;
- la mise en avant des facteurs explicatifs dominants.

Cette approche est adaptee a un contexte PFE, car elle privilegie la robustesse metier et la lisibilite plutot qu'une sophistication mathematique difficilement justifiable avec peu de donnees terrain structurees.

### 6.6 Limites du projet

Malgre les resultats encourageants, plusieurs limites doivent etre mentionnees :

- la taille et l'equilibre des jeux de donnees restent perfectibles ;
- les modeles fruit et branche sont encore plus faibles que le pipeline foliaire ;
- la qualite des images utilisateur reste une source importante de variabilite ;
- certaines sorties du module de production reposent sur des hypothese par defaut lorsque l'information est absente ;
- le deploiement local reste a completer pour une exploitation industrialisee.

### 6.7 Perspectives

Les perspectives d'amelioration du projet sont nombreuses :

- enrichir les bases de donnees terrain en conditions reelles ;
- ameliorer les modeles fruit et branche ;
- integrer davantage de donnees meteorologiques et historiques ;
- proposer un deploiement cloud et une application mobile ;
- relier la plateforme a des capteurs ou donnees satellitaires ;
- etendre l'assistant vers une aide agronomique plus conversationnelle et contextualisee.

### 6.8 Conclusion

Les validations realisees montrent que la plateforme est fonctionnelle, techniquement coherente et suffisamment robuste pour servir de base a une solution d'aide a la decision. Le projet demontre surtout la pertinence d'une approche hybride combinant intelligence artificielle, metier et prudence.

---

## Conclusion generale

Ce projet de fin d'etudes a permis de concevoir et de developper une plateforme intelligente d'aide a la decision pour l'oleiculture, baptisee **AgroVision Olive AI**. La solution proposee reunit plusieurs briques complementaires : un dashboard de suivi de ferme, un module de diagnostic sanitaire, un module d'estimation de la recolte et un module de prevision de production. L'ensemble repose sur une architecture moderne et modulaire, combinant React, FastAPI, PyTorch, SQLite et des services meteorologiques.

L'un des apports majeurs du projet est l'adoption d'une approche prudente et interpretable. Le systeme ne se contente pas de renvoyer une classe issue d'un modele ; il applique des controles de qualite, des regles de coherence et des niveaux de confiance afin de limiter les erreurs excessives. Cette orientation est particulierement importante dans un contexte agricole reel, ou une mauvaise recommandation peut avoir des consequences economiques directes.

Sur le plan scientifique et technique, ce travail montre l'interet d'une architecture hybride combinant vision par ordinateur, regles expertes, donnees climatiques et modeles metier. Sur le plan pratique, il aboutit a un prototype avance, coherent et extensible, adapte a une demonstration academique et a des evolutions futures plus ambitieuses.

En perspective, plusieurs pistes peuvent etre poursuivies : l'extension des jeux de donnees, l'amelioration des modeles de detection, l'integration de nouvelles sources de donnees et le passage vers une plateforme plus industrialisee. Ce projet constitue ainsi une base solide pour des travaux ulterieurs en agriculture de precision appliquee a l'oleiculture tunisienne.

---

## Bibliographie et webographie

### References scientifiques et techniques

[1] ICMJE, "Recommendations for the Conduct, Reporting, Editing, and Publication of Scholarly Work in Medical Journals".  
[2] EASE, "EASE Guidelines for Authors and Translators of Scientific Articles".  
[3] Purdue OWL, "Writing Scientific Abstracts".  
[4] IEEE, "IEEE Reference Guide".  
[5] Documentation officielle de FastAPI.  
[6] Documentation officielle de React.  
[7] Documentation officielle de PyTorch.  
[8] Documentation officielle de scikit-learn.  
[9] Documentation officielle d'Open-Meteo.  

### Webographie technique du projet

- FastAPI: https://fastapi.tiangolo.com/  
- React: https://react.dev/  
- Vite: https://vitejs.dev/  
- PyTorch: https://pytorch.org/  
- Torchvision: https://pytorch.org/vision/stable/  
- scikit-learn: https://scikit-learn.org/  
- Open-Meteo: https://open-meteo.com/  
- Recharts: https://recharts.org/  
- React Leaflet: https://react-leaflet.js.org/  

### Sources internes du projet

- Code source backend : `backend/`  
- Code source frontend : `frontend/`  
- Modeles entraines : `models/curated/`  
- Tests : `tests/`  
- Documentation interne : `docs/`  

---

## Annexes suggerees

### Annexe A - Captures d'ecran

- page d'accueil ;
- tableau de bord ;
- module Disease Scan ;
- module Harvest Time ;
- module Production Model ;
- page Farm Setup.

### Annexe B - Diagrammes

- diagramme global d'architecture ;
- diagramme de sequence Disease Scan ;
- diagramme de sequence Harvest Time ;
- schema relationnel de la base de donnees.

### Annexe C - Modeles et fichiers techniques

- metriques du modele foliaire ;
- metriques du plant-part router ;
- matrice de confusion des modeles ;
- extraits de configuration et captures de tests.

---

## Notes finales d'adaptation

Ce document constitue un **rapport PFE complet de base**, redige a partir de l'etat reel du projet AgroVision Olive AI dans le depot courant. Avant soumission finale, il faudra adapter :

- les noms et informations administratives ;
- le contexte exact de votre structure d'accueil ;
- les captures d'ecran finales ;
- les figures, diagrammes et tableaux ;
- la bibliographie detaillee selon le style exige ;
- les chiffres definitifs si des modeles ou pages changent avant soutenance.
