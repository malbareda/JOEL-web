# 1. Arquitectura i mòduls del JOEL

> Autor d'aquesta documentació: **Edgar**

Aquesta secció explica, mòdul per mòdul, com està organitzat el codi del JOEL. Es divideix en:

- [1.1. Visió general del repositori](1.1-visio-general.md) —el mapa de carpetes de dalt a baix.
- [1.2. El paquet de projecte `dmoj/`](1.2-projecte-dmoj.md) —configuració, rutes, Celery, correu.
- [1.3. L'app `judge/`: models, vistes i admin](1.3-app-judge-models-vistes-admin.md) —el nucli
  del producte.
- [1.4. L'app `judge/`: la resta (bridge, utilitats, comandes, migracions)](1.4-app-judge-suport.md)
- [1.5. Plantilles i recursos de frontend](1.5-frontend-i-recursos.md)
- [1.6. Altres paquets i integracions de tercers](1.6-altres-paquets.md)

## Què és, en una frase

El JOEL és un fork fortament personalitzat de **DMOJ** (un jutge en línia de codi obert), amb Django
al costat web i un motor de correcció (jutge) que corre com a **procés separat**, comunicant-se amb
la web a través d'un tercer procés pont. Damunt d'aquesta base s'hi han afegit, específicament per a
l'ús a l'institut, funcionalitats pròpies: el sistema de pistes, els problemes guiats, el checker
SQL, el gacha de personalització, i la "Lliga de Programació FP".

## Els dos processos, mai un de sol

És fonamental no confondre mai:

- **L'aplicació web** (aquest repositori, `/home/ubuntu/educational-online-judge`): Django, serveix
  pàgines, gestiona usuaris/problemes/concursos, i **mai executa codi d'alumnes**.
- **El motor de jutge** (un paquet Python instal·lat a part, vegeu
  [1.2](../02-sistemes/2.7-jutge-intern.md)): un procés independent que sí executa codi d'alumnes,
  dins un sandbox fort.

Es parlen a través d'un tercer procés, el **pont** (`bridged`), descrit a
[5.2](../05-sistemes-mecanics/5.2-comunicacio-web-jutge.md).

## Funcionalitats pròpies d'aquest fork (no del DMOJ original)

- El sistema de pistes ([2.1](../02-sistemes/2.1-sistema-de-pistes.md)).
- Els problemes guiats, model `Guide`/`GuideTranslation` ([2.2](../02-sistemes/2.2-problemes-guiats.md)).
- La "Lliga de Programació FP" a nivell de `Contest` ([2.3](../02-sistemes/2.3-concursos.md)).
- El gacha de personalització ([2.4](../02-sistemes/2.4-gacha-i-personalitzacio.md)).
- El rànquing dividit "primera"/"segona" (cicles).
- El checker `sql` per a problemes de consultes a bases de dades
  ([5.5](../05-sistemes-mecanics/5.5-checker-sql.md)).
- L'enviament de correu a través de la API de Gmail
  ([1.2](1.2-projecte-dmoj.md), [5.7](../05-sistemes-mecanics/5.7-particularitats-servidor.md)).
- L'emmagatzematge en fitxer (no en text pla a la base de dades) del *feedback* estès de les
  submissions ([2.1](../02-sistemes/2.1-sistema-de-pistes.md)).
