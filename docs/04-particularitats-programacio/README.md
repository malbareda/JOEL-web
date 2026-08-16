# 4. Particularitats de la programació del JOEL

> Autor d'aquesta documentació: **Edgar**

Aquesta secció recull convencions, paranys i decisions de disseny que no són òbvies llegint el codi
per sobre —el tipus de coses que normalment s'aprenen a cops, i que val la pena tenir escrites
perquè no calgui redescobrir-les.

## Dos motors de plantilles conviuen al mateix projecte

`dmoj/settings.py` registra **dos** backends de plantilles alhora:

1. **`django_jinja` (Jinja2)** —renderitza gairebé tot el que veu un usuari (tot el que és a
   `templates/` excepte els camins que comencen per `admin/`).
2. **Django Template Language (DTL)**, estàndard —només per al propi admin de Django i qualsevol
   plantilla d'una app de tercers que vingui ja escrita en DTL.

Això té conseqüències pràctiques directes:

- La internacionalització a les plantilles Jinja2 és `{{ _('un text') }}`, **no** `{% trans "un
  text" %}` (això és una etiqueta exclusiva de DTL i no funciona sota Jinja2).
- **`{% include "plantilla.html" %}` no admet la sintaxi `with variable=valor` de Django** sota
  Jinja2 —l'`include` de Jinja2 no accepta arguments amb nom d'aquesta manera. **Aquest error
  concret es va patir i corregir durant aquesta mateixa sessió**, en construir la funcionalitat de
  "problemes guiats": una crida `{% include ... with x=y %}` no passava la variable extra
  silenciosament. Si un fragment necessita dades que no són ja al context, cal assegurar que hi
  siguin abans de la crida (o fer servir un macro/`import` en lloc d'`include`), mai la sintaxi
  `with`.
- `{% csrf_token %}` continua funcionant igual (el propi `django_jinja` en fa un cas especial).
- `trim_blocks`/`lstrip_blocks` estan activats: les etiquetes de bloc (`{% if %}`, `{% for %}`)
  "es mengen" el salt de línia posterior i els espais anteriors —permet fer servir blocs amb
  llibertat sense que apareguin línies en blanc espúries a l'HTML.
- **Les plantilles de l'admin de Django fan servir DTL, no Jinja2** —si es personalitza una
  plantilla de l'admin, cal recordar que s'hi torna a fer servir `{% trans %}`/`{% load %}` i la
  resta de la sintaxi DTL.

### El parany silenciós: accés a un atribut trencat

Django Templates, si un accés a un atribut falla (relació que no existeix, mètode que llença una
excepció), ho resol silenciosament com a cadena buida. **Jinja2 no ho fa: llença l'excepció tal
qual.** Això va ser directament rellevant per a la funcionalitat de "problemes guiats": `problem.
guide` és una relació `OneToOneField` inversa —si no existeix cap `Guide` per aquest problema,
accedir-hi llença `Guide.DoesNotExist`, i Jinja2 **no** ho amaga com faria DTL. La solució adoptada
és fer que la pròpia consulta de la vista anoti un booleà segur
(`.annotate(has_guide=Exists(Guide.objects.filter(problem_id=OuterRef('pk'))))`) i que la plantilla
comprovi sempre `problem.has_guide`, mai `problem.guide` directament en un context de llista.

### `DEBUG=False` no recarrega plantilles soles

Amb `DEBUG=False` (producció), Jinja2 no torna a llegir el codi font d'una plantilla que ha canviat
al disc mentre el procés uwsgi ja porta una estona funcionant —es queda amb la versió compilada en
memòria. **Després d'editar qualsevol plantilla `.html` en producció cal reiniciar el procés web**
(`supervisorctl restart site`, o `restart all`) perquè el canvi es vegi; editar el fitxer sol no
n'hi ha prou.

## Dos sistemes de traducció, per raons diferents

- **`gettext`/`gettext_lazy as _`** (domini `django`, l'estàndard): per a tot el text d'interfície
  que s'escriu al codi font o directament a les plantilles.
- **`user_gettext`/`user_trans`** (`judge/user_translations.py`, domini propi `dmoj-user`,
  compilat amb una comanda pròpia `makedmojmessages` en lloc de l'estàndard `makemessages`): per a
  **contingut curt introduït per professors/administradors des de fora del codi font**, com ara
  `Problem`/`ProblemType`/`ProblemGroup.full_name` —el nom d'una categoria de problemes es pot
  traduir per la comunitat sense necessitat de tocar cap fitxer de codi. Regla pràctica: `_()` per
  a la interfície que s'escriu al codi; `user_gettext`/`user_trans` només per a etiquetes curtes
  introduïdes dinàmicament per professors.

## Paranys de MariaDB/MySQL, patits en aquesta mateixa sessió

### Una columna `NOT NULL` sense valor per defecte trenca `bulk_create` en silenci

El camp `extended_feedback` de `SubmissionTestCase` era `LONGTEXT NOT NULL` sense cap `DEFAULT` a
nivell de base de dades (MySQL/MariaDB no permet posar un `DEFAULT` a una columna `TEXT`/`BLOB`).
En eliminar el camp del model de Django, l'`INSERT` generat per `bulk_create(...)` (a
`judge/bridge/judge_handler.py`) va deixar d'incloure aquesta columna —i el mode estricte de
MariaDB va rebutjar **tot l'`INSERT`** perquè faltava un valor per a una columna obligatòria sense
valor per defecte. La fallada va ser silenciosa des del punt de vista de Django: **cap fila de
`SubmissionTestCase` s'arribava mai a desar**, cosa que en cascada feia que el bucle
d'agregació final (`on_grading_end`) mai trobés cap cas i totes les submissions es quedessin al seu
estat "buit" inicial.

**Lliçó**: abans d'eliminar un camp d'un model de Django, comprovar si la columna corresponent a la
base de dades encara té una restricció `NOT NULL` sense valor per defecte —cal relaxar-la o
eliminar-la amb una migració a la mateixa vegada, mai només treure-la del model.

### `UNIQUE`/`unique_together` tracta diversos `NULL` com a diferents

Patit amb `GuideTranslation.unique_together = ('problem', 'language', 'runtime')`: dues files amb
el mateix `problem`+`language` però totes dues amb `runtime=NULL` **no** xoquen a nivell de base de
dades, encara que semànticament siguin duplicades —MySQL/MariaDB (a diferència d'altres motors)
tracta cada `NULL` com un valor diferent als efectes d'un índex únic. La solució va ser afegir un
`clean()` explícit al model que fa aquesta comprovació en Python i llença `ValidationError`
manualment.

**Lliçó**: qualsevol `unique_together`/`UniqueConstraint` que inclogui un camp que admeti `NULL`
necessita una comprovació d'aplicació (`clean()`) pròpia si es vol que els duplicats amb `NULL`
també quedin bloquejats —no es pot confiar només en la restricció de la base de dades.

## `django-reversion`: historial d'edicions a l'admin

Registrat explícitament a `judge/models/__init__.py`, amb estils diferents segons el model:

```python
revisions.register(Profile, exclude=['points', 'last_access', 'ip', 'rating'])
revisions.register(Problem, follow=['language_limits'])
revisions.register(Contest, follow=['contest_problems'])
revisions.register(Organization)
revisions.register(BlogPost)
revisions.register(Solution)
revisions.register(Judge, fields=['name', 'created', 'auth_key', 'description'])
revisions.register(Comment, fields=['author', 'time', 'page', 'score', 'body', 'hidden', 'parent'])
```

- `exclude=[...]`: es guarda tot **menys** els camps que canvien constantment (els punts d'un
  alumne canvien a cada submissió; guardar-ne l'historial complet inundaria l'historial de
  versions sense aportar res útil).
- `fields=[...]`: només es vigila una llista concreta de camps.
- `follow=[...]`: una "versió" també arrossega objectes relacionats (una versió d'un `Contest`
  inclou també l'estat dels seus `ContestProblem`), de manera que una sola foto capturi tot el graf
  d'objectes relacionat.

Perquè el botó "Historial" aparegui de veritat a l'admin, el `ModelAdmin` corresponent ha
d'heretar de `reversion.admin.VersionAdmin` —registrar el model sol amb `revisions.register()` no
n'hi ha prou.

## `request.profile`, no `request.user.profile`

`Profile` és un model amb relació un a un amb el `User` de Django (`user =
models.OneToOneField(User)`), on hi viu tot el que és específic del jutge (punts, *rating*,
llenguatge preferit, tema, etc.) i que no té sentit posar al model d'usuari estàndard.

Un middleware personalitzat (`judge.middleware.DMOJLoginMiddleware`) posa
`request.profile = request.user.profile` (o `None` per a un visitant anònim) a cada petició; un
segon middleware (`DMOJImpersonationMiddleware`) el torna a sobreescriure quan un administrador
està "suplantant" un altre usuari. **Convenció d'aquest projecte: fer servir sempre
`request.profile`, mai `request.user.profile` directament** —és segur per a usuaris anònims (no
llença cap excepció), no repeteix la consulta a la base de dades, i reflecteix correctament l'estat
de suplantació.

## El full d'estils: compilat, mai editat directament

`resources/*.scss` és el codi font; `make_style.sh` el compila (`sass` → `sass_processed/`, després
`postcss --use autoprefixer` cap a `resources/*.css`). **Els cinc fitxers `.css` resultants estan
exclosos del control de versions** (`.gitignore`) i cal tornar-los a generar en local després de
clonar el projecte o de tocar cap `.scss`. Hi ha un avís cosmètic conegut i inofensiu: `resources/
style.css:150` conté `--background_input: ##3A3A3A;` (doble `#`) —`sass` avisa d'això a cada
compilació, però no trenca res ni cal perseguir-ho.

## Petits recordatoris pràctics

- **Cal activar l'entorn virtual** abans d'executar `manage.py` o el dimoni del jutge: les
  llibreries de Python només estan instal·lades dins d'un `venv`, no al sistema.
- Des d'una plantilla Jinja2, es pot cridar un mètode de la **vista** amb `view.el_meu_metode(...)`;
  un mètode d'un **model** es crida directament sobre l'objecte (`membre.calculate_points()`), sense
  passar per `view` —una petita inconsistència del model de plantilles que val la pena recordar.
- `python3 manage.py check` detecta errors de configuració (imports que falten, camps de model mal
  definits) sense necessitat d'arribar a tocar cap URL —útil com a primera comprovació abans de
  reiniciar res.
- Reconstrucció completa quan alguna cosa sembla molt encallada: `./make_style.sh` →
  `manage.py collectstatic` → `manage.py compilemessages` → `manage.py compilejsi18n` →
  `manage.py migrate` → `manage.py check`.
