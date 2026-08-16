# Documentació del JOEL

> Autor d'aquesta documentació: **Edgar**

Aquesta és la documentació exhaustiva del JOEL, el jutge en línia de l'institut. Ha estat escrita
sencera en català, i pensada perquè qualsevol persona amb accés al codi —professorat, alumnat
avançat o qui hagi de mantenir el projecte en el futur— pugui entendre com funciona per dins, des de
l'arquitectura general fins al detall més concret d'un sistema específic.

Al llarg del text, l'"Edgar" apareix com a exemple d'usuari típic —un alumne que envia una
submissió, demana una pista, o fa una tirada de gacha— per il·lustrar els fluxos amb un cas concret
en lloc de parlar sempre en abstracte.

## Com està organitzada

### [1. Arquitectura i mòduls](01-arquitectura/README.md)
El mapa complet del repositori: com es reparteix el codi entre el paquet de projecte (`dmoj/`),
l'app principal (`judge/`), les plantilles, els recursos de frontend, i els paquets de tercers que
s'hi integren. Comença per aquí si vols saber "on és cada cosa".

### 2. Sistemes
Cada funcionalitat important del JOEL, explicada de dalt a baix:

- [2.1. Sistema de pistes](02-sistemes/2.1-sistema-de-pistes.md)
- [2.2. Problemes guiats](02-sistemes/2.2-problemes-guiats.md)
- [2.3. Concursos](02-sistemes/2.3-concursos.md) (amb la Lliga de Programació FP a
  [2.3.1](02-sistemes/2.3-concursos.md#231-lliga-de-programació-fp))
- [2.4. Gacha i personalització](02-sistemes/2.4-gacha-i-personalitzacio.md)
- [2.5. Organitzacions i mode professor](02-sistemes/2.5-organitzacions-mode-professor.md)
- [2.6. Estadístiques](02-sistemes/2.6-estadistiques.md) (de problema, d'organització i d'alumne)
- [2.7. El jutge intern](02-sistemes/2.7-jutge-intern.md) (executors, graders i checkers)

### 3. Flux intern, pas a pas
Què passa realment, internament, en els dos moments més importants del sistema:

- [3.1. Des de la creació d'un problema fins que està llest per executar-se](03-flux-intern/3.1-creacio-problema.md)
- [3.2. Des d'un enviament fins a tenir la solució del jutge](03-flux-intern/3.2-cicle-de-vida-enviament.md)

### [4. Particularitats de la programació del JOEL](04-particularitats-programacio/README.md)
Convencions, paranys i decisions de disseny que no són òbvies llegint el codi per sobre: els dos
motors de plantilla, els dos sistemes de traducció, paranys de MariaDB patits en producció,
`django-reversion`, i la convenció de `request.profile`.

### 5. Sistemes mecànics
Les peces d'infraestructura que fan que tot això funcioni:

- [5.1. Celery](05-sistemes-mecanics/5.1-celery.md) —tasques en segon pla.
- [5.2. El pas de web a jutge](05-sistemes-mecanics/5.2-comunicacio-web-jutge.md) —el protocol i
  el pont.
- [5.3. Múltiples jutges](05-sistemes-mecanics/5.3-multiples-jutges.md) —com es reparteix la feina.
- [5.4. Base de dades i còpies de seguretat](05-sistemes-mecanics/5.4-base-de-dades-copies-seguretat.md)
- [5.5. El checker SQL](05-sistemes-mecanics/5.5-checker-sql.md) —problemes de consultes a bases
  de dades.
- [5.6. La carpeta de problemes](05-sistemes-mecanics/5.6-carpeta-problemes.md) —on viuen les
  dades de correcció.
- [5.7. Particularitats del servidor](05-sistemes-mecanics/5.7-particularitats-servidor.md) —els
  processos, i la integració de correu amb l'API de Gmail.

## Una nota sobre seguretat

Aquesta documentació és pública. Per aquest motiu, **no conté cap testimoni d'accés, clau, ni
contrasenya**, i qualsevol identificador concret d'infraestructura (nom de projecte de núvol, compte
de servei, domini institucional) que apareix als registres interns del projecte s'ha substituït aquí
per un marcador de posició genèric. Els noms i identificadors reals es poden consultar, si cal, als
registres interns no públics del projecte.
