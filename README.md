# AMPTemplates-DDNet — DDraceNetwork pour AMP

Template **AMP Generic Module** pour héberger un serveur **DDNet**
(DDraceNetwork) sur Linux : parkour coopératif, classements par carte,
64 places.

CubeCoders ne propose qu'un template **Teeworlds** (la version vanilla).
Celui-ci en reprend la structure — même moteur, même format de config — mais
vise la variante où se trouvent réellement les joueurs.

## Pourquoi DDNet et pas Teeworlds vanilla

Mesuré sur la liste publique des serveurs, un soir de septembre 2026 :

| Famille | Serveurs | Joueurs en ligne |
|---|---|---|
| 0.6 + mods (DDNet & co) | 1 295 | **4 850** |
| 0.7 vanilla | 65 | **9** |

Neuf joueurs dans le monde entier sur du 0.7 vanilla. Un serveur vanilla
parfaitement réglé reste un beau terrain pour des soirées entre membres, mais
personne n'y passe par hasard. DDraceNetwork seul en compte 2 157.

C'est le genre de chiffre qu'il vaut mieux regarder **avant** de passer une
soirée à fignoler une rotation de cartes.

## Les deux pièges du fichier d'exemple de DDNet

DDNet livre un `autoexec_server.cfg` d'exemple très bien commenté. Monté tel
quel, le serveur a deux problèmes, et aucun ne se voit dans les logs :

| Réglage | Valeur dans l'exemple | Conséquence |
|---|---|---|
| `sv_register` | `0` | le serveur **n'apparaît nulle part** : il faut son IP pour y entrer |
| `sv_test_cmds` | `1` | le serveur change de **catégorie** : il devient un `TestDDraceNetwo` au lieu d'un `DDraceNetwork` |

Le second est le plus vicieux : le serveur marche, il est visible, il est
simplement rangé dans la mauvaise catégorie — celle où les joueurs vont
tester des triches, pas celle où ils viennent jouer. Le template met
`sv_test_cmds 0`, et `sv_register` sur **`ipv4`** plutôt que sur `1`.

Pourquoi `ipv4` et pas `1` : `sv_register` n'est pas un booléen, il accepte une
liste de familles d'adresses (« *can also accept a comma-separated list of
protocols to register on, like 'ipv4,ipv6'* » — le binaire connaît
`tw0.6/ipv4`, `tw0.6/ipv6`, `tw0.7/ipv4` et `tw0.7/ipv6`). Sur une machine
sans route IPv6 sortante — le cas d'un conteneur Docker par défaut —
l'enregistrement IPv6 échoue **toutes les 15 secondes, indéfiniment** :

```
E register/6/ipv6: error sending request to master
```

Le serveur est parfaitement listé en IPv4, mais son journal devient illisible.
Et un journal illisible cache le vrai problème le jour où il arrive. On ne
masque donc pas l'erreur, on supprime la cause.

## Le panneau d'AMP affiche les joueurs

Les motifs du bloc `Console.*` sont écrits d'après les **vraies lignes** du
journal d'une instance qui tourne, pas d'après une supposition de format :

| Ce qu'AMP apprend | Ligne lue |
|---|---|
| le serveur est prêt | `… I server: version 20.1.1 on linux amd64` |
| un joueur arrive | `… I chat: *** 'Hydrocut' entered and joined the game` |
| un joueur part | `… I chat: *** 'Hydrocut' has left the game` |
| un message de chat | `… I chat: 0:-2:Hydrocut: salut` |

Le format du chat vient d'une chaîne du binaire lui-même (`'%d:%d:%s: %s'`,
soit identifiant:équipe:pseudo: message), pas d'une devinette.

**Comment vérifier après le premier démarrage** : dans la liste des serveurs
du jeu, la colonne du type doit afficher `DDraceNetwork`. Si elle affiche
`TestDDraceNetwo`, `sv_test_cmds` n'a pas été pris en compte.

## Pourquoi les réglages vont dans `myServerconfig.cfg`

AMP n'écrit pas dans `autoexec_server.cfg`, mais dans **`myServerconfig.cfg`**,
à la racine du serveur.

Ce n'est pas une invention : le fichier d'exemple de DDNet se termine
lui-même par

```
exec myServerconfig.cfg
```

C'est l'emplacement que DDNet prévoit pour les réglages personnels, et donc
le seul qu'une mise à jour du jeu **n'écrase jamais**. Les votes de cartes,
les niveaux d'accès des modérateurs et les suggestions de client restent dans
`autoexec_server.cfg`, fournis et tenus à jour par DDNet.

Partage du travail :

| Fichier | Qui l'écrit | Contenu |
|---|---|---|
| `autoexec_server.cfg` | DDNet (mises à jour) | votes de cartes, droits des modérateurs, valeurs par défaut |
| `myServerconfig.cfg` | **AMP** | tout ce qui est dans l'onglet Configuration |

## Installation

### 1. Ajouter le dépôt dans ADS

Configuration → Instance Deployment → Configuration Repositories → ajouter :

```
hydrocut/AMPTemplates-DDNet:main
```

puis **Fetch Latest**.

### 2. Créer l'instance et l'installer

Create Instance → **DDNet (TeamKit)**, puis **Update**. Trois étapes
s'enchaînent : téléchargement de l'archive, extraction et mise à plat,
création de `myServerconfig.cfg` (sans l'écraser s'il existe déjà).

L'archive téléchargée est **`DDNet-latest-linux_x86_64.tar.xz`** : une URL
stable côté ddnet.org qui suit toujours la dernière version. Le template n'a
donc pas de numéro de version à remettre à jour — un simple **Update** dans
AMP suffit à passer à la version suivante.

### 3. Régler et démarrer

Deux choses avant le premier démarrage :

1. **Mot de passe admin (rcon F2)** — laissé vide, DDNet en génère un au
   hasard et l'affiche dans la console d'AMP, mais il change à chaque
   redémarrage
2. **Nom du serveur** — commencer par `FR` aide les francophones à te trouver,
   la liste DDNet est mondiale et se trie par nom

Puis **Start**. La console d'AMP lit et écrit directement dans le serveur
(`App.AdminMethod=STDIO`) : rien à configurer, et l'arrêt propre passe par la
commande `shutdown` du jeu.

## Ce dont le serveur a besoin sur la machine

Lecture des `DT_NEEDED` de l'ELF de `DDNet-Server` : **six bibliothèques**,
dont cinq font partie de la base Debian. La seule à installer est donc :

```
libcurl.so.4   →   libcurl4
```

Plus `xz-utils` pour décompresser l'archive. Les deux sont déclarés dans
`Meta.ExtraContainerPackages`, donc posés automatiquement en conteneur ; sur
l'hôte, ils y sont déjà dans une Debian normale.

Aucune base de données à monter : les temps des joueurs vont dans un fichier
**SQLite** (`ddnet-server.sqlite`), créé tout seul au premier démarrage.
`sv_use_sql` reste à `0` — il ne sert qu'à brancher un MySQL, ce qui n'a
d'intérêt que pour partager les classements entre plusieurs serveurs.

Ce fichier de classements est ce qui fait revenir les joueurs : il est couvert
par les sauvegardes AMP grâce à `*.sqlite` dans `App.SmartExcludeExemptions`.

## Vérifier le template avant de le pousser

```bash
python verifier.py
```

Il teste ce qui casse en silence : JSON valide, `@IncludeJson` qui pointent
sur des fichiers existants, `PrimaryApplicationPortRef` qui correspond à un
port déclaré, chaque réglage exposé dans AMP présent dans le fichier livré, et
la relecture de trois lignes piégeuses — une valeur avec espaces
(`sv_map Sunny Side Up`), un nom de serveur avec tirets, et une valeur **vide**
(les mots de passe, qui ont besoin d'un espace en fin de ligne pour être
relus). Il doit afficher `Tout est bon.`

## Crédits

DDNet est un logiciel libre de l'équipe DDNet, dérivé de Teeworlds. Ce
template s'inspire de la structure du template Teeworlds officiel de
CubeCoders. Le dépôt ne contient que le template : les fichiers du jeu sont
téléchargés depuis ddnet.org à l'Update.

Réglages et commandes : <https://ddnet.org/settingscommands/>
