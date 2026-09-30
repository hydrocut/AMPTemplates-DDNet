# -*- coding: utf-8 -*-
"""
Contrôle du template avant de le pousser.

Un template AMP cassé ne se voit qu'au déploiement, quand l'instance refuse de
démarrer ou qu'un réglage ne redescend pas dans le fichier de config. Les
erreurs qui coûtent le plus cher sont bêtes : un `@IncludeJson` qui pointe sur
un fichier qui n'existe pas, une clé exposée dans AMP mais absente du fichier
de config, une regex qui ne relit pas ce que le template vient d'écrire.

Ce script teste exactement ces trois choses, plus le JSON lui-même.

    python verifier.py
"""
import io
import json
import os
import re
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
NOM = 'ddnet'
soucis = []


def lire_json(nom):
    chemin = os.path.join(ICI, nom)
    with io.open(chemin, encoding='utf-8') as f:
        return json.load(f)


# ── 1. tous les JSON se parsent ──────────────────────────────────────────────
fichiers = ['manifest.json', NOM + 'config.json', NOM + 'metaconfig.json',
            NOM + 'ports.json', NOM + 'updates.json']
data = {}
for nom in fichiers:
    try:
        data[nom] = lire_json(nom)
        print('ok   %-22s JSON valide' % nom)
    except Exception as e:
        soucis.append('%s : JSON invalide (%s)' % (nom, e))

if soucis:
    for s in soucis:
        print('NON  ' + s)
    sys.exit(1)

# ── 2. le .kvp ne reference que des fichiers existants ───────────────────────
kvp = io.open(os.path.join(ICI, NOM + '.kvp'), encoding='utf-8').read()
for ref in re.findall(r'@IncludeJson\[([^\]]+)\]', kvp):
    if os.path.isfile(os.path.join(ICI, ref)):
        print('ok   @IncludeJson         %s' % ref)
    else:
        soucis.append('@IncludeJson[%s] : fichier absent' % ref)

for cle in ('ConfigManifest', 'MetaConfigManifest'):
    m = re.search(r'^Meta\.%s=(.+)$' % cle, kvp, re.M)
    if not m:
        soucis.append('Meta.%s manquant dans le .kvp' % cle)
    elif not os.path.isfile(os.path.join(ICI, m.group(1).strip())):
        soucis.append('Meta.%s pointe sur %s, absent' % (cle, m.group(1)))
    else:
        print('ok   Meta.%-16s %s' % (cle, m.group(1).strip()))

# ── 3. le port declare dans ports.json est bien celui que le .kvp attend ─────
refs = set(p['Ref'] for p in data[NOM + 'ports.json'])
for cle in ('PrimaryApplicationPortRef',):
    m = re.search(r'^App\.%s=(.+)$' % cle, kvp, re.M)
    v = m.group(1).strip() if m else ''
    if v not in refs:
        soucis.append('App.%s=%s : aucun port ne porte ce Ref (%s)'
                      % (cle, v, ', '.join(sorted(refs))))
    else:
        print('ok   App.%-16s %s' % (cle, v))

for s in data[NOM + 'config.json']:
    fn = s.get('FieldName', '')
    if fn.startswith('$') and fn[1:] not in ('ApplicationIPBinding', 'RemoteAdminPassword'):
        if fn[1:] not in refs:
            soucis.append('reglage cache %s : aucun port ne porte ce Ref' % fn)

# ── 4. chaque reglage exposé existe dans le fichier de config livré ──────────
# On retrouve le contenu de myServerconfig.cfg dans l'etape CreateFile.
contenu = None
for etape in data[NOM + 'updates.json']:
    if etape.get('UpdateSource') == 'CreateFile' and 'myServerconfig' in etape.get('UpdateSourceArgs', ''):
        contenu = etape['UpdateSourceData']
if contenu is None:
    soucis.append('aucune etape CreateFile pour myServerconfig.cfg')
    contenu = ''

meta = data[NOM + 'metaconfig.json'][0]
# AMP est en C# : ses groupes nommes s'ecrivent (?<nom>...), comme dans tous les
# templates de CubeCoders. Le module `re` de Python exige (?P<nom>...). On
# traduit ICI, pour tester la vraie regex sans la denaturer dans le template.
motif = re.compile(meta['ConfigFormatRegex'].replace('(?<', '(?P<'))

lues = {}
for ligne in contenu.split('\n'):
    if not ligne.strip() or ligne.lstrip().startswith('#'):
        continue
    m = motif.match(ligne)
    if not m:
        soucis.append('la regex ne relit pas la ligne : %r' % ligne)
    else:
        lues[m.group('key')] = m.group('value')

print('ok   regex                 %d lignes relues dans myServerconfig.cfg' % len(lues))

exposes = [s['ParamFieldName'] for s in data[NOM + 'config.json'] if s.get('ParamFieldName')]
manquants = [p for p in exposes if p not in lues]
if manquants:
    soucis.append('regles exposees dans AMP mais absentes du fichier livre : %s'
                  % ', '.join(manquants))
else:
    print('ok   correspondance       %d reglages, tous presents dans le fichier' % len(exposes))

# ── 5. les deux cas qui cassent vraiment la relecture ────────────────────────
# a) une valeur qui contient des espaces : le nom du serveur, le MOTD et la
#    carte « Sunny Side Up » en ont. Si la regex s'arretait au premier espace,
#    le serveur s'appellerait « FR » et la carte « Sunny ».
# b) une valeur VIDE : les lignes de mot de passe. Elles ont un espace en fin
#    de ligne, exactement comme dans le fichier livre par CubeCoders pour
#    Teeworlds — sans cet espace, la ligne ne se relit pas du tout.
cas = [
    ('sv_map Sunny Side Up', 'sv_map', 'Sunny Side Up'),
    ('sv_name FR TeamKit - DDNet', 'sv_name', 'FR TeamKit - DDNet'),
    ('sv_rcon_password ', 'sv_rcon_password', ''),
]
for ligne, cle, valeur in cas:
    m = motif.match(ligne)
    if not m:
        soucis.append('la regex ne relit pas %r' % ligne)
    elif m.group('key') != cle or m.group('value') != valeur:
        soucis.append('relecture fausse pour %r : %r' % (ligne, m.groupdict()))
    else:
        print('ok   relecture            %-20s -> %r' % (cle, valeur))

# ── 6. doublons de reglages ──────────────────────────────────────────────────
vus = {}
for s in data[NOM + 'config.json']:
    p = s.get('ParamFieldName')
    if p:
        vus[p] = vus.get(p, 0) + 1
doubles = [p for p, n in vus.items() if n > 1]
if doubles:
    soucis.append('reglages en double : %s' % ', '.join(doubles))

# ── verdict ──────────────────────────────────────────────────────────────────
print()
if soucis:
    print('%d probleme(s) :' % len(soucis))
    for s in soucis:
        print('  NON  ' + s)
    sys.exit(1)
print('Tout est bon.')
