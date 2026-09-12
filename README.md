# Ginko Besançon — Intégration Home Assistant

> Intégration personnalisée pour suivre en temps réel les transports en commun du réseau **Ginko** (Besançon, France) depuis Home Assistant.

---

## Sommaire

1. [Description](#description)
2. [Prérequis](#prérequis)
3. [Installation](#installation)
4. [Configuration des modes](#configuration-des-modes)
   - [Mode 1 — Arrêt par nom](#mode-1--arrêt-par-nom-mode_lieu)
   - [Mode 2 — Lignes spécifiques](#mode-2--lignes-spécifiques-mode_liste)
   - [Mode 3 — Arrêts proches d'une personne](#mode-3--arrêts-proches-dune-personne-mode_person)
   - [Mode 4 — Suivi d'une ligne](#mode-4--suivi-dune-ligne-mode_ligne)
   - [Mode 5 — Positions des bus](#mode-5--positions-des-bus-mode_suivi_ligne)
5. [Capteurs globaux](#capteurs-globaux)
6. [Cartes Lovelace](#cartes-lovelace)
7. [Services](#services)
8. [Référence des attributs des capteurs](#référence-des-attributs-des-capteurs)
9. [Options après installation](#options-après-installation)
10. [Dépannage](#dépannage)

---

## Description

Cette intégration connecte Home Assistant à l'API REST du réseau de transports en commun **Ginko** de Besançon. Elle vous permet de surveiller :

- Les **prochains passages** de bus et tram à n'importe quel arrêt
- L'**état en temps réel** des lignes (perturbations, travaux, alertes)
- La **position** de tous les bus en service sur une ligne
- Les **arrêts les plus proches** d'une personne suivie par Home Assistant

Les données sont exposées sous forme de capteurs (`sensor`) exploitables dans vos automatisations, tableaux de bord et notifications.

---

## Prérequis

Avant de commencer, assurez-vous d'avoir :

| Élément | Détail |
|---|---|
| **Home Assistant** | Version 2024.1.0 ou plus récente |
| **Clé API Ginko** | À demander par e-mail à Keolis Besançon Mobilités |
| **Accès aux fichiers HA** | Via SSH, Samba ou l'add-on File Editor |

> 💡 **Obtenir une clé API :** Rendez-vous sur le portail api Ginko (https://api.ginko.voyage/#prez) et écrivez à ginko.support-ssi@keolis.com en décrivant votre usage (personnel / domotique).

---
## Installation

### Méthode 1 — HACS (recommandée)

1. Dans HACS, ouvrez le menu **⋮** (en haut à droite) → **Dépôts personnalisés**
2. Ajoutez l'URL du dépôt : `https://github.com/steph9742/ginko-ha`
   avec la catégorie **Integration**
3. Recherchez **"Ginko Besançon"** dans HACS et cliquez sur **Télécharger**
4. Redémarrez Home Assistant depuis **Paramètres → Système → Redémarrer**

> Les mises à jour apparaîtront ensuite automatiquement dans HACS à chaque nouvelle version.

### Méthode 2 — Manuelle

Copiez le dossier `custom_components/ginko/` dans le répertoire `config/custom_components/` de votre installation Home Assistant. La structure doit ressembler à ceci :

```
config/
└── custom_components/
    └── ginko/
        ├── __init__.py
        ├── manifest.json
        ├── config_flow.py
        ├── sensor.py
        └── ...
```

Puis redémarrez Home Assistant depuis **Paramètres → Système → Redémarrer**.

### Ajouter l'intégration

1. Allez dans **Paramètres → Appareils et services → Intégrations**
2. Cliquez sur **+ Ajouter une intégration**
3. Recherchez **"Ginko"** et sélectionnez-la
4. Entrez votre **clé API** Ginko
5. Choisissez le **mode** qui correspond à votre usage (voir ci-dessous)

---

## Configuration des modes

L'intégration propose cinq modes distincts. Vous pouvez créer plusieurs entrées (une par mode, ou plusieurs entrées du même mode pour différents arrêts).

---

### Mode 1 — Arrêt par nom (`MODE_LIEU`)

**Usage :** Afficher tous les prochains passages à un arrêt donné, toutes lignes et directions confondues.

**Configuration :**

| Champ | Description |
|---|---|
| Nom de l'arrêt | Liste déroulante avec autocomplétion |
| Nombre de passages | De 1 à 5 (défaut : 3) |
| Intervalle de rafraîchissement | Automatique (tram : 10 s, bus : 30 s) ou manuel de 10 à 300 |

**Capteur créé :**
- `sensor.ginko_<nom_arret>`
- **État :** nombre de passages à venir
- **Attributs :** `passages` (liste), `nom_arret`

---

### Mode 2 — Lignes spécifiques (`MODE_LISTE`)

**Usage :** Suivre le prochain passage pour des combinaisons précises arrêt + ligne + direction.

**Configuration (itérative) :**

Pour chaque entrée, vous choisissez successivement :
1. L'**arrêt** (liste déroulante)
2. La **ligne** desservant cet arrêt
3. La **direction** (aller / retour)
4. Optionnel : ajouter une autre combinaison

**Capteurs créés :**
- Un capteur par combinaison : `sensor.ginko_<nom>_<id_ligne>_aller` ou `_retour`
- **État :** secondes avant le prochain bus (entier)
- **Attributs :** voir [référence des attributs](#référence-des-attributs-des-capteurs)

> 💡 Ce mode est idéal pour déclencher des automatisations précises, par exemple "notifie-moi 5 minutes avant mon bus du matin".

---

### Mode 3 — Arrêts proches d'une personne (`MODE_PERSON`)

**Usage :** Trouver automatiquement les arrêts les plus proches d'une personne suivie par Home Assistant (via son GPS).

**Configuration :**

| Champ | Description |
|---|---|
| Entité personne | Sélecteur d'entité `person.*` |
| Nombre de passages | De 1 à 5 par arrêt |
| Nombre d'arrêts max | De 1 à 10 (défaut : 5) |
| Intervalle de rafraîchissement | Automatique (tram : 10 s, bus : 30 s) ou manuel de 10 à 300 |

**Capteur créé :**
- `sensor.ginko_proximite_<person_name>`
- **État :** nombre d'arrêts trouvés à proximité
- **Attributs :** `arrets` (liste avec nom, distance, passages), `person_state`

> 💡 Parfait pour afficher les options de transport disponibles en fonction de votre position actuelle.

---

### Mode 4 — Suivi d'une ligne (`MODE_LIGNE`)

**Usage :** Surveiller l'état en temps réel d'une ligne et ses éventuels messages de perturbation.

**Configuration :**

| Champ | Description |
|---|---|
| Ligne | Liste déroulante de toutes les lignes Ginko |

**Capteurs créés (2 par ligne configurée) :**

| Capteur | État | Description |
|---|---|---|
| `sensor.ginko_ligne_<N>_etat` | Libellé d'état (ex. "Normal") | État de la ligne |
| `sensor.ginko_ligne_<N>_messages` | Nombre de messages actifs | Messages de perturbation |

Ce mode crée également les **capteurs globaux** (voir section suivante).

**Rafraîchissement :** toutes les 60 secondes (fixe).

---

### Mode 5 — Positions des bus (`MODE_SUIVI_LIGNE`)

**Usage :** Suivre en temps réel la position GPS de tous les bus en service sur une ligne.

**Configuration :**

| Champ | Description |
|---|---|
| Ligne | Liste déroulante |
| Intervalle de rafraîchissement | Automatique (tram : 10 s, bus : 30 s) ou manuel de 10 à 300 s |

**Capteur créé :**
- `sensor.ginko_bus_ligne_<N>`
- **État :** nombre de bus actuellement suivis
- **Attributs :** `num_ligne`, `buses` (liste détaillée)

> ℹ️ Seuls les bus équipés GPS (temps réel) sont affichés. Les horaires théoriques sont exclus.

---

## Capteurs globaux

Ces deux capteurs sont créés **automatiquement** lors de la première configuration d'une entrée Ginko. Ils donnent une vue d'ensemble du réseau :

| Capteur | État | Attributs |
|---|---|---|
| `sensor.ginko_etat_lignes` | Nombre de lignes perturbées **en cours** (états 5/6) | `perturbations_en_cours`, `perturbations_prevues`, `lignes_perturbees`, `lignes` (liste complète) |
| `sensor.ginko_messages` | Total des messages actifs | `messages` : liste de tous les messages |

**Rafraîchissement :** toutes les 60 secondes.

---

## Cartes Lovelace

L'intégration inclut quatre cartes personnalisées pour visualiser les données dans votre tableau de bord. Elles sont automatiquement enregistrées au démarrage de Home Assistant.

> 💡 Les ressources JS sont versionnées automatiquement (`?v=<version>`) : après une mise à jour de l'intégration, un simple rechargement de la page suffit.

---

### Carte 1 — `ginko-card`

**Pour :** les modes Arrêt par nom, Lignes spécifiques, Arrêts proches.

Affiche la liste des prochains passages avec :
- Badge coloré (couleurs officielles, liseré adaptatif clair/sombre)
- Wifi = temps réel · ~ = théorique (infobulles)
- Icône PMR (véhicule accessible)
- Point de position : vert = à quai, bleu = en circulation
- Bandeau perturbations (un message par ligne + badge des lignes)
- Textes de remplacement en ambre (« Déviation », « Travaux »…)

**Configuration YAML :**

```yaml
type: custom:ginko-card
entity: sensor.ginko_chaprais
messages_entity: sensor.ginko_messages  # optionnel
```

| Option | Obligatoire | Description |
|---|---|---|
| `entity` | ✅ Oui | Capteur d'un arrêt (mode lieu, liste ou proximité) |
| `messages_entity` | Non | Capteur global des messages pour afficher les alertes |

---

### Carte 2 — `ginko-etat-card`

**Pour :** l'état du réseau et les messages de perturbation.

Affiche :
- Bannière verte "Tout est normal" si aucune perturbation
- Messages avec corps de texte dépliable
- Filtres : Toutes / ⚠ Perturbées / Prévues / par ligne, avec point de sévérité coloré (🟠 en cours, 🔴 interrompue, ⚪ prévue)
- Lignes triées par sévérité (les plus perturbées en premier)

**Configuration YAML :**

```yaml
type: custom:ginko-etat-card
entity: sensor.ginko_etat_lignes
messages_entity: sensor.ginko_messages
```

| Option | Obligatoire | Description |
|---|---|---|
| `entity` | ✅ Oui | `sensor.ginko_etat_lignes` |
| `messages_entity` | ✅ Oui | `sensor.ginko_messages` |

---

### Carte 3 — `ginko-suivi-card`

**Pour :** le suivi de position des bus (mode 5).

Affiche :
- Filtres de direction : Tous / → Aller / ← Retour
- Pour chaque bus : direction, terminus, position (arrêt précédent → prochain arrêt, ou "À quai", ou "Départ →")
- Temps en minutes avant le prochain arrêt
- Tri par heure d'arrivée

**Configuration YAML :**

```yaml
type: custom:ginko-suivi-card
entity: sensor.ginko_bus_ligne_7
```

| Option | Obligatoire | Description |
|---|---|---|
| `entity` | ✅ Oui | Capteur de suivi de ligne (`sensor.ginko_bus_ligne_<N>`) |

---

### Carte 4 — `ginko-recherche-card`

**Pour :** consulter les horaires de **n'importe quel arrêt** du réseau, suivi ou non, comme dans une application de transports.

Affiche :
- Un champ de recherche avec autocomplétion (accents et casse ignorés, navigation clavier ↑ ↓ Entrée)
- Les prochains passages de l'arrêt choisi, avec le même rendu que `ginko-card` (badges, pilules, PMR, bandeau infotrafic)
- Rafraîchissement automatique tant qu'un arrêt est affiché ; le dernier arrêt consulté est mémorisé dans le navigateur

Cette carte **ne crée aucun capteur** et n'interroge l'API Ginko que lorsqu'un arrêt est affiché, via les [services de l'intégration](#services).

**Configuration YAML :**

```yaml
type: custom:ginko-recherche-card
messages_entity: sensor.ginko_messages  # optionnel
nb_passages: 3
refresh: 30
```

| Option | Obligatoire | Description |
|---|---|---|
| `arret` | Non | Arrêt prédéfini (la recherche reste possible) |
| `nb_passages` | Non | Passages par ligne et direction, 1 à 5 (défaut : 3) |
| `refresh` | Non | Intervalle de rafraîchissement en secondes, 10 à 300 (défaut : 30) |
| `show_traffic` | Non | `if_disrupted` (défaut), `always` ou `never` |
| `messages_entity` | Non | Capteur global des messages pour le bandeau infotrafic |
| `remember` | Non | `false` pour ne pas mémoriser le dernier arrêt (défaut : `true`) |

---

## Services

L'intégration expose deux services **avec réponse**, utilisables depuis les automatisations, les scripts, les templates, la carte de recherche ou une autre intégration. Ils réutilisent la clé API déjà configurée et n'interrogent Ginko qu'à la demande (cache court de 20 s sur les horaires).

### `ginko.chercher_arret`

Recherche des arrêts par nom (accents et casse ignorés ; les noms commençant par la recherche sont classés en premier).

| Champ | Obligatoire | Description |
|---|---|---|
| `recherche` | ✅ Oui | Texte à chercher (ex. `viotte`) |
| `limite` | Non | Nombre maximum de résultats, 1 à 50 (défaut : 10) |

Réponse : `{ arrets: [ { nom, latitude, longitude, accessible, quais } ] }`

### `ginko.get_horaires`

Prochains passages d'un arrêt, qu'il soit suivi par un capteur ou non.

| Champ | Obligatoire | Description |
|---|---|---|
| `nom` | ✅ Oui | Nom de l'arrêt (correspondance approximative acceptée) |
| `nb` | Non | Passages par ligne et direction, 1 à 5 (défaut : 3) |

Réponse : `{ nom, nb_passages, passages: [ … ] }`. Chaque passage a la même structure que l'attribut `passages` des capteurs (`numLignePublic`, `destination`, `temps`, `tempsEnSeconde`, `fiable`, `typeDeTemps`, `couleurFond`…).

**Exemple dans un script :**

```yaml
sequence:
  - action: ginko.get_horaires
    data:
      nom: "Gare Viotte"
      nb: 2
    response_variable: horaires
  - action: notify.mobile_app
    data:
      message: >
        Prochain {{ horaires.passages[0].numLignePublic }} vers
        {{ horaires.passages[0].destination }} dans {{ horaires.passages[0].temps }}
```

**Exemple depuis une autre intégration (Python) :**

```python
resp = await hass.services.async_call(
    "ginko", "get_horaires",
    {"nom": "Gare Viotte", "nb": 3},
    blocking=True, return_response=True,
)
passages = resp["passages"]
```

---

## Référence des attributs des capteurs

### Mode Lieu (`sensor.ginko_<nom_arret>`)

| Attribut | Type | Description |
|---|---|---|
| `nom_arret` | string | Nom de l'arrêt |
| `passages` | liste | Liste des objets de passage (voir ci-dessous) |

### Mode Liste (`sensor.ginko_<nom>_<id_ligne>_aller/retour`)

| Attribut | Type | Description |
|---|---|---|
| `passages` | liste | Liste des prochains passages |
| `temps` | string | Temps lisible (ex. "3 min") |
| `destination` | string | Nom du terminus |
| `fiable` | bool | `true` si le temps est basé sur le GPS |
| `numLignePublic` | string | Numéro de ligne affiché (ex. "7") |
| `couleurFond` | string | Couleur de fond de la ligne (hex) |
| `couleurTexte` | string | Couleur du texte de la ligne (hex) |
| `modeTransport` | string | Type de transport (bus, tram…) |
| `typeDeTemps` | int | 0 = temps relatif, 1 = heure absolue, 2 = texte de remplacement |
| `deviation` | bool | `true` si le passage est remplacé par un texte (« Déviation », « Travaux », « Bus complet »…) |

### Mode Personne (`sensor.ginko_proximite_<person_name>`)

| Attribut | Type | Description |
|---|---|---|
| `person_state` | string | État actuel de la personne |
| `arrets` | liste | Liste d'objets `{nom, distance_meters, passages}` |

### Mode Ligne — État (`sensor.ginko_ligne_<N>_etat`)

| Attribut | Type | Description |
|---|---|---|
| *(état du capteur)* | string | Libellé d'état : `Normal`, `Information`, `Hors service`, `Perturbation prévue`, `Perturbation en cours`, `Circulation interrompue`, `Pas d'information` |
| `etat` | int | Code d'état 0–6 (voir tableau ci-dessous) |
| `etat_label` | string | Libellé lisible correspondant au code |
| `etat_description` | string | Phrase explicative de l'état |
| `couleur_etat` | string | Couleur hex conseillée pour l'affichage |
| `perturbation_active` | bool | Vrai si perturbation en cours ou ligne interrompue (états 5/6) |
| `perturbation_prevue` | bool | Vrai si une perturbation est prévue (état 4) |

**Codes d'état des lignes :**

| Code | Libellé | Couleur / picto | Signification |
|---|---|---|---|
| 0 | Pas d'information | — | Aucune info (ex. lignes à la demande / TAD) |
| 1 | Normal | 🟢 vert (check) | La ligne fonctionne normalement |
| 2 | Information | 🔵 bleu (info) | Une information concerne la ligne |
| 3 | Hors service | ⚪ gris (croix) | Ne circule pas en ce moment (hors de sa période de fonctionnement) |
| 4 | Perturbation prévue | ⚪ gris (attention) | Une perturbation est prévue dans le futur |
| 5 | Perturbation en cours | 🟠 orange (attention) | Une perturbation est en cours |
| 6 | Circulation interrompue | 🔴 rouge (croix) | Circulation totalement interrompue |

> 💡 Le capteur global `sensor.ginko_etat_lignes` ne compte comme « perturbées »
> que les lignes en état **5** ou **6**. L'état **3** (hors horaires) est normal
> et n'est pas comptabilisé.

### Mode Ligne — Messages (`sensor.ginko_ligne_<N>_messages`)

| Attribut | Type | Description |
|---|---|---|
| `messages` | liste | Liste des messages actifs de la ligne |

### Mode Suivi (`sensor.ginko_bus_ligne_<N>`)

| Attribut | Type | Description |
|---|---|---|
| `num_ligne` | string | Numéro de la ligne |
| `buses` | liste | Liste des bus (voir détail ci-dessous) |

**Détail d'un objet bus dans `buses` :**

| Champ | Type | Description |
|---|---|---|
| `id` | string | Numéro du véhicule |
| `sens` | string | `"aller"` ou `"retour"` |
| `terminus` | string | Nom du terminus de destination |
| `prochain_arret` | string | Prochain arrêt |
| `arret_precedent` | string ou `null` | Arrêt précédent (`null` en départ de terminus) |
| `statut` | string | `"a_quai"`, `"depart"` ou `"en_route"` |
| `dans_sec` | int | Secondes avant le prochain arrêt |

### Capteurs globaux

**`sensor.ginko_etat_lignes`**

| Attribut | Type | Description |
|---|---|---|
| `lignes` | liste | Liste de toutes les lignes avec leur état |

**`sensor.ginko_messages`**

| Attribut | Type | Description |
|---|---|---|
| `messages` | liste | Tous les messages de perturbation actifs |

---

## Options après installation

Vous pouvez modifier la configuration d'une entrée existante sans la recréer :

1. Allez dans **Paramètres → Appareils et services → Intégrations**
2. Trouvez votre entrée Ginko
3. Cliquez sur **Configurer**

Options disponibles selon le mode :

| Option | Modes concernés |
|---|---|
| Nombre de passages | Tous sauf Mode 4 |
| Intervalle de rafraîchissement | Tous |
| Ajouter des arrêts/lignes/directions | Mode 2 uniquement |


---

## Dépannage

### "Clé API invalide"

**Symptôme :** L'intégration refuse de s'ajouter ou affiche une erreur d'authentification.

**Solutions :**
- Vérifiez votre clé sur le portail api Ginko
- Assurez-vous qu'il n'y a pas d'espace au début ou à la fin de la clé
- Si la clé ne fonctionne plus, contactez **ginko.support-ssi@keolis.com** pour en obtenir une nouvelle
  
> 💡 Si votre clé devient invalide après l'installation, Home Assistant affiche automatiquement une notification « Ré-authentification requise » : cliquez dessus pour saisir la nouvelle clé, sans rien reconfigurer d'autre.

---

### Aucun bus n'apparaît en mode "Positions des bus"

**Symptôme :** Le capteur `sensor.ginko_bus_ligne_<N>` affiche 0 ou aucun bus.

**Causes possibles :**
- Les bus affichés sont **uniquement ceux équipés GPS** (avec `numVehicule`). Les horaires théoriques sont exclus.
- En **heures creuses**, moins de bus circulent.
- Le **premier rafraîchissement** peut être légèrement plus long (chargement des variantes de ligne).

**Solution :** Patientez quelques secondes et vérifiez aux heures de forte fréquence.

---

### La carte Lovelace n'est pas trouvée

**Symptôme :** Home Assistant affiche "Custom element doesn't exist: ginko-card" (ou similaire).

**Solutions :**
1. Les fichiers JS sont enregistrés automatiquement au démarrage — **redémarrez Home Assistant**
2. Rechargez la page — les URLs sont versionnées, un rechargement suffit après une mise à jour
3. Vérifiez que les entrées Ressources sont listées avec un suffixe `?v=<version>`

---

### Les données ne se mettent pas à jour

**Symptôme :** Le capteur affiche des données obsolètes ou ne change pas.

**Solutions :**
- Vérifiez l'intervalle de rafraîchissement dans les options de l'entrée
- Consultez les logs Home Assistant (**Paramètres → Système → Journaux**) pour identifier d'éventuelles erreurs API
- Assurez-vous que votre instance Home Assistant a bien accès à Internet

---

## Licence

Ce projet est une intégration communautaire non officielle, sans lien avec Ginko ou la Communauté d'Agglomération du Grand Besançon Métropole. Utilisez-la à vos propres risques.

---

*Fait avec ❤️ pour la communauté Home Assistant de Besançon.*
