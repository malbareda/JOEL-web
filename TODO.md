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

## 4. Forat de permisos a `ProblemsByOrganization`

**Detectat:** durant la mateixa documentació (secció 2.5).

La vista que mostra la graella de "qui ha resolt/intentat cada problema" d'una organització sencera
no comprova cap permís ni pertinença — qualsevol visitant que endevini l'identificador numèric d'una
organització en pot veure el progrés complet dels seus membres. Revisar si cal restringir-ho.
