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
