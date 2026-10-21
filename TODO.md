# TODO

Tasques detectades però no fetes perquè queden fora de l'abast de la petició concreta en què es van
trobar. Cada entrada indica quan es va detectar i per què s'ha deixat pendent.

---

## 1. Traduir el contingut de funcionalitats que mai han passat per `makemessages`

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

