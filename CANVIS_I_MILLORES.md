# Canvis i millores

Aquest document recull, de manera cronològica, tots els canvis tècnics rellevants fets al servidor i al codi del JODER (Jutge Online Destinat a Ensenyament amb Retroacció). Per a cada canvi es documenta: com estava abans, què es va decidir fer, per què, i quin és el resultat final. Pensat com a memòria tècnica del curs.

---

## 2026-08-15

### 1. Detecció de disc pràcticament ple i identificació de la causa

**Abans:**
El disc principal del servidor (`/dev/sda1`, 155G) estava al 99% d'ús, amb només 2.5G lliures. No hi havia cap monitorització ni alerta activa sobre això.

**Decisió:**
Es va fer una anàlisi amb `du -xh --max-depth=1` a `/` i després a `/var`, que va revelar que el directori `/var/backup/db` ocupava 124G, pràcticament tot l'espai consumit del disc.

**Per què:**
Dins de `/var/backup/db` hi havia 136 fitxers `db_backup_DD_Mon_AAAA_HHMM.sql.gz` (còpies de seguretat diàries de la base de dades MySQL `dmoj`, generades per un cron de `root` que executa `/var/backup/db/script.sh` cada dia a la 1:00 AM), acumulats des de gener de 2025 sense cap política de rotació ni esborrat. Cada còpia pesa ~1.1G en comprimit.

**Resultat:**
Es va identificar clarament l'origen del problema (còpies de seguretat sense rotació). Es va decidir com a solució pujar-les a Google Drive (veure canvi #2) i, en una fase posterior, aplicar una política de retenció local per alliberar espai en disc definitivament.

---

### 2. Automatització de la pujada de còpies de seguretat a Google Drive

**Abans:**
Les còpies de seguretat de la base de dades només es desaven localment a `/var/backup/db`, sense cap còpia externa. Si el disc del servidor fallés, es perdrien totes les còpies.

**Decisió:**
S'ha configurat `rclone` (v1.75.0, instal·lat via l'script oficial `https://rclone.org/install.sh`, ja que la versió d'`apt` era la 1.50.2 del 2019) per sincronitzar automàticament els fitxers de còpia de seguretat cap a una carpeta "Backups" a Google Drive, dins del Google Workspace `ies-sabadell.cat`.

Passos tècnics realitzats:
1. Creació d'un compte de servei (`service account`) a Google Cloud Console, dins d'un nou projecte GCP anomenat `joder-sabadell`, amb l'API de Google Drive activada. El compte de servei és `joder-backend@joder-sabadell.iam.gserviceaccount.com`.
2. Descàrrega de la clau JSON del compte de servei. **Es va moure fora del repositori git**, de `educational-online-judge/joder-sabadell-084b2b904b72.json` (arrel del projecte, on s'havia baixat inicialment) cap a `/home/ubuntu/.secrets/joder-sabadell-084b2b904b72.json`, amb permisos restringits (`chmod 700` al directori, `chmod 600` al fitxer). S'ha afegit el patró `joder-sabadell-*.json` al `.gitignore` per evitar que aquest tipus de credencial es pugui arribar a pujar mai al repositori.
3. **Primer intent fallit:** es va compartir una carpeta normal de Google Drive (propietat de `joder@ies-sabadell.cat`) amb el correu del compte de servei com a Editor. En provar de pujar-hi un fitxer, Google Drive va retornar l'error `403 storageQuotaExceeded — Service Accounts do not have storage quota`. Això és una limitació coneguda de Google: un compte de servei no té quota d'emmagatzematge pròpia i per tant no pot ser propietari de fitxers, ni tan sols en una carpeta que se li ha compartit.
4. **Solució aplicada — Domain-Wide Delegation:** en lloc de compartir una carpeta amb el compte de servei, es va configurar la delegació d'autoritat a tot el domini (*domain-wide delegation*), que permet que el compte de servei actuï *en nom de* `joder@ies-sabadell.cat` directament:
   - A Google Cloud Console, a la fitxa del compte de servei, es va activar "domain-wide delegation" i se'n va obtenir el *Client ID* numèric.
   - A l'Admin Console de Google Workspace (`admin.google.com` → Seguretat → Controls d'API → Delegació a tot el domini), es va autoritzar aquest *Client ID* amb l'abast (*scope*) `https://www.googleapis.com/auth/drive`.
   - També es va intentar afegir el compte de servei com a membre d'una Unitat compartida (*Shared Drive*), però la política de l'organització només permet membres amb comptes del domini `ies-sabadell.cat`, i el domini del compte de servei (`joder-sabadell.iam.gserviceaccount.com`) es considera extern — per això la delegació de domini (que no requereix afegir cap "membre") va ser la via definitiva.
5. Es va reconfigurar el remot d'`rclone` (`gdrive-backup:`) amb el paràmetre `impersonate = joder@ies-sabadell.cat`, de manera que totes les crides a l'API de Drive s'executen amb la identitat d'aquest compte, sense problemes de quota.
6. Es va verificar l'accés amb una pujada i esborrat de prova (`rclone-test.txt`), confirmant que funcionava correctament abans de fer-hi res real.
7. Es va crear l'script `/home/ubuntu/rclone-backup/upload.sh`, que executa:
   ```
   rclone copy /var/backup/db gdrive-backup:Backups --include "db_backup_*.sql.gz" --log-file=... --log-level INFO
   ```
   Aquest script s'executa com a usuari `ubuntu` (no `root`), ja que `ubuntu` té permisos de lectura sobre `/var/backup/db` (fitxers amb permisos `644`) però no d'escriptura al directori, cosa que de moment és suficient perquè només es puja, no s'esborra res localment.
8. S'ha afegit una entrada al crontab de l'usuari `ubuntu`:
   ```
   30 1 * * * /home/ubuntu/rclone-backup/upload.sh
   ```
   Que s'executa cada dia a la 1:30 AM, 30 minuts després que el cron de `root` generi la còpia diària (1:00 AM), donant marge perquè el `mysqldump` acabi.
9. S'ha llançat una càrrega inicial (*backfill*) de totes les 135 còpies existents (~124G) cap a Google Drive, en segon pla. **Completada amb èxit**: 135/135 fitxers (123.699 GiB) pujats correctament en 26m 53s (~60 MiB/s de mitjana).

**Per què:**
- Per tenir una còpia de seguretat externa (fora del servidor) de la base de dades, evitant dependre únicament del disc local.
- Per poder, en una segona fase, aplicar una política de retenció local (esborrar còpies antigues del servidor) sense perdre l'històric, ja que quedarà conservat a Drive.
- S'ha triat domain-wide delegation en lloc de compartir carpetes perquè és l'única via compatible amb la política de seguretat del Workspace (que restringeix la compartició a comptes del domini `ies-sabadell.cat`) i, alhora, evita el problema de quota dels comptes de servei.

**Resultat:**
- `rclone` puja automàticament cada nova còpia de seguretat de la base de dades a la carpeta "Backups" de Google Drive de `joder@ies-sabadell.cat`, sense intervenció manual.
- `rclone copy` només transfereix fitxers nous o modificats (per mida/data), de manera que reexecutar l'script cada dia és barat i idempotent.
- **Pendent (decidit, no executat encara):** un cop confirmat que tot el backfill inicial i el procés diari funcionen correctament, s'aplicarà una política de retenció local: conservar només els últims 14 dies de còpies al servidor, més una còpia del dia 1 de cadascun dels últims 3 mesos, esborrant la resta un cop confirmada la pujada a Drive. Això alliberarà la major part dels 124G actualment ocupats.

---

### 3. Migració de l'enviament de correu electrònic: de Gmail SMTP personal a Gmail API amb delegació de domini

**Abans:**
El JODER enviava tots els correus (notificacions, avisos d'error, etc.) mitjançant el backend SMTP de Django (`django.core.mail.backends.smtp.EmailBackend`), autenticant-se a `smtp.gmail.com` amb un compte de Gmail **personal** (`dm.albareda@gmail.com`) i una contrasenya d'aplicació (*app password*), guardada **en text pla** dins de `dmoj/local_settings.py`. Això s'havia arribat a fer com a solució temporal arran d'un tall anterior en la delegació de domini que hi havia configurada prèviament.

**Decisió:**
S'ha implementat un backend de correu personalitzat per a Django que envia els missatges a través de la **Gmail API**, autenticant-se amb el mateix compte de servei ja creat per a les còpies de seguretat (`joder-backend@joder-sabadell.iam.gserviceaccount.com`), utilitzant domain-wide delegation per actuar com a `joder@ies-sabadell.cat`.

Passos tècnics:
1. Activació de l'API de Gmail al projecte GCP `joder-sabadell` (Cloud Console → APIs & Services → Library → Gmail API → Enable).
2. Ampliació de l'autorització de domain-wide delegation ja existent (mateix *Client ID* que per a Drive), afegint-hi l'abast `https://www.googleapis.com/auth/gmail.send` a més del de Drive.
3. Instal·lació de les llibreries `google-auth`, `google-api-python-client` i `google-auth-httplib2` a l'entorn virtual del projecte (`/home/ubuntu/dmojsite`), i afegides a `requirements.txt`.
4. **Incident col·lateral detectat i resolt:** instal·lar `google-auth` va actualitzar `cryptography` de la 3.1 a la 47.0.0 (dependència directa de `google-auth`). Això va trencar `pyOpenSSL` 19.1.0, que ja estava instal·lat a l'entorn (usat únicament per la llibreria `webauthn`, amb una dependència molt laxa `>=16.0.0`). Com que `pip` mateix (via el seu `requests`/`urllib3` vendoritzat) intenta importar `pyOpenSSL` a l'arrencada, **`pip` va quedar completament trencat** per a qualsevol ordre. Es va solucionar:
   - Movent manualment (sense pip, per fitxers) els paquets `OpenSSL` i `pyOpenSSL-19.1.0.dist-info` fora del `site-packages`, per restaurar `pip`.
   - Instal·lant amb `pip` una versió moderna de `pyOpenSSL` (26.2.0), compatible amb `cryptography` 47.
   - Verificant amb `pip check` i imports manuals que `pip`, `webauthn` i les noves llibreries de Google conviuen sense conflictes.
5. Creació del backend personalitzat `dmoj/gmail_api_backend.py` (classe `GmailAPIBackend`, que hereta de `django.core.mail.backends.base.BaseEmailBackend`). Construeix el missatge MIME amb el mètode natiu de Django (`message.message()`), el codifica en `base64url` i el sends via `service.users().messages().send(userId='me', body={'raw': raw})`.
6. Actualització de `dmoj/local_settings.py`:
   - `EMAIL_BACKEND = 'dmoj.gmail_api_backend.GmailAPIBackend'`
   - `GMAIL_API_SERVICE_ACCOUNT_FILE = '/home/ubuntu/.secrets/joder-sabadell-084b2b904b72.json'`
   - `GMAIL_API_SENDER = 'joder@ies-sabadell.cat'`
   - `DEFAULT_FROM_EMAIL = 'JODER <joder@ies-sabadell.cat>'`
   - La configuració SMTP anterior (amb la contrasenya d'aplicació) s'ha deixat comentada com a referència, no esborrada.
7. Prova real d'enviament (`django.core.mail.send_mail` des de `manage.py shell`) a `joder@ies-sabadell.cat`, confirmada com a rebuda correctament, amb remitent `JODER <joder@ies-sabadell.cat>`.

**Per què:**
- Per deixar d'utilitzar un compte de Gmail personal per a l'enviament de correus institucionals del JODER, tant per professionalitat (el remitent ha de ser `joder@ies-sabadell.cat`, no un Gmail personal) com per seguretat (la contrasenya d'aplicació estava en text pla al codi, encara que `local_settings.py` no es puja al repositori).
- S'ha triat la Gmail API amb domain-wide delegation (en lloc de, per exemple, tornar a SMTP amb un altre compte) perquè reutilitza la mateixa infraestructura d'autenticació (compte de servei + delegació) ja creada per a les còpies de seguretat, evitant haver de gestionar contrasenyes d'aplicació addicionals i sent el mètode recomanat per Google per a l'enviament automatitzat en nom d'un compte de Workspace.

**Resultat:**
- El JODER envia ara tot el correu com a `joder@ies-sabadell.cat`, autenticant-se mitjançant OAuth2/domain-wide delegation, sense contrasenyes ni secrets SMTP.
- S'ha eliminat la dependència d'un compte de Gmail personal per al funcionament del servidor.
- **Pendent:** revocar manualment la contrasenya d'aplicació antiga (`dm.albareda@gmail.com`) des de la configuració de seguretat d'aquell compte, ja que ha quedat sense ús però encara no s'ha revocat.
- Efecte secundari beneficiós: l'entorn virtual del projecte ha quedat amb `cryptography` i `pyOpenSSL` actualitzats a versions modernes i mútuament compatibles (abans hi havia un `cryptography` 3.1 del 2020 i un `pyOpenSSL` 19.1.0 del 2019).

---

### 4. Registre automàtic de converses amb Claude Code (`CONVERSATION_LOG.md`)

**Abans:**
No hi havia cap registre persistent de les converses amb Claude Code dins del repositori; només quedava constància dels canvis de codi/servidor resumits a `CANVIS_I_MILLORES.md`.

**Decisió:**
S'han configurat dos hooks de Claude Code, a `.claude/settings.local.json` (configuració personal, no es puja al repositori — ja consta al `.gitignore` global de l'usuari):
- `UserPromptSubmit` executa `.claude/hooks/log-user-prompt.sh`, que registra el text exacte de cada missatge de l'usuari.
- `Stop` executa `.claude/hooks/log-assistant-response.sh`, que llegeix la transcripció JSONL de la sessió i n'extreu el text final de la resposta de Claude per a aquell torn.

Ambdós scripts afegeixen l'entrada a `CONVERSATION_LOG.md` (arrel del projecte) amb un timestamp, en el format `## [YYYY-MM-DD HH:MM:SS] Usuari` / `Claude`. Com que `jq` no està instal·lat a la màquina, els scripts fan servir `python3` per parsejar el JSON d'entrada dels hooks i la transcripció.

**Per què:**
Petició explícita per tenir un historial complet i cronològic de totes les converses, per sessió, sense haver-ho de fer manualment. Calia implementar-ho amb hooks (no només amb memòria) perquè cap mecanisme de memòria pot executar-se automàticament en cada torn de conversa.

**Resultat:**
Cada missatge nou (usuari i Claude) queda registrat automàticament a `CONVERSATION_LOG.md`, en qualsevol sessió futura d'aquest repositori en aquesta màquina.

---

### 5. Neteja de còpies de seguretat antigues a `/var/backup/db`

**Abans:**
El directori `/var/backup/db` acumulava 136 fitxers de còpia de seguretat (`db_backup_*.sql.gz`) des d'agost del 2023, ocupant ~129 GB, sense cap política de retenció aplicada.

**Decisió:**
S'han esborrat (amb `sudo rm`) tots els fitxers excepte:
- Els de les còpies diàries dels últims 14 dies (2–15 d'agost de 2026).
- Els snapshots mensuals de l'1 de juny, l'1 de juliol i l'1 d'agost de 2026.

En total s'han esborrat 118 fitxers (113.53 GB alliberats), deixant-ne 17.

**Per què:**
Petició explícita de l'usuari per alliberar espai de disc, mantenint una política de retenció concreta (14 dies + últims 3 mesos en punts mensuals). Relacionat amb la detecció prèvia de disc pràcticament ple (entrada #1 d'aquesta mateixa data).

**Resultat:**
`/var/backup/db` ha passat de ~129 GB a ~18 GB, mantenint els 17 fitxers previstos. La còpia de seguretat diària (cron `30 1 * * * /home/ubuntu/rclone-backup/upload.sh`) segueix intacta i continuarà generant-ne de noves cada dia.

---

### 6. Bug fix: error 404 en cercar un usuari a `/users`

**Abans:**
A la pàgina `/users`, en cercar un usuari pel quadre de cerca (widget select2 "Search by handle..."), la pàgina donava sempre error 404 amb el missatge "No se pudo encontrar la página `/users/find`".

**Decisió:**
S'ha localitzat un desajust entre el nom del paràmetre GET que envia realment el formulari i el que espera la vista:
- El JS de `templates/user/base-users.html` substitueix el camp de cerca per un `<select>` (select2) amb `name: 'handle'`, de manera que en seleccionar un usuari el formulari envia `GET /users/find?handle=<usuari>`.
- La vista `judge/views/user.py` (`user_ranking_redirect`) esperava, en canvi, `request.GET['search']`, provocant sempre un `KeyError` → `Http404()`.

Aquest desajust venia del commit `10eafddc4` ("joder 1.37", gener de 2024), que va canviar la clau llegida per la vista de `'handle'` a `'search'` sense actualitzar el JS corresponent (que continuava enviant `handle`).

**Fix aplicat:** una sola línia, `judge/views/user.py:790`, tornant a `username = request.GET['handle']` (no hi havia cap altre lloc del codi que depengués del nom `'search'`). Recàrrega en calent d'uWSGI (`kill -HUP $(cat /home/ubuntu/dmoj-site.pid)`) per aplicar el canvi a producció sense tallar sessions actives.

**Per què:**
Petició explícita de l'usuari en detectar el 404 en producció. S'ha triat revertir la vista (en lloc de canviar el JS) perquè és el canvi mínim i el que reverteix exactament la regressió introduïda pel commit del gener de 2024.

**Resultat:**
Verificat en viu contra `https://www.jo-el.es`: `GET /users/find?handle=admin` retorna ara `200` i redirigeix correctament a `/users/?page=22#!admin`; amb l'antic `search=admin` es reprodueix el 404 (confirmant el diagnòstic).

---

### 7. `extended_feedback` de `SubmissionTestCase`: de columna de BD a fitxers al disc

**Abans:**
`SubmissionTestCase.extended_feedback` era un `TextField` sense límit de mida a MySQL, escrit per cada testcase de cada submissió (`judge/bridge/judge_handler.py`, en `on_test_case`). Anàlisi de la BD (15/08/2026): aquesta única columna ocupava **4.42 GB de 5.11 GB de BD total (86.6%)**; el 97.6% d'aquest pes venia de només 4.270 files (de 886.293) amb valors de fins a 16 MB — sortides d'entrada/sortida legítimament grans d'alguns problemes, no un bug. Només el 9% de les files amb `extended_feedback` no buit arribaven mai a mostrar-se a un alumne (via el sistema de pistes), tot i que els profes poden consultar-ho sempre (`is_evaluable_by`), independentment de `allowed_tips`.

**Decisió:**
1. Nou emmagatzematge en fitxers, seguint el mateix patró que `zipfile`/`generator`/`sql_db` de `ProblemData`: `judge/utils/submission_feedback.py` (classe `SubmissionFeedbackStorage`, arrel `/judge_submission_feedback`, fora del repositori i de la BD), amb els fitxers repartits en subcarpetes (`submission_id % 1000`) per no tenir ~900.000 fitxers en un sol directori.
2. Al model (`judge/models/submission.py`): el `TextField extended_feedback` es substitueix per `FileField extended_feedback_file`, i s'afegeix una `@cached_property extended_feedback` que llegeix el fitxer i en cacheja el contingut per petició — **cap plantilla ni vista ha calgut tocar-les** (`templates/submission/status-testcases.html` segueix fent `case.extended_feedback.split(...)` exactament igual).
3. `judge/bridge/judge_handler.py` (`on_test_case`): en lloc d'assignar el text directament al camp, l'escriu a `submission_feedback_storage` i guarda només el nom de fitxer (`bulk_create` no crida `.save()` sobre `FieldFile`, així que el fitxer s'escriu manualment abans).
4. Migració de dades: migració `0137_submissiontestcase_extended_feedback_file` (només `AddField`, additiva i instantània) + comanda `manage.py migrate_extended_feedback_to_files` (via SQL cru, per lots de 2000, idempotent) que ha traslladat totes les 393.705 files amb contingut existent als fitxers corresponents. **No s'ha filtrat per `allowed_tips`**: com que els profes poden consultar el feedback de qualsevol problema, s'ha migrat tot.
5. Desplegament: reinici de `bridged` i `site` via `supervisorctl restart` per carregar el codi nou. Verificat amb Django test client (usuari admin) que `/submission/6` (problema amb pista i `checker=linecount`) renderitza correctament el bloc `case-ext-feedback` sense error.

**Per què:**
Petició explícita de l'usuari arran de detectar que una sola columna ocupava la major part de la BD. Es descarta truncar o limitar la mida del camp (les sortides grans són legítimes, no un error) i es descarta filtrar per `allowed_tips` (els profes necessiten veure-ho sempre). La solució és moure la ubicació de l'emmagatzematge, no canviar què es guarda.

**Resultat:**
`/judge_submission_feedback` ocupa ara 5.9 GB en disc (fora de la BD). **Pendent, com a pas final separat i encara per confirmar**: una segona migració (`0138_remove_submissiontestcase_extended_feedback`) que farà el `DROP COLUMN extended_feedback` a MySQL/MariaDB per recuperar físicament l'espai de la BD — es farà només després de validar el sistema nou en producció durant un temps.

---

### 8. Incident: totes les submissions sortien amb estat `SC` després del desplegament de l'entrada #7

**Abans (símptoma):** just després de reiniciar `bridged`/`site` (entrada #7), totes les submissions noves (343052, 343053, 343054, totes de proves de l'usuari) sortien amb resultat `SC` (Short Circuited) encara que el jutge real corregia correctament (confirmat als logs del jutge) i el problema no té batches curtcircuitables.

**Causa (`/tmp/dasdas.log`):**
```
django.db.utils.IntegrityError: (1364, "Field 'extended_feedback' doesn't have a default value")
```
a `judge_handler.py` → `SubmissionTestCase.objects.bulk_create(...)`. La columna vella `extended_feedback` a MariaDB era `LONGTEXT NOT NULL` **sense valor per defecte** (MySQL/MariaDB no permet `DEFAULT` en columnes `TEXT`/`BLOB`). En treure el camp del model (entrada #7), l'`INSERT` generat per `bulk_create` ja no l'incloïa, i el mode estricte de MariaDB rebutjava la inserció sencera → **cap `SubmissionTestCase` es guardava per a cap submissió**. `judge_handler.py.on_grading_end` calcula l'estat final fent `status_codes.index(case.status)` sobre `SubmissionTestCase.objects.filter(submission=submission)`; amb zero files, el bucle no s'executa mai i `status` es queda al seu valor inicial (`0` → `'SC'`), d'aquí el fals `SC` a totes les submissions.

**Fix:** `ALTER TABLE judge_submissiontestcase MODIFY extended_feedback longtext NULL;` — fa la columna vella nul·lable perquè l'`INSERT` sense aquest camp torni a ser vàlid (no s'ha esborrat la columna encara, això és independent del `DROP COLUMN` pendent de l'entrada #7).

**Abast de l'incident:** només 3 submissions afectades (343052, 343053, 343054), totes de proves pròpies de l'usuari entre les 20:05 i les 20:25 — **cap alumne real afectat**. Les 3 s'han tornat a corregir (`judge_submission(s, rejudge=True)`) i ja mostren resultat real (`WA`, amb testcases) en lloc de `SC`.

**Per què:** regressió pròpia introduïda a l'entrada #7, no detectada als tests previs a l'desplegament perquè l'`ALTER`/comprovació de restriccions de la columna vella no es va verificar explícitament abans de reiniciar en producció.

**Resultat:** grading en viu funcionant correctament de nou, verificat sense errors nous a `/tmp/dasdas.log` després del fix.

---

### 9. Refactor complet del sistema de pistes: del frontend al backend, revelat instantani per AJAX, i referència a pistes ja usades

**Abans:**
Tota la lògica del sistema de pistes (parsing del blob `extended_feedback`, separat per caràcters unicode `✙/✠/✡`) vivia a `templates/submission/status-testcases.html`, duplicada gairebé íntegrament dues vegades (bloc alumne + bloc profe), amb ~230 línies de `.split()`/`divisibleby`/slicing fetes en Jinja2 a cada render. Demanar una pista feia un `<form method="post">` que redirigia a pàgina sencera (`flag_submission` retornava sempre `HttpResponseRedirect`), sense cap comprovació atòmica (possible race condition en clics concurrents), i sense cap manera de veure, en una submissió posterior del mateix problema, que ja s'havia demanat una pista en un cas concret.

**Decisió:**
1. **Nou mòdul `judge/utils/hints.py`**: totes les funcions de parsing (`parse_rstripped`, `parse_linecount_single`, `parse_linecount_all`, `parse_generic_teacher`) traslladades de Jinja2 a Python pur, com a funcions independents del model. **Verificades una a una contra la lògica Jinja2 original**, comparant l'output amb dades reals de producció (un exemple de cada `caseformat`: standard/indiv/multicas/stop) abans de substituir res — totes coincideixen exactament, excepte una neteja deliberada d'una fila buida espúria causada per un separador final (`parse_generic_teacher`).
2. **`judge/views/submission.py`**: nova funció `build_case_hint(...)` que centralitza tota la decisió de què mostrar (alumne/profe, segons `checker`/`case.flag`/`is_evaluable_by`) i retorna un diccionari estructurat. `SubmissionStatus.get_context_data` calcula aquest `case.hint` per a cada testcase un sol cop per render (no dins la plantilla), i també `case.hint_reference`: l'`id` de la submissió MÉS ANTIGA on aquell mateix `case` (mateix problema, mateix número de cas) ja va tenir la pista revelada per aquest usuari (via una única consulta agregada amb `Min('submission_id')`), perquè es pugui mostrar un enllaç "ja vas demanar una pista aquí" en comptes de tornar-la a mostrar. **Els comptadors de pistes (`allowed_tips`) es mantenen exactament amb la mateixa semàntica d'abans** (submissions amb `flag=True`), sense canvis de comportament — decisió explícita de l'usuari.
3. **`flag_submission` convertida a AJAX**: ara respon amb JSON (`{success, html}`) quan la petició porta `X-Requested-With: XMLHttpRequest`, embolicada en `transaction.atomic()` + `select_for_update()` sobre la fila de `Submission` (evita la race condition de l'original). El fragment HTML retornat es renderitza amb el mateix `templates/submission/hint-fragment.html` que fa servir la pàgina normal, així no hi ha cap lògica de presentació duplicada entre el render inicial i la resposta AJAX.
4. **Frontend simplificat**: `status-testcases.html` ha passat de ~230 línies de lògica a un simple `{% include "submission/hint-fragment.html" %}`; el botó "Help!" ara és un `<button>` amb un handler jQuery delegat (`$(document).off/on('click.hintRequest', ...)`, namespaced per no duplicar-se en cada refresc AJAX de la graella durant la correcció) que fa `$.post` i injecta l'HTML retornat directament, sense recarregar la pàgina.
5. **Disseny renovat i menys "constrenyit"**: el contingut de la pista ha passat de diversos `<td colspan="5">` estrets forçats dins la taula a un únic `<td colspan="99">` amb una targeta (`hint-card`) d'ample complet, amb més espaiat, seccions separades i una taula pròpia per als casos fallits (`resources/submission.scss`, compilat amb `make_style.sh`). Estil coherent amb els temes existents del lloc (variables CSS `--highlight_blue`, `--border_gray`, etc., no colors fixos).
6. Neteja de pas: eliminades les línies de debug actives al hot path (`sys.stderr.write("test\n")`, `print(...)` a cada render de `SubmissionStatus`), i reducció de 4 consultes de vots a 1 sola consulta agregada (`Sum`/`Case`/`When`).

**Per què:**
Petició explícita de l'usuari: unificar la lògica al backend (era "una part molt antiga i poc eficient"), fer el revelat de pistes instantani (AJAX) en lloc de recarregar la pàgina, i que una submissió futura del mateix problema mostri (amb un enllaç, no el contingut sencer) que ja s'havia demanat una pista en aquell cas — mantenint el comptador de pistes usades exactament igual que abans, tal com l'usuari va confirmar explícitament.

**Resultat:**
Verificat en viu (rejudge real de la submissió #10, petició AJAX real a `/submission/flag/<id>`, i render de pàgina sencera) sense cap error a `/tmp/dasdas.log` ni tracebacks. Provat amb èxit els 4 `caseformat` (standard/indiv/multicas/stop) i els 3 tipus de checker (rstripped/linecount/genèric per a profes).

**Nota (no arreglada, fora d'abast):** s'ha detectat que la traducció catalana de "Wrong Answers (only first 5)" al fitxer `locale/ca/LC_MESSAGES/django.po` té un caràcter corrupte (`nom�s` en lloc de `només`) — és un bug preexistent al `.po`, no introduït per aquest canvi (la cadena ja es feia servir igual al codi antic). Pendent d'arreglar si es vol.

---

### 10. Bug fix: els selectors de personalització del perfil no mostraven el valor actual

**Abans:**
A `/edit/profile/`, els selectors de color d'usuari, icona, tema web i font web sempre es mostraven buits (primera opció), encara que l'usuari ja tingués una preferència guardada — calia recordar què tenies triat abans de canviar-ho.

**Decisió:**
Aquests 4 camps (`user_color`, `preferred_icon`, `preferred_theme`, `preferred_font` a `judge/models/profile.py`) no formen part de `ProfileForm` (es gestionen a mà a `judge/views/user.py:596-600` via `request.POST.get(...)`), i a `templates/user/edit-profile.html` (línies ~301-339) es renderitzaven com a `<select>` fets a mà, amb bucles `{% for %}` sobre `colors`/`icons`/`themes`/`fonts` sense cap comparació contra el valor actual del perfil. S'ha afegit `{% if x.name == profile.preferred_x %}selected{% endif %}` (i `icon.logo_override_image == profile.preferred_icon` per a la icona, ja que és el valor que realment es guarda) a cadascuna de les 4 opcions.

**Per què:** petició explícita de l'usuari; incòmode haver d'endevinar la configuració actual cada cop que es vol canviar una preferència.

**Resultat:** verificat en viu contra `jo-el.es` (sessió real d'un usuari amb `user_color=CornflowerBlue`): el `<select>` ara marca `CornflowerBlue` com a `selected` correctament. **Incidència durant la verificació**: el primer intent de comprovar-ho en producció va fallar perquè `site` (uwsgi) no s'havia reiniciat des de l'edició de la plantilla — amb `DEBUG=False`, Jinja2 no recarrega plantilles soles i els workers ja actius seguien servint la versió antiga en memòria. Solucionat reiniciant `site` via `supervisorctl`.

---

### 11. Pas final: `DROP COLUMN extended_feedback` — recuperació real de l'espai de la BD

**Abans:** des de l'entrada #7, la columna vella `extended_feedback` (substituïda per `extended_feedback_file`) seguia física­ment present a `judge_submissiontestcase`, ja buida d'ús però ocupant espai.

**Decisió:**
1. **Backup d'emergència previ** (a petició explícita de l'usuari, abans de tocar l'esquema): `mysqldump --single-transaction --quick` de tota la BD, comprimit, a `/db_backup_emergencia_abans_drop_extended_feedback_15_Aug_2026_2108.sql.gz` (1.14 GB, integritat verificada amb `gzip -t`). **Incident evitat durant aquest pas**: el primer intent es va llançar sense `--single-transaction`, cosa que fa que `mysqldump` bloquegi totes les taules durant tot el bolcat (comportament per defecte per garantir consistència entre taules); es va detectar en viu (consultes reals d'usuaris bloquejades a `SHOW PROCESSLIST`, esperant "table metadata lock") i es va matar el procés immediatament, reprenent-lo amb `--single-transaction --quick` (sense bloqueig, via snapshot MVCC d'InnoDB).
2. Migració `0138_remove_submissiontestcase_extended_feedback` (`RemoveField`), aplicada amb `manage.py migrate judge 0138`.
3. `OPTIMIZE TABLE judge_submissiontestcase` (InnoDB no allibera l'espai físic d'un `DROP COLUMN` fins reconstruir la taula).

**Per què:** completar la migració de l'entrada #7 i recuperar físicament l'espai de disc de la BD, ara que el sistema de fitxers ja portava temps validat en producció.

**Resultat:** BD total de **5.34 GB a 0.77 GB** (la taula `judge_submissiontestcase` de 4.68 GB a 0.12 GB). Verificat sense errors (`/tmp/dasdas.log` net, render de submissions amb hint funcionant correctament després del canvi).

---

### 12. Nova funcionalitat: guies per a problemes d'introducció

**Abans:** no existia cap manera de marcar un problema com a "punt d'entrada" d'una categoria (el primer de bucles, el primer de strings, etc.) ni d'oferir-hi una guia d'ajuda per començar, més enllà de l'enunciat mateix.

**Decisió:**
1. **Model** (`judge/models/problem.py`): nous `Guide` (`OneToOneField` a `Problem`, camp `is_public` i `content` com a text per defecte/de resguard) i `GuideTranslation` (`ForeignKey` a `Problem`, `language` + `content`, `unique_together=('problem','language')`) — **calcat exactament del patró ja existent `Solution`/`ProblemTranslation`**, que és com ja funcionen les traduccions dels enunciats. La resolució d'idioma és idèntica: es busca `problem.guide_translations.get(language=request.LANGUAGE_CODE)` i, si no existeix, es fa servir `guide.content` (el mateix mecanisme de fallback que `ProblemTranslation`/`Problem.description`).
2. **Cap categoria/tag nova**: un problema "és d'introducció" simplement si té un `Guide` associat — evita haver de mantenir sincronitzats un tag i un contingut per separat.
3. **Admin**: `GuideInline` i `GuideTranslationInline` afegits a `ProblemAdmin` (mateix lloc que `ProblemSolutionInline`/`ProblemTranslationInline`), amb editor Markdown (`AdminMartorWidget`).
4. **Vista i URL**: `ProblemGuide` (`judge/views/problem.py`) + `/problem/<code>/guide` (`dmoj/urls.py`), calcada de `ProblemSolution`/`/editorial`. Permisos: visible sempre que `is_public=True` (a diferència de l'editorial, una guia no és un "spoiler" de la solució, així que no cal amagar-la fins after-solve), o només per a editors del problema si `is_public=False`; amagada durant concursos (mateix criteri que l'editorial).
5. **Marcatge visual**:
   - A la pàgina del problema (`templates/problem/problem.html`): etiqueta "Introducció" al costat del títol, i un botó gran i molt destacat ("Llegeix la guia", color `--highlight_blue`) **per sobre** del botó "Submit solution".
   - A les llistes de problemes (`templates/problem/list.html`) i de tasques (`templates/problem/task.html`): fila ressaltada (`intro-problem-row`) i una icona de birret (`fa-graduation-cap`) al costat del nom del problema.
   - Per evitar consultes N+1 a les llistes, s'ha afegit `.annotate(has_guide=Exists(...))` a les consultes de `ProblemsByOrganization`, `ProblemList` i `TaskDetail` — **no s'accedeix mai a `problem.guide` directament des d'una plantilla** (una relació OneToOne inversa sense fila corresponent llença una excepció en accedir-hi, i Jinja2 no la capturaria de forma silenciosa com ho fa Django Templates).
6. Migració `0139_add_problem_guide`.

**Per què:** petició explícita de l'usuari — que els alumnes puguin demanar una guia (adaptada al seu idioma) al primer problema de cada categoria, i que aquests problemes quedin ben identificats a totes les llistes.

**Resultat:** verificat en viu contra `jo-el.es` (problema de prova amb `Guide` + `GuideTranslation` en anglès): la pàgina del problema mostra l'etiqueta i el botó correctament, `/problem/<code>/guide` retorna el contingut en anglès quan `django_language=en` i cau al contingut per defecte quan es demana un idioma sense traducció (`es`); el control de permisos (`is_public=False`) verificat directament (accessible per a editors, no per a un usuari qualsevol). Pàgines de llista i de tasca renderitzen sense errors ni amb ni sense guies presents. Dades de prova netejades després de la verificació.

---

### 13. Guies: també adaptables pel llenguatge de programació (no només l'idioma)

**Abans:** l'entrada #12 només adaptava el contingut de la guia per idioma d'interfície (ca/en/es). L'usuari va demanar que també pogués variar segons el llenguatge de programació (Python, Java, etc.), ja que un bucle en Python i en Java es veuen molt diferents.

**Decisió:**
1. `GuideTranslation` (`judge/models/problem.py`) ampliat amb un segon eix: `runtime` (`ForeignKey` a `Language`, el mateix model que ja representa els llenguatges de programació al jutge — `null=True, blank=True`). Ara `language` també pot deixar-se en blanc. Els dos camps es poden combinar de forma independent:
   - `language='ca', runtime=Python3` → contingut específic per a català + Python.
   - `language='ca', runtime=None` → contingut per a català, vàlid per a qualsevol llenguatge de programació.
   - `language='', runtime=Python3` → contingut per a Python, vàlid per a qualsevol idioma.
   - `language='', runtime=None` → el mateix `Guide.content` per defecte fa aquesta funció si no hi ha cap fila més específica.
2. Nou mètode `Guide.resolve_content(language, runtime=None)`: busca totes les traduccions compatibles (mateix idioma o en blanc, mateix `runtime` o en blanc) i es queda amb la **més específica** (coincidència exacta d'idioma val 2 punts, coincidència exacta de `runtime` val 1 punt). `unique_together=('problem','language','runtime')` evita duplicats exactes a la BD — **però MySQL/MariaDB no aplica aquesta restricció quan `runtime` és `NULL`** (tracta cada `NULL` com a diferent als efectes d'un índex únic), així que s'ha afegit un `clean()` al model que ho comprova explícitament i llença `ValidationError` també en aquest cas.
3. **Vista** (`ProblemGuide`): tria el `runtime` automàticament a partir del llenguatge de programació preferit del perfil de l'alumne (`request.profile.language`, el mateix camp "Llenguatge" que ja es configura a `/edit/profile/`), amb possibilitat de sobreescriure'l manualment amb `?runtime=<key>` (p. ex. `?runtime=PY3`).
4. **Plantilla** (`templates/problem/guide.html`): si la guia té contingut per a més d'un llenguatge de programació, es mostra un selector ("Show for: Python 3 | Java 11 | ...") per canviar-hi manualment.
5. Migració `0140_guide_translation_runtime`.

**Per què:** petició explícita de l'usuari, arran de veure la primera versió de la funcionalitat (entrada #12).

**Resultat:** provades les 5 combinacions de especificitat possibles (ca+Python més específic que ca+qualsevol, que al seu torn és més específic que qualsevol+Python, que cau al `Guide.content` per defecte quan no hi ha res més) — totes correctes. Verificat en viu (`?runtime=PY3` a `/problem/<code>/guide`) que el selector mostra l'opció correcta marcada i el contingut correspon exactament al que tocava. Verificat que el `clean()` detecta correctament els dos tipus de duplicat (amb `runtime` normal i amb `runtime=None`, el forat de MySQL). `site` recarregat i verificat sense errors després del canvi (pàgina de problema, `/admin` amb el nou camp `runtime` a l'inline). Dades de prova netejades.

---

### 14. Primera guia real (9 Barris) i neteja de la categoria "Introduccio"

**Abans:** cap problema tenia encara una guia real (només dades de prova, ja esborrades). La categoria `ProblemGroup` "Introduccio" (154+11=165 problemes) incloïa 11 problemes d'examen (`itbuf1nf1ex1a/b`, `itbuf1nf1ex2a/b`, `itbuf1nf2ex2a/b`, `ipedm3uf1ex2a/b`, `ipedm3uf1ex3a/b`, `itbpreparacioexamen`) barrejats amb problemes d'aprenentatge.

**Decisió:**
1. Primera guia real creada per al problema `9barrisqueson13` ("Nou Barris, o en son 13?"): explica l'estratègia general (llegir línies fins EOF, guardar els barris de 1984 en un conjunt, consultar-hi cada entrada) sense revelar la llista concreta de barris (que és precisament el que cal deduir de l'enunciat), més codi d'exemple específic per Python 3 i Java 11 (amb el conjunt de dades buit, perquè l'alumne l'ompli).
2. Nova categoria `ProblemGroup` **"Examens"**, i moguts els 11 problemes amb "examen" al nom des de "Introduccio" cap aquí (a petició explícita de l'usuari) — no té sentit oferir-hi una guia d'aprenentatge a un exercici d'avaluació.

**Per què:** l'usuari vol guies en català per a tots els problemes de la categoria "Introduccio", però primer calia netejar-la (traient-ne els exàmens, que no són problemes d'aprenentatge).

**Resultat:** "Introduccio" ha passat de 165 a **154** problemes. Verificat en viu que `9barrisqueson13` mostra correctament l'etiqueta, el botó i el contingut de la guia (sense revelar la solució). Pendent: escriure guies per als 153 problemes restants (per lots, revisant l'enunciat de cadascun per fer una guia real i no genèrica).

---

### 15. Guies per a un lot de 8 problemes d'introducció

**Abans:** els problemes `escriurebin`, `introarrays1`-`introarrays4`, `itbuf1nf2ex1b`, `lamaquinadeltemps` i `llegirfitxer` no tenien encara guia (formen part del lot de 153 pendents de l'entrada #14).

**Decisió:** creada `Guide` (contingut per defecte, `is_public=True`) + `GuideTranslation` (`language='ca'`) per a Python 3 i Java 11 per a cadascun d'aquests 8 problemes, llegint primer l'enunciat real de cada un (no assumint pel nom):
- `escriurebin`: escriptura d'un fitxer binari (mode `'wb'`/`FileOutputStream`, un byte per valor 0-255).
- `introarrays1`-`introarrays4`: sèrie d'arrays (llegir/escriure per índex, array de Strings, llista dinàmica amb sentinella `-1` i notació `[a, b, c]`, i el cas de dos bucles separats llegir+modificar).
- `itbuf1nf2ex1b`: matriu d'horari (files = franja horària `hora-E`, columnes = dia `dia-1`, "NO HI HA CLASSE" fora de rang).
- `lamaquinadeltemps`: tipus "Sense Bucles" — la guia i el codi d'exemple (Python i Java) eviten expressament qualsevol `for`/`while`, només un `if`/`else`.
- `llegirfitxer`: lectura del fitxer `in` (sense entrada estàndard) i impressió tal qual.

**Per què:** continuació del pla de l'entrada #14 (guies per a tota la categoria "Introduccio"), fet en paral·lel per diversos agents treballant cadascun sobre un subconjunt disjunt de problemes.

**Resultat:** verificat per BD que els 8 problemes tenen `Guide.is_public=True` i exactament 2 `GuideTranslation` cadascun (ca+PY3, ca+JAVA11). Cap solució ni dada real (barris, matèries, etc.) revelada als continguts — només tècnica/esquelet de codi amb comentaris de marcador de posició on caldria la dada real. No s'ha tocat cap altre problema ni reiniciat cap servei.

---

### 16. Guies per a un segon lot de 7 problemes d'introducció

**Abans:** els problemes `r4c4`, `rebaixesmagatzem`, `reiarturtaularodona`, `stonknt`, `thorhijodeodin`, `tiradesperf` i `unbomboperpersona` no tenien encara guia (formen part del lot de problemes pendents de l'entrada #14, treballats en paral·lel per un altre agent).

**Decisió:** creada `Guide` (contingut per defecte, `is_public=True`) + `GuideTranslation` (`language='ca'`) per a Python 3 i Java 11 per a cadascun d'aquests 7 problemes, llegint primer l'enunciat real de cada un:
- `r4c4` (Strings): separar el nom del Pokémon dels tres valors numèrics, comprovar primer la condició de fracàs (dany >= 40) i després decidir el rang S/A/B/C — sense revelar els llindars exactes, que calen extreure de l'enunciat.
- `rebaixesmagatzem` (Matrius): llegir una matriu quadrada de preus, aplicar-hi un descompte percentual element a element i trobar el preu màxim resultant.
- `reiarturtaularodona` (Geometria, **Sense Bucles**): calcular el perímetre a partir del diàmetre i comparar quants cavallers hi caben amb el nombre real; codi d'exemple sense cap `for`/`while`.
- `stonknt` (Bucles simples, Matrius): comptar els "retard" d'una taula setmanes x dies i aplicar el descompte del 0,50% per retard sobre el sou base, amb sortida en format de coma decimal.
- `thorhijodeodin` (Grafs): construir un graf no dirigit a partir de les relacions "X HIJO DE Y" i fer un BFS des de THOR per comprovar connectivitat (família llunyana), reconstruint el graf a cada cas.
- `tiradesperf` (Bucles simples, Simple Math): comptar els 6 d'una seqüència fins trobar el -1 de tall.
- `unbomboperpersona` (Matemàtiques, **Sense Bucles**): comparar alumnes i bombons amb una simple resta i condicionals, sense bucle.

**Per què:** continuació del pla de l'entrada #14 (guies per a tota la categoria "Introduccio"), fet en paral·lel per diversos agents treballant cadascun sobre un subconjunt disjunt de problemes.

**Resultat:** verificat per BD que els 7 problemes tenen `Guide.is_public=True` i exactament 2 `GuideTranslation` cadascun (ca+PY3, ca+JAVA11). Cap solució ni dada real (llindars de rang, valors de matriu, relacions familiars concretes...) revelada als continguts — només tècnica/esquelet de codi amb comentaris de marcador de posició on caldria la dada real. No s'ha tocat cap altre problema ni reiniciat cap servei.

---

### 17. Guies per als tres lots restants (23 problemes) i tancament del pla de l'entrada #14

**Abans:** de la selecció de 40 problemes de l'entrada #14 (els de menys punts de cada tipus dins "Introduccio"), només `9barrisqueson13` (entrada #12) i els 15 de les entrades #15/#16 tenien guia.

**Decisió:** completats els 23 problemes restants, repartits en 3 lots fets en paral·lel per agents independents, cadascun sobre un subconjunt disjunt (mateix format que #15/#16 — `Guide` amb contingut per defecte + `GuideTranslation` ca+PY3 i ca+JAVA11, llegint primer l'enunciat real):
- Lot 1: `01`, `a22sanhussha`, `ahorcado`, `apostesperdudes`, `apostesperdudes0`, `bitlles1`, `cagatio`, `cistellcompra`.
- Lot 2: `cistellcompra2`, `classeaob`, `contador`, `copia`, `detectoridioma`, `eduardochillida`, `elmeuprimerbucle`, `elmeuprimerbuclewhil`.
- Lot 4: `llegirfitxer2`, `llistatalumnes`, `lubinaspormesas`, `nombresprimers`, `nota10`, `numerospositius`, `operadorsrelacio`, `passantllista`.

Als problemes "Sense Bucles" (`classeaob`, `detectoridioma`, `eduardochillida`, `operadorsrelacio`, entre d'altres de les entrades anteriors) el codi d'exemple evita expressament `for`/`while`.

**Incident menor durant l'execució (sense conseqüències):** diversos agents en paral·lel van fer servir inicialment el mateix nom de fitxer temporal a l'scratchpad (`insert_guides.py`) per al seu script d'inserció, provocant que es sobreescrivissin entre ells. Cada agent ho va detectar abans d'executar res contra la BD (via `NameError`/contingut inesperat) i va canviar a un nom de fitxer únic — **verificat que cap dada incorrecta es va arribar a escriure** (cada problema té exactament les 2 traduccions esperades, dels tipus correctes).

**Per què:** completar la petició original de l'usuari (guies en català per a la categoria "Introduccio", començant pels problemes de menys punts de cada tipus).

**Resultat:** **els 40 problemes seleccionats tenen ara guia** (`Guide.objects.count() == 40`, `GuideTranslation.objects.count() == 80`, cap forat). Verificat en viu (render de pàgina + pàgina de guia) per una mostra de 4 problemes nous (`bitlles1`, `introarrays2`, `reiarturtaularodona`, `llegirfitxer`) sense errors; confirmat que els problemes "Sense Bucles" no contenen cap bucle al codi d'exemple. Com que aquest lot només ha afegit contingut a la BD (cap canvi de codi/plantilla), no ha calgut recarregar `site`.

---

### 18. Bug fix: el codi de la guia desapareixia si la interfície no estava en català

**Abans:** `Guide.resolve_content(language, runtime)` exigia que l'idioma de la interfície coincidís amb el de la traducció (o fos en blanc) A MÉS del `runtime`. Com que totes les `GuideTranslation` escrites fins ara són `language='ca'`, un alumne amb la interfície en castellà o anglès que triava "Python 3" al selector no veia el codi Python — queia directament al contingut genèric sencer (`Guide.content`, sense codi), com si no hi hagués cap pista específica. A més, en triar un llenguatge de programació, les "consideracions generals" (l'explicació de l'estratègia) desapareixien del tot, substituïdes pel codi.

**Decisió (detectat i reportat per l'usuari mateix, provant `/problem/thorhijodeodin/guide`):**
1. `Guide.resolve_content` se separa en dos mètodes: `resolve_general(language)` (només la part sense codi, filtrant per `runtime__isnull=True`) i `resolve_runtime_hint(runtime, language=None)` (només la part de codi, cercant **exclusivament pel `runtime`, ignorant l'idioma de la interfície** — el codi és útil independentment de l'idioma en què es llegeixi la pàgina; si hi hagués traduccions del mateix `runtime` en més d'un idioma, es prefereix la que coincideix amb `language`).
2. La vista (`ProblemGuide`) i la plantilla (`guide.html`) ara mostren **sempre** `guide_general_content`, i per sota (si n'hi ha) `guide_runtime_content` — mai l'un en lloc de l'altre.
3. Nova opció **"General considerations"** al selector de dalt (`?runtime=none`), que talla explícitament la selecció automàtica de llenguatge de programació (basada en el perfil de l'alumne) per tornar a veure només l'explicació general.

**Per què:** petició/detecció explícita de l'usuari en provar la funcionalitat en un idioma diferent del català.

**Resultat:** verificat (`site` recarregat) amb 4 escenaris: català sense selecció (mostra Python, auto-detectat pel perfil), `?runtime=none` (només general, pastilla "General considerations" marcada), `?runtime=JAVA11` (codi Java), i **interfície en castellà + `?runtime=PY3`** (el cas que fallava): ara mostra correctament tant les consideracions generals com el codi Python.

---

### 19. Reducció d'idiomes actius i auditoria/correcció d'i18n incomplet

**Abans:** `settings.LANGUAGES` activava 17 idiomes (ca, de, en, es, fr, hr, hu, ja, ko, pt, ro, ru, sr-latn, tr, vi, zh-hans, zh-hant), amb catàlegs de traducció (`locale/*`) per a 23, la majoria sense manteniment real. A més, no s'havia fet mai una auditoria de text hardcoded (no traduïble) a les plantilles/vistes.

**Decisió:**
1. **Idiomes actius reduïts a 5**: català, castellà, anglès, alemany i xinès simplificat (`zh-hans`, triat explícitament per l'usuari per sobre del tradicional: 869 missatges ja traduïts vs. 122). Canvi d'una sola línia a `dmoj/settings.py` (`LANGUAGES`). **Els fitxers `locale/` de la resta d'idiomes es deixen intactes al disc** (decisió explícita de l'usuari: no esborrar-los, només desactivar-los), per si en un futur es volen reactivar.
2. **Auditoria d'i18n** (agent de recerca dedicat, només lectura): 24 troballes de text hardcoded sense passar per `_()`/`{{ _(...) }}`, repartides entre plantilles pròpies (gacha, lligues, perfil), plantilles generals del lloc, i vistes Python (`FTS syntax error`, diversos `HttpResponseBadRequest` amb text pla).
3. **Correcció de les 24 troballes**: totes embolicades en `_()` (Python) o `{{ _(...) }}` (Jinja2). **Troballa destacada durant la correcció**: `templates/user/edit-profile.html` tenia un bug real, no només un problema d'i18n — `showTooltip(e.trigger, _('Copied!'));` cridava una funció JS `_` inexistent (el patró correcte, usat a la resta del fitxer, és `{{ _('...') }}`, avaluat pel servidor, no en temps d'execució al navegador); això hauria llençat un `ReferenceError` silenciós cada vegada que un usuari copiava un codi de reserva (*scratch code*), sense trencar la resta de la pàgina però sense mostrar mai el tooltip de confirmació.
4. **Traducció de les cadenes noves** (`manage.py makemessages -l ca -l es -l en -l de -l zh_Hans`, seguit de traducció manual amb `polib` per a les ~33 cadenes noves/reutilitzades, cap a els 4 idiomes que no en són l'origen). **Incident detectat durant la traducció**: `msgmerge` havia fet *fuzzy-matching* automàtic d'algunes cadenes noves contra cadenes antigues similars però semànticament no relacionades (p. ex. `"Punts Disponibles"` va aparellar-se amb la traducció vella de `"points possible"` → `"punts possibles"`; `"Could not vote: "` es va aparellar amb la traducció de `"Could not find page"`) — aquestes coincidències *fuzzy* no s'apliquen mai en producció (`msgfmt` les ignora en compilar per defecte), però calia netejar-les igualment abans de donar per bo el fitxer. Es van corregir totes manualment i es va treure la marca `fuzzy`. També es va detectar i corregir un flag `#, python-format` fals positiu (per un `50%` literal dins un text, no un format Python real) que feia fallar `msgfmt --check` per al xinès simplificat.
5. **No s'ha traduït tota la resta de contingut que `makemessages` ha trobat sense traduir** (funcionalitats afegides en sessions anteriors —Guies, Tasques, checker SQL, Lliga— que mai s'havien passat per `makemessages`): és una feina de traducció molt més gran, fora de l'abast d'aquesta petició concreta, i queda pendent com a possible feina futura.
6. Desplegament: `manage.py compilemessages` + `manage.py compilejsi18n` + `manage.py collectstatic` + `sudo supervisorctl restart site`.

**Per què:** petició explícita de l'usuari ("no podem mantenirho" en referència a mantenir 17+ idiomes) i petició explícita de trobar i corregir text no traduïble, "encara que sigui amb una traducció automàtica".

**Resultat:** `manage.py check` net; prova en viu amb `django.utils.translation` confirmant les 5 traduccions noves en els 5 idiomes actius; lloc verificat funcionant (`200`, sense errors a `/tmp/dasdas.log`, jutge continua acceptant i corregint submissions amb normalitat) després del reinici de `site`.

---

### 20. Repensat el sistema de problemes SQL: múltiples preguntes per problema, explorador d'esquema, i rànquing propi

**Abans:** el checker SQL ([5.5](docs/05-sistemes-mecanics/5.5-checker-sql.md)) només permetia **una consulta per enviament** (cada problema, `provasql`/`provasql2`, tenia exactament 1 cas de prova) — calia fer un enviament separat per cada pregunta sobre la mateixa BD, triant manualment el llenguatge "Text" cada vegada. No hi havia manera de veure l'esquema de la BD des de la interfície, i un problema SQL sumaria als mateixos punts/rànquing que la programació normal.

**Decisió**, després d'un pla revisat i aprovat explícitament amb l'usuari:

1. **Categoria pròpia**: `ProblemGroup(name='sql')` (migració `0141_sql_problem_group`, no destructiva), assignat a `provasql2` — pura categorització, calcat del precedent de "Lliga de Programació FP" a nivell d'organització de la llista de problemes, sense codi especial necessari (el filtre `?category=` de `/problems/` ja ho suporta).

2. **Diverses preguntes, un quadre per pregunta**: cada `ProblemTestCase` normal (sense lots) passa a representar una pregunta. `ProblemDataCompiler.make_checker()` (`judge/utils/problem_data.py`) assigna automàticament un `question_index` (1-based, per ordre) a cada cas SQL, sense que el professor hagi d'escriure cap índex a mà; el professor només introdueix, per a cada cas, l'enunciat de la pregunta (nova peça de JS a `templates/problem/data.html`, desat dins `checker_args` com a `{"question": "..."}` — un camp que ja existia al model però que abans només s'omplia per al checker de floats). Nova plantilla `templates/problem/submit_sql.html` (activada automàticament quan `problem.data_files.checker == 'sql'`, via `ProblemSubmit.get_template_names()`): un quadre de text per pregunta, sense selector de llenguatge visible (sempre és "Text" per sota), que en enviar uneix totes les respostes en un sol text amb marcadors `-- @@Q<n>@@` (un comentari SQL, per tant inofensiu si mai arriba sense processar) — segueix sent un únic `Submission` normal, cap canvi al pipeline d'enviament ni al motor de jutge en si.

   El checker real (`dmoj/checkers/sql.py`, **fora d'aquest repositori**, al host del jutge) va rebre suport per `question_index`: si es passa i la submissió conté marcadors, en localitza i corregeix només el fragment corresponent; **si no hi ha cap marcador present a la submissió (compatibilitat amb enviaments antics o via API), es corregeix tot el text tal qual, exactament com abans** — cap risc de trencar `provasql2` ni cap integració externa.

3. **Explorador d'esquema** (`ProblemDatabaseSchema`, `/problem/<codi>/database`): nomé lectura, mostra taules i columnes (via `sqlite_master`/`PRAGMA table_info`) llegint el `.db` directament del disc compartit en mode `mode=ro`; cap possibilitat d'executar consultes lliures (decisió presa: només esquema, de moment). Botó nou a la pàgina del problema, visible només si el checker és `sql`.

4. **Rànquing i punts separats de la programació**: nous camps `Profile.sql_points`/`sql_problem_count` (migració `0142_sql_points`), nou mètode `Profile.calculate_sql_points()` (mirall senzill de `calculate_points()`, sense la fórmula de *performance points*, escopat als problemes del grup `sql`), i **el `calculate_points()` existent ara exclou explícitament els problemes del grup `sql`** — separació total confirmada amb l'usuari, un problema SQL mai suma als punts normals de programació. Enganxat a `on_grading_end` (`judge/bridge/judge_handler.py`) al costat de la crida existent a `calculate_points()`. Nou rànquing `/users/sql` (`UserListSql`, calcat de `UserListPrimera`/`UserListSegona` però amb desempat pel comptador de problemes SQL propi, no el comptador global com fa —per error— el patró Lliga).

**Incident detectat i corregut durant el desplegament d'aquest canvi:** just després d'aplicar la migració `0142_sql_points` en calent (afegint les columnes noves a `Profile` a la BD en viu, sense reiniciar `site` de seguida), **un usuari real va fallar en registrar-se** (`IntegrityError: Field 'sql_points' doesn't have a default value`) — exactament el mateix parany documentat anteriorment ([[feedback_db_field_retirement]]) però en la direcció inversa: el procés `site` (uwsgi) ja en marxa tenia encara en memòria la classe de model *antiga* (sense `sql_points`), així que el seu `INSERT` no incloïa la columna nova, i la BD (ja amb la columna afegida per la migració) el va rebutjar en mode estricte. Es va comprovar que **no va quedar cap usuari orfe** (cap `User` sense `Profile` corresponent — el compte del mateix intent es va acabar registrant bé en un reintent posterior), i es va reiniciar `site`/`bridged` immediatament per sincronitzar el procés en marxa amb l'estat real de la BD/codi. **Lliçó, ampliant la ja existent**: aquest parany no és només "en treure un camp" — també pot passar en **afegir-ne un de nou i no reiniciar `site` de seguida**, ja que un procés uwsgi de llarga durada no torna a importar el codi Python sol.

**Per què:** petició explícita de l'usuari per repensar els dos problemes de prova (`provasql`/`provasql2`) —feixuguesa d'un enviament per pregunta, manca d'un explorador de BD, i el dubte pedagògic de si SQL hauria de compartir puntuació amb la programació— resolta amb un pla revisat i aprovat abans d'escriure cap codi.

**Resultat:** provades en viu, contra el jutge real ("NouJutge", calia reiniciar-lo perquè el canvi al checker és un fitxer fora d'aquest repositori i Python no en recarrega el codi sol): un problema de 2 preguntes real (`provasql2`, ampliat amb una segona pregunta i el seu fitxer de resposta de referència dins el mateix `.zip`) es corregeix correctament amb totes dues preguntes bé (`AC`, 1.0/1.0), amb una barreja d'encert/error (`WA`, cada cas puntuat per separat), i amb un enviament antic d'una sola consulta sense marcadors (cau correctament al mode de compatibilitat). Verificat per separat que `calculate_sql_points()` puja els punts SQL sense tocar `calculate_points()` normal. `manage.py check` net; `/tmp/dasdas.log` sense errors nous després dels reinicis.

**Pendent, afegit a `TODO.md`:** representació gràfica automàtica de l'esquema (diagrama ER) a l'explorador de BD.

---

### 21. Selector "Problemes de Programació" / "Problemes de Bases de Dades" a la llista de problemes

**Abans:** la llista de problemes (`/problems/`) no distingia entre problemes de programació i problemes SQL —tot sortia mesclat, i l'únic filtre era el desplegable general de categoria.

**Decisió:** afegides dues pestanyes noves a la barra de pestanyes ja existent de la llista de problemes (`templates/problem/problem-list-tabs.html`, calcat del mateix patró de pestanyes ja usat a "Tasks"/rànquings): **"Problemes de Programació"** (`/problems/`, per defecte) i **"Problemes de Bases de Dades"** (`/problems/?category=<id_grup_sql>`). La pestanya de Programació ara **exclou explícitament** els problemes de la categoria `sql` (`ProblemList.get_normal_queryset`, `judge/views/problem.py`) —abans, sense cap categoria seleccionada, es mostraven tots els problemes mesclats; ara la vista per defecte és neta i els problemes SQL només surten si es demanen expressament (aquesta pestanya, o el desplegable de categoria). De pas, es va corregir un bug ja existent a `templates/problem/tasklist.html`: la pestanya "Tasks" no es marcava mai com a activa a la seva pròpia pàgina (còpia i enganxa mal feta que hi posava `tab='list'`/`title='Problems'` en lloc de `tab='task'`/`title='Tasks'`).

**Per què:** petició explícita de l'usuari, per no haver de fer servir el desplegable de categoria cada vegada per distingir programació de SQL.

**Resultat:** provat en viu (fent temporalment públic `provasql2` i desfent-ho): la pestanya de Programació ja no el mostra, la de Bases de Dades sí. Traduïdes les cadenes noves als 5 idiomes actius. `manage.py check` net; verificat contra el procés `site` real després de reiniciar-lo (`200`, pestanyes correctes).

---

### 22. Primer set real de problemes SQL: 4 problemes temàtics amb diverses preguntes cadascun

**Abans:** només hi havia els dos problemes de prova (`provasql`/`provasql2`), pensats per validar el sistema, no per fer-los servir de veritat amb alumnes.

**Decisió:** creats 4 problemes reals, públics, tots sobre la mateixa base de dades d'exemple ("Northwind" en miniatura: `categories`, `customers`, `products`, `orders`, `order_details`, la mateixa que ja feia servir `provasql2`), cadascun amb diverses preguntes fent servir el sistema de multi-pregunta ([entrada #20](#20-repensat-el-sistema-de-problemes-sql)):

- **`sqlselects`** — "Bases de Dades: Selects bàsics" (2 preguntes: filtre per país, filtre per booleà).
- **`sqljoins`** — "Bases de Dades: Joins" (3 preguntes: `JOIN` de dues taules, `JOIN` amb filtre sobre una comanda concreta, `LEFT JOIN` + `COUNT` per incloure clients sense comandes).
- **`sqlagregacions`** — "Bases de Dades: Agregacions i GROUP BY" (3 preguntes: `COUNT`+`GROUP BY`, `AVG`+`GROUP BY`, `HAVING`).
- **`sqldificil`** — "Bases de Dades: Problemes més difícils" (3 preguntes: subconsulta correlacionada per comparar amb la mitjana de la pròpia categoria, unió de 3 taules amb agregació i ordenació ("qui ha gastat més"), patró de "màxim per grup" amb subconsulta).

Tots amb `partial=True` (a diferència de `provasql2`), perquè cada pregunta puntuï per separat en lloc de tot-o-res —amb diverses preguntes per problema, té molt més sentit pedagògic. Categoritzats al grup `sql` i al tipus de problema ja existent "BD - Selects" (creat per l'usuari mateix). Creats programàticament (ORM de Django + compilador de dades), no des de l'admin a mà, per poder-los provar tots de seguida.

**Per què:** petició explícita de l'usuari per tenir un primer conjunt real de problemes SQL, amb la distribució de dificultat que va demanar (bàsics de una taula, joins de diferents tipus, agregacions, i uns quants de més difícils).

**Resultat:** cada consulta de referència verificada manualment contra la base de dades real abans de crear el problema. Provats els 4 problemes de cap a cap contra el jutge real: **`sqljoins`, `sqldificil` i `sqlselects`** amb totes les respostes correctes → `AC` a puntuació completa; **`sqlagregacions`** amb una resposta intencionadament equivocada (`SUM` en lloc d'`AVG`) → `WA` general però amb **crèdit parcial correcte** (2 de 3 punts, exactament les preguntes ben contestades). Confirmat que aquestes submissions reals van pujar `Profile.sql_points` de l'usuari (a `/users/sql`) sense tocar `Profile.points`/`performance_points` normals —el rànquing separat funciona de veritat en producció, no només en proves. `manage.py check` net.

**Nota posterior (mateix dia):** a petició de l'usuari, s'ha canviat l'autor d'aquests 4 problemes de "ningú" a l'usuari `edgar` (id 4928) —`provasql`/`provasql2` continuen amb "marc" com a autor, sense tocar.

---

### 23. Bases de dades d'exemple per als problemes SQL, en lloc de pujar-ne una cada vegada

**Abans:** cada problema SQL necessitava que el professor pugés el seu propi fitxer `.db` (SQLite) a mà —feixuc si es volen reutilitzar les mateixes bases de dades clàssiques d'ensenyament (Northwind, Chinook...) en diversos problemes.

**Decisió:** l'usuari va deixar 10 bolcats `.sql` de MySQL/MariaDB a l'arrel del repositori (`northwind.sql`, `northwind-data.sql`, `miniwind.sql`, `Chinook_MySql.sql`, `Chinook_MySql_AutoIncrementPKs.sql`, `traders.sql`, `KnightsDB.sql`, `hotel.sql`, `lastnames.sql`, `Employees.sql`, `groupbytest.sql`, `ies23g.sql`). Es van convertir a SQLite (script de conversió de dialecte propi: neteja de comentaris `/*!...*/`, `ENGINE=`/`CHARSET=`/`AUTO_INCREMENT`, índexs secundaris amb nom, i el diferent escapament de cometes dins de cadenes MySQL vs. SQLite) i es van desar a `/judge/_sql_templates/` (fora del repositori), un fitxer per base de dades. **`Chinook_MySql_AutoIncrementPKs.sql` es va descartar per ser un duplicat exacte** de `Chinook_MySql.sql` (només canvia si les claus primàries porten `AUTO_INCREMENT` explícit, irrellevant un cop convertit a SQLite).

**Troballa important, reportada abans de continuar:** `ies23g.sql` **conté dades reals de persones** —una taula `usuaris` amb noms, cognoms, dates de naixement, i una columna `password` en text pla, que sembla un bolcat real d'un sistema similar a aquest mateix JOEL. **No s'ha convertit ni incorporat enlloc** —es descarta completament per motius de privacitat, i es documenta aquí perquè quedi constància clara del motiu (l'usuari hauria de revisar per què aquest fitxer conté dades tan sensibles i decidir si cal esborrar-lo o protegir-lo millor, ja que continua existint tal qual a l'arrel del repositori, fora de git per `*.sql` al `.gitignore`).

A `judge/views/problem_data.py` (`ProblemDataForm`) s'ha afegit un desplegable nou, **"Or choose an example database"**, que apareix a l'editor de dades del problema (`/problem/<codi>/test_data`) quan el checker és `sql`, al costat del camp de pujada manual. Es genera dinàmicament escanejant `settings.DMOJ_SQL_SAMPLE_DATABASES_ROOT` (`judge/utils/problem_data.py::get_sql_sample_databases()`), amb noms/descripcions bonics definits a `SQL_SAMPLE_DATABASE_INFO`. En triar-ne una (sense pujar cap fitxer propi), es copia directament dins la carpeta del problema —cap canvi al mecanisme del checker.

**Per què:** petició explícita de l'usuari per no haver de pujar una base de dades cada vegada, reutilitzant les que ja havia preparat.

**Resultat:** provades les 9 bases de dades convertides —totes carreguen sense errors a SQLite amb dades reals (Northwind: 29 clients/45 productes/48 comandes; Chinook: 3503 cançons; etc.). Verificat de cap a cap que triar "chinook" des del formulari real (`ProblemDataForm`) copia el fitxer correcte dins la carpeta del problema, amb l'esquema esperat. `manage.py check` net; verificat en viu (`200`) després de reiniciar `site`.

---

### 24. Suport per a problemes SQL d'`INSERT` i `UPDATE` (encara no `DELETE`), amb garantia que mai es toca la BD real

**Abans:** el checker SQL només acceptava `SELECT`, executat sempre en mode de només lectura directament contra el fitxer `.db` del problema.

**Decisió**, amb un pla revisat i aprovat explícitament amb l'usuari (l'èmfasi de seguretat va ser explícit: "sota cap concepte s'ha de permetre un `USE`, `DROP DATABASE` o whatever, i sota cap concepte han de poder tenir mai accessos a la BD real de la web"):

1. **Detecció automàtica del tipus de cas**: es dedueix de la primera paraula de la consulta de referència (`.out`) —`SELECT`, `INSERT` o `UPDATE`. Cap camp nou a la interfície, cap canvi a la web (aquest repositori); un professor crea una pregunta d'`INSERT`/`UPDATE` exactament igual que una de `SELECT`.
2. **Llista de bloqueig reforçada, sempre activa** (`_ALWAYS_FORBIDDEN`, independent del tipus de cas): `DELETE, DROP, ALTER, CREATE, TRUNCATE, EXEC, EXECUTE, ATTACH, DETACH, PRAGMA, VACUUM, REINDEX, USE, REPLACE`. `ATTACH`/`DETACH` són els que realment evitarien que una consulta "sortís" del fitxer assignat (és el mecanisme de SQLite per obrir un altre fitxer com a BD addicional); `USE` s'hi afegeix tot i no existir en SQLite, explícitament, perquè quedi blindat al codi; `REPLACE` es bloqueja perquè equival a `DELETE`+`INSERT` combinats.
3. **Execució d'`INSERT`/`UPDATE` sempre sobre una còpia d'un sol ús, mai sobre l'original**: `_make_temp_copy()` fa una còpia de fitxer pura (`shutil.copyfile`, mai `sqlite3`) cap a un fitxer temporal; la sentència de l'alumne (i, per separat, la de referència, en una segona còpia independent) s'executen només contra aquestes còpies; es compara **tot el contingut de totes les taules** entre totes dues (files ordenades en Python, no per SQL, per no dependre de l'ordre físic); les còpies s'esborren sempre en acabar. El fitxer `.db` real **mai s'obre en mode d'escriptura**.
4. **Xarxa de seguretat addicional, no demanada explícitament però afegida per coherència amb l'èmfasi de l'usuari**: totes les connexions que executen SQL de l'alumne porten un `set_progress_handler` de SQLite que interromp la consulta si triga més d'uns segons —evita que una consulta patològica (p. ex. un producte cartesià enorme) pengi el procés del jutge.
5. **Confirmat que no hi ha ni pot haver-hi cap camí cap a la BD real de la web** (el MySQL de Django): el checker només fa servir el mòdul `sqlite3` contra fitxers locals dins la carpeta del problema —mai cap client MySQL, mai cap connexió de xarxa. Aquesta garantia ja existia abans del canvi (no depèn de res que s'hagi tocat ara); el que es reforça amb aquest canvi és la llista de bloqueig, no l'existència d'un camí que mai hi ha hagut.

**Incident detectat i corregit durant les proves de seguretat (abans de donar-ho per bo)**: la primera versió del bloqueig comparava la primera paraula de la consulta amb una llista exacta (`"VACUUM" in forbidden`), però `sql.split()[0]` sobre `"VACUUM;"` (sense espai abans del punt i coma) retorna `"VACUUM;"` —amb el punt i coma enganxat— que **no coincidia** amb l'entrada `"VACUUM"` de la llista, deixant-la passar (encara que després queia igualment en un rebuig genèric per no ser del tipus esperat, la sentència real mai arribava a executar-se, però el missatge d'error no era el correcte i la robustesa de la comprovació era fràgil). Corregit extraient la paraula clau amb una expressió regular (`^([A-Z_]+)`) en lloc de dividir per espais.

**Per què:** petició explícita de l'usuari per poder fer problemes d'`INSERT`/`UPDATE`, amb les garanties de seguretat que va remarcar explícitament ell mateix.

**Resultat:** provat exhaustivament amb el checker aïllat i després de cap a cap contra el jutge real (afegint temporalment una tercera pregunta d'`UPDATE` a `provasql2`, provada i retirada després, deixant el problema exactament com estava): `UPDATE`/`INSERT` correctes → `AC`; valors equivocats → `WA` amb el missatge correcte; intent de `DELETE` en lloc d'`UPDATE` → rebutjat amb "This statement type is not allowed: DELETE"; **el fitxer `miniwind.db` real comprovat bit a bit idèntic abans i després de totes les proves** (incloent-hi intents maliciosos de `DROP TABLE`, `ATTACH DATABASE`, `USE`, `REPLACE INTO`, sentències múltiples, i un `VACUUM;` sense espai). Problemes `SELECT` existents (`provasql2`, `sqlselects`, etc.) verificats sense cap regressió. Reiniciat el procés del jutge; `/tmp/dasdas.log` sense errors nous.

---

### 25. Sis problemes reals d'`INSERT`/`UPDATE`, cadascun en una base de dades diferent

**Abans:** el mode `INSERT`/`UPDATE` (entrada #24) estava implementat i provat, però encara no hi havia cap problema real que el fes servir.

**Decisió:** creats 6 problemes públics més, autor `edgar`, cadascun sobre una base de dades diferent de la llibreria d'exemples (entrada #23) —cap repeteix la mateixa BD que un altre, ni la mateixa que els problemes de `SELECT` ja existents (`miniwind`):

- **`sqlinsertemployees`** (BD Employees, 2 preguntes): inserir empleats nous, un d'ells amb un camp `NULL` explícit.
- **`sqlinsertknights`** (BD Knights & Dragons, 2 preguntes): inserir un cavaller i un drac —el drac fa referència a un cavaller **ja existent** a la BD (clau forana), no pas a un inserit per una altra pregunta del mateix problema, ja que cada pregunta es corregeix contra la seva pròpia còpia neta de la BD original, independentment de les altres.
- **`sqlinsertchinook`** (BD Chinook, 3 preguntes): inserir un artista, un gènere musical i un àlbum (aquest últim referenciant un artista ja existent).
- **`sqlupdategroupby`** (BD GroupByTest, 2 preguntes): actualitzar un salari i un cognom, en dues taules diferents del mateix fitxer.
- **`sqlupdatehotel`** (BD Hotel, 2 preguntes): actualitzar un telèfon de client i l'estat d'una reserva.
- **`sqlupdatetraders`** (BD Traders, 2 preguntes): actualitzar la capacitat d'una nau i el nom d'un producte.

Tots amb `partial=True`, categoria `sql`, i creats programàticament (ORM + compilador de dades) igual que el primer set de problemes de `SELECT` (entrada #22).

**Per què:** petició explícita de l'usuari per tenir problemes reals d'`INSERT`/`UPDATE`, en bases de dades diferents entre si.

**Resultat:** cada sentència de referència verificada manualment contra la seva base de dades abans de crear el problema. Provats els 6 problemes de cap a cap contra el jutge real: totes les respostes correctes → `AC` a puntuació completa; una resposta amb un valor equivocat (`sqlinsertknights` amb el cavaller equivocat com a `KilledBy`, `sqlupdatehotel` amb un telèfon equivocat) → `WA` amb crèdit parcial correcte a les altres preguntes; un intent de `DELETE` en lloc d'`INSERT` a `sqlinsertchinook` → rebutjat amb el missatge de seguretat esperat, sense afectar la correcció de les altres preguntes del mateix enviament. Confirmat que **cap dels fitxers `.db` originals de la llibreria d'exemples ha canviat** després de totes les proves (recomptes i valors comprovats abans/després). Un petit incident menor durant la creació (un enllaç trencat en un intent previ de `sqlinsertemployees`, per una peculiaritat de com `manage.py shell` gestiona funcions definides per stdin) es va detectar, el problema a mig crear es va esborrar, i es va tornar a crear bé —cap conseqüència per als altres 5 problemes ni per res més del sistema.

---

### 26. Suport per a problemes MongoDB (checker `mongo`), i generalització de "SQL" a "Bases de Dades"

**Abans:** el sistema de "problemes de bases de dades" (categoria, rànquing separat, format de diverses preguntes, explorador d'esquema, selector de BD d'exemple) assumia que l'única tecnologia possible era SQL/SQLite: URLs (`/users/sql`), plantilles i etiquetes ho deien explícitament.

**Decisió**, amb un pla revisat i aprovat explícitament amb l'usuari:

1. **Generalització del que és visible** (Milestone 1, cap migració de schema): `/users/sql` → `/users/bd` (nom de la URL `sql_list` → `database_list`), plantilles renombrades (`list_sql.html`/`users-table_sql.html`/`base-users-table-sql.html`/`submit_sql.html` → `..._database.html`), etiqueta de la pestanya "SQL" → "Bases de Dades", i migració de dades que actualitza `ProblemGroup.full_name` de "Bases de Dades (SQL)" a "Bases de Dades". **Deliberadament NO es toca cap nom intern** (camps de model com `Profile.sql_points`, mètodes com `calculate_sql_points()`, variables com `is_sql_problem`/`sql_group_id` a `judge/views/problem.py`, el `name='sql'` del `ProblemGroup`) —només la seva lògica es generalitza per cobrir Mongo, mai el nom.
2. **Infraestructura web genèrica** (Milestone 2): nou camp `ProblemData.mongo_db` i entrada `CHECKERS` (migració de schema `0144`); `DATABASE_CHECKERS = ('sql', 'mongo')` centralitzat a `judge/utils/problem_data.py` i reutilitzat arreu on abans només es mirava `checker == 'sql'` (`ProblemSubmit.is_sql_problem`, el flag `is_sql_problem` de `ProblemDetail`, `make_checker()`); `MONGO_SAMPLE_DATABASE_INFO`/`get_mongo_sample_databases()` calcats dels equivalents SQL, escanejant `.json` en lloc de `.db`; camp `mongo_template` al formulari de dades, amb el mateix mecanisme de còpia; `ProblemDatabaseSchema` bifurcat per mostrar taules (SQL) o col·leccions amb document d'exemple (Mongo); `templates/problem/database.html` amb renderitzat condicional segons `db_kind`.
3. **El checker `dmoj/checkers/mongo.py`** (Milestone 3, fora d'aquest repositori): calcat de l'arquitectura de `sql.py`, però amb `mongomock` (llibreria en memòria, pur Python, sense procés servidor) en lloc de SQLite —**verificat empíricament abans de dissenyar-hi res que `mongomock` no implementa mai JavaScript** (`$where` → `NotImplementedError`, `$function`/`$accumulator` → `OperationFailure`), una propietat estructural de seguretat semblant a la de SQLite. Format de consulta restringit `db.<col·lecció>.<mètode>(<JSON estricte>)`, parsejat amb `json.JSONDecoder().raw_decode()` (parser JSON estàndard, no un mini-parser JS fet a mà). Mètodes permesos: `find`, `insertOne`, `insertMany`, `updateOne`, `updateMany` —cap `delete*`/`drop*`/`aggregate`, coherent amb la mateixa restricció del checker SQL. Detecció automàtica de mode lectura/escriptura des de la referència del `.out`, igual que SQL. En mode escriptura, dos `mongomock.MongoClient()` independents (l'alumne i la referència), cadascun carregat de zero des del mateix JSON —aquí no calen còpies de fitxer com a SQLite, ja que `mongomock` viu només en memòria. Bloqueig explícit (segona xarxa de seguretat) de `$where`/`$function`/`$accumulator`/`$expr` a qualsevol nivell de niuament dels arguments.
4. **Dues bases de dades d'exemple i dos problemes reals** (Milestone 4): `/judge/_mongo_templates/employees.json` (equivalent conceptual a la BD SQL "Employees") i `blog.json` (articles amb comentaris **niats** dins de cada document, un exemple genuïnament no relacional). Problemes `mongofindemployees` (3 preguntes `find()`) i `mongoblogposts` (`insertOne`+`updateOne` amb `$push`/`$inc`), autor `edgar`, creats programàticament igual que els problemes SQL anteriors (entrades #22 i #25).

**Per què:** petició explícita de l'usuari per afegir MongoDB com a segona tecnologia de bases de dades, després d'una pregunta exploratòria sobre si el mateix sistema podria funcionar amb Mongo (l'avantatge de SQLite —un sol fitxer, fàcil de copiar— no té equivalent directe, d'aquí la substitució per `mongomock`).

**Incident durant la posada en marxa:** els checkers de DMOJ es registren a `dmoj/checkers/__init__.py` amb un `from dmoj.checkers import (..., sql)` explícit —un mòdul nou (`mongo.py`) no apareix automàticament com a atribut del paquet en un procés Python ja en marxa, encara que el fitxer ja existeixi al disc (a diferència d'editar un mòdul ja carregat, on n'hi hauria prou amb reiniciar). Es va detectar en la primera tanda de proves reals (`InvalidInitException: error loading checker: module 'dmoj.checkers' has no attribute 'mongo'`), es va afegir `mongo` a la llista d'imports de `__init__.py`, i es va reiniciar el procés del jutge (`dmoj -c judge.yml -p 48462 localhost`, localitzat recuperant l'historial de la sessió `screen` on corre).

**Resultat:** `manage.py check`/`makemigrations --check` nets. Verificat en viu sense regressió: `/users/bd` (rànquing renombrat, mateixos punts), `/problem/provasql2` i el seu editor de dades (`/problem/provasql2/test_data`, ara amb els camps `mongo_db`/`mongo_template` visibles al costat dels de SQL) segueixen funcionant exactament igual. Provat de cap a cap contra el jutge real, després de reiniciar-lo: `find()`/`insertOne`/`updateOne` correctes → `AC`; una resposta equivocada a cada problema → `WA` amb crèdit parcial correcte a les altres preguntes del mateix enviament; `$where` → rebutjat amb "This query uses an operator that is not allowed"; `deleteOne` → rebutjat amb "This Mongo method is not allowed: deleteOne". **Confirmat bit a bit que cap fitxer `.json` (ni les plantilles a `_mongo_templates/` ni les còpies dels problemes) ha canviat** després de totes les proves. Reiniciat també `site` (`uwsgi`, via `SIGHUP` al procés mestre per a una recàrrega neta dels workers); `/tmp/dasdas.log` sense errors nous. Documentació actualitzada: introducció de `5.5-checker-sql.md` referenciant la nova secció `5.8-checker-mongo.md`, taula de checkers a `2.7-jutge-intern.md`, i entrada nova a `TODO.md` sobre l'absència (conscient) d'un límit de temps dur per a consultes Mongo.

---

### 27. Suport per a `aggregate()` al checker Mongo, i cinc problemes Mongo nous (find, insert, update, 2×agregació)

**Abans:** el checker `mongo` (entrada #26) només acceptava `find`/`insertOne`/`insertMany`/`updateOne`/`updateMany`. Només hi havia 2 problemes Mongo reals (`mongofindemployees`, `mongoblogposts`), sense cap que fes servir el framework d'agregació.

**Decisió:**

1. **`dmoj/checkers/mongo.py` ampliat per admetre `aggregate`**: nou mètode permès a `_ALLOWED_METHODS`, tractat com a **lectura** (`_READ_METHODS = ('find', 'aggregate')`), igual que un `SELECT` de SQL —es compara el resultat de la pipeline de l'alumne contra el de la de referència. `aggregate` accepta un únic argument JSON: la llista d'etapes (`[{"$group": ...}, {"$sort": ...}, ...]`). **`$out` i `$merge`** (les dues etapes d'agregació que escriurien a una col·lecció) s'afegeixen a `_FORBIDDEN_KEYS` —es rebutgen pel mateix motiu "esperit SELECT-only" que ja aplicava a `$where`/`$function`/`$accumulator`/`$expr`, no perquè poguessin escapar del client `mongomock` d'un sol ús on corren (no hi ha res a on escapar). `_check_find`/`_run_find` es van generalitzar a `_check_read`/`_run_read` per cobrir tots dos mètodes de lectura amb la mateixa lògica de comparació de documents.
2. **Cinc problemes nous, autor `edgar`**, cadascun amb una base de dades d'exemple pròpia (noves plantilles a `/judge/_mongo_templates/`), seguint l'estil dels problemes SQL (un tema per problema, 2-3 preguntes cadascun):
   - **`mongoselectstudents`** (BD `students.json`, nova: notes d'alumnes per assignatura, 3 preguntes `find()`): filtres simples, projecció, cerca per nom.
   - **`mongoinsertlibrary`** (BD `library.json`, nova: biblioteca de novel·la catalana, 2 preguntes): `insertOne` i `insertMany`.
   - **`mongoupdateinventory`** (BD `inventory.json`, nova: estoc d'una botiga d'informàtica, 2 preguntes): `updateOne`+`$set` i `updateMany`+`$inc`.
   - **`mongoaggregateorders`** (BD `orders.json`, nova: comandes d'una botiga, 2 preguntes): `$group`+`$sum` (total per client) i `$match`+`$group`+`$sort` (recompte de comandes per client per sobre d'un import).
   - **`mongoaggregateblog`** (BD `blog.json`, reutilitzada de l'entrada #26 pels seus comentaris niats, 2 preguntes): `$project`+`$size` (nombre de comentaris per article) i `$unwind`+`$group` (recompte de comentaris per autor, a través de tots els articles) —exactament el tipus de consulta que necessita dades desnormalitzades per tenir sentit.

**Per què:** petició explícita de l'usuari per tenir un conjunt de problemes Mongo "a l'estil dels problemes SQL", cobrint selects senzills, inserts, updates i, com a novetat respecte als problemes SQL existents, el framework d'agregació.

**Resultat:** cada consulta de referència **calculada a mà i verificada contra les dades reals amb `mongomock` abans de crear cap problema** (no es va confiar en la intuïció per a les agregacions). `manage.py check` net. Provats els 5 problemes de cap a cap contra el jutge real, després de reiniciar-lo (calia perquè s'havia editat el cos de `mongo.py`, a diferència de l'entrada #26 on només calia registrar un mòdul nou): totes les respostes correctes → `AC` a puntuació completa; una resposta amb un valor equivocat a cada problema → `WA` amb crèdit parcial correcte a les altres preguntes; un intent de `$out` i un altre de `$where` dins una agregació → rebutjats amb el missatge de seguretat esperat, sense afectar la correcció de l'altra pregunta del mateix enviament. **Confirmat bit a bit que cap fitxer `.json` (ni les 4 plantilles noves, ni `blog.json` reutilitzat, ni les còpies dins de cada carpeta de problema) ha canviat** després de totes les proves.

---

### 28. Corregit forat de permisos a `ProblemsByOrganization` (`/organization/<id>-<slug>/stats`)

**Abans:** `ProblemsByOrganization` (`judge/views/problem.py`) no comprovava cap permís ni pertinença: qualsevol visitant, fins i tot no autenticat, que endevinés l'identificador numèric d'una organització podia veure la graella completa de "qui ha resolt/intentat cada problema" (`templates/organization/stats.html`) de tots els seus membres, amb enllaç directe als seus enviaments —detectat durant l'auditoria de la secció 2.5 de la documentació, anotat a `TODO.md` entrada #4.

**Decisió:** afegit un control d'accés a `get()`, seguint el mateix patró ja establert a `judge/views/organization.py` (`can_edit_organization`/comprovació de pertinença via `org.members.filter(...)`): es carrega l'organització una sola vegada (`self.org`, reutilitzat després a `get_context_data` en lloc de tornar-la a consultar), i només es permet continuar si el visitant és **membre** (`org.members.filter(id=profile.id).exists()`) o **administrador/registrant** (`org.admins.filter(...)` o `org.registrant_id == profile.id`) de l'organització; en cas contrari, `Http404()` —mateix comportament que la resta de vistes d'organització quan no es té accés, per no revelar ni tan sols l'existència de la pàgina.

**Per què:** petició explícita de l'usuari per tancar aquest forat de seguretat, ja documentat a `TODO.md`.

**Resultat:** provat contra una organització real (`1r DAM 24-25 IES Jaume II`, id 141) amb quatre perfils diferents: anònim → `404`; usuari autenticat però no membre → `404`; membre normal → `200`; administrador de l'organització → `200`. `manage.py check` net. Entrada retirada de `TODO.md`.

---

### 29. Gacha: animació de partícules i so sintetitzat en revelar el premi, i un bug real de producció corregit pel camí

**Abans:** la revelació del premi del gacha (`templates/gacha/gacharesult.html`) era només una targeta 3D en CSS que gira en fer-hi clic, sense cap efecte visual ni so —anotat directament per l'usuari a `TODO.md` entrada #5.

**Decisió**, amb les opcions triades explícitament per l'usuari:

1. **So**: sintetitzat amb la Web Audio API (`playGachaSound()`) —sense cap fitxer d'àudio (no n'hi havia cap al repositori), un petit arpegi d'oscilꞏladors amb una nota més per cada nivell de raresa (comú→1 nota, llegendari→4 notes, timbre "triangle" en lloc de "sine" per a llegendari). Anotat a `TODO.md` (entrada #5, reescrita) com a possible substitució futura per àudio real, a petició de l'usuari.
2. **Animació**: un esclat de partícules fet a mida en `&lt;canvas&gt;` (`burstGachaParticles()`), sense cap llibreria nova —més partícules, més velocitat i una paleta de colors pròpia com més alta és la raresa (verd→blau→lila→taronja/groc). El canvas es superposa a la targeta amb `pointer-events: none` perquè els clics continuïn arribant a la targeta.
3. Tots dos efectes es disparen **una sola vegada**, la primera vegada que la targeta gira cap al revers (`gachaRevealed`, per no repetir-los si l'usuari torna a girar la targeta per mirar-la).

**Bug real de producció trobat i corregit pel camí** (no relacionat amb la petició, però bloquejava les meves pròpies proves): el missatge que es mostra quan el premi surt repetit ("...et torno un 50% dels teus GachaPoints") conté un `%` literal seguit d'un espai i una `d` ("50% dels"). Jinja2 aplica sempre `cadena % variables` a qualsevol `_()`/`{{ _(...) }}`, encara que `variables` sigui buit —i Python interpreta "% d" com un format `%d` amb bandera d'espai, cosa que **provocava un error 500 real per a qualsevol usuari** (incloent l'idioma per defecte `en`) que obtingués un premi repetit. Corregit escapant-lo com `50%%` a la plantilla i actualitzant `manage.py makemessages`+els `msgstr` ja traduïts (es/en/de/zh_Hans) amb el mateix escapament, sense fuzzy. Es documenta com a possible patró repetit en altres textos amb `%` literal dins de `_()`, pendent d'una auditoria més àmplia si mai cal (no s'ha fet ara, fora de l'abast d'aquesta petició concreta).

**Incident durant la correcció d'aquest bug**: en un primer intent de pedaç ràpid amb `polib` (assignar `entry.previous_msgid = []`), la crida a `po.save()` va petar per una API mal usada, i en investigar-ho es va executar per error `git checkout -- locale/ca/LC_MESSAGES/django.po`, **desfent tots els canvis sense confirmar d'aquest fitxer** (no n'hi havia cap còpia de seguretat prèvia, ja que cap d'aquesta sessió s'havia arribat a fer commit). Anàlisi de l'impacte real: com que el català és l'idioma font dels textos (`msgid`), un `msgstr` buit ja mostra el text correcte per fallback —la diferència perduda era només bibliogràfica (comentaris de número de línia, marques `fuzzy` netejades) i no afectava cap traducció real ni cap comportament en producció. Es va optar per **no** intentar una recuperació arriscada a partir del `.mo` ja compilat (una re-serialització amb `msgunfmt` hauria perdut comentaris/ordre de totes maneres), sinó pel camí correcte i net: `manage.py makemessages` per a totes les llengües (regenera `ca` des de zero, correctament) seguit de la correcció manual només dels 4 `msgstr` afectats (es/en/de/zh_Hans) amb `polib`, sense el bug de l'intent anterior.

**Per què:** petició explícita de l'usuari (juntament amb les entrades #3, #4 i #6 del `TODO.md`); les decisions concretes de disseny (so sintetitzat vs. fitxers reals, canvas vs. només CSS) es van triar amb l'usuari via preguntes explícites abans d'implementar-les.

**Resultat:** provat contra el jutge real amb 25 tirades consecutives (incloent-hi diversos premis repetits, cobrint les 4 raresa), totes retornant `200` sense cap error —abans de la correcció, qualsevol tirada amb premi repetit petava amb un error 500. `manage.py check`/`msgfmt --check` nets per als 5 idiomes. També corregit, aprofitant que es tocava el mateix fitxer, un bug de visualització preexistent: dos elements amb `id="desc"` duplicat (HTML invàlid) feien que `getElementById("desc")` només trobés el primer, deixant sempre amagada la descripció de l'objecte quan el premi era repetit —ara `desc-repeat`/`desc-item` són ids separats i tots dos es mostren. Reiniciat `site`.

---

### 30. Diagrama ER automàtic a l'explorador d'esquema dels problemes SQL, amb Mermaid.js vendoritzat

**Abans:** l'explorador d'esquema (`/problem/<codi>/database`) només mostrava, per a cada taula, una llista en text de columnes i tipus, sense cap representació de les relacions entre taules —anotat a `TODO.md` entrada #6.

**Decisió**, amb l'opció triada explícitament per l'usuari (vendoritzar una llibreria real, en lloc de dibuixar-ho a mida amb SVG pla):

1. **`resources/mermaid.min.js`** (nou, 3,2 MB): el bundle UMD oficial de Mermaid.js v10.9.1 (llicència MIT), descarregat de `cdn.jsdelivr.net` i desat directament a `resources/` —**no** al submòdul `resources/libs/` (que apunta a l'upstream de DMOJ i no es pot tocar). És l'única manera de "vendoritzar una llibreria real" sense dependre d'un CDN extern en producció, ja que `resources/` (a diferència de `resources/libs/`) sí que forma part d'aquest repositori.
2. **`judge/views/problem.py::ProblemDatabaseSchema`**: la branca `sql` ara també executa `PRAGMA foreign_key_list(<taula>)` per a cada taula (a més del `PRAGMA table_info` que ja hi havia), i marca cada columna com a `PK` (mirant l'últim camp de `PRAGMA table_info`) o `FK` (si apareix a la llista de claus foranes). Amb aquestes dades, una funció nova `_build_er_diagram()` genera la sintaxi `erDiagram` de Mermaid com a text pla —sanititzant noms de taula/columna/tipus amb una expressió regular (`\W` → `_`) abans d'inserir-los, tant perquè Mermaid només accepta identificadors senzills com per no haver de raonar sobre el seu analitzador sintàctic com a segona superfície d'atac.
3. **`templates/problem/database.html`**: la branca `sql` mostra ara un bloc nou "Diagrama ER" amb `&lt;pre class="mermaid"&gt;{{ er_diagram }}&lt;/pre&gt;`, carregant `mermaid.min.js` (sense passar-lo pel pipeline de `django-compressor`, ja minificat) i cridant `mermaid.initialize({startOnLoad: true})` només quan `db_kind == 'sql'` —el flux Mongo no es toca ni carrega mai aquest fitxer.

**Per què:** petició explícita de l'usuari (`TODO.md` entrada #6, agrupada amb les entrades #3/#4/#5 en aquesta mateixa tanda de feina); l'elecció concreta (Mermaid vendoritzat vs. SVG fet a mida) es va triar amb l'usuari via una pregunta explícita.

**Resultat:** provats els 11 problemes SQL existents (`provasql2` i tots els d'`INSERT`/`UPDATE`) contra `/problem/<codi>/database` en viu: `200` a tots, sense cap excepció durant la generació del diagrama. Verificat manualment el contingut generat per `sqlinsertknights` —la columna `Dragons.KilledBy` es marca correctament `FK` i apareix la línia de relació `Knights ||--o{ Dragons : "KilledBy"`— i per `provasql2` (Northwind, amb diverses taules i claus foranes). `manage.py check`/`makemigrations --check` nets; `manage.py collectstatic` executat per publicar el fitxer nou a `/tmp/static/` (`STATIC_ROOT`), on el serveix directament nginx. Reiniciat `site`. **Nota**: `mermaid.min.js` fa servir sintaxi moderna (p. ex. optional chaining) que l'eina local `node -c` (Node 12, del 2020) no pot analitzar —confirmat que és una limitació de l'eina de comprovació local, no del fitxer, ja que el bundle es carrega i executa al navegador de l'usuari final, no sota aquest Node antic.

---

## Nota de manteniment d'aquest document

A partir d'ara, **cada canvi tècnic fet al servidor o al codi (aquesta sessió i les següents) s'ha de documentar amb una entrada nova en aquest fitxer**, seguint el mateix format (abans / decisió / per què / resultat), immediatament després de fer el canvi.
