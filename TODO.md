# TODO

Tasques detectades però no fetes perquè queden fora de l'abast de la petició concreta en què es van
trobar. Cada entrada indica quan es va detectar i per què s'ha deixat pendent.

---

## 1. Traduir el contingut de funcionalitats que mai han passat per `makemessages`

**✅ Resolt el 2026-10-24** (`CANVIS_I_MILLORES.md`, entrada #124): `makemessages` complet i totes les llacunes
omplertes als 5 idiomes (ca 238, es 147, en 134, de 1297, zh_Hans 676 cadenes), 174 traduccions catalanes
existents corregides, i catàleg `dmoj-user` (menú i tipus de problema) creat. El text de sota es conserva com a
historial.

**Detectat:** 2026-08-15/16, en fer l'auditoria i correcció d'i18n (veure `CANVIS_I_MILLORES.md`,
entrada #19). **Parcialment resolt el 2026-08-17** (veure `CANVIS_I_MILLORES.md`, entrada #35): les
5 àrees llistades sota queden traduïdes a `ca`/`es`/`en`/`de` (77 missatges únics). **Encara
pendent**: les mateixes 77 cadenes a `zh_Hans` (l'usuari va decidir explícitament deixar-lo fora
d'aquesta tanda), i la resta del backlog d'i18n que no forma part d'aquestes 5 àrees concretes
(sobretot text tècnic del DMOJ original —`verbose_name`/`help_text` de formularis i admin— que mai
s'ha traduït a cap idioma; sortia de l'abast que l'usuari va triar explícitament per a aquesta
tanda).

Diverses funcionalitats pròpies d'aquest fork ja tenen el seu text embolicat en `_()`/
`{{ _(...) }}`, però **el contingut mai s'ha traduït a cap idioma** (ni tan sols al català, en els
casos on el text font ja és en anglès), perquè `manage.py makemessages` no s'havia tornat a executar
des que es van construir:

- **Guies per a problemes d'introducció** (`Guide`/`GuideTranslation`, secció
  `docs/02-sistemes/2.2-problemes-guiats.md`). ✅ traduït (ca/es/en/de).
- **Tasques** (`ProblemTask`, l'agrupació de problemes en "Tasques"). ✅ traduït (ca/es/en/de).
- **Checker SQL/Mongo**: els noms de les opcions de checker ("Compara contra fitxer", "SQL
  checker"...) i missatges d'error del formulari de dades del problema. ✅ traduït (ca/es/en/de).
- **Gacha**: força text (`"Has aconseguit"`, `"un Sticker!"`, `"una Icona!"`, etc. a
  `templates/gacha/gacharesult.html`). ✅ traduït (ca/es/en/de).
- **Lliga de Programació FP**: alguns textos relacionats. ✅ traduït (ca/es/en/de).

Estat aproximat abans d'aquesta tanda (`msgfmt --statistics` sobre `locale/*/LC_MESSAGES/django.po`):
~58-66 missatges sense traduir a ca/es, ~380 a zh_Hans, i una part important (difícil de quantificar
sense revisar-los un a un) dels ~1280-1320 "sense traduir" a en/de corresponia realment a text
d'origen català que mai s'havia traduït a l'anglès/alemany (la resta són missatges ja en anglès, que
correctament es deixen en blanc perquè `gettext` recorre al `msgid`). Després d'aquesta tanda
(només les 5 àrees de dalt): ca 92 pendents (-19), es 42 (-42), en 1336 (-18, tot i que la xifra
global segueix dominada pel backlog general no tocat), de 1231 (-69); zh_Hans sense canvis (399).

**Per fer-ho (la resta)**: repetir el mateix procés (auditoria per fitxer/plantilla, classificar
cada `msgid` com a font-català o font-anglès abans de traduir per no perpetuar l'error de
`msgmerge`, mai reaprofitar cegament un `msgstr` marcat `#, fuzzy`) per a `zh_Hans` en aquestes
mateixes 5 àrees, i després per a la resta del backlog (text tècnic del DMOJ original a l'admin de
Django, visible sobretot per a professorat/administració, no per l'alumnat). Recompilar amb
`manage.py compilemessages` i reiniciar `site` per aplicar-ho.

## 3. Camp mort `Organization.access_code`

**Detectat:** durant la documentació de la secció 2.5 (`docs/02-sistemes/2.5-organitzacions-mode-professor.md`).

El camp existeix al model però no es fa servir enlloc del codi (ni en unir-se a una organització
oberta ni en cap altre flux). Decidir si val la pena implementar-hi alguna cosa (p. ex. un codi
d'accés per unir-se a organitzacions obertes) o eliminar-lo del tot.

## 5. Gacha: substituir el so sintetitzat per àudio real (opcional)

**Detectat:** 2026-08-16, en implementar animacions i so per al gacha (veure
`CANVIS_I_MILLORES.md`).

El so de la revelació (`playGachaSound()` a `templates/gacha/gacharesult.html`) es genera amb la
Web Audio API (osciŀladors, sense cap fitxer d'àudio) perquè no hi havia cap fitxer de so al
repositori i generar-lo evita qualsevol dubte de llicència. L'usuari ha confirmat que aquesta
solució és vàlida per ara, però ha demanat deixar anotat que **més endavant es podria substituir
per fitxers d'àudio reals** (efectes de "moneda"/"fanfàrria" gravats o descarregats d'un banc de
sons amb llicència compatible), un per raresa, si es vol un resultat més polit.

**Per fer-ho, si mai cal:** afegir els fitxers (`.mp3`/`.ogg`) a `resources/` (no al submòdul
`resources/libs/`), i canviar `playGachaSound(quality)` per crear un `&lt;audio&gt;`/`Audio()` amb
la ruta corresponent en lloc dels osciŀladors actuals.

## 8. Auditoria de cadenes `_()`/`{{ _(...) }}` amb un `%` literal (risc d'error 500)

**Detectat:** 2026-08-16, en implementar animacions pel gacha —veure `CANVIS_I_MILLORES.md`,
entrada #29, on es documenta el bug real trobat i corregit a `gacharesult.html`.

Jinja2 aplica sempre `cadena % variables` a qualsevol `_()`/`{{ _(...) }}`, encara que no es passi
cap variable (`variables` acaba sent un diccionari buit). Si el text conté un `%` literal seguit
d'un caràcter que Python interpreta com a especificador de format vàlid (per exemple "% d", "%s",
"%i"...), `"text" % {}` **peta amb un `TypeError`/`ValueError` en temps real** —no és un error
detectable per `msgfmt --check` (que només compara `msgid`/`msgstr`, no simula l'operador `%`), ni
depèn de si l'entrada porta la marca `#, python-format`. Ja se n'ha trobat i corregit un cas real
(el missatge de premi repetit del gacha, "...un 50% dels..."), escapant-lo com `%%`. És probable
que n'hi hagi d'altres sense detectar en algun altre lloc del codi (qualsevol `_()` amb un `%`
seguit de `d/s/i/x/o/f/g/c/r/a/%` sense espai).

**Per fer-ho:** buscar totes les cadenes font (català) embolicades en `_()`/`{{ _(...) }}` que
continguin un caràcter `%`, i comprovar una per una si el caràcter següent formaria un
especificador de format vàlid de Python; escapar-les com `%%` on calgui. Es podria automatitzar amb
un script que provi `"cadena" % {}` per a cada `msgid` i reporti els que peten.

## 9. Aïllament real dels enviaments: lectura de fitxers i `exec` de processos

> **ACTUALITZACIÓ 2026-10-21 — RESOLT EL DUBTE, I ÉS GREU (vegeu `CANVIS_I_MILLORES.md` entrada #83).** Prova amb
> enviaments reals al jutge en producció (problema privat `aplusb`, un directori testimoni a `/tmp`): **Java 11 i
> Kotlin poden llançar processos (`ProcessBuilder`, `Runtime.exec("sh -c ...")`) i escriure fitxers fora de les
> carpetes permeses (`FileWriter`, `File.writeText`)**. Tots cinc fitxers testimoni es van crear. La JVM s'engega
> amb `-javaagent:java_sandbox.jar=policy:...` i la política només permet escriure a `out/` i `/outputfiles/`, però **no
> s'aplica**. Python 3, en canvi, ho va bloquejar tot (`cptbox`): `subprocess` → `BlockingIOError`, `open(...,'w')`
> fora del sandbox → `FileNotFoundError`, `os.system` no va crear res.
> **Conseqüència:** qualsevol usuari registrat pot executar codi arbitrari al servidor com a `ubuntu`, que és
> propietari de tot `/judge`, del codi del lloc i de les còpies de seguretat, i **té `sudo` sense contrasenya**.
> En la pràctica, això vol dir control total del servidor a través d'un enviament Java.
> **Pendent de decidir (urgent):** (1) contenció immediata, (2) descobrir per què l'agent `java_sandbox.jar` no
> aplica la política, (3) fer córrer els jutges amb un usuari propi sense `sudo` ni permisos d'escriptura fora del que
> necessiten.
>
> **Estat 2026-10-21: RESOLT per a tots els Java.** Java 8, Java 11 i Kotlin, amb l'agent antic i el `SecurityManager`
> (`CANVIS_I_MILLORES.md` #86 i #88); Java 25, amb `cptbox` (#89). Verificat amb proves del testimoni als dos jutges i regressions amb
> solucions `AC` reals. Queda: fer commit dels canvis al repositori del jutge, i (opcional) jutges amb un usuari propi sense `sudo`.
>
> **Causa (2026-10-21, `CANVIS_I_MILLORES.md` #84):** el commit `3fb52a5` del jutge va substituir `java_sandbox.jar` per
> l'agent nou del DMOJ, que ignora `policy:` i no instal·la cap `SecurityManager`; `JavaExecutor.get_security()` torna
> `None`, així que Java i Kotlin no tenen cap sandbox. Opcions d'arreglament:
> - JAVA8, JAVA11 i KOTLIN (Java 11): tornar a fer servir l'agent antic (`git show 9e45a91:executors/java_sandbox.jar`)
>   només per a ells, que sí que activa el `SecurityManager` amb la política. Cal provar-ho (prova del testimoni + que
>   programes normals continuïn donant AC) i reiniciar els jutges.
> - JAVA25: el `SecurityManager` ja no existeix al JDK 25, així que cal el sandbox `cptbox` (com al DMOJ actual), o
>   desactivar-lo temporalment (31.950 enviaments: molt disruptiu).
> - En qualsevol cas: jutges amb un usuari propi, sense `sudo`, i treure `ubuntu` del grup `lxd` si no es fa servir LXD.
>
> **Treure el `sudo` sense contrasenya (a fer per l'usuari, el classificador no deixa Claude fer-ho amb seguretat):**
> 1. Comprovar que es recorda la contrasenya d'`ubuntu`: `su - ubuntu -c true` (ha de demanar-la i acceptar-la).
> 2. Obrir una segona sessió i deixar-hi `sudo -i` obert, com a xarxa de seguretat.
> 3. `sudo visudo -f /etc/sudoers.d/90-cloud-init-users` i esborrar o comentar la línia `ubuntu ALL=(ALL) NOPASSWD:ALL`.
> 4. A la primera sessió: `sudo -k; sudo -v` ha de demanar la contrasenya i acceptar-la. Si falla, desfer el pas 3 des
>    de la sessió de root oberta.
> 5. Opcional: `sudo gpasswd -d ubuntu lxd` (el grup `lxd` equival a root) si no es fa servir LXD (`lxc list`).

**Detectat:** 2026-08-18, arran de la investigació del canvi de Kotlin (entrada #10 d'aquest mateix
fitxer / `CANVIS_I_MILLORES.md` entrada #69), i de proves explícites demanades per l'usuari amb
enviaments reals (Kotlin i Python) contra el jutge en producció.

**Lectura de `/etc/passwd`, confirmada als dos llenguatges provats** (Kotlin i Python), amb
enviaments reals via `holamon`: el contingut real de `/etc/passwd` del servidor es pot llegir i
mostrar a la sortida. **Risc baix, no una fuga greu**: `/etc/passwd` és a la llista blanca explícita
de `BASE_FILESYSTEM` (`dmoj/executors/mixins.py`, al repositori del jutge) per a tots els llenguatges
que fan servir el sandbox de sistema (`cptbox`) —necessari perquè moltes llibreries estàndard
(resolució de noms d'usuari, DNS...) el necessiten per funcionar— i no conté contrasenyes (això és a
`/etc/shadow`, no inclòs a la llista blanca, i ja restringit per permisos normals del sistema
operatiu independentment del sandbox). Per a Java/Kotlin, a més, no hi ha cap sandbox de sistema
(`java_executor.py::get_security` torna `None`), així que la protecció allà depèn només de la
política de Java (`java-security.policy`), que és un únic bloc `grant {}` sense `codeBase` —permet
llegir explícitament `/inputfiles/`, `/outputfiles/`, `in/`, `out/`, però no restringeix cap altra
ruta a nivell de `SecurityManager` (i el sandbox de sistema, que sí que ho faria, està desactivat per
aquest llenguatge concret).

**`exec` de processos, resultat ambigu i pendent d'investigar**:
- En **Kotlin/Java** (sense sandbox de sistema, entrada #69): en una prova manual directa (fora del
  procés real del jutge) amb l'agent i política reals, `ProcessBuilder("id").start()` **funcionava
  sense cap bloqueig**. Però en un enviament real fet a través del jutge en producció, el mateix codi
  no va imprimir ni el missatge d'èxit ni el de captura d'excepció —es va quedar sense resposta
  d'aquella part, tot i acabar en 0.169s (no és un mata per timeout). No està clar si això és un
  bloqueig de seguretat real o un detall tècnic de com es gestionen els pipes del procés fill dins
  del llançador (`launch()`/`TimedPopen`) del jutge real, diferent del meu test manual.
- En **Python** (amb sandbox de sistema `cptbox`, filtratge de syscalls): el mateix intent
  (`subprocess.run(["id"], ...)`) tampoc va imprimir cap dels dos missatges en un enviament real.
  Aquí és més versemblant que el procés es mati directament en l'intent de fer `exec` (per
  filtratge de syscalls), sense arribar a llençar una excepció capturable en Python —però no s'ha
  confirmat mirant els logs interns del jutge en viu.

**Per fer-ho:** revisar els logs del procés del jutge (`screen -r` a la sessió corresponent, o
`extended_feedback`/stderr de la submissió) durant un enviament de prova similar, per veure
exactament quin syscall/excepció talla l'intent d'`exec` a cada llenguatge, i decidir si cal reforçar
alguna cosa més (per exemple, si `ProcessBuilder`/`Runtime.exec()` haurien d'estar explícitament
bloquejats per política a Java/Kotlin, ja que ara mateix no ho estan de manera demostrada —només no
s'ha vist que funcionin en un enviament real, cosa diferent de saber que estan bloquejats).

## 10. Dimoni de compilació persistent per a Kotlin (millora molt més gran que l'entrada #69)

**Detectat:** 2026-08-18, en la mateixa conversa sobre la lentitud de `kotlinc` que va portar a
l'entrada #69 (eliminar `-include-runtime`, ~8% de millora, ~0.5s d'uns ~6.3s).

El gruix del temps de compilació de Kotlin (uns 5-6 segons, fins i tot per a un "Hello World") és
l'arrencada de la JVM i la càrrega de tot el compilador de Kotlin, no la mida del programa —cost que
es paga sencer a cada enviament perquè no hi ha cap dimoni (`kotlin.daemon`) actiu al servidor (es
va comprovar explícitament: `ps aux | grep kotlin` no mostra cap procés de dimoni). El propi
`kotlinc` sap arrencar i reaprofitar un dimoni (una JVM que es queda calenta entre compilacions, via
socket) que reduiria dràsticament aquest temps en compilacions successives —potencialment un ordre
de magnitud més ràpid que l'actual.

**Per què no s'ha fet ja:** cada enviament es corregeix de manera aïllada (procés/entorn propi per
seguretat), i no està clar si el sandbox actual permetria que diferents enviaments d'alumnes
diferents reutilitzessin el mateix dimoni (procés JVM persistent i compartit) sense trencar aquest
aïllament o introduir algun vector nou (per exemple, si el dimoni manté cap estat entre compilacions
que un enviament maliciós pogués llegir o corrompre per afectar el següent alumne que compili).

**Per fer-ho, si es vol perseguir:** investigar si `kotlinc` es pot fer servir amb
`-Dkotlin.compiler.execution.strategy=daemon` (o el comportament per defecte) de manera seva pel
jutge —per exemple, un dimoni compartit però on cada compilació és una crida independent sense estat
persistent visible entre alumnes (el dimoni de Kotlin normalment només manté calenta la JVM i les
classes carregades, no dades de l'usuari)— i mesurar l'impacte real (comparant amb els ~5.79s ja
mesurats a l'entrada #69) abans de decidir si val la pena el risc/complexitat addicional.

## 11. Kotlin amb declaració `package`: el jutge no troba la classe principal

**Detectat:** 2026-10-21, durant la regressió de `CANVIS_I_MILLORES.md` #88. Una solució `AC` de febrer del 2026 de `tortasaceitepro` (Kotlin)
que comença per `package org.example.Lliga2526.Jornada11.TortasAceitePro` ara falla: "Could not find or load main class
org.example.Lliga2526.Jornada11.TortasAceitePro.Tortasaceite". Passa igual amb l'agent antic i amb el nou, així que no és el sandbox: ve del
canvi de #69 (Kotlin sense `-include-runtime`, executat amb `-cp` i la classe principal del manifest).

**Per fer-ho:** reproduir-ho amb `KOTLIN.Executor` fora dels jutges (com a #88) i mirar per què la classe que es fa servir no és la
`Main-Class` del manifest que genera `kotlinc` (`...TortasAceitePro.MainKt` en compilar-ho a mà).


---

## 12. Problemes SQL: procediments, funcions i triggers amb correcció automàtica (MariaDB)

**Detectat:** 2026-10-22, en parlar de què més es pot fer amb el motor MySQL (veure `CANVIS_I_MILLORES.md`,
entrades #100–#107). **Pendent de decidir per on començar** (aquest o l'entrada 13).

Disseny proposat (no començat):
- Checker nou `mysqlproc` (cap en 10 caràcters). Com que `CREATE PROCEDURE/FUNCTION/TRIGGER` és DDL i fa commit
  implícit a MariaDB, no es pot desfer amb `ROLLBACK`: cada correcció crea una **BD temporal** a partir d'un dump
  petit del problema (amb `mysql_grader.load_dump`, que ja converteix `DELIMITER`), hi instal·la el codi de l'alumne
  amb un usuari que només té permisos sobre aquella BD, executa els casos de prova del professor, fa el mateix amb
  la solució de referència en una altra BD temporal, compara i ho esborra tot.
- Casos de prova, un per cas de DMOJ i amb punts propis: **funció** (`SELECT f(args)` → comparar el valor),
  **procediment** (`CALL p(args)` → comparar les taules i els resultats que retorni), **trigger** (executar un DML →
  comparar l'estat, o comprovar que falla amb el mateix `SIGNAL SQLSTATE` quan ha de fallar).
- Retroacció: dir quina prova falla (p. ex. "`SELECT descompte(250)`: el resultat no coincideix") sense ensenyar
  la solució.
- Seguretat: el mateix que ara (sense `FILE` ni `SUPER`, `MAX_STATEMENT_TIME` contra els bucles infinits,
  `PREPARE` confinat a la BD temporal).
- Format de lot nou a `create_db_problems` (dump base, nom i signatura de la rutina, referència, proves) i suport a
  la pàgina d'enviament. Per rendiment, fer servir BD de partida **petites** (cada prova en crea dues).
- Estimació: 2–3 dies.

---

## 13. Bloc de problemes només de PostgreSQL (checker propi, com Mongo)

**Detectat:** 2026-10-22. L'usuari el vol com un bloc a part, amb el seu checker i problemes només de Postgres,
sense barrejar-lo amb els de MySQL (perquè els alumnes no confonguin dialectes).

- Interès: el que MariaDB 10.5 **no** té: `FULL OUTER JOIN`, `COUNT(*) FILTER (WHERE …)`, `DISTINCT ON`, `LATERAL`,
  `GROUPING SETS`/`CUBE`, `generate_series`, arrays i `unnest`, JSONB amb operadors, i la part objecte-relacional
  (tipus compostos, herència de taules, tipus propis), útil per a la UF de BD objecte-relacionals de M02. A més, a
  Postgres el DDL és transaccional: fins i tot `CREATE FUNCTION`/`CREATE TABLE` es poden corregir dins d'una
  transacció i desfer amb `ROLLBACK` (exercicis de DDL i de PL/pgSQL molt més nets de corregir).
- Pla: segona instància (PostgreSQL) com la de MariaDB (`/home/ubuntu/mariadb-grader/`): només socket, rol de
  només lectura, `statement_timeout`; checker calcat de `mysql.py`/`mysqlwrite.py` amb `psycopg2`; carregador de
  dumps sense passar per `psql`; selector al formulari; motor `"engine": "postgres"` a `create_db_problems`.
  BD de partida: Chinook, Pagila (sakila) i northwind tenen versions oficials per a Postgres.
- Estimació: uns 2 dies, més portar les BD i escriure els problemes.
- Ja apuntat per si es fa: no fer servir el mateix nom `||`/`LIMIT`… en problemes que s'assemblin als de MySQL.

**Estat (2026-10-23):** fet en gran part (CANVIS #110–#113): servidor PG 17, checker `postgres`, web i 15 problemes
privats (`sqlpg*`). Queda pendent:
- Pujada de dumps de Postgres dels professors (rol `joel_pg_loader`, propietaris al grup `joel_pg_owners`).
- Dates relatives a "avui" (`current_date + 14`): el checker només normalitza els valors iguals a "ara"; si la
  correcció de l'alumne i la de la referència cauen a banda i banda de la mitjanit, dona WA. Afecta dues preguntes
  de Northwind (`crear_comanda` i el trigger de comandes). Solució possible: fixar el rellotge de la transacció o
  normalitzar també les dates a `ara ± n dies`.

---

## 14. Pendents de la migració a MySQL i de QueryTest (2026-10-22)

- **Dumps que falten** per migrar unes 240 preguntes més de QueryTest: ies26 (146, i les 4 del test #209, que és
  d'ies26 encara que QueryTest el marqui com a ies23), ies (34), cinema (20), pilotador (19), noms (11) i "Múltiples
  taules" (9). `importacions/noms.sql` i `importacions/ies23.sql` estan **malmesos** (falten els `INSERT INTO … VALUES (`
  i el principi de les dades): cal tornar-los a exportar. Les BD `noms` i `ies23` hi són buides a la instància.
- **30 preguntes aparcades** a `problem_batches/sql/aparcades/` (README amb el motiu de cadascuna): 29 amb la
  resposta buida amb les dades actuals i 1 que posa 'Pending' en una columna `ENUM('Card','Cash')`. Cal decidir si
  es canvien les dades, l'enunciat, o es descarten.
- **Enunciats per revisar** a `problem_batches/sql/aparcades/revisar_enunciats/`: els reconstruïts a partir del SQL
  (a QueryTest només hi havia el títol) i uns 14 casos (4 de valorant, ~10 de sakila) on la solució de QueryTest no
  feia el que deia l'enunciat original (p. ex. "el mapa més jugat" amb `ORDER BY COUNT(*)` sense `DESC`): potser el
  que s'ha de corregir és el SQL.
- **Problemes DML nous** (`sqldml*`, entrada #107): les notes de verificació són a `problem_batches/sql/dml_notes/`.
  Convé que un professor els repassi.
- **Retirada de SQLite, passos 2 i 3** (entrada #106): moure les funcions compartides de `sql.py` a un mòdul base i
  treure el checker `sql`; retirar el camp `sql_db` (migració que esborra una columna: mirar-ne abans els valors);
  esborrar els `.db` antics d'11 problemes i les plantilles de `/judge/_sql_templates/` (amb còpia abans).
- **`celebracio.mp3`** surt com a esborrat de l'arrel del repo (ara és a `importacions/`, de root, del 18 d'agost) i
  el gacha encara el fa servir amb `static('celebracio.mp3')`: comprovar si el so sona.
- **Commit**: els canvis de les entrades #107 (i les notes d'aquest TODO) encara no estan commitejats al repo del
  web. Al repo del jutge sí (`5f1017d`, `abf79bc`).

## 15. Restes de la revisió de pàgines estàtiques i traduccions (2026-10-24, entrades #124 i #125)

**Resolt el 2026-10-24 (entrada #125):** errades dels `msgid` del codi, noms dels tipus "Extracció de Dígits" i
"Matemàtiques simples", comptador de pistes per AJAX, normes de participació (aprovades per l'usuari), tipus "listas" fusionat i
traduccions `ca` redundants de les pàgines planes esborrades (entrada #126). Només queda, com a referència:

- **Comptes demo de les captures** (`demo_alumne`, `demo_alumna`, `demo_alumne3`, `demo_profe`, equip "Grup demo
  (guies)" id 195 a l'Institut JOEL, problema privat `demoguia` id 1396): ocults, sense contrasenya utilitzable i sense
  grups. Per refer captures cal donar-los una contrasenya i, a `demo_profe`, els grups Profe i "creador de problemes
  Jr" i `is_staff`. Script de captura: `~/shots/guies/shot.py` (Selenium + Chromium, anonimitza els noms d'altres usuaris; llegeix les contrasenyes d'un `demo_creds.json` que ja no existeix), amb les tandes a `~/shots/guies/specs/`.

## 16. Traduccions al castellà: falten els problemes no públics (2026-10-27, entrades #130 i #131)

Fet: els 491 problemes de tasques (#130) i els 342 públics fora de tasques (#131): 952 traduccions `es` en total, 916 de 955 públics
(96%). Queden **402 problemes sense fila `es`**: 39 públics que ja estan escrits en castellà (veure sota), **96 privats
d'organització** (~54.000 caràcters, 20 amb `is_public`) i **267 no públics** (~437.000 caràcters). Els no públics es poden traduir amb el
mateix procés (només cal canviar el filtre de l'exportació a `is_public=False` o `is_organization_private=True`); `es2/INSTRUCCIONES.md`
té les normes ja ajustades.

- **Mateixes normes:** només l'enunciat (res d'exemples, casos de prova, comentaris ni `<img>`), noms propis intactes (també topònims,
  títols de jocs i pel·lícules). Les decisions de criteri són a l'entrada #130.
- **Procés usat** (scripts a l'scratchpad de la sessió, es perdran): exportar a `NAME:/---/enunciat`, lots de ~40.000 caràcters traduïts
  per subagents, `validate.py` (compara blocs ```` ``` ````, `<img>`, codi en línia, `~LaTeX~`, URLs, encapçalaments), unificació de noms
  propis, i inserció amb `ProblemTranslation` + `problem_update()` (el senyal de `Problem` no es dispara per traduccions, i `problem_html`
  es cacheja 24 h). Si es repeteix, val la pena guardar-los al repo.
- **39 problemes públics ja eren en castellà** i no tenen fila `es`, així que compten com a "sense traducció" a la caixa de la portada
  (916 de 955, 96%). 15 de tasques (`discotheque`, `descomprimir`, `esqueelpolloenlegion`, `reabastpluto`, `inception`, `furros`,
  `oftalmologo`, `oftalmologo2`, `cuadradoaritmetico1`, `cuadradoaritmetico2`, `regladesustitucion`, `saltocab`, `npapa`, `arribaabajo`,
  `barrilesexplosivos`) i 24 de fora (entre ells `cocitrol`, `lutrija`, `dzumbus`, `zoo`, `encuentralapagina`, `pato`, `excel`,
  `jocdecartes`; la llista sencera són els `SKIP` de `<scratchpad>/es2/out/`). Decidir si s'hi crea una `ProblemTranslation` idèntica a
  l'original per quadrar el comptador, o si la caixa ha de comptar només els que cal traduir. Cas especial: `jocdecartes` té el cos en
  castellà però el títol en català («Joc de Cartes»).
- **Recompte de la caixa**: només mira `language='es'`; les 2 traduccions `ca` i 2 `en` no hi compten.

---

## 17. Restes dels textos de presentació de les tasques (2026-10-27, entrada #136)

Fet: les 53 tasques on `marc` és l'únic autor tenen text nou en català i traducció `es` (model `ProblemTaskTranslation`). Queda:

- **`bdfuncionscase`** conserva el seu text antic, que diu «funcions de text i de dates de **SQLite**»; la correcció SQL és MySQL des del 22/10.
  Es va deixar tal qual perquè l'usuari va triar conservar el text real antic. Corregir-ho a mà (ca i `es`).
- **Tasques de prova/clon** amb text nou: `test7` («test»), `wwwww` i `xxxx` (clons de «Problemes Selectes de Marc Clonat», 1 problema cada una) i
  `buclesclonat` (clon d'«Iniciació als Bucles»). Valdria la pena eliminar-les (cal permís explícit abans d'esborrar-les).
- **8 tasques sense cap autor** que es van ignorar: `sabpython2damvi`, `matrius`, `2damvim3uf5iteradors`, `2damvim3uf5diccionar`, `11strings`,
  `m6accesdadeschashtag`, `11dicionaris`, `edtrepas`. Decidir si tenen propietari (algunes semblen de `marc`) i si es fa el mateix amb elles.
- **Les altres 131 tasques** (d'altres professors) conserven el seu `about` (sovint un placeholder: `aaa`, `bbb`…) i no tenen traducció; ara que el
  model existeix, es pot repetir el procés (subagents per lots + validador + `apply_task_texts.py`) si els seus autors ho volen. Els scripts eren a
  l'scratchpad de la sessió i es perdran: si es repeteix, convé guardar-los al repo.
- **Idiomes:** només `es`. El model admet qualsevol idioma de `LANGUAGES` (`en`, `de`, `zh-hans`); a la resta es mostra el català.

---

## 18. Restes del botó de descàrrega de la base i de la guia del DBeaver (2026-10-28, entrades #137, #138 i #139)

- **Recarregar uwsgi** (`~/dmojsite/bin/uwsgi --reload /home/ubuntu/dmoj-site.pid`): és l'únic pas que falta perquè surtin el botó de descàrrega i l'enllaç a la guia a
  la pàgina de l'esquema, perquè els volcats nous (línies de 16 KB, binaris en hexadecimal) siguin els que es serveixen, i perquè l'etiqueta «Guia DBeaver» del menú
  surti traduïda. El sistema va denegar fer-ho com a desplegament a producció; cal l'OK explícit de l'usuari.
- **`/guiaalumnes/`** no esmenta encara el botó «Descarrega la base de dades» ni la guia `/guiadbeaver/`.
- **Neteja de `/home/ubuntu/dbeaver-xvfb`** (746 MB: DBeaver, paquets, captures de treball, dades de les bases temporals), de `/home/ubuntu/Downloads/hotel.sql` i de l'scratchpad
  (sobretot `a_ies23g.sql`, que té correus i contrasenyes en clar de `ies23g`). No s'ha esborrat res; cal l'OK de l'usuari. Si cal refer o ampliar les captures,
  `dbeaver-xvfb/session-all.sh` + `env.sh` + `dbx.sh` deixen el DBeaver a punt (veure l'entrada #139).
- **`ies23g`**: té contrasenyes en text pla d'alumnes dins la base d'un problema públic; l'esquema continua sent visible. Valdria la pena substituir la base o amagar-hi les
  columnes.
- Els passos de la guia no s'han provat amb MySQL 8 ni amb DBeaver per a Windows/macOS.

---

## 19. Restes del problema `calorcito` (2026-11-03, entrada #145)

L'enunciat (català i castellà) ja està reescrit. Queda, **sense tocar perquè no era demanat**:
- **Casos de prova pobres:** els 5 casos privats són exactament els 5 exemples de l'enunciat, i els dos que no donen punts (`i2` i `i4`, 0 punts a `init.yml`) fan que només puntuïn 3 de 5.
  Faltarien casos de frontera: 15/16 alumnes, 18/19, 22/23 i 25/26 graus, i `NO` amb més de 25 graus i pocs alumnes (resposta `Res`). Canviar-ho vol dir **substituir el zip de dades d'un problema
  ja publicat** (`/judge/calorcito/coses.zip` + `init.yml`) i que canviïn els punts; cal preguntar abans a l'usuari i a l'autor (`gsantama`).
- ~~**Imatge:** un alfil d'escacs carregat d'un Google Sites extern.~~ **Resolt el mateix dia (entrada #147):** ara és una foto CC0 d'una unitat d'aire condicionat, allotjada al servidor.
- **Els fitxers de prova usen `\r\n` i no acaben amb salt de línia** (`19\r\n27\r\nNO`), a diferència dels problemes «Sense Bucles» més nous. No s'ha provat cap enviament per veure si afecta
  algun llenguatge (el checker és `linecount`); és només una nota per si algun dia es refan les dades.

---

## 20. Restes de la còpia local d'imatges dels enunciats (2026-11-03, entrada #147)

Fet: 537 imatges copiades, reduïdes i servides des de `/media/problem-images/` (1.016 referències reescrites). Queda:
- ~~**`/tmp/media` s'esborra a cada arrencada.**~~ **Resolt (entrada #148, 2026-11-03):** els fitxers són a `/home/ubuntu/joel-media/media/`, `/tmp/media` n'és un enllaç i el crontab d'`ubuntu` té
  `@reboot [ -e /tmp/media ] || ln -s /home/ubuntu/joel-media/media /tmp/media`. Queda **sense provar amb un reinici real**. Si després d'un reinici les imatges donen 404: `ln -s /home/ubuntu/joel-media/media /tmp/media`
  (si Django ja ha creat una carpeta `/tmp/media` real, mou-ne primer el contingut a `joel-media/media`). Còpia de seguretat feta abans del canvi: `/home/ubuntu/joel-media/media-backup-20261103/` (es pot esborrar quan es vulgui);
  còpia del crontab d'abans: `/home/ubuntu/joel-media/crontab-abans-20261103.txt`. Alternativa sense enllaç (cal `sudo`): `MEDIA_ROOT` i el `location /media` de nginx apuntant a `/home/ubuntu/joel-media/media`.
- **imgur (60 URL, 65 problemes):** el servidor rep `429` (bloqueig per IP, ~180 peticions seguides). **L'admin (2026-11-05) ha comprovat des del navegador que les 6 URL de mostra es veuen bé** (buscamines, 8reines, oftalmologo, notes1, desiertosinai, penjat) i diu que les veu "totes": per tant no estan trencades, només sense còpia pròpia; urgència baixa (el risc és que imgur les tombi en el futur). Tornar-ho a provar d'aquí unes hores/dies amb `tools/mirror_problem_images/` (pauses llargues, sense paral·lelisme) i, si s'aconsegueix, repetir passos 3-5 del `README.md` d'aquella carpeta.
- ~~**`casinosort`** (`lucky-player.jpg`)~~ i ~~les trencades dels problemes públics~~: **resolts (entrada #150)**, amb substituts CC0/domini públic i dos diagrames dibuixats. Llista actual de pendents: `/home/ubuntu/joel-media/imatges_pendents.tsv`.
- **Imatges que queden (entrada #150):** 60 URL d'imgur (65 problemes, 53 públics; `429` des del servidor), 2 de vives sense copiar (AVIF) i **26 URL trencades, totes en problemes privats (27)**. Decidir si es treuen les etiquetes o es busquen substituts també per als privats.
- **Revisar amb l'autor** (substituts decoratius, no els originals): `keypaddesordenat` (teclat genèric) i `quadratpeo` (tauler genèric), per si la imatge original explicava alguna cosa; els 41 substituts són a `/home/ubuntu/joel-media/substituts_cc0.tsv` (23 són «domini públic», no formalment CC0).
- **Imatges fora dels problemes** (blog, pàgines estàtiques, comentaris, `about` de tasques) no mirades.
- `alfil`: l'`alt` de la imatge diu «aireacondicionat» (copiat de `calorcito`); no s'ha tocat.
- Còpia dels textos antics: `/home/ubuntu/joel-media/backup-descriptions-20261103-190531.json` i `backup-botwhatsapp-20261103.json`; es poden restaurar per `pk` si cal desfer-ho.

## 21. Concursos/exàmens: s'accepten enviaments després del final via participació virtual (2026-11-04, entrada #149)

Un professor de Pedralbes va avisar que `ipedsimdaw123a` admet enviaments un cop acabat. **No és un forat dels enviaments en directe:** a tota la BD hi ha 0 enviaments de participacions en directe posteriors a `end_time`
(el middleware `ContestMiddleware` treu l'usuari del concurs en acabar-se i el que envia després ja és un enviament normal). El que passa és la **participació virtual** (`ContestJoin.join_contest`, rama `if contest.ended:`
a `judge/views/contests.py`, comportament de DMOJ des del 2016): passat el final, qualsevol que pugui veure el concurs i el premi a «Unir-se» obté una participació virtual amb la mateixa durada i els seus enviaments
queden com a `ContestSubmission` d'aquell concurs. A `ipedsimdaw123a`: 10 participacions virtuals (5 alumnes uns minuts després de les 08:45, i `ipedtest`/`srivas` l'endemà), 3 enviaments, cap amb puntuació d'alumne
al rànquing real (el rànquing només mostra `virtual=0`). Només es bloqueja amb **codi d'accés** (`requires_access_code`).
- Falta decidir la solució. Proposta: camp `Contest.disallow_virtual` (com a DMOJ upstream), que fa que `join_contest` rebutgi la unió quan `contest.ended`, visible a l'admin (i marcar-lo per defecte als exàmens/lliga).
  **Cal migració** (i el teu OK per migrar a producció). Alternativa sense migració: posar un codi d'accés als exàmens i comunicar-lo només a qui toqui.
- Relacionat: les participacions virtuals **compten per a la lliga** (`Contest.lliga_points()`: màxim de totes les participacions del concurs). A les lligues passades afecta 28 parelles usuari/concurs. Decidir si ha de comptar només `virtual=0`.
- Tampoc hi ha cap avís visible per a l'organitzador que distingeixi els enviaments virtuals a la llista d'enviaments del concurs; es poden confondre amb enviaments «fora de temps».

## 22. Restes de la «Guia de crear achievements» i dels creadors d'achievements (2026-11-04, entrades #152 i #153)

- **«Achievements» no surt al menú lateral de l'administració** (la configuració `WPADMIN` de `dmoj/settings.py` no el porta, ni com a fill de cap apartat). Un creador d'achievements, que només té permís sobre aquest model, veu el menú ple d'apartats on no pot fer res i no troba on crear-ne: arriba a `/admin/judge/achievement/` només per l'enllaç directe, i per això la guia el dona explícitament. Es pot afegir `('judge.Achievement', 'fa-trophy')` al menú.
- **El `help_text` de «Qualitat» diu «5 superllegendari»** (`Achievement.quality`) i el desplegable que veu un alumne no el té (és només d'admins): pot confondre. El `help_text` de «Categoria» també parla de color/tema/font, que tampoc pot triar.
- **Les restriccions de pàgina plana per permís viuen al codi** (`judge/flatpage_permissions.py`, un diccionari URL → permís), no a l'admin de pàgines estàtiques: per restringir-ne una altra cal editar-lo (i que l'entrada del menú tingui el mateix `path`). Si es vol poder fer-ho des de l'admin caldria un camp nou (migració).
- La captura `achievements-admin.png` és només en català (com les altres guies) i el nom d'usuari que hi surt és el genèric `alumne1`.

## 23. Restes de la «Roda de la pissarra» (2026-11-05, entrada #154)

- **`vote_submission` fa `request.user.has_perm('see_extended_answers')` sense el prefix `judge.`** (`judge/views/submission.py`, línia ~290). Django exigeix `'app.codename'`, així que només els superusuaris reben el vot ×10; els professors amb el permís Profe no (a `judge/models/problem.py:205` sí que s'escriu bé, `judge.see_extended_answers`). No s'ha tocat: queda fora de la petició de la roda. Cal decidir si és intencionat abans de «arreglar-ho», perquè canviaria el pes dels vots dels professors d'ara endavant.
- **Un alumne no rep cap avís quan un professor li dona GachaPoints** des de la roda: només veu que el saldo puja. Es podria afegir un missatge privat o un avís al gacha.
- **Els professors que són membres d'un equip però no admins** surten com a alumnes a la roda (només s'exclouen admins, `registrant`, `is_unlisted` i qui gira). El professor els pot treure amb el xip; si molesta, es pot excloure qui tingui el permís Profe.
- **La roda només dona 1–5 punts per clic també als superusuaris** (només es salten el límit diari). Si es vol donar-ne més d'un cop (p. ex. 20), caldria un camp numèric per als superusuaris.
- ~~No s'ha provat el bloqueig de fila~~ **Resolt el 2026-11-05** (entrada #154): provat amb dues connexions contra la MariaDB real (error 1205 mentre una el té). **Encara no s'ha fet** una prova de cursa completa del flux de donació (dues peticions `POST /wheel/grant` simultànies per al mateix alumne) perquè exigiria files confirmades i esborrar-les després.
- **La roda encara no l'ha provat ningú amb un compte de professor real** (les proves van ser amb comptes falsos que es desfan). Convé que un professor real l'obri un cop i confirmi que veu l'enllaç i que el so i l'animació van bé en el seu projector.
- **Slider «Over-the-top» (entrada #155):** cal que algú el provi amb una **GPU real i un projector** (el rendiment s'ha mesurat sense GPU) i que escolti els sons dels nivells 8–10. Si als ordinadors de l'aula va just, es pot abaixar `MAX_PARTS` o el llindar del governador (`frameMs > 45`) a `templates/organization/wheel.html`.

## 24. Restes de la «Imatge del problema» (2026-11-05, entrada #156)

- ~~Aplicar la migració 0169~~ **Fet el 2026-11-05** (l'usuari, amb `!`). **uwsgi recarregat** (01:44, l'usuari). Falta una **prova real**: pujar una imatge des de l'admin amb un compte d'autor i veure la pàgina i el PDF en un navegador (també en mòbil).
- **Convertir els enunciats existents:** **fet per als que compleixen la regla estàndard**: 358 públics (entrada #159 i prova #157) i 145 no públics (entrada #161), 503 en total. **Queden 84 públics + 79 no públics** amb una `<img>` d'una altra forma (enmig del text, `float:none`, URL externa/imgur...), **13 públics + 4 no públics** amb 2 o més imatges i **2 saltats** (`pozojubilat`, `professorasubstituta`: la traducció `es` té una altra imatge). Decidir què fer-ne (a mà, o una regla nova).
- La **previsualització en viu** de l'admin no mostra la imatge nova.
- Només una imatge i mida fixa (300 px); si cal triar mida/posició, afegir un camp més.
- Els autors que no són *staff* segueixen pujant les imatges del text a **imgur** (`martor_image_uploader`); es podria fer que també usin el nostre servidor (amb la mateixa reducció).
- **Captura de la guia de crear problemes** (`resources/guides/problemes-admin.png`): no mostra el camp «Imatge del problema» (entrada #160); tornar-la a fer si es vol. Els textos en alemany i xinès de la guia i del camp són meus, sense revisió.

## 25. Restes de la «protecció contra la mala sort» del gacha (2026-11-05, entrada #162)

- ~~Aplicar la migració `0170_profile_gacha_pity` i recarregar uwsgi~~ **Fet el 2026-11-06 11:03** (l'usuari, amb `!`) i verificat (entrada #162). Falta veure-ho amb un alumne real (només s'ha provat amb un usuari fals en una transacció desfeta).
- **Possible doble tirada per un doble clic (existent, no tocat):** `GachaGo.gacha_roll` llegeix `profile.gacha_points`, hi suma el cost a la memòria i desa tot el perfil sense bloqueig de fila ni transacció. Per la lectura del codi, dues peticions `POST /gacha/go/` alhora podrien fer dues tirades pagant-ne una, i també comptarien una sola vegada per a la ratxa. **No s'ha provat.** Es podria arreglar amb `transaction.atomic()` + `select_for_update()` sobre el perfil (com a la roda de la pissarra).
- ~~Inicialitzar el comptador dels que ja tenen moltes tirades~~ **Fet el 2026-11-06** per als 219 alumnes amb més de 100 tirades i cap super (entrada #163). Queden a 0 els que tenen algun super però no tots (11 amb més de 100 tirades) i els de 100 tirades o menys.
- Mesurar-ne l'efecte real al cap d'unes setmanes (quants supers nous i quantes tirades portaven) per retocar `SUPERLEGENDARY_PITY_STEPS`; avui no es guarda la ratxa en el moment d'obtenir-lo.
- Vigilar la càrrega manual si «Dret a Crear Achievements» surt més sovint (correu + permisos a mà).
