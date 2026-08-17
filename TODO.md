# TODO

Tasques detectades però no fetes perquè queden fora de l'abast de la petició concreta en què es van
trobar. Cada entrada indica quan es va detectar i per què s'ha deixat pendent.

---

## 1. Traduir el contingut de funcionalitats que mai han passat per `makemessages`

**Detectat:** 2026-08-15/16, en fer l'auditoria i correcció d'i18n (veure `CANVIS_I_MILLORES.md`,
entrada #19).

Diverses funcionalitats pròpies d'aquest fork ja tenen el seu text embolicat en `_()`/
`{{ _(...) }}`, però **el contingut mai s'ha traduït a cap idioma** (ni tan sols al català, en els
casos on el text font ja és en anglès), perquè `manage.py makemessages` no s'havia tornat a executar
des que es van construir:

- **Guies per a problemes d'introducció** (`Guide`/`GuideTranslation`, secció
  `docs/02-sistemes/2.2-problemes-guiats.md`).
- **Tasques** (`ProblemTask`, l'agrupació de problemes en "Tasques").
- **Checker SQL**: els noms de les opcions de checker ("Compara contra fitxer", "Linea a Linea",
  etc.) i missatges d'error del formulari de dades del problema.
- **Gacha**: força text (`"Has aconseguit"`, `"un Sticker!"`, `"una Icona!"`, etc. a
  `templates/gacha/gacharesult.html`) segueix sense traduir a cap dels 5 idiomes actius, tot i estar
  correctament embolicat.
- **Lliga de Programació FP**: alguns textos relacionats.

Estat aproximat a data d'avui (`msgfmt --statistics` sobre `locale/*/LC_MESSAGES/django.po`): ~58-66
missatges sense traduir a ca/es, ~380 a zh_Hans, i una part important (difícil de quantificar sense
revisar-los un a un) dels ~1280-1320 "sense traduir" a en/de correspon realment a text d'origen
català que mai s'ha traduït a l'anglès/alemany (la resta són missatges ja en anglès, que
correctament es deixen en blanc perquè `gettext` recorre al `msgid`).

**Per fer-ho**: revisar entrada per entrada els missatges marcats `#, fuzzy` (`msgmerge` n'hi ha
aparellat molts amb traduccions antigues no relacionades — cal comprovar-los un a un abans de
donar-los per bons) i traduir els que queden buits. Recompilar amb `manage.py compilemessages` i
reiniciar `site` per aplicar-ho.

## 2. La pàgina "About" (`templates/about/about.html`) té contingut equivocat, no només sense traduir

**Detectat:** 2026-08-15/16, durant la mateixa auditoria d'i18n.

Aquesta pàgina és el text original del DMOJ de referència, sense adaptar: parla del "DMOJ Monthly
Open Programming Competition", demana contactar per Slack a `slack.dmoj.ca`, dona `contact -at-
dmoj.ca` com a adreça de contacte, i llista com a administradors usuaris que no existeixen en aquest
desplegament (`quantum`, `Xyene`, `FatalEagle`, `WallE256`, `Kirito`). No té sentit limitar-se a
embolicar-la en `_()` sense abans reescriure'n el contingut perquè parli d'aquest institut i
d'aquest jutge, no del DMOJ original.

**Per fer-ho**: reescriure el contingut de la pàgina (en català, com a idioma font) amb informació
real d'aquest desplegament, i llavors sí, embolicar-lo en `_()` per als altres idiomes actius.

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

## 7. Checker Mongo: sense límit de temps dur per consulta

**Detectat:** 2026-08-16, en construir el checker Mongo (`dmoj/checkers/mongo.py`, vegeu
`docs/05-sistemes-mecanics/5.8-checker-mongo.md`).

El checker SQL talla una consulta patològica a mig fer amb `sqlite3`'s `set_progress_handler`
(`_QUERY_TIME_BUDGET_SECONDS`, 5 segons). `mongomock` no té cap equivalent net per interrompre una
operació ja en marxa. Decisió conscient de no implementar-hi res en aquesta primera versió. Des de
2026-08-16 el checker també admet `aggregate` (vegeu `CANVIS_I_MILLORES.md`, entrada #27), cosa que
eixampla una mica el risc real (una pipeline amb `$lookup` mal dissenyada, o sobre una col·lecció
gran, podria trigar) —però les bases de dades d'exemple són petites i les pipelines les escriu un
professor a mà, així que el risc es manté baix a la pràctica.

**Per fer-ho, si mai cal:** executar la crida Mongo en un fil a part i fer-hi `join(timeout=...)`,
matant/ignorant el resultat si es passa del límit (amb cura: `mongomock` no és necessàriament
thread-safe per a escriptures concurrents sobre el mateix client, així que caldria un client nou
per intent, no compartir-ne un entre el fil principal i el fil vigilat).

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
