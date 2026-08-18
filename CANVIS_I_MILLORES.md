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

### 31. Corregit bug real de producció: les preguntes múltiples SQL/Mongo es trencaven amb qualsevol enviament fet des del navegador (CRLF)

**Abans:** l'usuari va detectar que `https://jo-el.es/problem/sqlinsertemployees` "semblava no funcionar". Investigant les submissions reals (`343105`, `343106`), totes dues preguntes d'un enviament amb respostes **correctes** fallaven amb `WA` i el missatge "Only a single SQL statement is allowed" (o, en un altre problema amb el mateix bug, "No answer found for question 1"/"Empty submission").

**Causa:** `_QUESTION_MARKER_RE = re.compile(r'^[ \t]*--[ \t]*@@Q(\d+)@@[ \t]*$', re.MULTILINE)`, a `dmoj/checkers/sql.py` i `dmoj/checkers/mongo.py`, exigia que el marcador `-- @@Qn@@` acabés la línia (`[ \t]*$`). Però el `&lt;textarea&gt;` de `templates/problem/submit_database.html` que uneix les respostes (`build_source()`) genera el text amb `\n`, i **qualsevol navegador normalitza els finals de línia d'un `&lt;textarea&gt;` a `\r\n` (CRLF) en enviar el formulari** —és el comportament estàndard de l'especificació HTML, no un cas rar. Aquest `\r` extra, situat just abans del `\n` de cada marcador, feia que `[ \t]*$` no hi coincidís mai per als marcadors **enmig** del text (només el marcador final, si no tenia cap `\r` darrere per ser el final absolut de la cadena, es detectava —d'aquí la barreja estranya de símptomes entre `sqlinsertemployees` i `sqlupdatetraders`). El checker acabava tractant totes les respostes com un sol text, que després queia pel control "una sola sentència per resposta".

És un bug **sistèmic**: afectava qualsevol problema SQL o Mongo amb més d'una pregunta enviat des del formulari web real, no un problema concret.

**Decisió:** canviar la regex a `r'^[ \t]*--[ \t]*@@Q(\d+)@@[ \t]*\r?$'` (un `\r` opcional abans del final de línia), als dos fitxers.

**Per què:** petició explícita de l'usuari arran d'un problema real que no funcionava en producció.

**Resultat:** reproduïda la submissió `343106` (que abans fallava) directament contra el checker corregit: `AC` a les dues preguntes. Judge (`NouJutge`) aturat net (`Ctrl-C` a la sessió `screen` on corre) i reiniciat (`dmoj -c judge.yml -p 48462 localhost`); confirmat en línia i, rejudicant la submissió real, `343106` va passar de `WA` a `AC` (2.0/2.0) sense intervenir-hi manualment més enllà del reinici.

---

### 32. Checker Mongo: parser propi per acceptar la sintaxi real de la consola Mongo (claus sense cometes), en lloc de JSON estricte

**Abans:** el checker `mongo` exigia JSON estricte (`json.loads`): claus i cadenes sempre amb cometes dobles. Cap pàgina de l'alumne (enunciat, esquema, quadre de resposta) avisava d'aquesta restricció —només ho deia la documentació interna (`docs/05-sistemes-mecanics/5.8-checker-mongo.md`). Detectat arran de la submissió real `343107` a `mongoupdateinventory`: l'usuari va escriure `db.products.updateOne({ _id: 7 }, { $set: { stock: 15 } })` (sintaxi Mongo normal, la que ensenya qualsevol tutorial) i va rebre "Arguments must be valid JSON".

**Decisió**, triada explícitament per l'usuari entre relaxar el parser o només avisar millor a la interfície: **relaxar el parser**. `dmoj/checkers/mongo.py` incorpora un petit parser recursiu-descendent propi (`_JsonLikeParser`) que substitueix `json.JSONDecoder`: accepta claus sense cometes (`_id`, `$set`...), cadenes amb cometes simples o dobles, objectes/llistes niats, `true`/`false`/`null`, números, i comes finals. **No fa servir `eval()` en cap moment** —construeix només `dict`/`list`/`str`/`int`/`float`/`bool`/`None`, així que no obre cap forat d'execució de codi. Deliberadament **no** entén cap sintaxi de crida a funció (`ObjectId(...)`, `ISODate(...)`, `new Date()`), que continua sent rebutjada exactament igual que abans (no són valors vàlids d'aquesta gramàtica). El JSON estricte d'abans continua funcionant idènticament, ja que és un subconjunt d'aquesta gramàtica.

**Per què:** petició explícita de l'usuari, després de detectar que la restricció (una decisió de disseny d'una sessió anterior) no es comunicava enlloc a l'alumne i rebutjava sintaxi Mongo perfectament vàlida.

**Resultat:** reproduïda la submissió `343107` contra el checker corregit amb `_id`/`$set` sense cometes: `AC` a les dues preguntes, `inventory.json` real sense cap canvi (`md5sum` idèntic abans/després). Verificat que `ObjectId("abc")` i similars encara es rebutgen amb un error clar, i que la detecció d'operadors prohibits (`$where`, etc.) continua funcionant igual sobre el resultat ja parsejat. Judge reiniciat per aplicar el canvi.

---

### 33. Marcatge especial, avís per correu i pantalla d'alerta per a intents de consultes destructives (`DROP`, `DELETE`, `$where`...)

**Abans:** un intent d'una consulta destructiva o d'escapar del fitxer assignat (`DROP TABLE`, `DELETE`, `ATTACH DATABASE`, `PRAGMA`, un mètode Mongo com `deleteOne`, un operador com `$where`...) ja es bloquejava des de sempre (mai tenia cap efecte real sobre les dades —vegeu `docs/05-sistemes-mecanics/5.5-checker-sql.md` i `5.8-checker-mongo.md`), però es mostrava a l'alumne exactament igual que qualsevol altra resposta incorrecta (`WA` normal), sense cap registre ni notificació.

**Decisió**, amb les tres peces demanades explícitament per l'usuari:

1. **Marcatge diferenciat**: nou codi de resultat `SEC` ("Security Violation") a `SUBMISSION_RESULT` (`judge/models/submission.py`, migració `0145_security_violation_result`). Els checkers (`dmoj/checkers/sql.py`/`mongo.py`) prefixen el missatge de retorn amb un marcador reservat (`@@SECVIOL@@`) **només** quan el rebuig ve de la llista de paraules/operadors sempre prohibits —**no** quan és un error normal (tipus de sentència equivocat per a la pregunta, múltiples sentències, mètode Mongo correcte però equivocat per aquesta pregunta). `judge/bridge/judge_handler.py::on_test_case` detecta aquest marcador, el treu abans de desar el `feedback`, i posa el cas com a `SEC` en lloc de `WA`; a `on_grading_end`, `SEC` es tracta com el pitjor resultat possible (per davant de `TLE`/`OLE`/etc.) a l'hora de calcular el resultat global de la submissió. Estil CSS propi (`case-SEC`, vermell fort amb text blanc) a `resources/submission.scss`.
2. **Avís per correu**: `_notify_security_violation()` (nou mètode a `JudgeHandler`) envia un correu a `settings.ADMINS` (via `mail_admins`, reaprofitant el backend de l'API de Gmail ja configurat) cada cop que apareix algun cas `SEC`, amb l'usuari, el problema, l'enllaç directe a la submissió, la(les) sentència(es) bloquejada(es) i el codi font complet enviat. `fail_silently=True` i encapsulat en `try`/`except` propi —un problema enviant correu mai ha d'afectar la correcció.
3. **Pantalla d'avís a l'alumne**: `judge/views/submission.py::SubmissionStatus.get_context_data` calcula `has_security_violation` (si algun cas de la submissió és `SEC`); `templates/submission/status-testcases.html` mostra, en aquest cas, un banner vermell (☠) explicant que la consulta no ha tingut cap efecte real però que l'intent ha quedat registrat i notificat al professorat, i que fer-ho en un sistema real podria tenir conseqüències disciplinàries o legals. Traduït als 5 idiomes actius (`ca`/`es`/`en`/`de`/`zh-Hans`).

**Per què:** petició explícita de l'usuari arran d'una conversa sobre què passaria si algú provés un `DROP DATABASE` o similar contra un problema SQL/Mongo real.

**Resultat:** creada i corregida una submissió real de prova a `sqlinsertemployees` (pregunta 1 correcta, pregunta 2 = `DROP TABLE Employees;`): cas 1 `AC`, cas 2 `SEC`, resultat global de la submissió `SEC`. Comprovat en viu, amb el client de test de Django autenticat com a usuari real, que el banner apareix a la pàgina de la submissió, tant en català com en castellà (traducció correcta). Confirmat que l'enviament de correu funciona de veritat (correu de prova rebut sense excepcions). `manage.py check`/`makemigrations --check` nets. Reiniciats `bridged` (via `supervisorctl`, per carregar `judge_handler.py`), `site` (`SIGHUP` net al mestre `uwsgi`) i el judge (per carregar el marcador nou als checkers).

---

### 34. Corregit typo preexistent a `resources/base.scss` (`--background_input: ##3A3A3A`, doble coixinet) que trencava la compilació completa de `resources/`

**Abans:** el tema fosc (`:root[data-theme=theme-dark]`) tenia `--background_input: ##3A3A3A` (doble `#`) —un valor invàlid per a una propietat CSS personalitzada, que fa que qualsevol `background: var(--background_input)` que en depengui caigui al valor heretat/inicial en lloc del gris fosc previst per als camps d'entrada de text en aquest tema. Detectat com a efecte secundari en intentar compilar tot `resources/` d'un cop amb `sass resources:sass_processed` (fallava amb "Expected identifier" a `resources/style.css`, l'artefacte ja compilat que reprocessa el mateix error).

**Decisió:** corregit el doble coixinet a un de sol.

**Per què:** demanat explícitament per l'usuari en assabentar-se'n durant una altra tasca.

**Resultat:** recompilat `resources/style.scss` → `sass_processed/style.css` (net, sense l'error), regenerat `resources/style.css`/`table.css`/`content-description.css`/`ranks.css`/`martor-description.css` amb `postcss`+`autoprefixer` (el mateix conjunt de `make_style.sh`), i confirmat que ara **sí** que es pot compilar tot `resources/` d'un sol cop sense errors (abans només funcionava compilant fitxers individuals). `manage.py collectstatic` executat per publicar els fitxers nous a `/tmp/static/`.

---

### 35. Traduïdes 77 cadenes pendents de `TODO.md` #1 (guies, Tasques, checker SQL/Mongo, gacha, Lliga FP) a ca/es/en/de

**Abans:** `TODO.md` entrada #1 documentava que diverses funcionalitats pròpies d'aquest fork tenien el text ja embolicat en `_()`/`{{ _(...) }}` però mai traduït a cap idioma, perquè `manage.py makemessages` no s'havia tornat a executar des que es van construir. `msgfmt --statistics` confirmava l'abast real: 111/84/1354/1300/399 missatges sense traduir a ca/es/en/de/zh_Hans respectivament, més 68/75/7/10/74 marcats `#, fuzzy` —i els `fuzzy` no eren de fiar: `msgmerge` els havia aparellat per semblança de text amb traduccions antigues no relacionades (per exemple `"task code"` tenia aparellat `"Codi d'accés"`, o `"guide content"` tenia `"Amagar comentaris"`).

**Decisió**, amb l'abast triat explícitament per l'usuari (només les 5 àrees ja llistades a `TODO.md` #1, no tot el backlog general; idiomes ca/es/en/de, deixant `zh_Hans` per a més endavant):

1. Extrets, amb un script `polib`, els 77 `msgid` únics d'aquestes 5 àrees (localitzats pels seus `#: fitxer:línia` a `judge/models/problem.py`, `judge/forms.py`, `judge/models/problem_data.py`, `judge/models/profile.py`, `judge/models/contest.py`, `judge/views/user.py`, i les plantilles de gacha/lliga/guia) que estaven sense traduir o marcats `fuzzy`.
2. **Classificat cada `msgid` pel seu idioma font real** (català o anglès —aquest fork barreja totes dues convencions: `verbose_name`/`help_text` de models en anglès, seguint l'estil DMOJ original, però el text de plantilles pròpies en català) abans de traduir, en lloc de confiar en el `msgstr` `fuzzy` existent. Per als missatges on el `msgid` ja és en l'idioma font d'un fitxer concret (p. ex. un `msgid` català dins de `ca.po`), s'ha buidat el `msgstr` i tret la marca `fuzzy` en lloc de traduir-lo —mateixa convenció que a l'entrada #29 (el buit recorre correctament al `msgid`).
3. Traduïdes les 77 cadenes a `es`/`de` sempre, a `ca` només quan el `msgid` és anglès (53 de les 77), i a `en` només quan el `msgid` és català (24 de les 77) —a la resta, buidat el `msgstr` existent si calia (2 a `ca`, 1 a `en`).

**Per què:** petició explícita de l'usuari per continuar `TODO.md` #1, amb l'abast concretat via preguntes explícites (quines àrees, quins idiomes).

**Resultat:** `manage.py compilemessages` net, `manage.py check` net. Verificat en viu (`django.utils.translation.activate`) que una mostra de 7 cadenes de les 5 àrees es renderitza correctament als 4 idiomes (p. ex. `"SQL checker"` → `"Verificador SQL"`/`"Verificador SQL"`/`"SQL checker"`/`"SQL-Prüfer"` a ca/es/en/de). `msgfmt --statistics` abans → després (només comptant "sense traduir", entrades d'aquestes 5 àrees incloses en el total): ca 111→92, es 84→42, en 1354→1336, de 1300→1231 (la resta del descens ve del backlog general, no tocat). `zh_Hans` sense canvis (fora de l'abast triat). Reiniciat `site` (`SIGHUP` net al mestre `uwsgi`). `TODO.md` #1 actualitzada per reflectir el que queda pendent (les mateixes 5 àrees a `zh_Hans`, i la resta del backlog general).

---

### 36. Nova entitat `Institution`, contenidor real d'equips, i migració de les 160 organitzacions existents

**Abans:** `Organization` ("equip") feia doble funció des de sempre: representava alhora un institut sencer (`Institut Sabadell`, 370 membres) i un grup-classe concret d'un curs (`Institut Sabadell - 1r DAM A`), sense cap relació entre totes dues coses —una barreja que "mai havia tingut massa sentit", en paraules de l'usuari.

**Decisió**, amb l'abast concretat via preguntes explícites (només model + admin en aquesta primera tanda; instituts nous creats a partir d'un esborrany revisat abans d'aplicar-se; imatge amb pujada real de fitxer):

1. **Model `Institution`** nou (`judge/models/profile.py`): `name`, `slug`, `short_name`, `image` (`ImageField`, la primera pujada de fitxer real d'aquest projecte —tota la resta d'"imatges" al lloc són camps de text amb una ruta/URL), `creation_date`. **Sense** `is_open` ni cap mecanisme d'unir-s'hi: mai és un equip obert, és pur contenidor administratiu.
2. **`Organization.institution`**: FK opcional (`null=True, on_delete=SET_NULL`) cap a `Institution`.
3. **Admin**: secció nova "Institutions" (`judge/admin/institution.py`) per crear/gestionar-los; `OrganizationAdmin` ara mostra i permet filtrar per institut (protegit pel mateix permís `judge.organization_admin` que `is_open`/`slots`).
4. **`MEDIA_ROOT`/`MEDIA_URL`** configurats de zero (no existien —tot el sistema d'imatges previ eren rutes de text): `/tmp/media`, servit per un bloc `location /media` nou a l'nginx real de producció (`/etc/nginx/conf.d/nginx.conf`), calcat del bloc `/static` ja existent.
5. **Migració de dades de les 160 organitzacions existents**: proposada com un esborrany complet (agrupació per nom probable, amb nivells de confiança) perquè l'usuari el revisés abans d'aplicar-hi res. Aplicat després de dues rondes de correccions de l'usuari (SVF = Institut Sant Vicent Ferrer, Proven\* = Institut Provençana, i un grup sencer —Institut El Calamot— que se m'havia escapat completament al primer esborrany, detectat en repassar les organitzacions que quedaven sense vincular).

**Per què:** petició explícita de l'usuari per resoldre la confusió estructural entre "institut" i "equip".

**Resultat:** **37 instituts creats, 128 organitzacions vinculades** (149 al final, després de les rondes de correcció), **11 deixades sense vincular** deliberadament (noms de prova/broma: `AAA`, `aaaaaa`, `FuturaFP`, etc.). Provat de cap a cap: pujada real d'una imatge de prova, verificada servida via `nginx` a `/media/institutions/...` (esborrada després). `manage.py check` net, migracions aplicades, `site` reiniciat.

---

### 37. Vistes públiques d'Instituts, bandera/nom de l'institut a les llistes d'usuaris i concursos, i redimensionat de les banderes

**Abans:** l'entitat `Institution` (entrada #36) només existia a l'admin —cap pàgina pública, i les llistes d'usuaris només mostraven la bandera/nom de l'equip.

**Decisió:**

1. **`/institutions/`** (nova pestanya "Institutions" al costat d'"Organizations" dins d'Usuaris): cada institut amb les seves estadístiques agregades (membres, punts, problemes, mitjana —sumats sobre el conjunt *distint* de membres de tots els seus equips, per no comptar dos cops qui és a diversos equips del mateix institut) i, per sota, els equips que en formen part.
2. **`/institution/<id>-<slug>`**: fitxa individual d'un institut, amb imatge i les mateixes estadístiques.
3. **Bandera i nom de l'institut a les 4 taules d'usuaris i al rànquing de concursos**: nova columna de bandera **a l'esquerra** de la de l'equip, i el nom de l'institut en una línia separada dins la mateixa cel·la que l'equip —**sense repetir-se** si l'usuari és a diversos equips del mateix institut (funció Jinja nova i reutilitzable, `distinct_institutions`, `judge/jinja2/organization.py`, en lloc de repetir la lògica de deduplicació a cada plantilla).
4. **Redimensionat de les dues banderes**, a petició de l'usuari en veure-ho en producció: la imatge de bandera de l'equip tenia mides HTML fixes (90×40) que deixaven text incrustat (p. ex. "Institut Sabadell") il·legible; ara la mida la controla el CSS (`resources/users.scss`), amb la columna d'equip a 200px (imatge fins a 190×70) i la d'institut a 150px (fins a 140×70), i la de nom d'usuari reduïda del 35% al 18% de l'amplada, ja que gairebé mai necessita tant espai.

**Per què:** petició explícita de l'usuari, amb el redimensionat com a segona volta després de veure el resultat real en producció (confirmat amb captures de pantalla reals via Chromium headless, no només revisió de codi).

**Resultat:** verificat en viu que el nom de l'institut no es repeteix per a un usuari amb dos equips del mateix institut ("Jaume II" surt un sol cop). Captures abans/després confirmen que el text de la bandera ("Institut Sabadell") ara es llegeix. `manage.py check` net, traduccions nova a ca/es/de, `site` reiniciat.

---

### 38. Concursos: contenidor més ample, congelació del marcador (`freeze_time`), i colors de "first blood"/"resolt fa poc"

**Abans:** tres problemes reportats per l'usuari sobre la pàgina de rànquing de concursos (`/contest/<clau>/ranking/`): (1) el contenidor de la pàgina es limitava als `107em` habituals del lloc, tallant les columnes de problemes en concursos amb moltes preguntes (confirmat amb una captura real d'`xviiicodejam`: es tallava a la columna 9); (2) no hi havia cap manera de "congelar" el marcador; (3) no hi havia cap distinció visual per a qui resol primer un problema ni per a resolucions molt recents.

**Decisió**, amb el comportament de congelació concretat via preguntes explícites (organitzadors veuen sempre el marcador real; descongelar és manual, buidant `freeze_time`; la pàgina de "les meves submissions" mai es congela per a un mateix):

1. **Contenidor ample**: només a `/contest/.../ranking/` (`templates/contest/ranking.html`), `body{max-width:100% !important}`/`#content{width:97% !important}` —no toca cap altra pàgina del lloc.
2. **`Contest.freeze_time`** (nou, `DateTimeField` opcional, editable des de l'admin a "Scheduling"): si es defineix i ja ha passat, `Contest.is_frozen` és cert. `Contest.can_see_frozen_scoreboard(user)` (= `is_editable_by`) decideix qui veu el marcador real.
3. **Càlcul del marcador congelat, sense tocar mai les dades reals**: `BaseContestFormat`/`DefaultContestFormat`/`ICPCContestFormat` guanyen un mètode nou, `get_frozen_state()`, que recalcula `format_data`/`score`/`cumtime`/`tiebreaker` **només amb els enviaments anteriors a `freeze_time`** (mai toca ni desa els camps persistits de `ContestParticipation`, que `update_participation` continua calculant amb dades reals com sempre) i retorna també quins problemes tenen algun enviament posterior (`pending`), mostrats amb una casella grisa ratllada "?" que no revela mai si van anar bé. A `judge/views/contests.py`, `make_contest_ranking_profile` construeix una còpia superficial (`copy.copy`) de la participació amb aquests valors congelats només per a qui no pot veure el marcador real —el rànquing final es **reordena en Python** amb aquests valors (la consulta a la base de dades encara ordena pels valors reals, que mentre està congelat ja no coincideixen amb el que es mostra).
4. **"First blood"** (primer a aconseguir puntuació completa en un problema, entre qui és visible segons el punt anterior): casella daurada amb una estrella. **"Resolt fa poc"** (puntuació completa aconseguida fa 2 minuts reals o menys): casella pulsant (`@keyframes`, respecta `prefers-reduced-motion`). Tots dos calculats a `BaseContestFormat` (mètodes compartits `first_blood_map`/`solve_extra_classes`, memoitzats per petició) i cridats des de `display_user_problem` de `default.py`/`icpc.py` —els únics dos formats de concurs realment en ús en aquest desplegament (82 concursos `default`, 15 `icpc`).

**Per què:** petició explícita de l'usuari, amb el disseny de la congelació (qui veu què, com es descongela) concretat via preguntes abans d'implementar-ho.

**Resultat:** provat contra un concurs real ja acabat (`xviiicodejam`, 884 enviaments dins la finestra en viu), congelant-lo temporalment a un punt intermedi: com a organitzador (superusuari), marcador real, 8 "first blood" reals, cap casella "pendent". Com a visitant normal, banner de congelació visible, 105 caselles "pendent" reals, 7 "first blood" visibles (el 8è quedava amagat perquè la primera resolució real d'aquell problema va ser posterior a la congelació —exactament el comportament esperat), i **l'ordre de classificació canvia realment** a partir de la posició 4 (`faq_equipo1`/`3x2ers` en lloc de `DavidFeliciano`/`Petes`), confirmant que el reordenament amb els valors congelats funciona. Pulsació de "resolt fa poc" verificada amb una prova unitària directa (una resolució simulada de fa 30 segons pulsa; una de fa 5 minuts no). `freeze_time` de prova retirat del concurs real en acabar. `manage.py check` net, traduccions noves a ca/es/de, `site` reiniciat.

---

### 39. Comptador d'intents incorrectes a la casella del rànquing (format `default`)

**Abans:** la casella de cada problema al rànquing (format `default`, 82 dels 97 concursos —l'`icpc`, 15 concursos, ja mostrava això des de sempre com a "penalització") només mostrava els punts i el temps, sense cap indicació de quants intents incorrectes hi havia hagut pel mig, ni si el problema no s'havia arribat a resoldre.

**Decisió:** `DefaultContestFormat` (`judge/contest_format/default.py`) guanya un comptador nou, `tries`, calculat igual a totes dues bandes (`update_participation`, real, i `get_frozen_state`, entrada #38): nombre d'enviaments no-IE/no-CE previs al millor resultat (exclosos ells mateixos si el millor va encertar), o el total d'intents si mai es va encertar. Es mostra en vermell entre parèntesis al costat dels punts —`1 (2)` (resolt, després de 2 intents fallits) o `0 (3)` (no resolt, 3 intents)— reaprofitant l'estil visual que l'`icpc` ja feia servir per a la penalització.

**Per què:** petició explícita de l'usuari.

**Resultat:** com que els concursos `default` ja acabats mai rebran cap enviament nou que disparés el recàlcul, s'ha **recalculat `format_data` de les 3439 participacions existents en concursos `default`** (`fmt.update_participation(p)` per a cadascuna, dins una única transacció, 0 errors, ~25 segons) perquè el comptador aparegui de seguida arreu, no només a partir d'ara. Verificat en viu contra `xviiicodejam`: caselles com `1 (2)`, `1 (6)`, `0 (2)`, `0 (3)` apareixent correctament tant en problemes resolts com no resolts. `manage.py check` net, `site` reiniciat. Cap traducció nova (només un comptador numèric, sense text).

---

### 40. Revelació del gacha, versió totalment exagerada i còmica (estil gacha real)

**Abans:** la revelació del gacha (entrada #29) era una targeta que gira amb un so i un esclat de partícules senzills. L'usuari va demanar explícitament anar molt més enllà: "totalment over-the-top, com en els gachas reals, fins a un punt còmic".

**Decisió**, aplicada amb la mateixa escala progressiva per raresa que fan servir els gachas mòbils de veritat (una raresa comuna es revela quasi a l'instant; la millor raresa té una seqüència de diversos segons), jugada completament seriosa perquè això és precisament el que la fa còmica tractant-se d'un adhesiu de perfil:

1. **Fase de "càrrega"** abans de girar la targeta (0,45s per a comú, fins a 2,4s per a llegendari): l'anell de la targeta pulsa amb una lluentor del color de la raresa, un so sintetitzat de "to que puja" (`playChargeSound`, un oscil·lador en dents de serra amb tremolo) i, per a èpic/llegendari, l'esquena de la pantalla comença a tremolar i uns raigs de sol rotatoris apareixen darrere la targeta.
2. **Flaix i "cop" a l'impacte**: un flaix blanc a tota la pantalla i un so d'impacte (soroll blanc filtrat generat al navegador + un "boom" greu per a èpic/llegendari) al moment exacte en què la targeta comença a girar.
3. **Revelació**: l'arpegi de sempre (ara amb un acord final "fanfara" cursi de debò per al llegendari), diversos esclats de partícules successius (1 a 3 segons l'un de l'altre) per a les raresa altes, pluja de confeti a tota la pantalla per a èpic/llegendari, i un **banner còmic gran** que apareix amb un rebot ("Bé... un més per la col·lecció." per al comú, fins a "★ LLEGENDARI ★ EL MILLOR DIA DE LA TEVA VIDA!!!" amb un fons arc de Sant Martí animat per al llegendari).
4. Tot respecta `prefers-reduced-motion` (sense tremolor de pantalla ni animacions, el banner apareix directament).

**Bug real detectat i corregut abans de publicar-se**: el filtre `|json` d'aquest projecte (`registry.filter('json', json.dumps)`) no marca la sortida com a seguim —cal encadenar-hi `|safe` sempre (com ja fan `organization/stats.html` i `problem/list.html`), o Jinja2 escapa les cometes com a `&#34;`, cosa que trenca la sintaxi de JavaScript dins un `<script>` (les entitats HTML no es descodifiquen mai dins d'un `<script>`) i hauria inutilitzat *tot* el bloc de script, ni tan sols el gir bàsic de la targeta hauria funcionat. Detectat abans de publicar-se perquè es va renderitzar la pàgina real i es va inspeccionar el JavaScript generat en lloc de confiar només en la revisió del codi font.

**Per què:** petició explícita de l'usuari.

**Resultat:** provades les 4 rareses contra registres reals d'`AchievementObtained` (200 a totes 4), i el JavaScript renderitzat final validat amb `node --check` (sintaxi vàlida un cop aplicades totes les substitucions de Jinja2). Verificat **visualment** (no només revisió de codi): es va renderitzar la pàgina real, s'hi va injectar un clic automàtic, i es va capturar amb Chromium headless fent servir `--virtual-time-budget` perquè els `setTimeout`/`requestAnimationFrame` s'executessin abans de la captura —la imatge resultant mostra els raigs de sol rotatoris, la targeta ja girada, i el banner "★ LLEGENDARI ★" amb el degradat arc de Sant Martí, tal com estava dissenyat. `manage.py check` net, traduccions noves dels 4 textos del banner a es/en/de (el català ja n'és l'idioma font), `site` reiniciat.

---

### 41. Gacha: pausa de suspens abans de conèixer la raresa, llegendari encara més exagerat, i 15 frases per raresa (traduïdes)

**Abans:** l'entrada #40 ja feia una revelació molt més dramàtica, però l'usuari en va demanar tres retocs concrets després de veure-la: (1) faltava una pausa d'expectació abans de saber quin color sortiria —ara mateix el color de la raresa es veia des del primer instant; (2) el llegendari s'havia de notar encara més exagerat i "rainbow"; (3) el text del banner era sempre la mateixa frase fixa per raresa, i calia assegurar la traducció i ampliar-ho a 10-20 frases per raresa triades a l'atzar.

**Decisió:**

1. **Un segon de suspens pur** (`GACHA_SUSPENSE_MS = 1000`) abans de cap pista de raresa: la seqüència sempre comença amb una lluentor grisa neutra i un so de càrrega genèric (qualitat 0), idèntic per a totes les raresa —només després d'aquest segon es revela el color/raigs/tremolor propis de la raresa real i continua la resta de la seqüència (entrada #40).
2. **Llegendari encara més exagerat**: temps de càrrega de 2,4s → 3,2s, tremolor de pantalla de 9px → 15px, esclats de partícules de 3 → 5, paleta de partícules ampliada a un arc de Sant Martí complet (abans només tons taronja/vermell). A més, **els raigs de sol i la lluentor de la targeta ara canvien de to contínuament** (`filter: hue-rotate()` animat, classe nova `.rainbow-mode`, només per al llegendari) en lloc de quedar-se en un sol color, i el banner llegendari ara també oscil·la lleugerament (`gacha-banner-wiggle`) per rematar l'excés.
3. **15 frases còmiques per raresa** (60 en total), triades a l'atzar a cada revelació, del deprimentment anticlimàtic per al comú ("Bé... un més per la col·lecció.", "Ah. Val.") fins al totalment desbocat per al llegendari ("EL GACHA HA PLORAT D'EMOCIÓ EN DONAR-TE AIXÒ!!!").

**Bug real de disseny detectat i corregit durant la implementació**: l'extractor `babel`/Jinja2 d'aquest projecte **no detecta cap `_()` fet servir dins d'una llista `{% set %}`** —les 60 frases, escrites així en un primer intent, no apareixien enlloc al catàleg de traducció (0 de 60 extretes), tot i renderitzar-se bé en català (l'idioma font). Solució: renderitzar-les com a text ja traduït dins d'un `<div>` amagat (`#gacha-lines`, un `<span>` per frase amb `{{ _(...) }}` normal, el patró que sí que s'extreu correctament arreu del lloc) i llegir-les des de JavaScript per `textContent` en lloc de construir un array de JS directament amb Jinja.

**Per què:** petició explícita de l'usuari, en tres punts concrets.

**Resultat:** confirmades les 60 frases noves al catàleg de traducció (`polib`, cap ni una perduda) i totes traduïdes a es/en/de (el català ja n'és la font). Verificat en viu que el català i el castellà mostren les 15 frases de la raresa 4 correctament. Verificat **visualment** amb dues captures fetes a diferents `--virtual-time-budget` (700ms: encara en suspens, targeta sense girar, cap pista de color; ~4,8s: targeta girada, raigs ara en verd en lloc de taronja —confirmant el cicle de tonalitats—, confeti visible, i una frase *diferent* de la vista anteriorment —confirmant la tria a l'atzar). `manage.py check` net, `site` reiniciat.

---

### 42. Gacha: el missatge de "premi repetit" integrat a la revelació, en lloc de ser un text pla que feia spoiler

**Abans:** el sistema de premis repetits (existent des de fa temps: si l'alumne ja tenia el mateix premi, es retornava un 50% dels GachaPoints gastats) seguia funcionant correctament per sota, però el missatge que ho explicava ("Però estava repetit...") es feia visible **instantàniament en clicar la targeta** (`document.getElementById("desc-item").style.display = "block"` disparat al primer clic, abans que comencés cap animació) —cosa que espatllava la sorpresa de tota la seqüència dramàtica de les entrades #40/#41: l'alumne ja sabia, abans que la targeta ni tan sols comencés a girar, tant quin premi li havia tocat com si estava repetit.

**Decisió:**

1. **Eliminat l'spoiler**: `desc-item` (nom/descripció del premi) i `desc-repeat` (el missatge de repetit) ja no es mostren en clicar —ara `desc-item` es revela com a part de la seqüència, al mateix moment que el banner i les partícules de la revelació principal (`runGachaSequence`), i `desc-repeat` ja no es mostra mai directament com a paràgraf.
2. **El premi es "destrueix" i es substitueix per GachaPoints**, integrat a la mateixa targeta: ~2,8 segons després de la revelació principal (perquè l'alumne primer gaudeixi el moment gran), si el premi és repetit, la imatge del premi es difumina i es torna grisa (`filter: grayscale + opacity`, transició d'1,1s) mentre esclata un doll de monedes daurades des de la targeta (`burstCoinParticles`, reutilitzant el mateix canvas de partícules) i sona un "womp womp" descendent (`playDuplicateSound`, dues notes que baixen de to, el contrari exacte del so de càrrega ascendent). El banner de raresa (ja esvaït) es reutilitza per mostrar el text real de "repetit" (llegit del `desc-repeat` original via `textContent`, així el missatge —i la seva traducció— és sempre el mateix, no un de nou hardcodejat), amb un estil propi platejat/gris en lloc del color de la raresa.

**Per què:** petició explícita de l'usuari, arran de veure que el missatge de repetit "spoilejava" la nova revelació dramàtica.

**Resultat:** verificat que la lògica de joc (retorn del 50% de GachaPoints) no s'ha tocat, només la seva presentació. Verificat **visualment** amb dues captures a `--virtual-time-budget` diferents sobre una submissió real amb `repe=1`: a ~4,9s la revelació principal surt intacta i sense cap pista de repetit (imatge vibrant, banner normal de raresa); a ~8,5s la imatge ja apareix difuminada/grisa amb restes de monedes daurades, i el banner mostra el missatge real de repetit ("Però estava repetit... Quina llàstima!...") amb l'estil platejat, tal com estava dissenyat. `manage.py check` net, `site` reiniciat. Cap traducció nova (es reutilitza el text de `desc-repeat` ja existent i ja traduït).

---

### 43. Bonus de GachaPoints pel "primer problema nou del dia"

**Abans:** resoldre problemes no donava cap incentiu addicional per dia; els GachaPoints només s'obtenien pels mecanismes ja existents (punts normals del problema). L'usuari va demanar una mecànica nova: la primera vegada que un alumne resol, cada dia, un problema que **no tingués ja resolt anteriorment**, ha de rebre GachaPoints extra de regal.

**Decisió:**

1. **Detecció d'"problema nou"**: es comprova, al moment de rebre el veredicte `AC` (a `judge_handler.py::on_grading_end`, abans de desar l'enviament actual), que no existeixi ja cap enviament `AC` previ del mateix (usuari, problema) i que el problema sigui públic i no restringit a organització —això evita que un enviament duplicat d'un problema ja resolt, o un problema privat d'un concurs, disparin el bonus.
2. **Import: 5 GachaPoints** ("una tirada gratis", tal com va concretar l'usuari), aplicats **restant** del camp `Profile.gacha_points` (aquest camp desa els punts *gastats*, no els disponibles —restar-hi és el que dona punts extra a favor de l'alumne, tal com l'usuari va remarcar explícitament que calia fer).
3. **Frontera de dia = data de calendari de Madrid (Europe/Madrid), no per usuari**: es guarda `Profile.last_daily_solve_bonus_date` i es compara amb `timezone.now()` convertit a `Europe/Madrid`; resoldre a les 23:59 i a les 00:01 (Madrid) compten com dos dies diferents, exactament com va demanar l'usuari, independentment de la zona horària configurada per cada alumne.
4. **Idempotent i segur davant de condicions de carrera**: `Profile.grant_daily_solve_bonus()` fa servir `select_for_update()` dins una `transaction.atomic()`, de manera que si dos enviaments d'un mateix alumne acabessin de jutjar-se gairebé alhora el mateix dia, només un pot arribar a concedir el bonus.
5. **Avís visible**: un banner nou (`daily-bonus-banner`, groc, amb icona d'estrella) a la pàgina de l'enviament, mostrat només si aquell enviament concret va ser el que ha concedit el bonus (`Submission.daily_bonus_awarded`, desat en el moment de jutjar i no recalculat mai després —per exemple, en un rejutjament no reapareix ni desapareix).
6. **Marca persistent a un racó de la pantalla**: una insígnia rodona, taronja i amb pols (`#daily-bonus-badge`, icona de regal), fixa a la cantonada superior dreta de totes les pàgines, visible només si `profile.has_daily_solve_bonus_available` (és a dir, si `last_daily_solve_bonus_date` no és el dia de Madrid d'avui) i desapareix automàticament en el moment que l'alumne cobra el bonus (la pàgina següent que carregui ja no la mostrarà, perquè la condició deixa de complir-se). Enllaça a la pàgina del gacha.

**Per què:** petició explícita de l'usuari, amb tots els detalls (import, restar de `gacha_points`, frontera horària global de Madrid, avís + marca persistent) concretats per ell mateix.

**Resultat:** migració `0149_daily_solve_bonus.py` aplicada (camps `Profile.last_daily_solve_bonus_date` i `Submission.daily_bonus_awarded`). Verificat contra el sistema real: (1) via `manage.py shell`, `grant_daily_solve_bonus()` concedeix els 5 punts un únic cop per dia de Madrid, és idempotent en una segona crida el mateix dia, i torna a concedir-los si es simula un canvi de dia; (2) via el client de test de Django, la insígnia apareix a la pàgina d'inici quan el bonus està disponible i desapareix quan ja s'ha cobrat avui; (3) el banner es renderitza correctament a la pàgina de l'enviament quan `daily_bonus_awarded=True`. Verificat **visualment** amb captures reals de Chromium (sessió autenticada de veritat via el formulari de login, no només cookies injectades): la insígnia taronja amb la icona de regal apareix correctament a la cantonada superior dreta sense xocar amb la barra de navegació, i el banner groc ("First new problem of the day! ... +5 free GachaPoints!") apareix damunt dels resultats d'execució tal com estava dissenyat. Traduccions noves (els 2 camps del model i els 3 textos d'interfície) afegides i compilades a ca/es/en/de. `bridged` reiniciat (calia perquè `judge_handler.py` ha canviat) i `site` recarregat. `manage.py check` net.

---

### 44. Correcció de la mida de les banderes a les llistes d'usuaris i al rànquing de concursos

**Abans:** l'usuari va reportar que les banderes s'havien tornat massa grans. En investigar-ho es va trobar un **bug real** anterior a aquesta petició: la cel·la `<td>` que mostra el logo de l'organització (`orgs[0].logo_override_image`, la columna "Flag") **mai havia tingut la classe `flag`** —només la capçalera `<th class="header flag">` la tenia— així que la regla CSS `#users-table .flag img` (afegida a l'entrada #37) no s'havia aplicat mai a aquesta columna en producció. El resultat era que cada logo es mostrava a la seva mida nativa sense cap límit: la majoria d'escoles tenen logos ja prou petits per casualitat, però alguns (per exemple un meme pujat com a logo per una organització sense nom) es mostraven enormes, trencant les files de la taula.

**Decisió:**
1. **Corregit el bug de la classe que faltava**: afegida `class="flag"` a la `<td>` del logo de l'organització (i a la seva variant buida `{% else %}`) a les 5 plantilles que en repeteixen la mateixa estructura: `templates/user/base-users-table.html`, `base-users-table-lliga1.html`, `base-users-table-lliga2.html`, `base-users-table-database.html` i `templates/contest/base-ranking-table.html`.
2. **Reduïdes les mides màximes** a `resources/users.scss`, ja consistents ara que la regla afecta realment totes dues columnes: bandera d'equip de 190×70px (columna 200px) a **100×40px (columna 110px)**, bandera d'institut de 140×70px (columna 150px) a **80×40px (columna 90px)**.

**Per què:** petició explícita de l'usuari ("ara es massa gran"); el bug de la classe que faltava es va descobrir pel camí en investigar per què una bandera concreta sortia desproporcionadament més gran que la resta tot i compartir la mateixa regla CSS nominal.

**Resultat:** verificat **visualment** amb captures reals de Chromium (sessió autenticada de veritat) abans/després a `/users/` i al rànquing d'`xviiicodejam`: totes les banderes —incloent la que abans es mostrava enorme— ara es veuen a una mida consistent i compacta a totes dues pàgines. `manage.py check` net, CSS recompilat i publicat (`collectstatic`), `site` recarregat. Cap traducció nova (només CSS i un atribut `class` afegit).

---

### 45. Columna de "Classificació" (posició) més estreta, espai alliberat cedit a "Equip" (Organització)

**Abans:** arran de la correcció de mida de les banderes (entrada #44), l'usuari va notar que la columna de posició/classificació ("Rank") havia quedat innecessàriament ampla (117px a la llista d'usuaris) per mostrar només un número d'1 a 4 xifres, mentre que la columna d'Equip/Organització sovint necessita més espai (noms llargs d'instituts i equips que es parteixen en diverses línies).

**Decisió:** la columna de posició compartia la classe CSS `.rank` amb altres columnes sense relació (la d'Icona a la llista d'usuaris, la d'Organització al rànquing de concursos), així que no es podia estrènyer sense afectar-les. Es va afegir una classe pròpia i exclusiva `rank-number` (capçalera i cel·la) a les 5 plantilles que repeteixen aquesta taula (`base-users-table.html` i les seves 3 variants, i `contest/base-ranking-table.html`), fixada a 50px —de sobres per a qualsevol classificació real del lloc. Igualment, la columna d'Organització va deixar de compartir classe amb la d'Usuari (a la llista d'usuaris) o amb la de posició (al rànquing de concursos) i ara té la seva pròpia classe `organization-col`, ampliada del 18% al 24% de l'amplada de la taula.

**Per què:** petició explícita de l'usuari, seguint directament de l'entrada #44.

**Resultat:** verificat **amb mesures reals del DOM** (no només visualment): a `/users/`, la columna de posició ha passat de 117px a 66px, i la d'Organització de 240px a 320px. Verificat també **visualment** amb captures noves a `/users/` i al rànquing d'`xviiicodejam`: la posició ocupa l'espai just i l'Organització es llegeix amb menys línies partides, sense trencar cap altra columna. `manage.py check` net, CSS recompilat i publicat, `site` recarregat. Cap traducció nova.

---

### 46. Nom de l'institut destacat amb negreta i lletra més gran a la llista d'usuaris

**Abans:** dins la cel·la d'Equip/Organització, el nom de l'institut (per exemple "Ins Sabadell") es mostrava amb exactament el mateix estil que el nom de l'equip/classe de sota (per exemple "Institut Sabadell - 1r DAMviA"), cosa que no deixava clar d'un cop d'ull quin dels dos era l'institut i quin l'equip concret.

**Decisió:** afegit un estil propi a `.user-institutions` (`resources/users.scss`, dins `#users-table`) amb `font-weight: 700` i `font-size: 1.15em`, sense tocar cap altre estil de la cel·la (els noms d'equip de sota mantenen l'aparença de sempre).

**Per què:** petició explícita de l'usuari ("marcar l'Institut d'una forma més clara... lletra més important").

**Resultat:** verificat **visualment** amb captures noves a `/users/` i al rànquing d'`xviiicodejam`: el nom de l'institut ara destaca clarament en negreta i una mica més gran per sobre del nom de l'equip, a totes dues pàgines. `manage.py check` net, CSS recompilat i publicat, `site` recarregat. Cap traducció nova (només CSS).

---

### 47. Bloquejar l'accés directe per URL al resultat de gacha d'un altre usuari, i evitar el 500 en un id inexistent

**Abans:** la vista `GachaResult` (`/gacha/result/<id>-<repe>`) identifica el resultat només per l'`id` d'`AchievementObtained` a la URL, sense cap comprovació de propietari —qualsevol usuari autenticat podia veure el resultat (imatge, nom, descripció del premi) de **qualsevol altre usuari** només canviant l'id a la URL (sense poder-hi interactuar ni que això li afegís res, però violant la privacitat del resultat). A més, un id que no existís (`AchievementObtained.objects.get(...)` sense capturar `DoesNotExist`) provocava un **error 500 real, amb el corresponent correu automàtic a l'administrador**, en lloc d'un simple 404.

**Decisió:** moguda la consulta de l'`AchievementObtained` de `get_context_data` a `get()`, on ara es fan dues comprovacions abans de renderitzar res:
1. Si l'id no existeix (`DoesNotExist`), es respon amb un **404** (`generic_message(..., status=404)`) en lloc de deixar-ho petar.
2. Si l'`AchievementObtained` trobat **no pertany a l'usuari que fa la petició**, es respon amb un **403** (`generic_message(..., status=403)`), sense arribar mai a mostrar cap dada del premi d'un altre usuari.

`get_context_data` reutilitza l'objecte ja validat (`self._ach`) en lloc de tornar-lo a consultar.

**Per què:** petició explícita de l'usuari, en detectar que es podia accedir al gacha d'un altre per URL i que un id inexistent generava un error gros amb correu a l'admin.

**Resultat:** verificat amb el client de test de Django amb 3 casos reals: el propi resultat (200, es veu amb normalitat), el resultat d'un altre usuari (403, bloquejat), i un id que no existeix (404, ja no 500). Verificat que els textos es renderitzen correctament en català ("Permís denegat", "No existeix aquest resultat de gacha"). Traduccions noves afegides i compilades a ca/es/en/de. `manage.py check` net, `site` recarregat.

---

### 48. Concursos "en grups": nom de grup triat per l'alumne en lloc del nom d'usuari a la classificació

**Abans:** en unir-se a un concurs, un participant sempre s'identificava (a la classificació, etc.) pel seu propi nom d'usuari. No hi havia manera de fer que un grup/equip triés un nom propi per aparèixer a la classificació.

**Decisió:**
1. **Nou camp a l'admin de concursos**, dins "Settings": `use_group_names` ("usa noms de grup"), una simple casella de verificació.
2. **Nou camp `ContestParticipation.group_name`**: es fixa un únic cop, en el moment d'unir-se, i mai es torna a modificar.
3. **Flux d'unió al concurs**: si el concurs té `use_group_names` activat i encara no hi ha cap participació amb nom de grup fixat, en clicar "Unir-se" apareix un formulari nou (`contest/group_name.html`, seguint el mateix patró que el ja existent formulari de codi d'accés) demanant el nom de grup abans de crear la participació. Si l'usuari **abandona el concurs i hi torna a entrar**, com que la participació (no acabada) ja existeix amb el nom fixat, es reutilitza directament sense tornar a preguntar ni permetre canviar-lo —tal com es va demanar explícitament. El flux gestiona correctament també el cas (rar) que el concurs tingui alhora codi d'accés i noms de grup, arrossegant el codi ja validat cap al segon pas.
4. **Classificació**: quan el concurs usa noms de grup, la columna que abans deia "Nom d'usuari" ara diu "Grup" i mostra el nom de grup en lloc del nom d'usuari real. Per als organitzadors del concurs, el nom de grup segueix enllaçant al perfil real de l'usuari (per poder gestionar-ho); per a la resta de participants, es mostra com a text pla, sense enllaç.

**Per què:** petició explícita de l'usuari.

**Resultat:** verificat de cap a cap amb el client de test de Django sobre un concurs real creat expressament per a la prova: (1) el primer clic per unir-se mostra el formulari de nom de grup i NO uneix encara l'usuari; (2) enviar el formulari amb un nom uneix l'usuari i desa el nom a la participació; (3) abandonar el concurs i tornar-s'hi a unir reutilitza la mateixa participació (mateix id) amb el mateix nom de grup, sense tornar a preguntar; (4) la classificació mostra el nom de grup ("Els Marcians") amb la capçalera "Grup", com a text pla per a un participant normal i com a enllaç per a un organitzador; (5) provada la regressió amb un concurs normal (`use_group_names=False`): la classificació segueix mostrant el nom d'usuari real i la capçalera "Nom d'usuari", exactament com abans. Comprovat que la casella `use_group_names` apareix a l'admin. Migració `0150_contest_group_names` aplicada. Traduccions noves a ca/es/en/de. `manage.py check` net, `site` recarregat.

---

### 49. Filtre per institut a la llista de Tasques

**Abans:** la llista de Tasques (`/tasks/`) ja es podia filtrar per nom d'usuari i per equip (`Organization`), però no per institut —calia conèixer i seleccionar un per un tots els equips d'un institut per veure només les seves tasques.

**Decisió:** afegit un tercer desplegable "Institution" (`judge/views/problem.py`, `TaskList`), seguint exactament el mateix patró ja existent per als altres dos: una tasca es considera "d'un institut" si el seu autor pertany a algun equip (`Organization`) enllaçat a aquell `Institution`. Es combina amb els altres filtres com un AND (seleccionar institut + usuari només mostra les tasques d'aquell usuari si a més pertany a l'institut triat).

**Per què:** petició explícita de l'usuari.

**Resultat:** verificat amb dades reals (autors de `Institut Sabadell` vs. `Institut El Calamot`): filtrar per un institut mostra només les tasques d'autors d'aquell institut i n'exclou les de l'altre, sense filtre es veuen totes dues, i combinat amb el filtre d'usuari es comporta com un AND correctament. `manage.py check` net, traducció nova a ca/es/en/de, `site` recarregat.

---

### 50. Activada la generació de PDF dels enunciats de problemes (sense necessitat de Pdfoid)

**Abans:** `HAS_PDF` era `False` i el botó "View as PDF" no sortia mai a cap problema —cap dels quatre motors de renderitzat que suporta aquest fork (`PhantomJSPdfMaker`, `SlimerJSPdfMaker`, `PuppeteerPDFRender`, `SeleniumPDFRender`, tots ja implementats a `judge/pdf_problems.py`) estava activat. La guia oficial de DMOJ que coneixia l'usuari només parla d'instal·lar un servei extern (Pdfoid, via Selenium+un servidor REST propi), pensat per a la versió original del projecte.

**Decisió:** aquest fork **ja no necessita Pdfoid** —`SeleniumPDFRender` parla directament amb Chrome via Selenium, sense cap servei intermedi. `dmoj/local_settings.py` ja tenia (comentades) les línies exactes que calien, apuntant al `chromium-browser`/`chromedriver` que aquesta sessió ja fa servir per a captures de pantalla:
```
USE_SELENIUM = True
SELENIUM_CUSTOM_CHROME_PATH = '/usr/bin/chromium-browser'
SELENIUM_CHROMEDRIVER_PATH = '/usr/bin/chromedriver'
```
**Bug real detectat i corregut durant la primera prova**: amb aquesta configuració mínima, tota renderització fallava per timeout ("PDF math rendering timed out"). Causa: `chromium-browser` és un paquet **snap**, que aïlla l'accés al sistema de fitxers —només pot obrir `file://` sota el directori de l'usuari (`$HOME`), mai sota `/tmp` (el directori temporal per defecte, `DMOJ_PDF_PROBLEM_TEMP_DIR = tempfile.gettempdir()`, on es desa l'`input.html` que Chrome ha de llegir per renderitzar). Afegida una línia nova a `local_settings.py`:
```
DMOJ_PDF_PROBLEM_TEMP_DIR = '/home/ubuntu/pdf_render_tmp'
```
(un directori nou, sota `$HOME`, creat expressament). **`DMOJ_PDF_PROBLEM_CACHE` (`/joder-extras/pdfcache`, el PDF ja generat i servit) no es veu afectat per aquesta restricció**, perquè mai l'obre Chrome directament —només s'hi llegeix/escriu des de Django/nginx.

`exiftool` (opcional, només serveix per posar el títol al PDF com a metadada) **no s'ha pogut instal·lar**: `apt-get install` falla per un problema previ no relacionat amb aquesta petició (un paquet de kernel amb dependències trencades al sistema). Es deixa pendent; sense ell, els PDF es generen igualment bé, només sense el títol incrustat als metadades del fitxer.

**Per què:** petició explícita de l'usuari, seguint la guia oficial de DMOJ —adaptada al fet que aquest fork ja té un camí molt més senzill (Selenium directe) que no requereix cap servei extra.

**Resultat:** verificat contra el procés `site` real (no només `manage.py shell`): `curl` real per HTTPS a `/problem/9barrisqueson13/pdf` i `/problem/laempresadeldiable/pdf` (aquest amb notació matemàtica LaTeX) retornen tots dos `200`, `Content-Type: application/pdf`, i un fitxer PDF vàlid (capçalera `%PDF-`). Provat també amb un problema amb una imatge incrustada a l'enunciat (Chrome la incrusta fidelment al PDF imprès, d'aquí que el fitxer pesi més —comportament esperat, no un error). Confirmat que la memòria cau funciona (segona petició servida en 0,03s, sense tornar a renderitzar). Confirmat que el botó "View as PDF" ja apareix a la pàgina del problema. `manage.py check` net; cap canvi de codi, només configuració, així que només ha calgut recarregar `site` (`sudo kill -HUP`), sense tocar `bridged` ni el jutge.

---

### 51. Revelació "mega fanfare" per a l'sticker especial ("Dret a Crear Achievements"), avís per correu, i accés d'admin al gacha de tothom

**Abans:** tots els llegendaris (`quality=4`) es revelaven amb la mateixa posada en escena (entrades #40-#42). No hi havia manera de fer que un sticker concret destaqués encara més, ni cap avís automàtic quan algú l'obtingués —l'sticker "Dret a Crear Achievements" (l'únic que dona accés a crear nous stickers) depenia que l'alumne mateix enviés un correu manualment, tal com diu la seva pròpia descripció. A més, l'entrada #47 (bloqueig d'accés al gacha d'un altre usuari) impedia també als administradors veure el gacha de qualsevol alumne.

**Decisió:**
1. **Nou camp `Achievement.mega_fanfare`** (booleà, editable des de l'admin), marcat per a l'sticker "Dret a Crear Achievements" (l'únic marcat de moment). Quan un sticker el té activat, la seva revelació:
   - Allarga la fase de "càrrega" un 40% i n'intensifica el tremolor de pantalla i el nombre d'esclats de partícules, per sobre de qualsevol llegendari normal.
   - Fa sonar **`celebracio.mp3`** (l'únic so real d'aquest gacha —la resta són sintetitzats al navegador), publicat a `resources/celebracio.mp3` i servit com a fitxer estàtic normal.
   - Fa aparèixer un **degradat arc de Sant Martí animat que cobreix tota la pàgina** (no només la targeta).
   - Fa desfilar **una autèntica processó d'ànecs de goma (🦆)** creuant la pantalla en onades contínues durant uns 12 segons.
2. **Avís automàtic per correu**: quan un usuari obté un sticker marcat `mega_fanfare`, s'envia un correu als administradors del lloc (`settings.ADMINS`, és a dir, malbareda@ies-sabadell.cat) amb el nom d'usuari, l'sticker obtingut, un enllaç al seu perfil i un enllaç directe al seu resultat de gacha —exactament la informació que abans calia que l'alumne enviés a mà. Seguint el mateix patró ja establert per als avisos de consultes destructives (entrada #33): sempre `fail_silently`, un correu que no arriba mai no ha de trencar la tirada de gacha de l'alumne.
3. **Accés d'administradors al gacha de tothom**: el bloqueig de l'entrada #47 (403 si el resultat no és teu) ara es salta per a `request.user.is_staff` o `is_superuser` —els administradors poden veure el resultat de gacha de qualsevol usuari, la resta segueix exactament igual que abans.

**Per què:** petició explícita de l'usuari.

**Resultat:** migració `0151_achievement_mega_fanfare` aplicada, camp activat per a l'sticker correcte (verificat: `Achievement.objects.get(id=156).mega_fanfare == True`, "Dret a Crear Achievements"). Verificat que `celebracio.mp3` es serveix correctament (`200`, `audio/mpeg`). Verificat el correu amb un backend de prova (sense enviar-ne cap de real durant la verificació): assumpte, destinatari i cos correctes, amb els dos enllaços. Verificat l'accés d'administrador amb el client de test (`200` per a un admin veient el resultat d'un altre usuari real que ja té l'sticker, `403` sense canvis per a un usuari normal, `200` sense canvis per al propietari). Verificat **visualment** amb una seqüència real de captures de Chromium (sessió autenticada de veritat, com a administrador, veient el resultat real d'un altre usuari): es veuen els raigs rosats/arc de Sant Martí de fons, la targeta girada mostrant l'sticker real, el banner llegendari, confeti, i **una desena d'ànecs de goma travessant la pantalla alhora**. `manage.py check` net, `site` recarregat. Cap traducció nova (cap text nou visible a l'usuari, només CSS/JS/so).

**ID per comprovar-ho en producció**: `AchievementObtained` amb id **26101** (usuari `Wenjun`) —visitable a `https://jo-el.es/gacha/result/26101-0` (com a administrador, gràcies al punt 3 d'aquesta mateixa entrada).

---

### 52. Corregit bug real de rendiment: el filtre de nom d'usuari carregava els 14.705 usuaris registrats a cada pàgina (Submissions i Tasques)

**Abans:** l'usuari va reportar que el JS trigava anormalment a la pàgina de Submissions. Investigant l'HTML real que servia el servidor (no només el codi), es va trobar que el desplegable de filtre "Nom d'usuari" contenia **14.705 etiquetes `<option>`** —literalment tots els comptes registrats al lloc (la immensa majoria, registres de bots/spam, a jutjar pels noms). Això feia que la pàgina pesés **~2,1 MB** només per aquest desplegable, i que `select2` (la llibreria del desplegable cercable) hagués d'inicialitzar-se sobre totes aquestes opcions al navegador —exactament el que es notava com "el JS carrega anormalment lent". El mateix patró exacte (`User.objects.all().values_list('username','username')`) existia també al filtre de la llista de Tasques (entrada #49).

**Decisió**, triada explícitament per l'usuari entre dues opcions plantejades (retallar la llista vs. cerca en viu): **cerca AJAX real**, reutilitzant l'endpoint públic ja existent `user_search_select2_ajax` (el mateix que ja fa servir la caixa "Search by handle..." de `/users/`, que retorna com a màxim 20 coincidències per consulta, mai la llista sencera). Els dos desplegables (`judge/views/submission.py`, `judge/views/problem.py`) ja no reben `all_usernames` —només `selected_usernames` (típicament 0 o 1-2 elements), suficient perquè els filtres ja actius es vegin correctament sense haver de tornar a consultar res. Als dos JS (`templates/submission/list.html`, `templates/problem/tasklist.html`) el `select2` del camp d'usuari passa de `matcher` sobre opcions precarregades a `ajax: {url: ...}` amb `minimumInputLength: 1`.

**Per què:** petició explícita de l'usuari en notar lentitud real; en investigar-ho es va trobar la causa concreta i mesurable.

**Resultat:** verificat contra el `site` real: la pàgina de Submissions ha passat de **2.103.790 bytes a 101.978 bytes** (un 95% menys), i el desplegable d'usuari de 14.705 opcions a 0 (o només les seleccionades). Verificat que l'endpoint de cerca (`/widgets/select2/user_search?term=marc`) retorna coincidències reals paginades. Verificat que filtrar per `?username=marc` segueix funcionant idènticament a totes dues pàgines (Submissions i Tasques) després del canvi. `manage.py check` net, imports morts (`User`) eliminats de tots dos fitxers de vistes, `site` recarregat.

---

### 53. Corregida l'amplada del quadre de cerca de "Nom d'usuari" a Submissions i Tasques

**Abans:** just després de l'entrada #52, el quadre de filtre "User Name" havia quedat visiblement minúscul (uns 17px, davant els ~338px dels altres quadres del mateix formulari) i pràcticament il·legible.

**Causa:** `select2` calcula l'amplada del quadre a partir de l'element `<select>` original. Abans, aquest `<select>` es renderitzava sempre amb les 14.705 opcions precarregades, cosa que li donava prou amplada pròpia perquè `select2` la copiés. En treure aquestes opcions (entrada #52), l'element ja no tenia cap amplada pròpia i `select2` el col·lapsava a la mida mínima —exactament com ja els passava, abans d'aquesta sessió, als altres filtres (`#language`, `#status`), que ho tenen resolt amb una regla CSS `width: 100%` explícita.

**Decisió:** afegida la mateixa regla `#username { width: 100%; }` a `resources/submission.scss`, seguint el patró ja existent.

**Per què:** petició explícita de l'usuari, en veure el quadre massa estret arran del canvi de l'entrada #52.

**Resultat:** verificat **amb mesures reals del DOM**: l'amplada del contenidor de `select2` per a `#username` ha passat de 17px a 338px, igual que `#status`/`#language`/`#equip`. Verificat també **visualment** amb captures de Chromium a `/submissions/` i a `/tasks/` (la mateixa regla és global i arregla totes dues pàgines alhora), incloent-hi una captura mentre s'escriu "marc" al quadre, mostrant els suggeriments de la cerca AJAX amb l'amplada correcta. `manage.py check` net, CSS recompilat i publicat, `site` recarregat.

---

### 54. Permisos per als alumnes amb accés limitat a crear stickers: pujar imatge en lloc d'URL, categories restringides, i `mega_fanfare` només per a admins

**Abans:** l'sticker "Dret a Crear Achievements" ([entrada #51](#51-revelació-mega-fanfare-per-a-lsticker-especial-dret-a-crear-achievements-avís-per-correu-i-accés-dadmin-al-gacha-de-tothom)) dona accés a crear noves fites (`Achievement`) des de l'admin, però un cop allà, un alumne amb accés limitat podia: (1) enganxar qualsevol URL externa com a imatge (`logo_override_image` era un simple camp de text), (2) triar **qualsevol** categoria, incloent-hi colors, temes i fonts (pensats només per a l'equip de professorat), i (3) marcar el seu propi sticker com a `mega_fanfare` (l'efecte "molt més que un llegendari normal" + avís per correu als admins).

**Decisió:**
1. **`Achievement.logo_override_image` ara és una imatge pujada de veritat** (`ImageField`, mateix mecanisme que les imatges d'Institut de l'entrada #37), en lloc d'un camp de text amb una URL. **Els ~258 stickers ja existents, amb una URL externa desada com a valor** (p. ex. `https://i.postimg.cc/...`), es continuen mostrant correctament: `FieldFile.url` normalment *fa malbé* una URL absoluta enlloc de retornar-la tal qual (verificat directament, no és un comportament ben conegut de Django que calgués donar per fet), així que s'ha afegit `Achievement.get_image_url()`, que detecta si el valor desat ja és una URL absoluta i, si és així, la retorna directament; només resol via `.url` (el mecanisme normal de fitxers pujats) per als stickers nous.
2. **Categories restringides per rol**: `category` ara té `choices` explícits al model (sticker/icona/color/tema/font/bonus intern). A l'admin (`AchievementAdmin.formfield_for_choice_field`), un usuari que no sigui superusuari només veu —i només pot desar— **sticker** i **icona**; color, tema, font i la categoria interna del bonus de GachaPoints queden fora d'abast, **validat també al servidor** (no és només amagar l'opció al desplegable: enviar `category=3` a mà des d'un compte limitat es rebutja com a valor no vàlid).
3. **`mega_fanfare` només per a admins**: el camp desapareix directament del formulari (`AchievementAdmin.get_fields`) per a qui no sigui superusuari —no es pot ni veure ni, per tant, activar-lo, encara que s'intenti enviar el camp a mà.
4. **Taula de l'admin**: la columna `mega_fanfare` se substitueix per la de **qualitat** (comú/rar/èpic/llegendari) —com que `quality` també té ara `choices`, l'admin ja mostra l'etiqueta llegible en lloc del número (1-4). De pas, la columna d'imatge (abans enllaçava trencat per als 258 stickers antics, pel mateix motiu del punt 1) passa a fer servir `get_image_url()`.

**Per què:** petició explícita de l'usuari.

**Resultat:** verificat contra el sistema real amb un compte de prova amb accés limitat (`is_staff=True`, `is_superuser=False`, únicament els permisos `add_achievement`/`change_achievement`/`view_achievement`, exactament l'escenari real d'un alumne): el formulari només mostra "sticker"/"icona" a categoria i no mostra el camp `mega_fanfare`; intentar enviar `category=3` a mà queda rebutjat (l'sticker no es crea), i enviar `mega_fanfare=on` a mà amb una categoria vàlida es desa igualment com a `False`. Verificat que un superusuari real conserva accés a totes 6 categories i al camp `mega_fanfare`. Verificat la pujada real d'una imatge de prova (es desa, es serveix per `/media/...`, `200`). Verificat que **cap dels 258 stickers existents s'ha vist afectat**: cap URL truncada (calia fixar `max_length=150` explícitament, ja que el valor per defecte d'`ImageField` és 100 i diverses URLs reals superaven els 100 caràcters), i totes seguint mostrant-se correctament via `get_image_url()`. Verificat que la revelació del gacha de l'sticker "Dret a Crear Achievements" segueix funcionant. Migració `0152_achievement_permissions_and_upload` aplicada. Traduccions noves a ca/es/en/de. Dades de prova netejades. `manage.py check` net, `site` recarregat.

---

### 55. Raresa limitada a 1 per als alumnes, i edició/esborrat només dels propis achievements

**Abans:** continuació de l'entrada #54. Un alumne amb accés limitat encara podia pujar la `rarity` d'un sticker per sobre d'1 (fent-lo aparèixer amb més probabilitat que la resta dins la seva qualitat) i podia editar o esborrar **qualsevol** achievement de l'admin, no només el seu propi.

**Decisió:**
1. **`rarity` limitada a 1 per a no-admins**: el camp desapareix del formulari (`AchievementAdmin.get_fields`, mateix mecanisme que ja s'usava per a `mega_fanfare`) per a qui no sigui superusuari. Com que el valor per defecte del model és 1 i el camp mai és editable per a aquests comptes, qualsevol achievement que creïn té sempre raresa 1 —provat també que enviar `rarity=99` a mà queda ignorat.
2. **Nou camp `Achievement.created_by`** (`ForeignKey` a `Profile`, `null=True`, assignat automàticament a `AchievementAdmin.save_model` en crear-se, mai en editar-se). Afegida també a la taula de l'admin (`list_display`) perquè es pugui veure qui ha creat cada entrada.
3. **Editar i esborrar, només els propis**: `AchievementAdmin.has_change_permission`/`has_delete_permission` sobreescrits perquè, quan es demana permís sobre un objecte concret, un compte que no sigui superusuari només el tingui si `created_by` coincideix amb el seu propi perfil. Els superusuaris (els admins reals) mantenen accés total a qualsevol achievement, com sempre.

**Efecte secundari (comportament estàndard de Django, no un bug)**: com que aquests comptes limitats conserven el permís de "veure" (`view_achievement`), poden obrir la pàgina d'edició d'un achievement d'un altre alumne, però Django la mostra automàticament en **mode només lectura** (sense botó de desar, camps deshabilitats) en lloc de donar un error —intentar desar-hi cap canvi de debò es continua rebutjant amb un 403.

**Per què:** petició explícita de l'usuari, continuació directa de l'entrada #54.

**Resultat:** verificat contra el sistema real amb dos comptes de prova amb accés limitat (`student_a`, `student_b`): (1) `student_a` crea un sticker, el camp de raresa no surt al formulari, i enviar `rarity=99` a mà queda ignorat (es desa com a `1.0`); `created_by` queda assignat correctament a `student_a`. (2) `student_b` obrint la pàgina d'edició de l'sticker de `student_a` la veu en mode només lectura (sense botó de desar); un intent real de `POST` per canviar-ne el nom es rebutja amb `403` i el nom no canvia; intentar esborrar-lo dona `403` directament. (3) `student_a` pot editar i **esborrar de veritat** el seu propi sticker (verificat: desapareix de la BD). (4) un superusuari real conserva accés total —camp de raresa visible, i pot obrir/editar l'sticker de `student_a` sense restriccions. Migració `0153_achievement_created_by` aplicada. Dades de prova netejades. `manage.py check` net, `site` recarregat. Cap traducció nova (cap text nou visible per a usuaris normals, només etiquetes internes de l'admin ja cobertes).

---

### 56. Normalitzada a 1 la raresa de tots els achievements el creador dels quals no és en Marc

**Abans:** continuació de l'entrada #55. El camp `created_by` és nou (entrada #55) i, ara mateix, **cap dels 259 achievements existents el té assignat** (ni els d'en Marc mateix, creats abans que existís aquest mecanisme) —tècnicament, "el creador no és en Marc" hi incloïa el 100% dels achievements. D'aquests, 33 tenien una raresa personalitzada diferent d'1 (des de 0,05 fins a 5), incloent-hi l'sticker especial "Dret a Crear Achievements" (raresa 0,05, és a dir 20 vegades menys probable que la resta dins la seva qualitat).

**Decisió**, confirmada explícitament amb l'usuari en veure l'abast real del canvi (afectava l'sticker especial i no només futures creacions d'alumnes): `Achievement.objects.exclude(created_by=<perfil de marc>).exclude(rarity=1).update(rarity=1)`, dins una transacció.

**Per què:** petició explícita de l'usuari.

**Resultat:** 33 achievements actualitzats a `rarity=1.0` (verificats un a un abans i després: "Dret a Crear Achievements" 0,05→1, "Comic Sans"/"Papyrus" 0,5→1, la sèrie "paquirrin..." de 1,5 fins a 5→1, etc.). Verificat que no en queda cap amb raresa diferent d'1 enlloc del sistema. Cap canvi de codi ni de plantilla —només dades— així que no calia recarregar `site`.

---

### 57. Permisos dels "responsables d'institut": administrar equips i editar alumnes, però només dins el seu propi institut

**Abans:** un responsable d'institut amb permís d'administrar organitzacions només podia veure/editar l'equip (`Organization`) concret on constava com a `admins` —cap altre equip del mateix institut, ni que en fos responsable de facto. I qui tenia permís per editar comptes d'usuari (`User`/`Profile`) —per exemple, per ajudar alumnes amb problemes de compte— podia veure i editar **qualsevol** usuari del lloc sencer, sense cap relació amb el seu propi institut.

**Decisió:**
1. **Nou mètode `Profile.administered_institution_ids`**: els instituts en què aquest perfil ja és admin d'algun equip (`Organization.admins`). És la peça compartida per les tres restriccions següents.
2. **`OrganizationAdmin` ampliat, no restringit**: abans, sense el permís especial `judge.edit_all_organization`, un admin només veia/editava els equips on constava directament com a `admins`. Ara, a més d'aquests, també veu/edita **qualsevol altre equip que comparteixi institut** amb algun dels que ja administra —és a dir, passa de "administro aquest equip concret" a "administro tot l'institut d'aquest equip". Qui té `judge.edit_all_organization` (els admins reals) segueix veient-ho tot, sense cap canvi.
3. **`ProfileAdmin` restringit per institut**: abans no hi havia cap restricció pròpia (qualsevol amb permís de model veia tots els perfils). Ara, per a qui no sigui superusuari, `get_queryset` es limita als perfils que són membres d'algun equip dins els instituts que administra —la resta ni tan sols surt a la llista.
4. **Nou `RestrictedUserAdmin`** (`judge/admin/user.py`), que substitueix el `UserAdmin` per defecte de Django per al model `User`: mateixa restricció que `ProfileAdmin`, aplicada des de `User` (via `user.profile.organizations`).
5. Els superusuaris (i, per a organitzacions, qui té `judge.edit_all_organization`) mantenen accés total a tot arreu, sense cap canvi de comportament.

**Per què:** petició explícita de l'usuari.

**Resultat:** verificat contra el sistema real amb un institut de prova, dos equips dins seu (un on l'usuari de prova hi constava com a admin directe, l'altre no) i un tercer equip en un institut diferent, més tres alumnes (un a cada equip): l'usuari de prova pot veure i editar tots dos equips del seu institut (`200` a totes dues pàgines d'edició) però **no** el de l'altre institut (redirigit, "no existeix" —Django amaga els objectes fora de l'abast de `get_queryset` així en lloc de donar un 404 pelat). Mateix resultat exactament amb els perfils i els comptes d'usuari dels tres alumnes de prova: veu els dos del seu institut, no el del tercer. Verificat que un superusuari real segueix veient-ho i editant-ho absolutament tot, sense cap restricció. `manage.py check` net, dades de prova netejades, `site` recarregat.

---

### 58. Descarregades i allotjades internament les imatges externes dels achievements

**Abans:** 257 dels 258 achievements tenien la imatge (`logo_override_image`) apuntant a un enllaç extern (postimg.cc, ibb.co, imgur.com, discord, reddit, github...) —fràgil per definició: qualsevol d'aquests serveis pot esborrar o bloquejar l'enllaç en qualsevol moment i l'sticker deixaria de mostrar-se.

**Decisió:** script (`ThreadPoolExecutor`, fora d'aquest repositori) que per a cada achievement amb imatge externa: la descarrega, la desa amb `logo_override_image.save(...)` (queda allotjada a `/media/achievements/`, servida des del mateix lloc), i actualitza el camp a l'enllaç intern. Fet en diverses passades progressivament més conservadores (menys connexions simultànies, més espera entre peticions) a mesura que alguns servidors (imgur.com, i.ibb.co, postimg.cc) responien amb bloquejos temporals de freqüència (`429`) davant tantes peticions seguides. Per a un grapat de casos especials —enllaços que apunten a la *pàgina* de visualització d'ibb.co/tenor.com en lloc de la imatge directa, enllaços `github.com/.../blob/...` (pàgina HTML, no el fitxer), i un enllaç embolicat de reddit.com— s'ha aplicat una petita conversió coneguda (`github.com/blob/` → `raw.githubusercontent.com/`, extreure la URL real del paràmetre `?url=` de reddit, o llegir l'etiqueta `og:image` de la pàgina) per arribar al fitxer real.

**Per què:** petició explícita de l'usuari.

**Resultat:** **237 de 258 (92%) migrats correctament** a allotjament intern, verificat un a un que cada imatge nova serveix `200` amb el `Content-Type` correcte. **21 pendents**, tots del mateix origen (`i.imgur.com`), que després de tres intents en un interval d'uns 30 minuts continuen rebutjant-se amb `429` —sembla un bloqueig temporal d'imgur.com cap a la IP d'aquest servidor per l'acumulació de peticions, no un problema del script ni dels enllaços en si (que probablement encara són vàlids). Es poden reintentar més endavant (l'script queda desat, o es poden pujar a mà des de l'admin, ara que ja és un camp de pujada d'imatge —entrada #54). Cap canvi de codi en aquesta entrada —només dades— així que no calia recarregar `site`.

---

### 59. Corregit un bug real de l'entrada #57: "estar en un institut" era pertànyer, no administrar, i faltaven permisos al grup

**Abans:** l'usuari va provar l'entrada #57 amb un compte real ("fletxa", del grup "Responsable d'Institut") i va reportar dues coses trencades: la pestanya "Equips" sortia buida, i entrar a la gestió d'usuaris fallava. Investigant-ho amb el compte real (no dades de prova):
1. **Bug real de disseny**: `Profile.administered_institution_ids` es calculava a partir dels equips que el perfil **administra** (`Organization.admins`). Però "fletxa" no consta com a `admin` de cap equip —hi és com a **membre normal**. La intenció original de l'usuari ("les organitzacions en les que ells estiguin") volia dir pertinença, no administració, i jo ho vaig interpretar malament en implementar l'entrada #57.
2. **Permisos incomplets**: el grup "Responsable d'Institut" tenia permisos sobre `Organization` (ja existents, d'abans d'aquesta sessió) però **cap permís sobre `Profile` ni `User`** —així que, encara que la lògica de restricció per institut hagués estat correcta, ningú d'aquest grup podia arribar-hi de cap manera.

**Decisió:**
1. `administered_institution_ids` ara es calcula a partir de **`self.organizations`** (els equips on el perfil és membre), no de `Organization.admins`.
2. Afegits al grup "Responsable d'Institut" els permisos `view_profile`, `change_profile`, `view_user`, `change_user` (edició, no esborrat —tal com es va demanar a l'entrada #57, "permís per editar").

**Per què:** bug real reportat per l'usuari en provar-ho amb un compte real, cosa que va revelar que la meva interpretació original de "en les que ells estiguin" no coincidia amb la intenció real (pertinença, no administració), i que faltava un pas de configuració (permisos del grup) per completar la petició original.

**Resultat:** verificat contra el compte real de "fletxa" (institut real "Institut Sabadell", 19 equips): ara veu i pot editar tots els equips del seu institut, i pot accedir a la gestió d'usuaris i perfils. Verificat també que **no** pot veure ni editar un equip ("1r DAM 24-25 IES Jaume II") ni un alumne (`a25adataftaf`, d'un institut diferent), amb el mateix compte real —redirigit en tots dos casos. `manage.py check` net, `site` recarregat.

---

### 60. Imatges dels equips (Organization) també convertides de URL a pujada, i descarregades internament

**Abans:** com els achievements abans de l'entrada #54, `Organization.logo_override_image` (la bandera/logo d'un equip) era un simple camp de text amb una URL externa.

**Decisió:** exactament el mateix tractament que a les entrades #54/#58: el camp passa a ser una imatge pujada de veritat (`ImageField`, `upload_to='organizations/'`, `max_length=150` conservat per no truncar cap valor existent), amb un nou `Organization.get_image_url()` que detecta valors previs que ja siguin una URL absoluta (`http(s)://`) —o, es va trobar en revisar les dades reals, **dues organitzacions amb una imatge `data:` en base64 ja truncada a 150 caràcters** (dada corrupta d'abans d'aquesta sessió, no arreglable per descàrrega ja que no és una URL— es deixa tal qual, gestionada amb el mateix pass-through) i els retorna sense passar-los per `.url` (que els faria malbé). S'han actualitzat les 7 plantilles que mostren la bandera d'un equip (rànquings, llistes d'usuaris, `solvestatus`/`tasksolvestatus`) i el fallback de logo de capçalera d'un concurs (`judge/views/contests.py`) perquè facin servir aquest mètode.

**Bug real trobat i corregit pel camí**: dues plantilles de l'entrada #54 (`edit-profile.html`, el selector d'icona del perfil, i `user-about.html`, la galeria d'stickers) encara feien servir `achievement.logo_override_image` directament en lloc de `.get_image_url()` —passades per alt en aquella revisió. Amb els 237 achievements ja migrats a pujada interna (entrada #58), això hauria mostrat una ruta relativa trencada (`achievements/xxx.png` en lloc de `/media/achievements/xxx.png`) tan bon punt un alumne triés un d'aquests icones/stickers com a preferit. Comprovat per BD que **cap alumne ho havia triat encara** (0 valors trencats), així que no calia cap reparació de dades, només corregir les dues plantilles.

**Resultat de la descàrrega**: de les 93 organitzacions amb imatge externa, **83 (89%) migrades** a `/media/organizations/`. Queden 12 sense migrar: 6 d'`i.imgur.com` (el mateix bloqueig temporal per excés de peticions que a l'entrada #58) i 6 enllaços realment morts (dominis que ja no existeixen o retornen 404). Verificat amb una mostra real que les imatges migrades es serveixen correctament. Migració `0154_organization_image_upload` aplicada. `manage.py check` net, `site` recarregat.

---

### 61. Cap dependència externa: MathJax i html5shiv vendoritzats localment, icones de vot també allotjades al servidor

**Abans:** la pàgina carregava MathJax (el motor de renderitzat de fórmules matemàtiques) i html5shiv des de `cdnjs.cloudflare.com` a totes les pàgines, i dues icones (vot a favor/en contra d'un enviament) des de wikimedia.org i flaticon.com.

**Decisió:**
1. **MathJax 2.7.5 vendoritzat sencer** a `resources/libs/mathjax/` (descarregat via el paquet npm oficial, retallat de fitxers no necessaris en producció —`test/`, `docs/`, `unpacked/`, manifests de node— però conservant `jax/`, `extensions/`, `fonts/` i `localization/` complets, ja que MathJax carrega aquests fitxers dinàmicament segons la fórmula i l'idioma, i retallar-los a ull hauria arriscat trencar algun cas d'ús). Actualitzades **totes** les referències trobades: `templates/mathjax-load.html` (la càrrega normal de qualsevol pàgina), `templates/problem/raw.html` (la vista especial per a la generació de PDF, entrada #50 —amb URL absoluta pròpia, ja que aquesta plantilla es renderitza com a fitxer local aïllat), `templates/comments/media-js.html`, `resources/dmmd-preview.js` i `resources/martor-mathjax.js` (les tres càrregues sota demanda de MathJax quan es prèvisualitza Markdown amb fórmules).
2. **Bug real trobat i corregit pel camí**: `templates/comments/media-js.html` tenia una URL de MathJax trencada des de sempre (li faltava `MathJax.js` al mig de la URL) —mai hauria funcionat. Corregit en el mateix canvi.
3. **html5shiv** (un pedaç per a Internet Explorer antic, dins un comentari condicional `<!--[if lt IE 9]-->`) descarregat i servit des de `resources/libs/html5shiv/`.
4. **Icones de vot** (👍/👎 a la pàgina d'un enviament) descarregades i servides des de `resources/icons/vote/`.
5. Eliminat `latest.js` del paquet de MathJax vendoritzat —un script auxiliar de MathJax mateix que, si mai s'invocés, consultaria cdnjs/jsdelivr per comprovar la versió més recent; no el fa servir ningú d'aquest projecte, però eliminar-lo talla de soca-rel qualsevol possibilitat que algú el referenciés per error en el futur.

**Limitació coneguda, deixada tal com estava**: l'extensió opcional d'accessibilitat de MathJax (`extensions/a11y/mathjax-sre.js`, el suport de lector de pantalla per a fórmules) té, dins el seu propi codi ja minificat de fàbrica, referències fixes a `cdn.jsdelivr.net` i `cdnjs.cloudflare.com` per a les dades de pronunciació. Només s'activaria si un usuari obre el menú contextual de MathJax i activa explícitament l'accessibilitat —una funcionalitat opcional que ningú fa servir activament en aquest projecte. Modificar el codi ja minificat d'una llibreria de tercers per aquest cas extrem es va considerar més risc que benefici.

**Per què:** petició explícita de l'usuari.

**Resultat:** verificat **en viu i de dues maneres**: (1) capturant totes les peticions de xarxa d'una pàgina de problema real amb Chromium —cap petició a `cdnjs.cloudflare.com` ni a cap altre domini de CDN—, i (2) una pàgina de prova mínima amb una fórmula LaTeX real (`\sum_{i=1}^{n} i = \frac{n(n+1)}{2}`) carregada des de `https://jo-el.es/static/libs/mathjax/MathJax.js`, capturada amb Chromium, mostrant la fórmula renderitzada correctament (sumatori i fracció ben dibuixats). Verificada la **regressió crítica** de la generació de PDF (entrada #50): el mateix problema de prova d'abans torna a generar un PDF idèntic (mateixa mida en bytes) amb el nou MathJax local. `manage.py check` net, `collectstatic` executat (1961 fitxers, ~46 MB nous de MathJax), `site` recarregat.

---

### 62. Els 12 equips restants de l'entrada #60, pujats a mà per l'usuari

**Abans:** de l'entrada #60 quedaven 12 organitzacions sense migrar (6 d'`i.imgur.com` bloquejat temporalment, 6 amb l'enllaç original ja mort).

**Decisió:** l'usuari les ha pujat totes a mà des de l'admin (ara que el camp és una pujada real d'imatge, entrada #60).

**Resultat:** verificat que **les 97 organitzacions amb imatge (100%) ja no en tenen cap d'externa** —`Organization.objects.exclude(...)` amb valor `http` dona 0 resultats. Verificat un a un que els 12 fitxers pujats existeixen al disc amb una mida real (entre 10 KB i 700 KB) i es serveixen correctament (`200`, `Content-Type` d'imatge vàlid: PNG i JPEG). `manage.py check` net. Cap canvi de codi en aquesta entrada —només dades pujades per l'usuari mateix.

---

### 63. Logo dels instituts omplert automàticament a partir dels equips, i nou "Institut JOEL"

**Abans:** cap dels 37 instituts tenia una imatge pròpia (el camp existeix des de l'entrada #37, però mai s'havia omplert). "Institut Club de Fans de Kernel" (un equip de broma/prova, vegeu l'entrada #36) no tenia institut assignat.

**Decisió:**
1. **Logo automàtic**: per a cada institut, s'ha copiat la imatge d'un dels seus equips —preferint l'equip amb **el mateix nom exacte que l'institut** (el cas més habitual, p. ex. equip "Institut Sabadell" → institut "Institut Sabadell"), i si no n'hi ha cap, el primer equip de l'institut que tingui una imatge vàlida (no una URL externa ni la dada `data:` corrupta de l'entrada #60).
2. **Nou "Institut JOEL"**: creat expressament, i "Institut Club de Fans de Kernel" (que no tenia institut) ara hi pertany. Se li ha posat com a logo la imatge del mateix equip (l'únic membre).

**Per què:** petició explícita de l'usuari.

**Resultat: 32 dels 38 instituts (84%) tenen ara logo** (31 de l'ompliment automàtic + Institut JOEL). **6 instituts s'han quedat sense logo**, perquè cap dels seus equips en té una imatge vàlida: **IES San Andrés, Institut Baix Camp, Institut El Calamot, Institut Nicolau Copèrnic, Institut Provençana i Institut Puig Castellar** —caldrà pujar-los-en una a mà des de l'admin si es vol. Verificat amb una mostra real que els fitxers copiats es serveixen correctament (`200`, tipus d'imatge vàlid), i **visualment** amb una captura de la pàgina pública `/institutions/`: cada institut mostra el seu logo correctament, i "IES San Andrés" surt en blanc tal com s'esperava. `manage.py check` net. Cap canvi de codi —només dades.

---

### 64. Traduccions per a les notícies (Blog) i les pàgines planes ("Sobre")

**Abans:** els problemes (`ProblemTranslation`) i les guies (`GuideTranslation`, entrada #12) es podien traduir per idioma, però les notícies del blog i les pàgines planes de la secció "Sobre" (`FlatPage`, el mòdul estàndard de Django) sempre es mostraven en l'idioma en què s'havien escrit, sense cap manera d'oferir-ne una versió en un altre idioma.

**Decisió**, calcada del patró ja establert per `ProblemTranslation`:
1. **Nou `BlogPostTranslation`** (`ForeignKey` a `BlogPost`, `language` + `title`/`content`/`summary`, `unique_together=('post','language')`), amb un inline nou a `BlogPostAdmin`. Nous mètodes a `BlogPost` (`get_translated_title/content/summary`, amb la traducció consultada un sol cop per publicació i reutilitzada per als tres) que retornen la traducció de l'idioma de la petició si existeix, o el contingut original si no. Actualitzats `judge/views/blog.py` (el títol de la pàgina) i les plantilles `templates/blog/content.html` (la pàgina sencera d'una notícia) i `templates/blog/list.html` (la llista de notícies i el requadre de la pàgina d'inici, que l'hereta) —incloent-hi la clau de memòria cau (`{% cache %}`), que ara inclou l'idioma perquè no es mostri en cau el contingut d'un idioma a un altre.
2. **Nou `FlatPageTranslation`** (`ForeignKey` a `flatpages.FlatPage`, un model de Django mateix, no d'aquest projecte). Com que `FlatPage` és un model de tercers sense cap punt d'extensió propi, i aquest projecte serveix les pàgines planes sempre pel mateix camí (`FlatpageFallbackMiddleware` → `views.flatpage()` → `views.render_flatpage()`), s'ha afegit `judge/flatpage_i18n.py`, que substitueix `render_flatpage` (cridat des de `JudgeAppConfig.ready()`, el mateix lloc on ja es feien altres inicialitzacions per efecte secundari) per una versió que, si hi ha una traducció per a l'idioma de la petició, en substitueix el títol i el contingut abans de renderitzar —**sense tocar la BD ni les plantilles existents**, ja que `render_flatpage` ja rep l'objecte per referència i les plantilles simplement mostren `flatpage.title`/`flatpage.content`. Inline nou a `FlatPageAdmin`.

**Per què:** petició explícita de l'usuari.

**Resultat:** verificat en viu, dels dos tipus de contingut i en totes dues situacions (amb traducció i sense): (1) una notícia real (`JOEL 1.5!`) amb una traducció de prova a l'anglès mostra el títol i el contingut traduïts tant a la pàgina pròpia com al requadre de notícies de la pàgina d'inici, i en català (sense traducció) segueix mostrant l'original; (2) la pàgina plana `/sobre/` amb una traducció de prova a l'anglès mostra el títol i el contingut traduïts, i en català mostra l'original; (3) comprovat als dos admins que l'inline de traducció apareix correctament i reflecteix les traduccions ja existents. Migració `0155_blogpost_flatpage_translations` aplicada. Traduccions noves de les etiquetes de l'admin a ca/es/en/de. Dades de prova netejades. `manage.py check` net, `site` recarregat.

---

### 65. Contingut real de traducció per a les 3 notícies fixades, les 5 més recents, i la pàgina "Sobre"

**Abans:** l'entrada #64 va crear la funcionalitat de traducció per a notícies i pàgines planes, però cap notícia ni la pàgina "Sobre" tenien encara cap traducció real escrita —la funcionalitat existia sense contingut.

**Decisió:**
1. **8 notícies traduïdes a es/en/de**: les 3 notícies fixades (`sticky=True`: #27 "JOEL 1.5!", #26 "Finalització de la II Lliga de Programació", #1 "Introducció") més les 5 més recents no fixades (#25, #24, #22, #21, #20), totes originalment en català. S'han escrit 24 files noves de `BlogPostTranslation` (8 notícies × 3 idiomes), traduint el contingut sencer (Markdown, enllaços, imatges, negretes i capçaleres conservats intactes; noms propis d'usuaris/equips/instituts no traduïts). **Cas especial, notícia #20**: el contingut original ja portava, enganxat dins del mateix cos amb un separador `---`, un bloc en castellà afegit a mà; en comptes de duplicar-ho, la traducció al castellà és només aquest bloc ja existent (net, sense el separador ni el text català), i les traduccions a l'anglès i l'alemany parteixen només del text català original.
2. **Pàgina plana "Sobre" traduïda a ca/en/de**: cas particular, ja que el contingut original d'aquesta pàgina està escrit **en castellà** (no en català com la resta del lloc), excepte l'últim apartat ("Com es calculen els punts?"), que ja estava en català des de l'origen. Per tant aquí calia traduir *cap a* el català (no *des de*), a més d'anglès i alemany, conservant intactes tots els enllaços, blocs `<code>` (els correus ofuscats) i les dues imatges (`postimg.cc`) de la fórmula de puntuació.

**Per què:** petició explícita de l'usuari, seguint directament de l'entrada #64.

**Resultat:** verificat en viu contra les 4 combinacions d'idioma (`django_language` ca/es/en/de) per a totes les pàgines afectades (`/`, `/blog/`, cadascuna de les 8 notícies, `/sobre/`): totes retornen `200`, el títol de cada pàgina canvia correctament segons l'idioma (comprovat també el `<title>` HTML), i el contingut del cos es va inspeccionar directament per a casos concrets (capçaleres Markdown renderitzades correctament en alemany a la notícia #27, enllaç a `/user/marc` present, contingut net sense el bloc català incrustat en l'anglès de la notícia #20, blocs `<code>` i imatges de la fórmula intactes a la traducció anglesa de "Sobre"). `manage.py check` net. Cap canvi de codi en aquesta entrada —només contingut.

---

### 66. Esborrat el fitxer mort `templates/about/about.html`

**Abans:** aquesta plantilla (entrada #2 de `TODO.md`) tenia el text original del DMOJ de referència
sense adaptar (parlava del "DMOJ Monthly Open Programming Competition", donava `contact@dmoj.ca` com
a contacte, i llistava administradors que no existeixen en aquest desplegament).

**Decisió:** confirmat (`grep` de tot el projecte) que cap vista ni cap altra plantilla la
referenciava enlloc —era un fitxer completament mort, no calia reescriure'n el contingut. S'ha
esborrat el fitxer i el directori `templates/about/`, que ha quedat buit. Treta l'entrada
corresponent de `TODO.md`.

**Per què:** confirmació explícita de l'usuari que no es feia servir enlloc.

**Resultat:** `manage.py check` net. Cap altre canvi de codi.

---

### 67. Límit de temps dur al checker Mongo (entrada #7 de `TODO.md`)

**Abans:** el checker Mongo (`dmoj/checkers/mongo.py`, al repositori separat del motor de correcció
—`~/dmojsite/lib/python3.8/site-packages/dmoj`, `github.com/malbareda/JODER-jutge`) no tenia cap
mecanisme per tallar una consulta que trigués massa, a diferència del checker SQL
(`set_progress_handler` de SQLite). Queda documentat a `docs/05-sistemes-mecanics/5.8-checker-mongo.md`
i anotat com a pendent a `TODO.md`, entrada #7.

**Decisió:** implementat `_run_with_timeout(func, *args, **kwargs)`, exactament com suggeria el
`TODO.md`: executa la crida (`_run_read`/`_run_write`) en un fil (`threading.Thread(daemon=True)`) a
part, i el fil principal hi fa `join(_QUERY_TIME_BUDGET_SECONDS)` (5 segons, el mateix valor que ja
fa servir el checker SQL). Si el fil segueix viu passat el termini, es llença una nova
`_MongoTimeoutError` (subclasse de `_MongoCallError`, així flueix pels mateixos `except` ja existents
sense haver de tocar la resta del checker) amb un missatge clar. **Limitació assumida, tal com ja
anticipava el `TODO.md`**: Python no pot matar un fil en marxa, així que això no interromp la
consulta de veritat, només deixa d'esperar-la —el fil abandonat mai torna a tocar-se des d'aquest
procés (cada crida sempre opera sobre un client `mongomock` acabat de carregar de zero,
`_load_client`, mai compartit entre el fil principal i cap fil vigilat, seguint exactament la
precaució que ja apuntava el `TODO.md` sobre no compartir client entre fils).

**Verificació:** com que aquest checker viu al repositori separat del motor de correcció (procés
"NouJutge", en marxa des del 17 d'agost, en una sessió `screen` independent), calia reiniciar-lo
perquè el canvi tingués efecte —**confirmat explícitament amb l'usuari abans de fer-ho**, ja que és
un procés de producció no tocat en tota la sessió i podia interrompre alguna correcció en curs. Fet
enviant les tecles dins la sessió `screen` existent (`Ctrl+C` + relençar exactament la mateixa
comanda, `dmoj -c judge.yml -p 48462 localhost`, trobada a l'historial de bash). Verificat: (1) totes
les 17 preguntes reals dels 7 problemes Mongo existents (`mongofindemployees`, `mongoblogposts`,
`mongoselectstudents`, `mongoinsertlibrary`, `mongoupdateinventory`, `mongoaggregateorders`,
`mongoaggregateblog`) segueixen corregint-se correctament en mil·lisegons —sense regressió; (2) una
consulta simulada artificialment lenta talla exactament al termini configurat, amb el missatge
d'error esperat, sense esperar mai la consulta sencera; (3) el jutge reiniciat completa correctament
el seu autotest de tots els executors i torna a fer *handshake* amb el servidor ("Judge 'NouJutge'
online"); (4) una submissió real de prova a `/problem/mongofindemployees/submit` (les 3 preguntes,
amb les respostes de referència reals) es va corregir de cap a cap contra el jutge ja reiniciat, amb
resultat `AC, 3.0/3.0` —submissió de prova esborrada després. `manage.py check` net.

---

## Nota de manteniment d'aquest document

A partir d'ara, **cada canvi tècnic fet al servidor o al codi (aquesta sessió i les següents) s'ha de documentar amb una entrada nova en aquest fitxer**, seguint el mateix format (abans / decisió / per què / resultat), immediatament després de fer el canvi.
