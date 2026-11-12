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

### 68. Segon jutge de correcció al mateix servidor ("EdgTest")

**Abans:** un sol procés de jutge ("NouJutge") corregia totes les submissions. Dades reals del
servidor: 8 cores, `load average` 0.12-0.14 (pràcticament idle), 5 GB de RAM lliure, i el procés del
jutge fent servir un 0.1% de CPU en repòs. El motor DMOJ, però, corregeix **una sola submissió alhora
per procés de jutge** (`Judge.current_submission_id`/`current_submission_thread`, un sol slot), així
que amb un únic jutge els 8 cores es quedaven a mitges buits durant moments de molta afluència (p. ex.
la Lliga de Programació, on hi ha entregues quasi simultànies de molts alumnes).

**Decisió:** creat un segon jutge, `EdgTest`:
1. Fila nova a `Judge` (taula de la web) amb `name='EdgTest'` i una clau d'autenticació nova,
   generada aleatòriament (100 caràcters, mateix format que les existents).
2. Còpia de `/judge/judge.yml` a `/judge/judge_edgtest.yml`, amb `id: EdgTest` i la clau nova (la
   resta de la configuració —rutes dels llenguatges, `problem_storage_root: /judge`— idèntica, ja
   que els dos processos només *llegeixen* els fitxers de problemes, mai els escriuen, així que
   compartir el mateix directori entre dos processos no suposa cap conflicte).
3. Llançat en una sessió `screen` pròpia i separada (`edgtest-judge`), amb la mateixa comanda que
   `NouJutge` (`dmoj -c judge_edgtest.yml -p 48462 localhost`) —es connecta al mateix pont
   (`bridged`), que ja sap repartir submissions entre jutges connectats.

**Per què:** petició explícita de l'usuari, després de preguntar si valia la pena vist l'estat real
del servidor. Resposta: sí —el coll d'ampolla no és CPU/RAM (pràcticament buits), sinó el disseny
d'"un jutge = una submissió alhora"; un segon procés dona un segon slot de correcció en paral·lel
sense cap cost pràctic de recursos.

**Resultat:** verificat en viu: (1) el procés `EdgTest` ha completat el seu autotest de tots els
llenguatges i ha fet *handshake* correctament ("Judge 'EdgTest' online"); (2) a la BD, els dos jutges
(`NouJutge` i `EdgTest`) surten `online=True`; (3) una submissió real de prova (`holamon`, en Python),
enviada demanant explícitament el jutge `EdgTest`, s'ha corregit de cap a cap i ha quedat marcada
`judged_on='EdgTest'` amb resultat `AC` —submissió de prova esborrada després. `manage.py check` net.
Cap canvi de codi —només configuració i un procés nou.

---

### 69. Kotlin: eliminat `-include-runtime` per accelerar una mica la compilació

**Abans:** l'usuari va reportar que els enviaments en Kotlin triguen molt, per la lentitud coneguda
de `kotlinc`. El checker compilava sempre amb `kotlinc -include-runtime -d <jar> <font>`, que
empaqueta tot l'stdlib de Kotlin dins del jar de l'alumne a cada compilació, i executava amb
`java -jar <jar>`.

**Decisió:** abans de tocar res, es va **mesurar** l'impacte real: 5 compilacions d'un "Hello World"
amb `-include-runtime` (mitjana 6.31s) contra 5 sense (mitjana 5.79s) —una millora d'uns 0.5s (~8%),
ja que el gruix del temps és arrencar la JVM i carregar el compilador sencer, no l'empaquetat de
l'stdlib. Es va decidir aplicar-ho igualment (guany petit però real i sense cost). També es va
verificar explícitament, a petició de l'usuari, que el canvi no afecta el sandbox: provat amb
l'agent de seguretat real (`java_sandbox.jar` + `java-security.policy`) que codi normal (stdlib
pesant, `readLine`) i codi adversarial (llegir `/etc/passwd`, `ProcessBuilder("id")`) es comporten
**exactament igual** en mode `-cp` que en l'antic `-jar` —la política és un únic `grant {}` sense
`codeBase`, i el "fs jail" del sandbox a nivell de sistema ja és `None` per a Java/Kotlin
(`java_executor.py::get_security`), així que afegir un segon jar al classpath no canvia res d'això.
**Troballa incidental, no relacionada, fora d'abast d'aquesta entrada**: es va detectar que tant
abans com després es pot llegir `/etc/passwd` i executar processos sense cap bloqueig —queda anotat
aquí per si es vol investigar en una altra sessió, ja que no és conseqüència d'aquest canvi.

**Implementació** (`dmoj/executors/KOTLIN.py`, al repositori del jutge):
1. `get_compile_args` ja no passa `-include-runtime`.
2. Nou `get_compiled_file()`: un cop compilat, llegeix el `Main-Class` del manifest del jar
   (`kotlinc` ja el genera correctament tot i no incloure el runtime) en lloc de re-derivar les
   regles de Kotlin per passar de nom de fitxer a nom de classe.
3. `get_cmdline` canvia de `-jar <jar>` a `-cp <jar>:<kotlin-stdlib.jar> <MainClass>`.
4. Nova clau de configuració `kotlin_stdlib`, afegida a `judge.yml` i `judge_edgtest.yml`
   (`/snap/kotlin/current/lib/kotlin-stdlib.jar` —el símlink `current` d'snap es manté estable entre
   actualitzacions). `initialize()` i `autoconfig()` actualitzats per validar/localitzar aquesta ruta.

**Per què:** petició explícita de l'usuari, després de demanar que es mesurés l'impacte abans
d'aplicar-ho, i de preguntar explícitament si podia afectar el sandbox.

**Resultat:** reiniciats els dos jutges (`NouJutge` i `EdgTest`) per aplicar el canvi. Verificat:
(1) el autotest de KOTLIN passa als dos jutges amb la nova comanda (`-cp self_test.jar:.../kotlin-
stdlib.jar Self_testKt`); (2) els dos surten `online=True` i amb Kotlin disponible
(`Judge.runtimes` inclou `KOTLIN`); (3) una submissió real (`holamon`, Kotlin) enviada al jutge
`EdgTest` s'ha corregit de cap a cap amb `AC` —esborrada després. `manage.py check` net.

---

### 70. Incident real: 502 Bad Gateway intermitents — `uwsgi` col·lapsava a 1 sol worker

**Abans (símptoma):** l'usuari va reportar `502 Bad Gateway` intermitents a `jo-el.es` un 30 de
setembre, sense cap canvi conscient al servidor en els dos mesos anteriors.

**Diagnòstic:** `sudo supervisorctl status` mostrava `site` com a `RUNNING`, però `ps aux` només hi
trobava **un sol procés `uwsgi`** (a banda del màster), actiu des del 18 d'agost, amb 554MB de RSS.
Als logs de nginx (`/var/log/nginx/error.log`) hi havia `connect() to unix:///home/ubuntu/dmoj-
site.sock failed (11: Resource temporarily unavailable)` —el sol worker no donava l'abast a la cua
de connexions del socket sota càrrega (trànsit real d'alumnat barrejat amb molt de soroll de bots
escanejant `.aws/credentials`, `.ssh/id_rsa`, `/actuator/heapdump`, etc.), produint 502 intermitents
en lloc d'una caiguda total —consistent amb el que reportava l'usuari (funciona a estones).

`uwsgi.ini` té una configuració d'escalat dinàmic (`cheaper-algo = backlog`, mínim 3, inicial 5,
màxim 7) amb un límit de memòria per worker (`cheaper-rss-limit-hard`) de només **224MB**. Com que un
worker sa d'aquesta aplicació ronda normalment els 550-580MB de RSS sota càrrega real (molt per sobre
d'aquest límit), `uwsgi` els anava matant per excedir-lo, i **el mecanisme de matança per RSS no
respectava el mínim configurat de 3** —confirmat empíricament: després d'un primer reinici, el pool
va tornar a baixar a 1 sol worker en menys d'un minut, reproduint exactament el mateix problema.

**Decisió:** pujar els límits de RSS a valors realistes per a aquesta aplicació concreta
(`cheaper-rss-limit-soft` de 192MB a **750MB**, `cheaper-rss-limit-hard` de 224MB a **1000MB**),
amb marge còmode per sobre dels ~580MB observats en workers sans, mantenint alhora una xarxa de
seguretat real contra una fuga de memòria genuïna. Es manté l'escalat dinàmic (`cheaper-algo`) tal
com estava —el problema no era l'algorisme d'escalat en si, sinó el llindar de memòria massa baix.

**Per què:** l'usuari ho va reportar com a incident actiu i calia una solució ràpida; es va triar
pujar el llindar (en lloc de, per exemple, desactivar `cheaper` del tot) perquè és el canvi mínim que
elimina la causa concreta observada, sense perdre l'estalvi de recursos de l'escalat dinàmic en
moments de poc trànsit.

**Resultat:** reiniciat `site` via `supervisorctl restart site`. Verificat durant més de 2 minuts sota
trànsit real (a diferència del primer reinici, que va col·lapsar en <1 minut): el pool es manté
estable a 3 workers (el mínim configurat), amb RSS entre 180-337MB —ben per sota del nou límit—, i
**zero 502 nous** a `/var/log/nginx/access.log` en aquesta finestra. `manage.py check` net.

**Pendent, no fet en aquesta entrada:** no hi ha rotació de logs per a `/tmp/site.stderr.log` (ha
crescut fins a 46MB sense cap política de `logrotate`); i encara no s'ha esbrinat si el creixement
gradual de RSS (~550MB→581MB observat als logs d'aquests darrers dies) és un lleuger fuita de memòria
real que convindria investigar més endavant, o simplement el rang normal sota càrrega variable.

---

### 71. Mateix incident (#70), continuació: `cheaper` no escalava prou i els 502 van tornar

**Abans (símptoma):** uns minuts després d'aplicar el fix de l'entrada #70 (pujar el límit de RSS),
els 502 van tornar. `ps aux` mostrava els 3 workers configurats com a mínim (`cheaper = 3`) tots
tres saturats (40-55% de CPU cada un, estat `R` continu). Un `strace` breu a un dels workers ocupats
va confirmar que **no estaven penjats ni en bucle**: processaven consultes reals ràpidament (una
`SELECT DISTINCT` sobre `judge_submission`, lectura/escriptura normal de la cache de fitxers a
`/cache`). L'`uptime` del sistema mostrava un load average d'entre 1.6 i 1.8 sobre 8 cores —és a dir,
**sobrava CPU al servidor**; el coll d'ampolla era purament que només 3 processos podien atendre
peticions alhora, i l'algorisme d'escalat dinàmic (`cheaper-algo = backlog`) no pujava per sobre
d'aquest mínim malgrat la càrrega —el mateix mecanisme que ja havia fallat baixant per sota del
mínim a l'entrada #70.

**Decisió:** eliminat l'escalat dinàmic (`cheaper`) del tot, substituït per un **pool fix de 6
workers** (`processes = 6`), deixant marge d'1-2 cores per als processos del jutge, MySQL, celery i
nginx en aquest servidor de 8 cores. Aprofitat el mateix canvi per afegir dues xarxes de seguretat
que no existien: `listen = 256` (cua d'acceptació del socket més gran, per defecte uwsgi en fa
servir una de mida molt més petita) i `harakiri = 30` (si una petició concreta triga més de 30
segons, es mata i es recicla el worker en lloc de deixar-lo bloquejat indefinidament).

**Per què:** l'incident #70 no s'havia resolt del tot —calia deixar de dependre d'un mecanisme
d'escalat dinàmic que ja havia demostrat dues vegades en la mateixa tarda un comportament erroni
(primer col·lapsant per sota del mínim, després no pujant per sobre seu), a favor d'una configuració
fixa i predictible.

**Resultat:** reiniciat `site`. Verificat durant més de 3 minuts sota trànsit real: el pool es manté
constant a 6 workers (sense col·lapsar ni quedar-se curt), i **zero 502 nous** després del breu
moment del reinici mateix. `curl` repetit contra `https://localhost/` (amb `Host: jo-el.es`) retorna
`200` de manera consistent durant tota la finestra de comprovació.

---

### 72. Bug real: la generació de PDF fallava (500) des que es va vendoritzar MathJax (entrada #61)

**Abans (símptoma):** l'usuari rebia sovint `Internal Server Error` a `/problem/<codi>/pdf` per a
problemes que encara no tenien el PDF en caché. Als logs: `GET /problem/escriurebin/pdf => ... 500`
trigant **18,7 segons**.

**Diagnòstic:** reproduït directament (`SeleniumPDFRender`, el backend actiu en aquest servidor,
comprovat que Puppeteer/SlimerJS/PhantomJS no ho estan) cridant el mateix codi que la vista. El log
real de Chrome mostrava:
```
Access to font at 'https://jo-el.es/static/libs/mathjax/fonts/.../MathJax_Main-Regular.woff'
from origin 'null' has been blocked by CORS policy
...
PDF math rendering timed out
```
La pàgina del PDF es carrega a Chrome com a fitxer local (`file:///home/ubuntu/pdf_render_tmp/...`),
i des d'un origen `file://` (que el navegador tracta com `null`), carregar un tipus de lletra
(`.woff`/`.otf`) d'un origen diferent (`https://jo-el.es`) requereix que el servidor enviï la
capçalera `Access-Control-Allow-Origin` —cosa que el CDN de MathJax (usat abans de l'entrada #61)
ja feia per defecte, però que el nostre propi nginx, servint els fitxers vendoritzats des de
`/static`, no enviava mai. Sense els tipus de lletra, MathJax no acaba d'inicialitzar-se, la classe
`.math-loaded` no apareix mai, i el `WebDriverWait(..., 15)` de `SeleniumPDFRender` expira sempre
als 15 segons —una **regressió real de l'entrada #61**, no detectada aleshores perquè la
verificació d'aquella entrada molt probablement va reutilitzar un PDF que ja estava en caché (el codi
només torna a renderitzar si `os.path.exists(cache)` és fals) en lloc de forçar-ne un de nou.

**Decisió:** afegida la capçalera `Access-Control-Allow-Origin: *` al bloc `location /static` de
`/etc/nginx/conf.d/nginx.conf` —segur de fer, ja que tot el que hi ha sota `/static` és contingut
públic i no sensible (CSS, JS, fonts, imatges). **No calia tocar cap PDF ja cachejat**: el codi de
la vista només escriu a la caché (`shutil.move`) després d'un èxit, així que els 637 PDF ja
existents eren tots vàlids (generats abans de la regressió); només fallaven els que encara no
s'havien generat mai.

**Per què:** petició explícita de l'usuari en reportar l'error real.

**Resultat:** `nginx -t` net, `systemctl reload nginx`. Verificat: (1) la capçalera `Access-Control-
Allow-Origin: *` ara surt en una petició real a un fitxer de tipus de lletra; (2) reproduint
exactament el mateix render que abans fallava, ara `success=True` en 2,6 segons (abans 15-19s i
fallava); (3) via el flux real del lloc (`GET /problem/escriurebin/pdf`), `200`, `application/pdf`,
36.727 bytes en 2,8s, i el fitxer ha quedat correctament cachejat a `/joder-extras/pdfcache/
escriurebin.ca.pdf`.

---

### 73. Creació massiva de problemes SQL: comanda `create_db_problems` i 90 problemes de `SELECT`

**Abans:** cada problema de Bases de Dades s'havia de crear a mà (fitxa a l'admin, després pujar BD, `.zip`
amb les consultes de referència i una fila de cas per pregunta a `/problem/<codi>/test_data`). La comanda
`create_problem.py` existent només feia una bastida buida i, a més, està trencada (`problem.types = [...]`
no es pot assignar a un camp M2M en aquest Django).

**Decisió:** nova comanda `judge/management/commands/create_db_problems.py` que fa el mateix que
`ProblemDataView.post` (crear `Problem`, `ProblemData`, copiar la BD d'exemple, generar el `.zip`, crear els
`ProblemTestCase` i cridar `ProblemDataCompiler.generate`) a partir de fitxers JSON de
`problem_batches/sql/<bd>.json`. Opcions: `--dry-run` (només valida), `--replace` (sobreescriu codis ja
existents; per defecte els salta), `--limit N`.
- **Validació prèvia, tot o res:** cada consulta de referència es comprova contra la BD real amb les mateixes
  funcions del checker del motor (`_security_check`, `_execute_sql`); s'exigeix que comenci per `SELECT`, no
  doni error, retorni entre 1 i 200 files, i que tot `LIMIT` tingui `ORDER BY`. Si hi ha cap error, no es crea res.
- El checker del motor es carrega **per ruta de fitxer** (amb stubs temporals de `dmoj.judgeenv` i
  `dmoj.result`) perquè el paquet `dmoj` d'aquest repositori (la configuració del web) amaga el del motor.
- Codi `sql<bd>NN`, grup `sql`, tipus `bdselects`, llenguatge `TEXT`, `partial=True`, 2 s / 64 MB, **privats**
  (`is_public=False`). Autors alternats: senars `edgar`, parells `marc`.
- Els 9 lots (10 problemes per BD, 281 preguntes, dificultat creixent) els han escrit 8 subagents en paral·lel
  (més miniwind fet a mà), cadascun explorant la seva BD i validant amb `--dry-run`.

**Per què:** petició de l'usuari: crear problemes massivament sense fer-los a mà. De moment només `SELECT`, 10 per
BD d'exemple, només SQL (Mongo i `INSERT`/`UPDATE` queden per a més endavant).

**Error corregit pel camí:** la descripció generada deia que "l'ordre de les files importa si l'enunciat ho demana",
cosa falsa (el checker no compara l'ordre si no té `order_matters`, que aquí no es configura). Ara diu que ni
els noms de columna ni l'ordre de files es tenen en compte.

**Resultat:** 90 problemes (`sqlchinook01..10`, `sqlemployees`, `sqlgroupbytest`, `sqlhotel`, `sqlknights`,
`sqllastnames`, `sqlminiwind`, `sqlnorthwind`, `sqltraders`), 45 per autor, 281 casos, 0 errors de compilació,
~290 MB a `/judge` en total. Verificat amb enviaments reals al jutge en viu: `sqlminiwind01` (2 `AC` + 1 `WA`
amb el feedback esperat, 2/3 punts) i el problema 10 de cada una de les 9 BD enviant les respostes de
referència (4/4 `AC` a totes). Tots els enviaments de prova s'han esborrat.

---

### 74. Problemes SQL temàtics de 10 preguntes, tipus "SQL - ..." i solucions visibles d'edgar

**Abans:** els problemes de BD tenien només dos tipus gruixuts (`BD - Selects`, amb 96 problemes, i
`BD - Inserts i Updates`, amb 6), les consultes de referència només vivien al `.zip` de cada problema (cap
alumne les veia) i els lots de l'entrada #73 eren de 3-4 preguntes per problema i una sola BD per lot.

**Decisió i canvis:**
1. **20 problemes temàtics nous de 10 preguntes** (200 preguntes), cadascun sobre una BD diferent d'exemple, en
   lots `problem_batches/sql/tematics_*.json`: 3 de selects bàsics (`sqlsel01-03`), 5 de joins (`sqljoin01-05`:
   `LEFT JOIN`, "l'altra banda" del `LEFT JOIN`, triar el join correcte, joins encadenats, joins mesclats), 5
   d'agregacions (`sqlagg01-05`: només `COUNT`, només `GROUP BY`, `HAVING`, `SUM/AVG/MIN/MAX`, mesclades), 5 de
   subconsultes (`sqlsub01-05`: escalars, `IN/NOT IN`, `EXISTS`, correlacionades, taules derivades) i 2 de
   mesclats (`sqlmix01-02`). Escrits per 4 subagents en paral·lel i validats amb `--dry-run`. Autors alternats:
   10 `edgar`, 10 `marc`.
2. **`RIGHT JOIN` no es pot practicar tal qual:** el SQLite de Python d'aquest servidor és el 3.31.1 i
   `RIGHT JOIN`/`FULL OUTER JOIN` no existeixen fins al 3.39. El problema `sqljoin02` treballa el mateix concepte
   com a "taula protagonista a l'esquerra d'un `LEFT JOIN`", i ho explica a la introducció.
3. **`create_db_problems` ampliada:** ara cada problema pot portar el seu `code`, `database`, `type` i `label`
   (els valors del lot són per defecte, així que els JSON antics funcionen igual), accepta un camp `explain` per
   pregunta, i els autors s'alternen amb un comptador global (abans era per fitxer: amb fitxers de 5 problemes
   donava 12/8 en lloc de 10/10; ja corregit també als 20 creats).
4. **Tipus nous** (substitueixen `bdselects` i `bdinsertupdate`; el nom curt té un màxim de 20 caràcters):
   `SQL - Selects: bàsics / joins bàsics / joins complexos / agregacions bàsiques / agrupacions / subconsultes /
   mesclats`, `SQL - Inserts` i `SQL - Updates`. **Mongo no s'ha tocat** (`BD - Mongo`, 7 problemes), a petició
   de l'usuari, fins a fer-ne la separació.
5. **Reclassificació** dels 102 problemes existents amb la nova comanda `reclassify_sql_problems`
   (`--dry-run` mostra el pla). Els 90 dels lots de #73 es classifiquen per la posició del problema dins del
   lot (totes les BD van seguir la mateixa corba de dificultat), amb 9 excepcions llegides de les consultes reals
   (p. ex. a `employees` i `lastnames` el 7 és de subconsultes; a `groupbytest` el 7 és d'operacions de conjunts);
   els 12 fets a mà (`sqlselects`, `sqljoins`, `sqlagregacions`, `sqldificil`, `provasql*`, els 6 d'insert/update)
   es van assignar un per un. Resultat: 33 bàsics, 8 joins bàsics, 12 joins complexos, 9 agregacions bàsiques, 19
   agrupacions, 4 subconsultes, 11 mesclats, 3 inserts, 3 updates (+ els 20 nous). Els dos tipus antics ja
   estaven buits i s'han esborrat.
6. **Editorials: retirades (vegeu #75).** En aquesta entrada vaig crear una editorial pública (model `Solution`) per
   a cada problema, per un malentès: l'usuari volia un **enviament** correcte d'`edgar`, no una editorial. Les 122
   editorials s'han esborrat (n'hi havia 0 abans) i s'han eliminat `judge/utils/sql_solution.py` i la comanda
   `create_sql_solutions`. El camp `explain` dels JSON dels 20 problemes nous ja no s'usa enlloc (queda com a
   documentació de cada consulta).

**Per què:** petició de l'usuari: problemes de 10 preguntes, temàtics, amb BD canviants; categories més fines
per als selects i per als inserts/updates amb prefix "SQL - " en lloc de "BD - "; una resolució correcta feta per
edgar i visible a cada problema.

**Resultat:** 20 problemes nous (200 casos, 0 errors de compilació). Verificat amb enviaments reals al jutge en
viu: les respostes de referència dels 20 problemes nous donen `AC` complet (200/200 punts). Tots els enviaments de
prova d'aquella comprovació s'han esborrat.

---

### 75. Respostes de referència com a enviaments `AC` d'edgar (en lloc d'editorials)

**Abans:** després de l'entrada #74 (que va crear editorials públiques per un malentès), calia que cada problema SQL
tingués la seva resposta correcta com a **enviament real d'`edgar`, corregit pel jutge amb `AC`**, perquè els professors
la puguin consultar.

**Decisió:** nova comanda `judge/management/commands/submit_reference_answers.py`. Per cada problema de tipus
`SQL - ...`: reconstrueix el text de la resposta des del `.zip` del problema (una consulta de referència per cas,
amb els marcadors `-- @@Q<n>@@` que fa servir el formulari web), crea un `Submission` d'`edgar` en llenguatge `TEXT`,
el fa corregir pel jutge en viu i espera el veredicte, en blocs de 20 (opcions `--chunk`, `--timeout`, `--dry-run`).
Salta els problemes on `edgar` ja té un `AC` amb tots els punts, així que es pot tornar a executar sense duplicar res;
i si algun enviament no treu `AC` complet, el deixa guardat i ho comunica. A més, s'han esborrat les 122 editorials de #74.

**Visibilitat (no s'ha canviat cap regla):** la decideix `Submission.can_see_detail`: la veuen l'autor/editor del problema,
qui té el permís `view_all_submission` (grup "Profe", entre d'altres), el propi usuari, i, als problemes **públics**, els
alumnes que ja han resolt el problema amb tots els punts. L'usuari ja ho sabia i ho va acceptar explícitament. Un alumne
que no ha resolt el problema no veu la resposta.

**Resultat:** 117 enviaments nous, tots `AC` complets (més 3 de la prova prèvia i 2 que `edgar` ja tenia d'abans, fets a
mà): els 122 problemes SQL tenen un `AC` complet d'`edgar` i 0 editorials. Comprovat amb `can_see_detail` sobre un problema
privat i un de públic: veuen la resposta `edgar` i un professor; un alumne que no ha resolt no la veu; un que ha resolt el
públic sí. Efectes secundaris: els enviaments compten a les estadístiques dels problemes (nombre d'AC, usuaris) i a
la puntuació/rànquing d'`edgar` quan els problemes siguin públics.

---

### 76. Problemes SQL d'`INSERT` i `UPDATE` temàtics (10 problemes de 10 preguntes) i validació d'escriptures

**Abans:** `create_db_problems` només sabia validar consultes `SELECT`, i els únics problemes d'`INSERT`/`UPDATE` eren
els 6 fets a mà (3 + 3), d'una o dues preguntes cadascun.

**Decisió i canvis:**
1. **Validació d'escriptures a `create_db_problems`** (`validate_write_question`): una resposta de referència
   d'`INSERT`/`UPDATE` ha de passar el mateix filtre de seguretat que el checker del motor, executar-se sense error
   sobre una còpia temporal de la BD i **canviar-la de debò**. Aquest últim punt és el que més importa: el checker
   puntua comparant l'estat final de totes les taules, de manera que una referència que no canviés res faria donar
   `AC` a qualsevol sentència que tampoc no canviés res. Es rebutgen també `DELETE`, columnes inexistents, etc.
   Comprovat amb casos positius i negatius. Les descripcions generades ara depenen del tipus de pregunta (per a
   escriptures expliquen que cada pregunta s'executa sobre una còpia de la BD original i que es compara tot el
   contingut final).
2. **10 problemes nous, 100 preguntes**, escrits per 2 subagents en paral·lel: 5 d'inserts (`sqlins01-05`, tipus
   `SQL - Inserts`: una fila, llista de columnes parcial i sense llista, diverses files amb un sol `VALUES`,
   `INSERT ... SELECT`, mesclat) i 5 d'updates (`sqlupd01-05`, tipus `SQL - Updates`: bàsic, expressions al `SET`,
   condicions riques i `CASE`, subconsultes, mesclat), cadascun sobre una BD diferent d'exemple. Autors alternats:
   5 `edgar`, 5 `marc`. Tots privats.
3. **Cada pregunta és independent:** s'avalua sempre sobre la BD original, no sobre l'estat que deixaria la
   pregunta anterior; els enunciats donen tots els valors i identificadors explícits (no depenen de cap autoincrement).
4. Limitacions de les BD que van condicionar el contingut: `knights.Knights` té totes les columnes `NOT NULL` sense
   `DEFAULT` (la llista parcial només es practica a `Dragons`); a `chinook` els preus són decimals, així que
   els enunciats demanen `ROUND(..., 2)` explícit o fan servir sumes sobre enters; a `hotel` la validació de cada
   pregunta triga ~0,9 s perquè el checker bolca totes les taules dues vegades; SQLite 3.31.1 no té `UPDATE ... FROM`
   (arriba a la 3.33), així que es fan servir subconsultes.

**Per què:** petició de l'usuari: fer ara els d'inserts i updates, amb els mateixos criteris que els selects.

**Resultat:** 10 problemes nous (100 casos, 0 errors de compilació), tots amb un enviament `AC` complet d'`edgar` fet
amb `submit_reference_answers` (inclòs `sqlupd03`, el de l'hotel). Prova negativa amb enviaments equivocats a `sqlins01`
i `sqlupd01`: `WA` amb el missatge "The database's final content does not match..." (enviaments de prova esborrats).

---

### 77. SQLite 3.51 per al checker SQL (via `pysqlite3-binary`) i `WITH` als `SELECT`

**Abans:** el checker SQL feia servir el SQLite del sistema (Ubuntu 20.04: 3.31.1), sense `RIGHT`/`FULL OUTER JOIN`
(3.39), `UPDATE ... FROM` (3.33), `RETURNING` (3.35) ni funcions matemàtiques; i rebutjava qualsevol resposta que
comencés per `WITH` (CTE), perquè només acceptava la primera paraula `SELECT`/`INSERT`/`UPDATE`.

**Decisió (amb l'usuari, després de valorar-ho amb una segona opinió):** no tocar el SQLite del sistema (apt no en
dona cap de més nou, i substituir-lo podia afectar altres programes), sinó instal·lar un SQLite modern només al
venv del jutge. Tots els jutges del JOEL corren en aquest servidor i amb aquest venv, així que no hi pot haver
jutges amb versions diferents.

**Fet fins ara:**
1. **Còpia de la BD del JOEL** abans de res: `/home/ubuntu/backups/joel-db-dmoj-20261020-231043.sql.gz`
   (`mysqldump --single-transaction`, 133 MB, 95/95 taules, `gzip -t` correcte; credencials passades per un
   fitxer temporal 600, esborrat).
2. **Còpia del checker:** `/home/ubuntu/backups/dmoj-checkers-sql.py.20261020-231150.bak`.
3. **`pysqlite3-binary` 0.5.4.post2** instal·lat al venv `/home/ubuntu/dmojsite` (roda cp38, sha256
   `6163744e1939f459803c6aed25ea5a9ff653063c1c1ea05fabb33a8b5bcad4f2`), que porta **SQLite 3.51.1**. El del sistema
   no s'ha tocat (continua 3.31.1). Comprovat: `RIGHT JOIN`, `FULL JOIN`, connexions `mode=ro` i
   `set_progress_handler` funcionen. Opcions de compilació: no porta cap accés a fitxers (`readfile`, `fsdir`,
   `sqlite_dbpage` no existeixen); `load_extension` hi és compilat però Python el deixa desactivat ("not authorized");
   porta `ENABLE_MATH_FUNCTIONS` (`CEIL`, `FLOOR`, `POWER`...).
4. **Checker** (`/home/ubuntu/dmojsite/lib/python3.8/site-packages/dmoj/checkers/sql.py`, **fora de git**):
   - Fa `import pysqlite3.dbapi2 as sqlite3` i, si no hi és, el `sqlite3` del sistema. (L'`import sqlite3` original
     no s'ha pogut treure perquè el classificador de permisos va denegar aquella edició concreta; com que el `try`
     ve després i reassigna el nom, l'efecte és el mateix: queda només una línia redundant.)
   - `WITH` acceptat **només als casos de `SELECT`** i només si la sentència a la qual pertanyen els CTE és un
     `SELECT` (`_main_keyword` recorre l'estructura `nom [(cols)] AS [[NOT] MATERIALIZED] (cos), ...`, perquè un CTE
     pot dir-se com una paraula clau). `WITH ... DELETE` (que SQLite accepta) es marca com a violació de seguretat
     (`@@SECVIOL@@`), igual que un `DELETE`; als casos d'`INSERT`/`UPDATE`, `WITH` continua rebutjat (aquells corren
     sobre una còpia en lectura-escriptura). Les referències `WITH ... SELECT` es detecten com a `SELECT`.
   - Provat fora dels jutges amb 14 casos (CTE simple, `RECURSIVE`, `MATERIALIZED`, CTE anomenat `"update"`,
     `WITH ... DELETE` als dos tipus de cas, `WITH ... UPDATE`, diverses sentències, `RIGHT JOIN`...): tots donen el
     resultat esperat. Confirmat també que un `WITH ... DELETE` contra la connexió de només lectura falla igualment.
   - Limitació que ja existia i no s'ha tocat: el control de "una sola sentència" parteix per `;` sense mirar
     cometes, i per això rebutja un `;` dins d'un text.

5. **Reinici dels jutges:** el classificador de permisos va denegar que Claude els reiniciés; **l'usuari els va
   reiniciar a mà** (NouJutge a les 23:19, EdgTest a les 23:20 del 2026-10-20). Comprovat que els dos han carregat el
   checker nou: un enviament real a `sqljoin02` amb una resposta en `RIGHT JOIN` (Q1) i una altra amb `WITH` (Q3)
   dona `AC` a totes dues, una vegada corregit per EdgTest i una altra forçant NouJutge (`judge_id`). Enviaments de
   prova esborrats. El cas `WITH ... DELETE` no es va enviar al jutge, perquè una violació de seguretat envia un
   correu als administradors; es va provar fora (punt 4).
6. **Regressió:** **recorreguts** (`rejudge=True`, sense crear-ne de nous) els 132 enviaments de referència d'`edgar`:
   **132/132 continuen donant `AC` complet** (65 per NouJutge, 67 per EdgTest).
7. **`sqljoin02` ara és un problema de `RIGHT JOIN` de debò** ("SQL Joins 2: RIGHT JOIN"): la introducció explica
   `RIGHT JOIN` com a mirall del `LEFT JOIN`, i les 10 consultes de referència fan servir `RIGHT JOIN` (els
   enunciats ja deien "Combinant A i B" amb la taula protagonista en segon lloc). Abans de substituir-lo es va
   comprovar que les 10 consultes noves donen exactament les mateixes files que les antigues amb `LEFT JOIN`. L'enviament
   de referència d'`edgar` s'ha substituït per un amb `RIGHT JOIN` (`AC`, 10/10).
8. **`create_db_problems`:** nova opció `--only CODI ...`, i `--replace` ja **no** reassigna els autors d'un
   problema existent (abans els hauria tornat a repartir per posició dins del lot).

**Pendent (opcional):** treure la línia `import sqlite3` redundant del checker (vegeu el punt 4), i actualitzar la
documentació `docs/05-sistemes-mecanics/5.5-checker-sql.md`, que encara no parla de `pysqlite3` ni de `WITH`.

**Com desfer-ho:** `/home/ubuntu/dmojsite/bin/pip uninstall pysqlite3-binary` (el checker torna sol al sqlite del
sistema) i/o restaurar el `.bak` del checker; després, reiniciar els jutges.

---

### 78. Publicats els 120 problemes SQL nous, i prova real de l'alarma amb `WITH ... DELETE`

**Prova de l'alarma (petició de l'usuari):** dos enviaments d'`edgar` amb `WITH t AS (SELECT 1) DELETE FROM ...`, un a
una pregunta d'`UPDATE` (`sqlupd01`, #368374, EdgTest; és el cas que importava, perquè corre sobre una còpia en
lectura-escriptura) i un a una de `SELECT` (`sqlsel01`, #368375, NouJutge): tots dos `SEC`, amb el correu als
administradors (`settings.ADMINS`, una adreça). L'enviament del correu no s'ha pogut confirmar des d'aquí: el backend
de Gmail s'usa amb `fail_silently`, així que un error no deixaria cap rastre. Els dos enviaments s'han deixat perquè
l'enllaç del correu funcioni. Detall cosmètic trobat: el missatge "This statement type is not allowed: WITH ...
DELETE" fa 51 caràcters i el camp `SubmissionTestCase.feedback` en té un màxim de 50, així que l'alumne el veu
tallat ("... DELET"); no s'ha corregit (caldria tocar el checker i tornar a reiniciar els jutges).

**Publicació:** els 120 problemes nous (`sql<bd>01-10` x 9, `sqlsel/join/agg/sub/mix 01-05`, `sqlins/upd 01-05`)
passen a `is_public=True` amb `date` = ara (no en tenien). Es va fer des del codi, no des de l'admin; l'admin
hauria encuat `rescore_problem`, que recalcula els punts dels enviaments (aquí no canvien) i `calculate_points`, que
**exclou** el grup `sql`. La puntuació SQL només es recalcula en rebre un veredicte (`calculate_sql_points` al
bridge), així que s'ha recalculat a mà per a l'únic usuari amb enviaments en aquests problemes, `edgar`: de 29 a
610 punts SQL (i s'han esborrat les seves claus `user_complete`/`user_attempted` de la cache).

**Comprovat com a visitant anònim:** les pàgines dels problemes responen 200; a la llista, els problemes de BD només
surten en triar la categoria (`/problems/?category=<id del grup sql>`), com ja passava, i el filtre per tipus nou
funciona (p. ex. "joins bàsics" mostra els de joins i no els altres); el codi de les respostes d'`edgar` no és
accessible (redirigeix al login). Recordatori: un alumne que resolgui un problema públic amb tots els punts **sí** que
pot veure la resposta d'`edgar` (regla estàndard de `can_see_detail`, acceptada per l'usuari). En total, ara hi ha 138
problemes públics al grup `sql`.

---

### 79. Guies (birret "Introducció") per als 27 problemes SQL més fàcils

**Abans:** només hi havia guies (`Guide`, secció 2.2 de la documentació) en 41 problemes de programació (40 del grup
"Introduccio" i 1 d'"Aprenentatge"); cap problema de BD en tenia.

**Decisió:** seguint el mateix criteri que es va fer servir a programació (els problemes que un alumne toca primer de
cada tècnica), **3 problemes per cada una de les 9 categories SQL**, prioritzant els de 2-3 preguntes, els de posició
més baixa dins del seu lot (segueixen una corba de dificultat) i les BD petites. S'han deixat fora `provasql2` (una
prova) i `sqldificil` (explícitament difícil):
- Selects bàsics: `sqlselects`, `sqlemployees01`, `sqlknights01` · Agregacions bàsiques: `sqlemployees04`,
  `sqlknights04`, `sqlminiwind04` · Agrupacions: `sqlemployees05`, `sqlknights05`, `sqlgroupbytest05`
- Joins bàsics: `sqljoins`, `sqlknights07`, `sqlminiwind07` · Joins complexos: `sqlemployees08`, `sqlknights08`,
  `sqlminiwind08` · Subconsultes: `sqlemployees07`, `sqllastnames07`, `sqlgroupbytest09`
- Mesclats: `sqlgroupbytest07`, `sqlemployees10`, `sqlknights10` · Inserts: `sqlinsertemployees`, `sqlinsertknights`,
  `sqlinsertchinook` · Updates: `sqlupdategroupby`, `sqlupdatehotel`, `sqlupdatetraders`

**Contingut:** a programació, a més del text general (`Guide.content`), cada guia té una pista de codi per llenguatge
(`GuideTranslation` amb `runtime` Python 3 / Java 11) que és pràcticament la solució. En SQL el codi **és** la resposta,
així que les guies SQL tenen **només el text general** (sense `GuideTranslation`; la vista amaga el selector de
llenguatge quan no n'hi ha), amb aquesta estructura: com abordar-lo, l'esquelet genèric de la sintaxi, què cal a cada
pregunta (sense la consulta), un o dos exemples resolts **anàlegs** (sobre una altra taula/columna/condició) i paranys
habituals. Les han escrites 3 subagents, i són al repositori: `problem_batches/sql/guides_*.json`
(`{codi: markdown}`).

**Control de fuites:** un script (fora del repo, a la carpeta temporal de la sessió) comprova cada guia: (1) que cap
resposta de referència hi aparegui (sense tenir en compte majúscules, espais i `;`), i (2) que cap bloc ```` ```sql ````
de la guia, **executat contra la BD del problema**, doni les mateixes files que una resposta (o, en el cas
d'`INSERT`/`UPDATE`, sobre una còpia temporal, el mateix estat final de la BD). Provat amb una fuita deliberada
(detectada) i passat a les 27: 0 fuites. Cinc exemples (`sqlknights05`, `sqlgroupbytest05`, `sqljoins`,
`sqlemployees08`, `sqllastnames07`) són molt propers a la pregunta (mateixa tècnica, una altra columna o condició);
s'han mantingut com a exemples anàlegs, menys explícits que les pistes de codi de programació.

**Resultat:** 27 `Guide` públiques (68 guies en total al lloc). Comprovat com a visitant anònim, per a les 27:
`/problem/<codi>/guide` respon 200 amb el contingut i el codi renderitzats, i la pàgina del problema mostra l'etiqueta
"Introducció" i l'enllaç a la guia; a la llista (categoria BD), el birret surt als problemes amb guia i no als altres.
Les guies s'amaguen durant els concursos, com les de programació.

---

### 80. Tasques de Bases de Dades (16 tasques de Marc) en una pestanya pròpia

**Abans:** hi havia 181 tasques (`ProblemTask`), totes de programació (37 de `marc`, amb la convenció de nom
"NN MM Títol": unitat i subtema, p. ex. "03 02 Bucles amb comptador"), en una sola pestanya "Tasks" de la barra de
pestanyes de problemes (`templates/problem/problem-list-tabs.html`). Cap tasca tenia problemes de BD.

**Decisió:**
1. **Pestanya pròpia, com al rànquing** (`/users/bd`): "Tasks" passa a ser dues pestanyes, **"Tasques de Programació"**
   (`/tasks/`, `problem_tasks`) i **"Tasques de Bases de Dades"** (`/tasks/bd/`, `problem_tasks_database`, vista nova
   `DatabaseTaskList`, subclasse de `TaskList` amb `database = True`). La URL nova va **abans** de
   `^tasks/(?P<task>...)` i no hi havia cap tasca amb codi `bd`.
2. **Què és una tasca de BD no és cap camp nou** (mateix criteri que les guies, #79): una tasca és de BD si té problemes
   i **tots** són del grup `sql` (`TaskList.database_task_ids`); qualsevol altra, incloses les mixtes, és de programació.
   El recompte es fa en una consulta a part perquè els filtres d'autor/equip/institut de la llista fan joins que
   inflarien un `Count` sobre el mateix queryset. Els problemes Mongo també són del grup `sql`, així que una futura
   tasca de Mongo sortiria sola a la pestanya de BD.
3. **16 tasques creades amb autor `marc`**, amb la seva convenció de nom i el prefix "BD" (perquè a l'admin no es
   confonguin amb les de programació, que també comencen per "01 00"...). Cobreixen els **130 problemes SQL**, un sol cop
   cadascun (tots menys `provasql` i `provasql2`, que són proves), seguint la corba de dificultat dels lots: BD 01
   Consultes bàsiques (Introducció a SELECT, WHERE, LIKE/IN/BETWEEN/NULL, Funcions i CASE, Repàs), BD 02 Agregacions
   (Introducció, GROUP BY, HAVING), BD 03 Joins (Introducció, LEFT i RIGHT JOIN, encadenats i autojoins), BD 04
   Subconsultes (Introducció, avançades), BD 05 Reptes finals, BD 06 Modificar dades (INSERT, UPDATE). Els problemes
   amb guia (birret, #79) s'han afegit primer a cada tasca, i la descripció de la tasca ho diu. La definició és a
   `problem_batches/sql/tasques_bd.json`. Cap problema Mongo, a l'espera de la seva separació.
4. Plantilla `tasklist.html`: la pestanya activa ve de la vista (`task_tab`) i el títol de la llista canvia a "Tasques de
   Bases de Dades". El canvi pendent anterior d'aquest fitxer (`|escapejs` als placeholders) s'ha respectat.

**Per què:** petició de l'usuari: sèries de tasques de BD, de Marc, que no es barregin amb les de programació.

**Resultat:** comprovat amb el client de proves (`/tasks/`: 181 tasques, cap de BD; `/tasks/bd/`: les 16 i cap de
programació; pestanya activa correcta a cada pàgina; filtre per usuari `marc` → 16, `jrodriguez` → 0; detall de les 16
tasques correcte, amb les files dels problemes guiats ressaltades). Entre la creació de les tasques i la recàrrega,
el lloc en viu les mostrava barrejades a `/tasks/` (uns minuts). Recàrrega suau d'uWSGI (`kill -HUP` al màster, sense
aturar el lloc) i verificat en viu: `/tasks/` sense tasques de BD, `/tasks/bd/` amb les 16, la pestanya nova també a
`/problems/`, i la portada responent amb normalitat.

---

### 81. Ordre dels problemes dins de les tasques de BD

**Abans:** l'usuari creia que el detall d'una tasca ordena els problemes per punts i va proposar ajustar-los fins a
0,1 per forçar l'ordre didàctic. Comprovat que **no és així**: `TaskDetail` no fa cap `order_by`, i els problemes surten
per **identificador del problema** (ordre de creació). Per exemple, `comptadors` (de Marc) surt 2, 2, 3.5, 3.5, 3, 3, 2,
3 punts. A les tasques de BD semblava per punts per casualitat (els problemes temàtics de 10 punts es van crear més
tard). Canviar puntuacions, doncs, no hauria canviat l'ordre.

**Decisió (de l'usuari, entre les opcions plantejades):** ordre d'**inserció** (l'ordre en què s'afegeixen els
problemes a la tasca), però amb la condició que dins d'una tasca **un problema anterior mai valgui més punts que un de
posterior**.
1. `TaskDetail`: si la tasca és de BD (tots els problemes del grup `sql`, mateix criteri que la pestanya de #80),
   ordena pels `id` de la taula intermèdia `judge_problemtask_problems` (ordre d'inserció). Les tasques de
   programació **no canvien**: es va comprovar que fer-ho per a totes hauria canviat l'ordre de 146 de les 181.
2. Les tasques de BD s'han reordenat de manera estable per punts (amb els mateixos punts es manté l'ordre
   didàctic), **sense tocar cap puntuació**. Només 3 tasques canvien: "BD 02 01 GROUP BY" (`sqlagregacions`, de 3 punts,
   passa davant de `sqlagg02`, de 10), "BD 03 01 LEFT JOIN i RIGHT JOIN" (els "09" de 3 punts passen davant de
   `sqljoin01-03`, de 10) i "BD 05 00 Reptes finals" (`sqldificil`, de 3 punts, passa a la segona posició, davant dels
   de 4 i 10). En totes tres, els problemes curts (3 preguntes) queden davant dels llargs (10). Els problemes guiats
   continuen primer. La definició (`problem_batches/sql/tasques_bd.json`) està actualitzada amb l'ordre nou, i els
   problemes de les 3 tasques s'han tornat a inserir en aquest ordre.

**Resultat:** recàrrega suau d'uWSGI (`kill -HUP` al màster). Verificat en viu: les 16 tasques de BD mostren els
problemes exactament en l'ordre del JSON, cap té punts que baixin al llarg de la tasca, i `comptadors` (programació)
surt igual que abans.

---

### 82. `sqldificil` passa de 3 a 10 punts, perquè quedi al final de "Reptes finals"

**Abans:** amb la regla de #81 (dins d'una tasca, un problema anterior mai val més punts que un de posterior),
`sqldificil` ("Bases de Dades: Problemes més difícils", 3 preguntes, 3 punts) quedava a la segona posició de "BD 05 00
Reptes finals", davant dels de 4 i 10 punts.

**Decisió (de l'usuari):** pujar-li els punts perquè quedi al final. **10 punts**, el mínim que compleix la regla (empata
amb `sqlmix02`, i amb l'empat l'ordre d'inserció el deixa l'últim).

**Efectes:** és un problema públic antic amb 4 enviaments de 3 usuaris, un d'ells un alumne real. Com que la puntuació
es va canviar des del codi i no des de l'admin, es va fer a mà el mateix que `rescore_problem` (punts de cada enviament =
`case_points / case_total × punts del problema`, `update_contest()`), i a més `calculate_sql_points()`, que aquella tasca no
fa. Enviaments: `admin` AC 3 → 10, `Elvin_Po_Ma` WA 2 → 6,7 i AC 3 → 10, `edgar` AC 3 → 10. Punts SQL: `admin` 25 → 29,
`Elvin_Po_Ma` 14 → 21, `edgar` 610 → 617 (la puntuació de programació no canvia, perquè exclou el grup `sql`). No és en cap
concurs.

**Resultat:** `sqldificil` s'ha mogut al final de la tasca (JSON i insercions). Verificat en viu: és l'últim dels 13
problemes de "Reptes finals", els punts no baixen al llarg de la tasca, i la pàgina del problema mostra "Punts: 10 (parcial)".

---

### 83. Seguretat de les BD dels problemes: prova d'atacs SQL, còpia de seguretat, i forat greu a Java/Kotlin

**Pregunta de l'usuari:** si un `INSERT`/`UPDATE` d'un alumne, sense voler o a propòsit, pot modificar la plantilla
SQLite (o la BD real del problema).

**Via SQL: tancada (comprovat).** El checker no obre mai les plantilles de `/judge/_sql_templates/`, que només es llegeixen
en crear el problema. Obre la còpia del problema (`/judge/<codi>/<fitxer>.db`): en mode `ro` + `query_only` per als
`SELECT`, i mitjançant una còpia temporal (`shutil.copyfile`) que s'esborra després per a `INSERT`/`UPDATE`. Es van
llançar 15 atacs contra el checker real (`check()`), usant una còpia com a "original": `ATTACH` (també darrere d'un
comentari), `VACUUM INTO`, `WITH ... DELETE`, diverses sentències amb `;`, `writefile()`, `load_extension()`, pragmes,
un `UPDATE` sense `WHERE`... Tots rebutjats o sense efecte; l'original i un fitxer víctima, **idèntics byte a byte**
(sha256), i cap fitxer nou.

**Però els fitxers no tenen protecció del sistema operatiu:** plantilles i còpies són de `ubuntu`, el mateix usuari amb què
corren els jutges i el web. A més, `/judge` és `777` (sense *sticky bit*), i `rclone` només puja els volcats de MySQL, no
`/judge`.

**Fet (a petició de l'usuari, punts 2 i 3 de la proposta; el punt 1, fer les plantilles de `root`, **no** es va fer):**
1. **Còpia de seguretat** de les 15 plantilles (SQL i Mongo) i de les BD dels 138 problemes que en tenen (`sql_db` /
   `mongo_db`): `/home/ubuntu/backups/joel-bd-fitxers-20261021-000425.tar.gz` (62 MB, 153 fitxers, rutes relatives a
   `/judge`) i `.sha256` amb l'empremta de cadascun. Restauració de prova en una carpeta temporal: les 153 empremtes
   coincideixen. Per comprovar en el futur que res no ha canviat: `cd /judge && sha256sum -c <fitxer>.sha256`.
2. **Prova pendent del `TODO.md` (punt 9), feta:** 5 enviaments d'`edgar` al problema privat `aplusb`, cadascun intentant
   crear un fitxer en un directori testimoni de `/tmp`:
   - **Java 11** (NouJutge): `ProcessBuilder("touch", ...)`, `Runtime.exec("sh -c ...")` i `FileWriter` → **els tres fitxers
     creats**.
   - **Kotlin** (EdgTest): `ProcessBuilder` i `File.writeText` → **els dos fitxers creats**.
   - **Python 3** (NouJutge, un enviament per via perquè el sandbox pot matar el procés al primer intent): `subprocess` →
     IR `BlockingIOError`; `os.system` → no crea res; `open(...,'w')` → IR `FileNotFoundError`. **Cap fitxer.**
   La JVM s'engega amb `-javaagent:java_sandbox.jar=policy:<fitxer>` i la política (`java-security.policy`) només permet
   escriure a `out/` i `/outputfiles/` i no dona permís d'execució, però **no s'aplica**. El motiu no s'ha investigat.
   Testimoni i enviaments de prova esborrats.

**Conseqüència (GREU, no resolta):** qualsevol usuari registrat pot executar codi arbitrari al servidor com a `ubuntu`
(propietari de `/judge`, del codi del lloc i de les còpies, i **amb `sudo` sense contrasenya**) enviant un programa en Java o
Kotlin. Això va molt més enllà de les plantilles SQL. Apuntat a `TODO.md` (punt 9), pendent de decisió de l'usuari.

---

### 84. Causa del forat de Java/Kotlin (#83) trobada; treure el `sudo` sense contrasenya, **no fet** (denegat)

**Investigació (només lectura, cap canvi):** el directori del jutge
(`/home/ubuntu/dmojsite/lib/python3.8/site-packages/dmoj`) és un repositori git (`malbareda/JOEL-jutge`). El commit
`3fb52a5` (2026-08-18, "... i Java 25") va **substituir `executors/java_sandbox.jar`** (7.518 → 9.546 bytes) per l'agent
nou del DMOJ (compilat el desembre de 2023). Desmuntant les dues versions amb `javap`:
- **Agent antic (2019, commit `9e45a91`):** reconeix l'opció `policy:<fitxer>`, carrega el fitxer com a
  `java.security.policy` i crida `System.setSecurityManager(new SecurityManager())`. És el que aplicava la política
  `java-security.policy`.
- **Agent nou:** només reconeix `unsafe`, `unicode`, `nobigmath` i `nobuf`. **L'opció `policy:` s'ignora sense cap avís i
  no hi ha cap `SecurityManager`.** El DMOJ actual va treure el `SecurityManager` (eliminat del tot a partir del JDK 24) i
  aïlla Java amb el sandbox de sistema `cptbox`, però en aquest jutge `JavaExecutor.get_security()` continua retornant
  `None` (el disseny antic, en què era l'agent qui protegia). Resultat: des del 18-08-2026, Java i Kotlin corren
  **sense cap aïllament**.
- Afecta JAVA8 (962 problemes, 55.873 enviaments), JAVA11 (1.043 / 128.089), JAVA25 (1.064 / 31.950) i KOTLIN (888 / 51.189;
  corre sobre `/usr/bin/java`, que és el Java 11.0.17).

**Treure el `NOPASSWD` d'`ubuntu` (petició de l'usuari): NO FET.** Comprovat abans: el permís ve de
`/etc/sudoers.d/90-cloud-init-users` (`ubuntu ALL=(ALL) NOPASSWD:ALL`); `ubuntu` té contrasenya (des del 2020) i és al grup
`sudo`, de manera que després `sudo` demanaria aquesta contrasenya; `root` està bloquejat i sense claus SSH, així que si no es
recorda la contrasenya d'`ubuntu` es perdria l'accés de root (llevat de la consola del proveïdor del VPS); l'única feina
automàtica amb privilegis (volcat de la BD) és al crontab de root i no en depèn. A més, **`ubuntu` és al grup `lxd`, que
equival a root**, i treure el `NOPASSWD` no tanca aquest camí. Es va intentar programar, abans del canvi, una restauració
automàtica (de root, d'aquí a 30 minuts, que l'usuari cancel·laria després de provar la contrasenya) per evitar el
bloqueig, però el classificador de permisos ho va denegar ("Unauthorized Persistence"), i no es va fer res: el fitxer de
`sudoers` està intacte, sense còpia ni tasca programada. Queda a mans de l'usuari (procediment al `TODO.md`, punt 9).

---

### 85. Privilegis d'`ubuntu`: estat després dels canvis fets per l'usuari (comprovació)

**Què ha fet l'usuari, a mà** (alternativa proposada a #84: un administrador separat en lloc de deixar `ubuntu` amb
`sudo` amb contrasenya): l'usuari `marc` (UID 1002) és al grup `sudo`; la línia `NOPASSWD` d'`ubuntu` ja no té efecte
(`sudo -n true` → "a password is required"), i `ubuntu` ja no és al grup `lxd` segons `/etc/group`.

**Comprovat que queda obert:**
1. **`ubuntu` continua al grup `sudo`** (`getent group sudo` → `ubuntu,marc`), així que encara pot fer `sudo` amb la seva
   contrasenya. Un atacant que corri com a `ubuntu` (p. ex. via el forat de Java de #83) podria capturar-la, per exemple
   amb un àlies trampa al `.bashrc`. Falta `gpasswd -d ubuntu sudo`.
2. **Els processos que ja corrien conserven el grup `lxd` (118)**: treure algú d'un grup només afecta les sessions noves.
   `/proc/<pid>/status` dels dos jutges, uWSGI, el bridge i la sessió de Claude encara mostren el 118, i des de la sessió
   de Claude `lxc list` **funciona** (LXD 6.9 instal·lat com a snap, sòcol `root:lxd 660`, sense cap contenidor ni
   inicialitzat). Accedir a LXD equival a ser root. Es tanca reiniciant tots aquests processos (el més net: reiniciar el
   servidor) o, ja que LXD no es fa servir, desinstal·lant-lo (`snap remove lxd`).
3. `marc` no té claus SSH (`/home/marc/.ssh/authorized_keys` no existeix): entra amb contrasenya (`PasswordAuthentication
   yes`).

No s'ha canviat res en aquesta comprovació (només lectura, més un `lxc list` per confirmar l'accés).

---

### 86. Sandbox de Java 8/11 i Kotlin restaurat (agent antic amb `SecurityManager`)

**Abans:** vegeu #83 i #84: des del commit `3fb52a5` del jutge (18-08-2026), `java_sandbox.jar` era l'agent nou del DMOJ, que
ignora `policy:` i no instal·la cap `SecurityManager`, i `JavaExecutor.get_security()` torna `None` (cap `cptbox`). Resultat:
Java i Kotlin sense cap aïllament.

**Decisió:** tornar a fer servir l'agent antic (el que hi havia del 2020 a l'agost del 2026) per als llenguatges que corren sobre
una JVM amb `SecurityManager` (Java 8, Java 11 i Kotlin, que corre sobre `/usr/bin/java` = Java 11.0.17), i deixar l'agent nou només
per a Java 25, on el `SecurityManager` ja no existeix (des del JDK 24, `System.setSecurityManager` llença una excepció i l'agent
antic faria petar tots els enviaments).

**Prova prèvia fora dels jutges** (mateixa línia d'arrencada que el jutge: `-client -javaagent:<jar>=policy:<fitxer>,unicode
-Xss128m -Xmx... -XX:+UseSerialGC`, amb la mateixa `java-security.policy`), amb un programa que llegeix dos enters amb `Scanner`
i n'imprimeix la suma, i després intenta `ProcessBuilder`, escriure un fitxer i llegir-ne un fora de les carpetes permeses:
- Java 11 + agent antic: la suma correcta, i **les tres vies bloquejades** (`AccessControlException`), cap fitxer testimoni creat.
- Java 11 + agent actual (per comparar): **les tres vies permeses**, fitxers testimoni creats.
- Java 8 + agent antic i Kotlin (compilat amb `kotlinc -d`, executat amb `-cp jar:kotlin-stdlib.jar` com el jutge) + agent antic:
  la suma correcta, totes les vies bloquejades.

**Canvis al jutge** (repositori `malbareda/JOEL-jutge` a `/home/ubuntu/dmojsite/lib/python3.8/site-packages/dmoj`, sense commit;
còpies prèvies a `/home/ubuntu/backups/dmoj-executors-*.20261021-003447.bak`):
- `executors/java_sandbox_legacy.jar`: l'agent antic, tret del mateix git (`git show 9e45a91:executors/java_sandbox.jar`).
- `executors/java_executor.py`: constant `JAVA_SANDBOX_LEGACY` i atribut de classe `agent_file = JAVA_SANDBOX_LEGACY`, que
  `create_files` fa servir en lloc de la constant `JAVA_SANDBOX`.
- `executors/JAVA25.py`: `agent_file = JAVA_SANDBOX` (l'agent nou), amb un comentari que avisa que **Java 25 continua sense
  aïllament** fins que tingui `cptbox`.
- Comprovat important els executors: JAVA8, JAVA11 i KOTLIN → `java_sandbox_legacy.jar`; JAVA25 → `java_sandbox.jar`.

**Comprovat que no trenca l'encoding (accents), a petició de l'usuari:** el commit `3fb52a5` que va canviar l'agent també
és el de la feina d'encoding, així que es va provar a part, amb el mateix entorn que el jutge (`JAVA_TOOL_OPTIONS`, `LANG`,
`LC_ALL` i els `-D...encoding=UTF-8`; Java 11 compilat sense `-encoding` i Java 8 amb `-encoding UTF-8 -profile compact1`,
com el jutge). Un programa amb accents en literals ("Còdi: àèéíòóú ç l·l ñ € ¿?") que llegeix una línia amb accents
("Pèrdua d’àngel: Çà i ñaña") i la torna en majúscules: **sortida idèntica byte a byte** entre l'agent antic i el nou a
Java 8, Java 11 i Kotlin, amb els accents i les llargades correctes. La solució de l'encoding són els paràmetres de la JVM,
que no s'han tocat. A la regressió s'han afegit 9 enviaments `AC` reals amb accents dins de literals (3 per llenguatge).

**Verificació després del reinici** (l'usuari va reiniciar els dos jutges a mà a les 00:39 del 2026-10-21):
- Tots dos jutges van tornar en línia oferint JAVA8, JAVA11, JAVA25 i KOTLIN; com que el jutge només ofereix un llenguatge si
  passa el seu programa de prova en arrencar, l'agent antic no trenca l'arrencada.
- **Prova del testimoni** (problema privat `aplusb`, directori testimoni a `/tmp`): JAVA8, JAVA11 i KOTLIN a **cada un dels dos
  jutges** (forçats amb `judge_id`), cadascun intentant `ProcessBuilder` i escriure un fitxer: **cap fitxer creat** (6
  enviaments). JAVA25 (EdgTest): **els dos fitxers creats**, com s'esperava (continua obert).
- **Regressió:** reenviat com a `edgar` el codi de 39 enviaments `AC` reals d'alumnes, cadascun al seu problema i llenguatge
  (inclosos 3 de "Fitxers de text", que llegeixen fitxers, i 9 amb accents dins de literals): **39/39 `AC`** (12 Java 8, 15 Java
  11, 12 Kotlin).

**Pendent:**
- **Java 25 continua sense aïllament** (1.064 problemes, 31.950 enviaments): cal `cptbox` o desactivar-lo.
- Neteja, **no feta** perquè l'usuari ha demanat no esborrar res sense explicar-ho abans: el directori testimoni de `/tmp` amb
  els 2 fitxers buits que va crear el Java 25, i els 46 enviaments de prova d'`edgar` (7 de testimoni a `aplusb` i 39 de
  regressió en problemes públics, que sumen a la seva puntuació). Si s'esborren, cal recalcular la puntuació d'`edgar`.
- Fer commit dels canvis al repositori del jutge (`malbareda/JOEL-jutge`), que ara estan sense commit.

**Com desfer-ho:** restaurar els dos `.bak` (o `git checkout -- executors/java_executor.py executors/JAVA25.py`) i reiniciar
els jutges.

---

### 87. Estudi: aïllar Java 25 amb `cptbox` (prova fora dels jutges, sense cap canvi al jutge)

**Pregunta de l'usuari:** quina complexitat tindria posar `cptbox` (el sandbox de sistema que ja fa servir Python) a Java 25,
que des de #86 és l'únic Java sense aïllament.

**Prova feta** fora dels jutges, carregant la configuració real (`/judge/judge.yml`), amb una subclasse de prova de l'executor
que fa servir `PlatformExecutorMixin.get_security()` (el `cptbox` dels altres llenguatges) en lloc del `return None` de
`JavaExecutor`. Fitxers de prova a `/tmp/joel-cptbox-G6rFU5/` (no esborrats):
1. Tal qual, **la JVM no arrenca** ("agent library failed to init: instrument"): `cptbox` no deixa llegir el `.jar` de
   l'agent, que és fora de les rutes permeses (la JVM, a `/usr/lib/jvm/...`, sí que ho està). Afegint la ruta de l'agent a
   `fs`, **Java 11 ja passa** el programa de prova del jutge.
2. Java 25 també necessita **dues crides al sistema** que el `cptbox` d'aquest jutge (DMOJ 2.1.0, del 2020) no deixa passar:
   `statx` i `clock_nanosleep`. Afegint-les a `syscalls`, **Java 25 passa** el programa de prova. No en calen d'altres.
3. **Aïllament real (Java 25 + `cptbox`):** `ProcessBuilder` → el procés mor amb una violació de protecció (`sys_execve`), igual que
   Python; escriure un fitxer fora del directori de l'enviament → `FileNotFoundException`; llegir `/etc/hostname` →
   `FileNotFoundException`. Cap fitxer testimoni creat. Els accents surten bé.
4. **Cost:** un programa pesat (300 milions d'iteracions + ordenar 3 milions d'enters) triga 1,10 s sense `cptbox` i 1,14 s amb
   (un 3% més).

**Què faltaria per posar-ho en producció** (no fet):
- A `JAVA25.py`: `get_security` amb `cptbox`, la ruta de l'agent a `fs`, i `statx` i `clock_nanosleep` a `syscalls` (unes 10
  línies). Millor fer passar `statx` pel mateix control de rutes que `stat`, en lloc de permetre'l sense més, perquè si no
  es pot consultar si existeix qualsevol fitxer.
- Afegir a `fs` les carpetes dels problemes de fitxers (`/inputfiles` per llegir, `/outputfiles` per escriure), que ara
  dona la política de Java i amb `cptbox` caldria donar explícitament; si no, aquests problemes fallarien.
- Regressió amb molts enviaments reals de Java 25 (crides al sistema poc habituals, com les de fils, `SecureRandom` o
  memòria, només surten en alguns programes, i un alumne veuria un error en lloc del seu resultat), i reiniciar els jutges.
- Opcional: posar també `cptbox` a Java 8/11/Kotlin, com a segona capa a més del `SecurityManager` (Java 11 ja passa la prova).

---

### 88. Política de Java ampliada (`setIO` i les carpetes `in`/`out`) perquè no es trenquin solucions reals

**Pregunta de l'usuari:** si s'havia provat que, amb el sandbox de #86, Java 8/11 continuessin fent problemes de fitxers i problemes amb
accents (p. ex. `mesvell`).

**Descobriment:** `java_sandbox.jar` (l'agent sense `SecurityManager`) té data al disc del **7-10-2025**, tot i que el commit és del 18-08-2026.
El forat de #83 existia, doncs, des de l'**octubre del 2025**, i tot el codi dels alumnes des de llavors s'ha provat sense cap restricció.
Per això es va buscar què fan les solucions d'aquest període que el `SecurityManager` pugui bloquejar.

**Regressions al jutge real** (enviaments d'`edgar` amb el codi de solucions `AC` d'alumnes; no esborrats, a petició de l'usuari):
1. `mesvell`: els seus casos de prova **no tenen cap accent** (ni a l'entrada ni a la sortida). La solució Java 11 → `AC`.
2. Els 20 problemes amb accents als casos de prova que tenen solucions Java/Kotlin, i els 8 de "Fitxers de text": 51 enviaments, **48 `AC`**.
   Fallades: un Kotlin del 2024 de `rimasmecano`, per un error de compilació (`toLowerCase()` obsoleta en el `kotlinc` actual; no té res a
   veure amb el sandbox), i 2 de Java 11 (`silencisala`, `tipusdevi`) bloquejats pel `SecurityManager`.
3. Les 22.367 solucions `AC` en Java 8/11/Kotlin des del 2025-10-07 es van filtrar per APIs que el `SecurityManager` pot bloquejar
   (`System.setOut/setErr/setIn`, `System.exit`, `System.getProperty`, `Locale.setDefault`, accés a fitxers): 102 enviaments, **92 `AC`**.
   Les 10 fallades:
   - 6 (`silencisala` i `tipusdevi`, Java 11 i Kotlin) fan `System.setOut(new PrintStream(System.out, true, StandardCharsets.UTF_8))`, el truc
     perquè els accents surtin bé, que necessita `RuntimePermission "setIO"`.
   - 2 (`copia`, Java 8) fan `new File("out").exists()` i `mkdir()`: la política permetia els fitxers de dins (`out/-`) però no la carpeta.
   - 2 (`tortasaceitepro`, Kotlin): **no és el sandbox**. Reproduït amb l'executor de Kotlin del jutge: amb l'agent antic i amb el nou falla
     igual ("Could not find or load main class ...TortasAceitePro.Tortasaceite"). El programa té una declaració `package`, i des del canvi de
     Kotlin de #69 el jutge en calcula malament la classe principal. Error previ, apuntat al `TODO.md`.

**Canvi a `executors/java-security.policy`** (còpia prèvia a `/home/ubuntu/backups/dmoj-executors-java-security.policy.20261021-005626.bak`):
- `RuntimePermission "setIO"`: només deixa canviar els fluxos estàndard del mateix procés.
- `FilePermission` de lectura per a les carpetes `in` i `/inputfiles`, i de lectura i escriptura per a `out` i `/outputfiles`. Abans només
  hi havia els fitxers de dins. També lectura a `out/-`, a més d'escriptura.

**Comprovat fora dels jutges amb la política nova:** el testimoni (Java 11 + agent antic) continua amb **les tres vies bloquejades**
(`ProcessBuilder`, escriure fora, llegir fora) i cap fitxer creat; i els 6 programes de `setOut`, executats amb l'executor real del jutge
(JAVA11 i KOTLIN) sobre el primer cas de prova del seu problema, donen **la sortida correcta** sense bloqueig.

**Verificat després del reinici** (l'usuari va reiniciar els dos jutges a mà a la 01:00 del 2026-10-21): les 8 fallades que eren del
sandbox (6 de `setOut` a `silencisala`/`tipusdevi`, en Java 11 i Kotlin, i 2 de `copia` en Java 8) tornades a enviar → **8/8 `AC`**,
repartides entre tots dos jutges. Prova del testimoni amb la política nova, JAVA8/JAVA11/KOTLIN a cadascun dels dos jutges: **cap fitxer
creat** (6 enviaments). Enviaments de prova no esborrats (a nom d'`edgar`).

---

### 89. Java 25 aïllat amb `cptbox`

**Abans:** Java 25 era l'únic Java sense aïllament (#86): el JDK 25 ja no té `SecurityManager`, i `JavaExecutor.get_security()` torna
`None`. L'estudi de #87 va mostrar que el `cptbox` del jutge (el de Python) hi funciona amb canvis petits.

**Canvi a `executors/JAVA25.py`** del jutge (sense commit; còpia prèvia a `/home/ubuntu/backups/dmoj-executors-JAVA25.py.20261021-010327.bak`):
- `get_security()` fa servir el `cptbox` de la resta de llenguatges (`super(JavaExecutor, self).get_security(...)`, saltant el `return None`
  de `JavaExecutor`), i hi afegeix dues crides al sistema que el JDK 25 necessita i aquest `cptbox` (del 2020) no coneix:
  `clock_nanosleep` (permesa) i `statx`, que **passa pel mateix control de rutes que `fstatat`** (`check_file_access_at`), en lloc de
  permetre-la sense més. Si no, es podria consultar si existeix qualsevol fitxer del servidor.
- `fs`: la ruta de l'agent (`java_sandbox.jar`) i `/inputfiles/` (la JVM és a `/usr/`, que ja es pot llegir). `get_write_fs()`:
  `<directori de l'enviament>/out/` i `/outputfiles/`, com `PY3`. `fsize = 60485`, com `PY3`, perquè els problemes de fitxers puguin
  escriure.
- ~~`create_files()` crea la carpeta `out/` buida~~ (tret després; vegeu més avall).

**Comprovat fora dels jutges, amb l'executor real i la configuració dels jutges:**
- El programa de prova del jutge passa.
- **Bloquejat:** escriure fora del directori de l'enviament, llegir `/etc/hostname`, i llançar un procés (el programa mor per
  `sys_execve`); cap fitxer testimoni creat. `new File("/etc/shadow").exists()` retorna `false` (el control de `statx` funciona).
- **Funciona:** escriure a `out/`, llegir `/inputfiles/copia1`, accents i el truc `System.setOut(new PrintStream(..., UTF_8))`.
- **Regressió amb 140 solucions `AC` reals de Java 25** (una per problema; 71 de les que fan servir fitxers, `setOut`, fils, `Random`,
  `exit`, `getProperty`, dates o streams, i 69 a l'atzar), executades amb el primer cas de prova del seu problema: **cap violació de
  `cptbox`**. 133 donen la sortida esperada; les altres 7 donen **exactament el mateix amb `cptbox` i sense** (comprovat), així que són
  artefactes de la prova (correctors especials, com el de fitxers, o format de l'entrada), no del sandbox.

**Primer reinici** (l'usuari, a la 01:09 del 2026-10-21) i verificació dins del jutge real:
- Tots dos jutges van tornar oferint JAVA25, és a dir, el programa de prova del jutge passa dins de `cptbox`.
- Testimoni (escriure un fitxer fora i `ProcessBuilder`): JAVA25 → `RTE` (mor en intentar el procés) i JAVA11 → bloquejat pel
  `SecurityManager`, a **tots dos jutges**; **cap fitxer creat**.
- Regressió amb 116 solucions `AC` reals de Java 25 (les 6 de problemes de fitxers, 70 amb APIs de risc i 40 a l'atzar), repartides entre
  tots dos jutges: **115 `AC`** i 1 `IE` a `holafile`.

**L'`IE` era culpa d'aquest canvi:** el problema declara `symlinks: {out: /outputfiles}` a l'`init.yml`, i el jutge crea `out` com un enllaç
en arrencar el programa (`PlatformExecutorMixin.launch`). La carpeta `out/` que `create_files()` creava per endavant hi xocava
(`FileExistsError`). 6 problemes fan servir aquests enllaços (`holafile`, `llegirfitxer`, `llegirfitxer2`, `copia`, `escriurebin`,
`lecturabin`). **Corregit:** tret el `create_files()` (i l'`import os`, sense ús): els problemes de fitxers ja reben `in`/`out` del jutge,
i les escriptures a `out/...` continuen passant pel control de rutes (`<directori de l'enviament>/out/` a `write_fs`). El programa de
prova continua passant fora dels jutges.

**Segon reinici** (l'usuari, a la 01:13): tots dos jutges en línia amb JAVA25. Testimoni JAVA25 a cada jutge → `RTE`, **cap fitxer creat**.
Problemes de fitxers en Java 25: les 6 solucions `AC` reals que hi ha (`holafile` i 5 de `llegirfitxer2`) → **6/6 `AC`**; control amb
Java 8/11 als mateixos problemes (`holafile`, `llegirfitxer`, `llegirfitxer2`, `copia`, `lecturabin`) → **5/5 `AC`**. Enviaments de prova
no esborrats (a nom d'`edgar`).

**Estat final: tots els Java del jutge tenen aïllament** — Java 8, Java 11 i Kotlin amb el `SecurityManager` de l'agent antic (#86, #88),
i Java 25 amb `cptbox` (aquesta entrada).

**Com desfer-ho:** restaurar el `.bak` de `JAVA25.py` i reiniciar els jutges.

---

### 90. `SEC` també quan el sandbox del jutge atura un programa

**Abans:** `SEC` (amb avís a la pàgina i correu als administradors) només es posava quan els checkers SQL/Mongo marcaven una consulta
destructiva (`@@SECVIOL@@`). Quan el sandbox aturava un programa, l'alumne veia un error normal: `RTE` "`<crida>` syscall disallowed"
(`cptbox`, per exemple Java 25 en intentar llançar un procés) o `IR` "Has intentat hackejar-me. Et sentencio a mort." (`SecurityManager` de
Java 8/11/Kotlin), sense cap avís a ningú.

**Decisió (de l'usuari):** marcar `SEC` en **qualsevol** cas en què el sandbox hagi intervingut i es pugui detectar. Prefereix un fals positiu
(un programa legítim que topi amb una crida que `cptbox` encara no coneix) a un fals negatiu.

**Canvis (al web; no toquen el jutge):**
- `judge/utils/sandbox.py` (nou): `is_sandbox_violation(estat, feedback)`. Cert si l'estat és `RTE` o `IR` i el feedback acaba en
  " syscall disallowed" (missatge de `dmoj/result.py` per a qualsevol violació de `cptbox`, en qualsevol llenguatge) o comença per "Has
  intentat hackejar-me" (`java_executor.py`, per a `AccessControlException`).
- `judge/bridge/judge_handler.py` (`on_test_case`): aquests casos passen a `SEC` i s'afegeixen a la llista de violacions, que envia el correu
  (`_notify_security_violation`). El correu té un assumpte propi ("[JOEL] Programa aturat pel sandbox (<problema>)"), diu el llenguatge, i
  avisa que pot ser un programa legítim i que cal mirar el codi abans d'actuar.
- `judge/views/submission.py` + `templates/submission/status-testcases.html`: si el `SEC` ve del sandbox, l'avís de la pàgina de l'enviament és
  un altre ("Programa aturat pel sistema de seguretat del jutge"): explica què ha passat, que s'ha notificat al professorat, i que, si
  l'alumne creu que és un error, en parli amb el professorat. El `SEC` del SQL manté el seu avís.
- Comprovat: la funció dona cert per a `RTE`+`execve`/`socket` "syscall disallowed" i `IR`+"Has intentat hackejar-me", i fals per a
  `segmentation fault`, una excepció normal, `WA`, `AC` i `TLE`. El bridge i la vista importen bé. Recàrrega suau d'uWSGI (`kill -HUP`) per a la
  vista i la plantilla; el web respon 200.

**Límit conegut:** quan `cptbox` denega un accés a fitxers, no mata el programa sinó que respon "no existeix" (el programa veu una
`FileNotFoundException`). Aquests intents no es poden distingir d'una ruta equivocada i no es marquen.

---

### 91. El grup "Creador d'Achievements" ara pot editar i esborrar els seus propis achievements

**Abans:** el grup "Creador d'Achievements" (48 membres, tots `is_staff`) només tenia `add_achievement` i `view_achievement`. La lògica de
l'entrada #55 ("cada alumne edita i esborra només els seus") no funcionava: `AchievementAdmin.has_change_permission`/`has_delete_permission`
comproven primer el permís de Django i, com que el grup no el tenia, ningú (ni el creador) podia editar ni esborrar res. La verificació de
l'entrada #55 s'havia fet amb un compte de prova que sí tenia `change_achievement`, no amb el grup real.

**Decisió:** afegits `change_achievement` i `delete_achievement` al grup. L'ha aplicat l'usuari mateix des de la interfície d'admin (el mode
automàtic de Claude Code va bloquejar fer-ho des de la línia d'ordres per ser una concessió de permisos). Cap canvi de codi.

**Per què:** petició explícita de l'usuari.

**Resultat:** comprovat sense escriure res a la BD (amb `RequestFactory` i el compte real `jmiracle`, membre només d'aquest grup): té els quatre
permisos; sobre un achievement d'un altre (id 156, sense `created_by`) `change=False`, `delete=False`, `view=True` (mode només lectura); sobre un
achievement amb `created_by` = el seu perfil (objecte en memòria, no desat) `change=True`, `delete=True`. L'acció massiva "esborrar
seleccionats" també queda limitada: Django 2.2 (`admin/utils.py`, `get_deleted_objects`) comprova `has_delete_permission(request, obj)` per a cada
objecte i rebutja tota l'operació si n'hi ha algun que no és seu. Com que cap dels achievements existents té `created_by` assignat, cap alumne en
pot tocar cap dels antics. Els professors del grup que no són superusuaris queden limitats igual als seus.

**A tenir en compte:** esborrar un achievement també esborra (en cascada) els `AchievementObtained` de tots els alumnes que l'havien obtingut
al gacha.

---

### 92. Achievements amb descompte permanent al gacha (tirades a 4 GachaPoints en lloc de 5)

**Abans:** el cost d'una tirada de gacha era un 5 fix al codi (`GachaGo.gacha_roll`) i als tres botons "Use 5 GachaPoints"
(`gachamain.html`, `gachago.html`, `gacharesult.html`). En treure un repetit es retornaven sempre 2,5 punts fixos.

**Decisió:**
- Nou camp `Achievement.gacha_discount` (booleà, per defecte fals, migració `0156_achievement_gacha_discount`). A l'admin només el veuen i
  el poden marcar els superusuaris, amb el mateix mecanisme que `mega_fanfare` i `rarity` (`AchievementAdmin.get_fields`).
- Nova propietat `Profile.gacha_roll_cost`: 4 (`GACHA_ROLL_COST_DISCOUNTED`) si l'usuari té algun achievement amb `gacha_discount`, i 5
  (`GACHA_ROLL_COST`) si no. No s'acumula: tenir-ne més d'una còpia, o més d'un achievement d'aquests, continua sent 4. No està en memòria
  cau a propòsit: la tirada on surt l'sticker es cobra a 5, i les següents ja a 4.
- `GachaGo.gacha_roll` fa servir aquest cost per comprovar si hi ha prou punts, per cobrar i per al missatge d'error. Un repetit ara retorna
  la meitat del que ha costat la tirada (`cost/2`: 2,5 a preu normal, 2 amb descompte), perquè el text "et torno un 50%" continuï sent cert.
- Els tres botons mostren el cost real de qui mira la pàgina (`request.profile.gacha_roll_cost`, que és qui tirarà si hi clica). Els textos
  passen a ser "Use %(points)s GachaPoints" i "You need %(points)s GachaPoints in order to make a gacha roll". S'han traduït a ca/es/de i
  s'han afegit les etiquetes noves de l'admin. Els `.po` s'han editat directament com a text perquè el diff sigui petit: polib reajustava
  les línies de tot el fitxer.
- L'sticker en si (imatge, nom, descripció, qualitat llegendària, `mega_fanfare` activat per rebre el correu i poder visitar l'alumne si és
  de l'institut) el crea l'usuari des de l'admin, marcant-hi "descompte al gacha".

**Per què:** petició explícita de l'usuari.

**Resultat:** comprovat de punta a punta amb el compte real `jmiracle`, dins una transacció que es desfà al final (backend de correu en memòria, cap
fila deixada a la BD): a preu normal, amb 4,5 punts la tirada es rebutja amb "Necessites 5". Després de rebre un achievement de prova amb
`gacha_discount`, el cost passa a 4 i el botó diu "Usa 4 GachaPoints". En 6 tirades, les normals cobren 4,0 i els repetits 2,0 nets. Amb 3,9
punts, la tirada es rebutja amb "Necessites 4". `msgfmt -c` net als 5 idiomes (només els avisos de capçalera que ja tenia `en`),
`compilemessages` i `manage.py check` nets. Migració aplicada a la BD.

**Pendent:** recarregar uWSGI (`kill -HUP $(cat /home/ubuntu/dmoj-site.pid)`). El mode automàtic de Claude Code ho va bloquejar per ser un
desplegament a producció. Fins que es recarregui, el web corre el codi vell amb la columna nova ja creada.

---

### 93. El gacha ignora sempre la preferència d'animacions reduïdes

**Abans:** `templates/gacha/gacharesult.html` respectava `prefers-reduced-motion: reduce` a tot arreu. Als PCs de l'institut, el Windows té
les animacions desactivades (probablement per política) i el navegador ho reporta com a `reduce`. Per això el gacha hi sortia sense
confeti, flaix ni sacsejada, i el mega fanfare també sense ànecs i amb el fons d'arc de Sant Martí quiet.

**Decisió:** primer es va forçar només per al mega fanfare. Després, a petició de l'usuari, s'ha tret tota la gestió de `reduce` de la pàgina:
- JS: eliminada la funció `prefersReducedMotion()` i les quatre comprovacions que la feien servir (ànecs, pluja de confeti, flaix, sacsejada).
- CSS: eliminats els dos blocs `@media (prefers-reduced-motion: reduce)` (targeta/raigs/banner i fons/ànecs del mega fanfare). Hi queda un
  comentari que explica que no hi és a propòsit.

**Per què:** petició explícita de l'usuari: el gacha és opcional i sempre té fanfàrria, així que qui necessita de debò animacions reduïdes
no hi va igualment.

**Resultat:** comprovat generant la pàgina real (client de test, dins una transacció desfeta) per a un resultat amb `mega_fanfare` i un de normal:
cap dels dos conté ja cap `reduce`, i el JS de la pàgina passa `node --check` en tots dos casos. No s'ha comprovat visualment amb Chromium.
**Pendent:** el mateix `kill -HUP` de l'entrada #92 perquè uWSGI agafi la plantilla.

---

### 94. Achievements amb una pista extra permanent (només en problemes que ja en tenen)

**Abans:** el nombre de pistes d'un problema era `ProblemData.allowed_tips` (per defecte 1), igual per a tothom. Cada enviament en pot gastar
com a molt una, i el límit es comprovava a `flag_submission` i a la plantilla `submission/status-testcases.html` (comptador "Pistes
usades/permeses" i botó "Help!").

**Decisió:**
- Nou camp `Achievement.extra_hint` (booleà, per defecte fals, migració `0157_achievement_extra_hint`). A l'admin només el veuen i el poden
  marcar els superusuaris, com `gacha_discount`.
- Nova propietat `Profile.has_extra_hint` i nou mètode `ProblemData.allowed_tips_for(profile)`: `allowed_tips + 1` si el problema en permet
  almenys una i l'usuari té algun achievement amb `extra_hint`; si no, `allowed_tips`. Els problemes amb 0 pistes es queden a 0. No s'acumula.
- `flag_submission` fa servir `allowed_tips_for(subm.user)` per decidir si queden pistes. La vista de l'enviament passa `allowed_hints` a la
  plantilla, calculat per al **propietari** de l'enviament (no per a qui mira): un professor que mira l'enviament d'un alumne veu el que té
  l'alumne. La plantilla fa servir `allowed_hints` al comptador i a la condició del botó.
- Etiquetes noves de l'admin traduïdes a ca/es/de.

**Per què:** petició explícita de l'usuari (tercer achievement superllegendari).

**Resultat:** comprovat de punta a punta amb el compte real `Vazgen` al problema `flymemoon` (`allowed_tips=1`, 3 enviaments seus), dins una
transacció que es desfà al final (cap fila deixada, flags de pistes intactes): sense l'achievement, la pàgina diu `0/1`, la primera pista
funciona i la segona es rebutja amb "You have no hint reveals left". Amb un achievement de prova amb `extra_hint`, la pàgina diu `1/2`, la
segona pista funciona i la tercera es rebutja. Un problema amb 0 pistes continua a 0. Migració aplicada a la BD abans de recarregar
(el codi nou llegeix la columna). `msgfmt -c`, `compilemessages` i `manage.py check` nets.
**Pendent:** el mateix `kill -HUP` de l'entrada #92.

---

### 95. Secció "Superachievements" a dalt de la pàgina d'usuari

**Abans:** a la pàgina d'usuari, tots els stickers sortien barrejats en una graella d'imatges al final, sense nom ni descripció. Els
superachievements (els que tenen `mega_fanfare`: "Dret a Crear Achievements", el descompte del gacha #92 i la pista extra #94) no es
distingien gens, i ningú podia saber què feien.

**Decisió:**
- `UserAboutPage` (`judge/views/user.py`) passa `super_achievements`: els achievements de l'usuari amb `mega_fanfare`, de qualsevol
  categoria. Es treuen de la graella normal de stickers (`mega_fanfare=False`) perquè no surtin dues vegades.
- `templates/user/user-about.html`: nova secció "Superachievements" a dalt de tot del contingut, que només apareix si l'usuari en té algun.
  Cada un surt en una targeta amb la imatge, el nom i la descripció (renderitzada amb markdown, estil `self-description`, igual que el "Quant a").
- Animacions permanents, només CSS: vora d'arc de Sant Martí que gira (`conic-gradient` amb `@property --super-angle`), resplendor que
  batega, la imatge flotant amb un reflex de llum que la travessa, i "✨" davant del nom. Sense excepció per a `prefers-reduced-motion`,
  igual que el gacha (#93). L'interior de la targeta fa servir `--background-white` (el fons de cada tema) perquè l'arc de Sant Martí només
  es vegi a la vora. En pantalles estretes (≤600px), la targeta passa a columna i centrada.
- Nou text "Super achievements" traduït a ca/es/de ("Superachievements", "Super-Achievements").

**Per què:** petició explícita de l'usuari.

**Resultat:** comprovat generant la pàgina real (client de test) per a `Jonny`, que té "Dret a Crear Achievements": surt la secció amb 1
targeta i la descripció, i l'sticker ja no surt repetit a la graella. Per a un usuari sense cap superachievement, la secció no apareix.
Verificat **visualment** amb captures de Chromium a 1200px i 390px d'amplada, i amb el tema clar i el `theme-dark`. Un primer intent
deixava veure l'arc de Sant Martí per tot el fons de la targeta (capa interior semitransparent); corregit amb la capa opaca del fons del tema.
Les captures són fotos fixes: no s'ha comprovat amb un vídeo que les animacions es moguin. Els navegadors sense `@property` (Firefox
anterior a la 128) veuen la vora quieta, però la resplendor i la imatge flotant també funcionen.
**Pendent:** el mateix `kill -HUP` de l'entrada #92.

**Verificat** després que l'usuari reiniciés el bridge (01:23 del 2026-10-21; els dos jutges s'hi van tornar a connectar sols). Tres enviaments
d'`edgar` al problema privat `aplusb`:
- Java 25 que intenta llançar un procés → **`SEC`** ("execve syscall disallowed"), amb l'avís nou del sandbox a la pàgina (no el del SQL).
- Java 11 que intenta el mateix → **`SEC`** ("Has intentat hackejar-me..."), amb l'avís nou.
- Java 25 amb una solució normal → `AC`, sense cap avís.
- Cap fitxer testimoni creat. L'enviament dels dos correus no es pot confirmar des d'aquí (`fail_silently`), i l'ha de comprovar l'usuari a la
  bústia d'`ADMINS`.

---

### 96. Tres superachievements més: bonus diari doble, assegurança antirepetits (80%) i nom d'arc de Sant Martí

**Abans:** el bonus del primer problema nou del dia era de 5 GachaPoints per a tothom. Un repetit al gacha retornava sempre el 50% del cost
de la tirada (#92), amb el text "et torno un 50%" fix. Els noms d'usuari només es pintaven amb el color del rating.

**Decisió:**
- Tres camps nous a `Achievement` (migració `0158_achievement_more_perks`): `double_daily_bonus`, `duplicate_insurance` i `rainbow_name`.
  Només els superusuaris els veuen a l'admin. La llista de camps restringits és ara `AchievementAdmin.ADMIN_ONLY_FIELDS`.
- `Profile._has_perk(camp)`: comprovació comuna ("té algun achievement amb aquest camp?"), feta servir també per `gacha_roll_cost` i
  `has_extra_hint`. Cap perk no s'acumula.
- **Bonus diari doble:** `Profile.daily_solve_bonus_points` (10 amb el perk, 5 sense), fet servir a `grant_daily_solve_bonus` i al banner de
  l'enviament (`status-testcases.html`).
- **Assegurança antirepetits:** `Profile.duplicate_refund_ratio` (0,8 amb el perk, 0,5 sense). Un repetit retorna `cost * ràtio`: a preu
  normal, 2,5 → 4 punts; amb el descompte també, 2 → 3,2. El text del repetit passa a ser "et torno un %(percent)s%%". El percentatge
  és el de l'usuari que va fer la tirada (`ach.user`), i les traduccions existents (es/en/de/zh_Hans) s'han adaptat.
- **Nom d'arc de Sant Martí:** `link_user` (`judge/jinja2/reference.py`), que pinta gairebé tots els noms d'usuari del web, afegeix la classe
  `rainbow-name` si l'usuari té el perk. El CSS (degradat animat retallat al text, `!important` per sobre del color de rating) és a
  `templates/base.html`, inline, perquè no calgui recompilar els estils. Per no fer una consulta per cada nom (en un rànquing n'hi ha
  centenars), `Profile.rainbow_name_ids()` guarda el conjunt d'ids a la memòria cau compartida (24 h), i cada worker en guarda una còpia
  30 s. Un senyal a `judge/signals.py` (`post_save`/`post_delete` d'`Achievement` i `AchievementObtained`) l'esborra amb
  `transaction.on_commit`. Esborrar-la abans del commit deixaria que una petició concurrent hi tornés a guardar el conjunt antic.
  Conseqüència: un nom nou pot trigar fins a 30 s a sortir amb l'arc de Sant Martí en els altres workers.
- Traduccions noves a ca/es/de per a les etiquetes i ajudes de l'admin.

**Per què:** petició explícita de l'usuari, que va triar el 2, el 3 (amb 80% en lloc del 100% proposat) i el 4 d'una llista d'idees.

**Resultat:** comprovat de punta a punta amb el compte real `jmiracle`, dins una transacció que es desfà al final (correu en memòria, cap fila
deixada, cap raresa canviada). Bonus diari: 5 sense perk, 10 amb perk, 0 si es torna a demanar el mateix dia. Repetit (forçat amb un
`mock` de `random.random` cap al nivell llegendari): sense assegurança cobra 2,5 nets i el text diu "50%"; amb assegurança, 1,0 i "80%";
amb assegurança i descompte, 0,8. Nom: el senyal registra 2 esborrats `on_commit`; executats, `rainbow_name_ids()` inclou l'usuari i
`link_user` dona `class="... rainbow-name"`, mentre que per a un altre usuari no. Captura de Chromium d'una mostra: es veu el degradat,
també per sobre d'un color de rating. Després de la prova, la memòria cau compartida conté el valor real (conjunt buit). `msgfmt -c`,
`compilemessages` i `manage.py check` nets, migració aplicada.

**Incidència i desplegament (#92-#96):** l'usuari va recarregar uWSGI a les 02:00, abans que s'acabés aquesta entrada (02:01-02:11). A les
08:16 un worker es va reiniciar sol: va heretar els models de les 02:00 del procés principal, però en la primera petició va carregar les
vistes noves. Per això `/gacha/result/84574-0` donava `AttributeError: 'Profile' object has no attribute 'duplicate_refund_ratio'`. Amb la
recàrrega completa de les 08:54 (`kill -HUP`, feta per l'usuari) es va resoldre. Comprovat després: tots els workers són de les 08:54,
`/user/Jonny` en viu mostra la secció de superachievements, `/users/` respon 200, i aquell resultat del gacha respon 200 per al seu propietari
(client de test). **Lliçó:** no encadenar més canvis de codi Python mentre hi hagi una recàrrega pendent, o avisar-ne clarament abans.

---

## 2026-10-22

### 97. El comandament `create_db_problems` admet un autor per lot (camp `author`/`authors`)

**Abans:**
El comandament `judge/management/commands/create_db_problems.py` fixava els autors dels problemes amb una constant global `AUTHORS = ('edgar', 'marc')`, i els anava alternant al llarg de tota l'execució. No hi havia manera d'indicar qui havia de constar com a creador d'un lot concret sense editar el codi.

**Decisió:**
S'ha afegit suport perquè cada fitxer de lot (JSON) pugui declarar el seu propi autor amb el camp `"author"` (un sol nom d'usuari) o `"authors"` (una llista). Si el lot no en declara cap, es manté el comportament anterior (alternança sobre `AUTHORS`). Els autors de cada lot es resolen **abans** de crear cap problema, de manera que un nom d'usuari inexistent atura l'execució amb `CommandError` sense deixar problemes a mig crear.

**Per què:**
S'estan migrant a JOEL els exercicis de la plataforma QueryTest (que es tanca per inseguretat del seu PHP antic). Es volia que tots aquests problemes constessin a nom de `joanq` (creador de QueryTest i autor original dels exercicis, que ja té compte a JOEL, id de perfil 113), i no d'`edgar`/`marc`. El camp per lot és la via neta per fer-ho sense tocar la constant global.

**Resultat:**
`create_db_problems` ja llegeix `author`/`authors` de cada lot. Comprovació de sintaxi correcta. Els lots SQL generats a partir de QueryTest porten `"author": "joanq"`. El canvi és retrocompatible: els lots existents sense aquest camp es comporten igual que abans. (De moment només s'ha preparat el codi i els fitxers de lot; la creació efectiva dels problemes a la base de dades encara no s'ha executat.)

---

### 98. Pujar `MAX_REFERENCE_ROWS` de 200 a 20000 a `create_db_problems`

**Abans:**
`create_db_problems.py` rebutjava qualsevol problema la consulta de referència del qual retornés més de 200 files (`MAX_REFERENCE_ROWS = 200`), com a comprovació de sanitat per detectar referències sense `WHERE` o amb un producte cartesià accidental.

**Decisió:**
S'ha apujat el límit a 20000 files.

**Per què:**
En migrar els exercicis de QueryTest, 45 preguntes legítimes retornen més de 200 files (p. ex. un `SELECT` de cognoms de la base `lastnames` que en retorna 16.685, o diverses consultes de `hotel` amb 6.000–7.500 files). Són exercicis vàlids que simplement llisten molts resultats. S'ha verificat que el checker del jutge (`dmoj/checkers/sql.py`) fa `fetchall()` **sense cap límit de files** i només es protegeix amb un guardià de temps (`set_progress_handler` amb deadline), de manera que corregir resultats grans és segur. El límit de 200 era, per tant, només una restricció del validador d'importació, no del jutge.

**Resultat:**
Amb el límit a 20000, les 45 preguntes de >200 files ja validen. Es manté una protecció raonable contra un producte cartesià accidental (res legítim d'aquestes bases s'acosta a 20.000 files, llevat del cas de `lastnames` esmentat, que hi queda per sota).

---

### 99. Creació de 78 problemes SQL migrats de QueryTest (autor `joanq`)

**Abans:**
Els exercicis de QueryTest (159 tests, 1.460 preguntes, plataforma PHP que es tanca per inseguretat) només existien a QueryTest. Es van descarregar tots (enunciat, solució i pista) des de les pàgines d'edició del compte de professor.

**Decisió:**
Es van migrar només les 6 bases de dades que JOEL ja té com a BD de mostra (chinook, hotel, miniwind, traders, northwind, lastnames). Els tests temàtics s'han mantingut com un problema per test; els exàmens (models A/B/C, parcials repetits entre cursos) s'han fusionat sense duplicats en "Examen fusionat N" de 10 preguntes ordenades per dificultat. Els enunciats s'han reescrit a l'estil JOEL, i els que a QueryTest només tenien un títol s'han reconstruït a partir del SQL. Arranjaments mecànics del SQL: s'ha tret el prefix `BD.Taula` i s'han canviat `NVL`→`IFNULL`, `UCASE`/`LCASE`→`UPPER`/`LOWER` i `CHAR_LENGTH`→`LENGTH`. També s'han eliminat els enunciats repetits dins de cada BD. Cada problema té un tipus SQL detectat a partir de les seves consultes.

**Per què:**
QueryTest corria sobre MySQL i el jutge de JOEL usa SQLite. Per indicació de l'usuari, només s'han creat les preguntes que validen tal com estan, sense reescriure SQL. Les que fallen queden aparcades temporalment: funcions MySQL de data, `ALL`/`ANY`, sintaxi no suportada, i les que retornen 0 files perquè les BD de mostra de JOEL tenen dades diferents (p. ex. cognoms en majúscules a `lastnames`).

**Resultat:**
78 problemes privats (`sql<bd>qtNN`), amb 530 preguntes en total, autor `joanq` i tipus assignat. 116 preguntes queden aparcades (`parked_<bd>.json` al scratchpad de la sessió) per revisar-les més endavant. Verificat a la BD: 78 problemes, 530 casos, 0 públics, cap sense tipus.

Posteriorment, a petició de l'usuari, s'ha enviat la solució de referència de tots 78 com a `edgar` amb `submit_reference_answers`: els 78 han obtingut AC amb la puntuació màxima, i llavors s'han publicat (`is_public=True` i `date` = data de publicació, com els altres problemes SQL públics). S'ha comprovat que tres d'ells es veuen sense iniciar sessió a https://jo-el.es.

---

### 100. Segona instància de MariaDB per corregir problemes SQL amb sintaxi MySQL (fase 1: servidor)

**Abans:**
El jutge SQL de JOEL només sap corregir sobre SQLite. Els alumnes, que a classe fan servir MySQL, poden topar amb consultes que fallen a JOEL (`YEAR()`, `DATEDIFF()`, `> ALL`, `GROUP_CONCAT ... SEPARATOR`, `BD.Taula`...) o, encara pitjor, que donen un resultat diferent sense cap error: la divisió entera (`5/2` és `2` a SQLite i `2.5` a MySQL), o `WHERE Name='Puig'`, que a MySQL troba `PUIG` gràcies a la col·lació que no distingeix majúscules i a SQLite no.

**Decisió:**
S'ha triat l'opció de corregir amb un MySQL/MariaDB de veritat, en lloc d'emular-lo sobre SQLite. Primera fase: el servidor. S'ha creat una **segona instància de MariaDB 10.5, separada de la BD del web**, a `/home/ubuntu/mariadb-grader/`:
- Corre com a usuari `ubuntu` (no hi ha `sudo` sense contrasenya), dins d'un `screen` anomenat `mariadb-grader`, igual que els jutges. S'ha afegit `@reboot` al crontab d'`ubuntu` perquè torni a arrencar si es reinicia el servidor.
- `skip-networking`: sense port de xarxa, només socket a `/home/ubuntu/mariadb-grader/run/mysqld.sock`. El directori té permisos 700.
- `innodb_buffer_pool_size=128M`, `max_connections=20`, `performance_schema=OFF`, `local_infile=0`, `secure_file_priv` apuntant a un directori buit, i col·lació per defecte `utf8mb4_general_ci`.
- L'administració es fa com a `ubuntu` via socket: `mariadb --defaults-file=/home/ubuntu/mariadb-grader/my.cnf`.
- Usuari de correcció `joel_grader`: només `SELECT`, BD per BD (mai `*.*`), `MAX_STATEMENT_TIME 5` i `MAX_USER_CONNECTIONS 10`. Les credencials són a `/home/ubuntu/.secrets/joel_grader.cnf` (permisos 600).

S'han carregat els dumps MySQL de `importacions/`: `Chinook` (versió amb claus autoincrementals, que és la que fa servir QueryTest), `hotel`, `miniwind`, `traders`, `northwind` (estructura + dades), `lastnames`, `futbol24`, `valorantProMatches`, `ies23g` (renomenada des de `ies23g.sql`; aquell fitxer comença amb `drop database if exists ies23` i s'ha canviat només a les línies 18–20 perquè no esborrés l'altra `ies23`), `company`, `knightsdb` i `groupbytest`. A `futbol24.sql` s'ha saltat la primera línia (`/*M!999999\- enable the sandbox mode */`, una capçalera de `mariadb-dump` 10.11.8+ que el client 10.5 no entén i que no conté dades).

**Per què:**
És l'única opció que resol alhora la sintaxi MySQL, les diferències silencioses (divisió, col·lació) i, quan hi hagi dumps, les BD que JOEL no té. Una instància a part evita que una consulta abusiva d'un alumne alenteixi el web, o que un error de permisos exposi dades reals.

**Resultat:**
- Les 6 BD que JOEL ja tenia en SQLite tenen **exactament el mateix nombre de files** a MariaDB: les SQLite es van fer a partir d'aquests mateixos dumps. Les "dades diferents" detectades en migrar QueryTest eren, en realitat, diferències de comportament del motor.
- Verificat amb `joel_grader`: funcionen `WHERE Name='Puig'`, `YEAR()`/`MONTH()`, `DATEDIFF(...NOW())`, `> ALL`, `GROUP_CONCAT ... SEPARATOR`, `Chinook.Artist` i `5/2 = 2.5`. Queden bloquejats `INSERT`, `CREATE`, `DROP DATABASE`, `INTO OUTFILE`, la lectura de `mysql.user`, l'accés a BD sense permís i `SET GLOBAL`. `LOAD_FILE('/etc/passwd')` retorna NULL. `SLEEP(8)`, `BENCHMARK(...)` i un producte cartesià triple es tallen tots als ~5 s.
- **Pendent:** `noms.sql` i `ies23.sql` estan malmesos. Després de cada "Dumping data for table X" hi falten les línies `LOCK TABLES` i `INSERT INTO X VALUES (` i el principi de les dades: per exemple, els noms de `female_names` anteriors a "ADRIANA FLORENTINA", o les files d'`alumnes_moduls` anteriors a la 643. Han quedat creades com a BD buides i sense permisos per a `joel_grader`. Cal tornar-les a exportar. Segons la capçalera de `noms.sql`, venen del servidor 162.19.137.5.
- Encara no ho fa servir cap jutge. Fases següents: checker `mysql` al jutge, suport a la part web, i migració dels problemes "QT".

---

### 101. Checker `mysql` al jutge i suport a la part web (fases 2 i 3a)

**Abans:**
La instància MariaDB de correcció (#100) existia, però ni el jutge ni el web la sabien fer servir.

**Decisió:**
- **Jutge** (repo `site-packages/dmoj`, commit `a56460c`): nou `checkers/mysql.py`, registrat a `checkers/__init__.py`. Executa la consulta de referència i la de l'alumne amb l'usuari `joel_grader` (credencials a `/home/ubuntu/.secrets/joel_grader.cnf`, mai a l'`init.yml`) sobre la BD indicada a l'argument `database`. Reaprofita de `sql.py` el tall per preguntes (`-- @@Q<n>@@`), la detecció del tipus de sentència, la llista negra que marca SEC i la comparació de resultats. Particularitats:
  - Només SELECT: una referència INSERT/UPDATE dona un error de configuració.
  - Llegeix en streaming com a màxim una fila més de les esperades. Si n'hi ha més, tanca el socket sense buidar el resultat (MariaDB avorta la consulta) i respon "got more than N". Un producte cartesià de 12 milions de files es resol en 0,08 s sense omplir la memòria del jutge.
  - Normalitza els valors per comparar com amb SQLite: `DECIMAL` es converteix a float (s'hi aplica la tolerància); els nombres sencers es converteixen a int (3, 3.0 i 3.00 són iguals); les dates i hores passen a text en format MySQL.
  - Timeout de lectura al client (15 s) a més del `MAX_STATEMENT_TIME` del servidor.
  - També un `.gitignore` per a `__pycache__/` i `*.pyc`.
- **Web:**
  - `judge/utils/mysql_grader.py` (nou): connexió de només lectura, llista de BD del catàleg (`SHOW DATABASES`; les etiquetes es reaprofiten de les BD SQLite si el nom coincideix), esquema llegit d'`information_schema` (taules, columnes, PK i FK) i `run_query` per validar referències.
  - Nova opció de checker `mysql` ("Verificador MySQL") a `ProblemData`/`ProblemTestCase`. La migració `0159_problemdata_mysql_checker` només canvia les opcions i no executa cap SQL.
  - `DATABASE_CHECKERS` inclou `mysql`: el problema té el formulari d'enviament amb una caixa per pregunta, el botó d'esquema i el diagrama ER.
  - `ProblemDataCompiler` genera `checker: {name: mysql, args: {database: ...}}`. La BD es desa als `checker_args` del problema com a `{"database": "..."}`, validada amb `^[A-Za-z0-9_]{1,64}$`.
  - Formulari de dades del problema: camp "Base de dades MySQL" (un desplegable amb el catàleg; només es mostra amb el checker `mysql`). En desar, es guarda a `checker_args`.
  - Vista d'esquema: branca `mysql` que fa servir la mateixa plantilla i el mateix diagrama.
  - `create_db_problems`: camp `"engine": "mysql"` (per lot o per problema). Valida les referències contra MariaDB, crea el problema amb checker `mysql` i no hi desa cap fitxer `.db`. La descripció hi afegeix que les consultes s'executen sobre MySQL.
  - **Correcció d'un parany:** amb `--replace`, `create_db_problems` tornava a posar `is_public = False`, de manera que convertir un problema ja publicat el despublicava. Ara només es posa privat un problema nou.
  - Traduccions al català de les cadenes noves (`msgfmt -c` net, `compilemessages -l ca`).

**Per què:**
Fases 2 i 3a del pla per corregir amb MySQL de veritat (#100). La fase 3b, la pujada d'un dump `.sql` propi per problema (BD `p_<codi>` carregada amb un usuari temporal limitat a aquella BD), queda pendent.

**Resultat:**
- L'usuari va reiniciar els dos jutges a mà (19:52–19:53). Llavors es va recarregar uWSGI amb `kill -HUP` al màster; els treballadors nous responen 200.
- Problema de prova privat `zzmysqltest01` (BD `northwind`, 4 preguntes amb `YEAR()`/`MONTH()`, `DATEDIFF(IFNULL(...,NOW()))`, `'Puig'` sobre `lastnames.LastNames` i `> ALL`): validat per `create_db_problems`, i la solució enviada com a `edgar` ha obtingut **AC 4/4 al jutge real** (NouJutge, enviament 370621).
- Amb sessió d'administrador, les pàgines del problema, l'enviament (caixes per pregunta), l'esquema (taules + ER des de MariaDB) i les dades (desplegable amb el catàleg, `northwind` seleccionada) responen 200.
- Provat també el checker directament: 7 casos amb sintaxi MySQL donen AC, i 10 de dolents fallen amb el missatge correcte (inclòs `@@SECVIOL@@` per a `DROP`). No queden connexions obertes.

---

### 102. Tots els problemes SQL de SELECT passen a corregir-se amb MySQL (MariaDB)

**Abans:**
209 problemes es corregien amb SQLite: els 78 de QueryTest ("QT"), 126 dels lots de `problem_batches/sql/` i 5 de fets a mà. A més, hi havia 116 preguntes de QT aparcades perquè no funcionaven a SQLite.

**Decisió:**
Per indicació de l'usuari, s'han passat a MySQL tots els problemes de SELECT. Els 16 d'INSERT/UPDATE (`sqlins01-05`, `sqlupd01-05`, `sqlinsert{chinook,employees,knights}`, `sqlupdate{groupby,hotel,traders}`) es queden a SQLite fins que hi hagi un checker d'escriptura. Es va acordar que seria un checker a part, `mysqlwrite`, amb transacció + `ROLLBACK` i un usuari d'escriptura propi. `mysql` es queda només per a SELECT, i un INSERT/UPDATE en una pregunta de SELECT acabarà marcant SEC.

1. **QT**: s'han regenerat des dels lots originals amb **el SQL original de QueryTest** (MySQL), sense els arranjaments mecànics de l'entrada #99. S'hi han tornat a posar les 116 preguntes aparcades al seu lloc, i els codis s'han mantingut associant-los per nom. Reapareix un problema que s'havia buidat sencer, `sqlchinookqt29` ("Chinook QT — Funcions 01"). 622 preguntes validen a MariaDB; s'han aplicat amb `create_db_problems --replace`, que ara manté públics els problemes publicats. **24 preguntes queden aparcades** perquè la seva referència retorna 0 files amb aquestes dades (factures amb un total que no quadra, habitacions sense estades, reserves de dates concretes…). Amb una referència buida, qualsevol consulta buida treu AC; l'usuari creu que no era el comportament volgut i ho consultarà.
2. **Lots antics**: s'ha comparat, pregunta per pregunta, el resultat de cada referència a SQLite i a MariaDB, amb la mateixa funció de comparació del checker: 438 iguals, 37 fallaven a MariaDB i 19 donaven resultats diferents. S'han traduït 42 referències a MySQL (`strftime`→`DATE_FORMAT`/`YEAR`, `julianday`→`DATEDIFF`, `||`→`CONCAT`, `LENGTH`→`CHAR_LENGTH`, `CAST(... AS INTEGER)` fora, àlies a les taules derivades). Comprovat: 33 donen exactament el mateix resultat que abans. Les altres 9 canvien perquè MySQL és més correcte:
   - la còpia SQLite de Chinook tenia `\"` en lloc de `"` (4 preguntes);
   - `Ç` i `C` s'agrupen juntes amb la col·lació (2);
   - `189/2` és 94.5, no 94 (1);
   - `LOWER('Ñ')` dona `ñ` (1);
   - la correlacionada de `sqlsub04` q1 retornava 110 files per errors de coma flotant i en realitat la resposta és buida, així que **s'ha aparcat** (1).

   Els fitxers del repo `problem_batches/sql/*.json` s'han editat com a text, sense reformatar: als 110 problemes de SELECT s'hi ha afegit `"engine": "mysql", "database": "<nom a MariaDB>"` (`Chinook`, `company` per a `employees`, `knightsdb` per a `knights`…), i s'hi han canviat les referències traduïdes. Abans es va comprovar que els 120 problemes dels lots coincidien exactament amb el que hi havia publicat, i després s'han aplicat amb `--replace --only` per als 110 codis.
3. **Els 5 fets a mà** (`provasql2`, `sqlselects`, `sqljoins`, `sqlagregacions`, `sqldificil`): feien servir un altre `miniwind.db`, de l'estil Northwind (`categories`, `unit_price`, `company_name`…), comú a tots cinc. S'ha convertit a MariaDB com a `miniwind_classic` (5 taules, 51 files, amb PK i FK; l'script és a `.../scratchpad/miniwind_classic.sql`), amb `GRANT SELECT` per a `joel_grader`. Les 13 referències donen el mateix resultat. S'han passat a `mysql` directament (checker i casos) i s'ha regenerat l'`init.yml`; el fitxer `.db` que tenien no s'ha esborrat.
4. **Error del checker arreglat** (repo del jutge, commit `d1f0df5`): la comprovació "Only a single SQL statement is allowed" partia pels `;` encara que fossin dins d'un literal (`LIKE '%;%'`) o d'un comentari, i rebutjava consultes correctes. Afectava també els alumnes. Ara treu literals i comentaris abans de comptar.
5. `submit_reference_answers` té una opció nova, `--force`, per tornar a enviar la solució encara que `edgar` ja tingui AC (per exemple, després de canviar el checker).

En convertir amb `create_db_problems --replace`, el codi existent esborra el fitxer `.db` dels QT i dels lots. Eren còpies de les plantilles de `/judge/_sql_templates/`, que es conserven.

**Per què:**
Que el comportament de JOEL sigui el de MySQL que veuen els alumnes a classe, i que no quedin dos dialectes barrejats.

**Resultat:**
195 problemes amb checker `mysql` (79 QT, 110 de lots, 5 de fets a mà i el de prova `zzmysqltest01`) i 16 encara amb `sql`, tots d'escriptura. Els que eren públics continuen públics. Les 25 preguntes aparcades s'han copiat al repo, a `problem_batches/sql/aparcades/` (amb un `README.md`). Al mateix lloc hi ha el bolcat complet dels 159 tests de QueryTest (`querytest_bolcat_complet.json`, l'única còpia quan es tanqui la plataforma) i, a `revisar_enunciats/`, les notes dels enunciats reconstruïts. Els lots dels problemes QT són ara al repo com a `problem_batches/sql/querytest_<bd>.json` (validen sense errors), i l'script de `miniwind_classic` és a `/home/ubuntu/mariadb-grader/fonts/`.

---

### 103. Verificació amb el jutge real i preguntes no deterministes

**Abans:**
Els 195 problemes MySQL (#102) estaven creats, però encara no s'havien corregit amb el jutge real.

**Decisió:**
Un cop l'usuari va reiniciar els jutges (20:10, amb `d1f0df5` carregat), s'ha enviat com a `edgar` la solució de tots 195 (`submit_reference_answers --force`). 191 van treure AC. Els 4 restants van treure WA en una pregunta perquè la referència **no era determinista**: comparada amb ella mateixa, donava un altre resultat. Tres eren "top 10" amb empats a la 10a posició (`sqlchinookqt10` q2, `sqlchinookqt16` q2, `sqlhotelqt03` q1) i una era un `GROUP_CONCAT` sense `ORDER BY` (`sqlhotelqt05` q4). Per decisió de l'usuari, s'hi ha afegit un desempat a la referència i a l'enunciat ("en cas d'empat, ordena alfabèticament pel compositor", "per `CustomerId`", "serveis en ordre alfabètic").

Després s'han revisat totes les preguntes MySQL:
- **1.119 referències executades 5 vegades:** cap altra canvia de resultat.
- **58 referències amb `ORDER BY ... LIMIT n`:** s'han executat amb `LIMIT n+1` per detectar empats just al tall. Només en surt `sqlchinookqt11` q6.
- **Referències amb `||` o `&&` fora de literals:** se n'han trobat 2 (`sqlchinookqt11` q6 i `sqlhotelqt04` q3). Venien de QueryTest i a MySQL `||` és un OR, de manera que la columna "Client" sortia `0` en lloc del nom, i un alumne que escrivís `CONCAT` treia WA. S'han canviat per `CONCAT(...)`. A la primera, a més, molts clients empaten amb 38 pistes, així que s'hi ha afegit "si n'hi ha diversos empatats, el primer per ordre alfabètic del nom complet", i s'ha tret el `||` de l'enunciat.

Els canvis s'han fet als lots del repo (`querytest_chinook.json`, `querytest_hotel.json`) i s'han aplicat amb `--replace --only`. Finalment s'ha publicat `sqlchinookqt29`, que ja tenia AC.

**Per què:**
Una referència no determinista pot donar WA a un alumne amb la consulta correcta només per l'ordre en què MariaDB llegeix les files.

**Resultat:**
Els 195 problemes MySQL tenen l'últim enviament d'`edgar` amb AC complet; 194 són públics (el privat és el de prova, `zzmysqltest01`). **Avís:** 9 referències depenen de la data actual (`NOW()`, `CURDATE()`, `CURRENT_DATE`...): `sqlnorthwindqt02` q1, `sqltradersqt05` q8, `sqlhotelqt04` q3, `sqlhotelqt05` q6, `sqlhotelqt08` q4, `sqlchinookqt17` q8, `sqlchinookqt29` q2 i q4, i la de prova. Avui funcionen, perquè la referència i l'alumne es corregeixen alhora. Però si n'hi ha alguna del tipus "els últims N anys", amb el temps es pot quedar sense resultats, i llavors qualsevol resposta buida seria acceptada.

---

### 104. Escriptures amb MySQL (checker `mysqlwrite`) i BD pròpia per problema (dump `.sql`)

**Abans:**
El checker `mysql` només corregia SELECT, de manera que els 16 problemes d'INSERT/UPDATE es corregien encara amb SQLite. Un professor només podia fer servir una BD del catàleg MariaDB. Per carregar-hi BD calia fer-ho a mà amb el client `mariadb`.

**Decisió (acordada amb l'usuari):**
- **Dos checkers separats.** `mysql` només fa SELECT i té només credencials de lectura. Ara, si en una pregunta de SELECT l'alumne envia una sentència d'escriptura o de control (`INSERT`, `UPDATE`, `DELETE`, `REPLACE`, `SET`, `LOCK`, `CALL`, `COMMIT`…), es marca **SEC**. Una errada de tecleig (`selec`) continua sent un error normal. El nou `mysqlwrite` (repo del jutge, commit `18b5495`) corregeix **INSERT, UPDATE i DELETE**; per decisió de l'usuari, DELETE ara s'admet amb MySQL. `DROP`, `TRUNCATE`, `ALTER`… continuen sent SEC.
- **Com corregeix `mysqlwrite`:** executa la sentència de l'alumne i la de referència dins d'una transacció a la **còpia d'escriptura `w_<bd>`**, compara el contingut final i sempre fa `ROLLBACK`.
  - Només es tornen a llegir les taules el `CHECKSUM TABLE` de les quals ha canviat: una pregunta sobre `hotel` passa de 3,7 s a 0,96 s.
  - Els valors `AUTO_INCREMENT` nous es comparen com a "nous", perquè InnoDB no desfà el comptador.
  - Si l'altre jutge té bloquejades les files, s'espera fins a 3 s i es reintenta.
  - El professor només tria "Verificador MySQL": quan es genera l'`init.yml`, cada pregunta va a `mysql` o a `mysqlwrite` segons la seva referència (`ProblemDataCompiler`, que la llegeix del zip).
- **Usuaris nous a la instància.** Cada usuari té les credencials al seu fitxer, a `/home/ubuntu/.secrets/`, amb permisos 600.
  - `joel_writer`: SELECT/INSERT/UPDATE/DELETE **només** sobre `w\_%`.
  - `joel_loader`: `CREATE USER` i tots els permisos amb `GRANT OPTION` **només** sobre `p\_%` i `w\_%`.
  - A més, `joel_grader` ara també pot llegir les BD `p\_%`.
  - `max_allowed_packet` passa a 64M (al `my.cnf` i amb `SET GLOBAL`).
- **Còpies `w_*` de les 13 BD del catàleg.** S'han creat amb la nova comanda `manage.py load_grader_db <nom> <fitxers...> [--copy-only]`, que carrega un catàleg i la seva còpia des de dumps. S'ha verificat que cada `w_*` té exactament les mateixes files que l'original.
- **Càrrega de dumps** (`judge/utils/mysql_grader.py`):
  - El text **no passa mai pel client `mariadb`**, que executaria ordres com `\! comanda` al servidor. S'envia pel protocol, en una sola petició multisentència.
  - Ho fa un **usuari temporal** amb permisos només sobre la BD de destinació, que s'esborra en acabar.
  - Abans d'enviar-lo, es treuen les línies `CREATE/DROP DATABASE` i `USE`, les clàusules `DEFINER=` i la capçalera de "sandbox mode" de `mariadb-dump` 10.11+. També es descarten les sentències condicionals per a versions més noves (`/*M!100616 ... */;`), es treuen els prefixos amb el nom de la BD original (`` `miniwind`.`customers` ``) i es converteix `DELIMITER`.
  - Totes les taules es passen a InnoDB. Si la càrrega falla, la BD s'esborra.
  - En el `GRANT` per a l'usuari temporal, el nom de la BD s'escapa (`p\_codi`): en un GRANT el `_` és un comodí, i sense escapar el carregador no hi tenia permís.
- **BD pròpia per problema:**
  - Camp nou `ProblemData.mysql_dump` (migració `0160`: `ADD COLUMN mysql_dump varchar(100) NULL`).
  - Al formulari de dades, el dump (com a màxim 10 MB) es carrega a `p_<codi>` i `w_p_<codi>` **durant la validació**: si MariaDB el rebutja, l'error surt al formulari i no es desa res. Si hi ha dump, té prioritat sobre la BD del catàleg; si s'esborra, es fan servir el catàleg i les BD `p_`.
  - Si se'n canvia el codi, es torna a carregar amb el nom nou. Si s'esborra el problema, un senyal `post_delete` de `ProblemData` esborra `p_<codi>` i `w_p_<codi>`.
  - El desplegable del catàleg ja no mostra les BD `p_*`/`w_*`.
- **`create_db_problems`:** amb `"engine": "mysql"` accepta INSERT/UPDATE/DELETE i les valida a la còpia `w_`: s'han d'executar i han de canviar alguna cosa. La descripció ja no diu "No es permet `DELETE`" als problemes MySQL.
- **Conversió dels 16 problemes d'escriptura:** s'ha comparat, per a cada una de les 113 referències, el canvi que fa a SQLite i a MariaDB (files afegides i esborrades per taula, amb els ids nous com a "nous").
  - 98 fan exactament el mateix canvi.
  - 13 s'han traduït i ara també fan el mateix canvi: `||`→`CONCAT`, `date(x,'+30 days')`→`DATE_ADD(x, INTERVAL 30 DAY)`, `CAST(... AS INTEGER)`→`TRUNCATE(...,0)` per conservar la truncació de SQLite, i subconsultes sobre la mateixa taula o amb `LIMIT` dins d'`IN` embolcallades en una taula derivada.
  - 1 (`sqlupd02` q1) només difereix pel `\"` de la còpia SQLite de Chinook.
  - **1 aparcada** (`sqlupd03` q4): demana posar 'Pending' a `Stays.PaymentType`, que a MariaDB és `ENUM('Card','Cash')`. És a `problem_batches/sql/aparcades/lots_escriptures.json`.
  - Els 10 de lots s'han aplicat amb `--replace --only` (afegint `"engine": "mysql"` als fitxers del repo) i els 6 fets a mà, directament.

**Per què:**
Completar el pas a MySQL (#100–#103): que no quedi res a SQLite, i que els professors puguin fer servir les seves pròpies BD MySQL.

**Resultat:**
- **211 problemes SQL amb checker `mysql`, 0 amb `sql`** (SQLite).
- Proves directes del checker d'escriptura: 6 casos correctes donen AC (també amb columnes en un altre ordre, un `WHERE` diferent amb el mateix efecte, i `AUTO_INCREMENT` sense id); 7 d'incorrectes o perillosos fallen bé (`DROP`/`TRUNCATE` donen SEC, i una clau forana violada dona l'error de MariaDB). No queda res escrit a les còpies. Amb dos correctors concurrents modificant la mateixa taula, 6 de 6 AC i la còpia intacta.
- Atacs al carregador: `\!`, `system` i `source` són errors de sintaxi i no creen cap fitxer. Llegir `mysql.user`, esborrar `hotel.Rooms`, `CREATE USER`, `GRANT`, `INTO OUTFILE`, `SET GLOBAL` o escriure en una altra `p_` són denegats. `LOAD_FILE` desa NULL. No queden usuaris temporals.
- Prova de punta a punta al formulari web amb `zzmysqltest01`: un dump erroni mostra l'error i no es desa; el dump de northwind es carrega a `p_` i `w_p_` (20 taules, 48 comandes), passa a ser la BD del problema, i funcionen l'`init.yml`, l'esquema i el diagrama ER. Traduccions al català afegides.
- L'usuari va reiniciar els dos jutges (20:47–20:48) i va fer `supervisorctl restart all` (uWSGI i bridge a les 20:48). Jutges en línia, web amb resposta 200, i la instància MariaDB de correcció no es va aturar.
- S'ha enviat com a `edgar` (`--force`) la solució dels 16 problemes d'escriptura i de `zzmysqltest01` (ara amb la BD pròpia `p_zzmysqltest01`): **17 de 17 AC** amb els jutges reals.
- Després de les correccions reals, el `CHECKSUM TABLE` de totes les taules de les 14 còpies `w_*` coincideix amb el de les originals: no ha quedat cap canvi.

---

### 105. Migració dels tests de QueryTest de sakila, valorantProMatches, futbol24 i ies23 (28 problemes més)

**Abans:**
Del bolcat de QueryTest quedaven unes 575 preguntes sense migrar perquè JOEL no tenia les seves BD.

**Decisió:**
- **Sakila:** descarregada del web oficial de MySQL (`downloads.mysql.com/docs/sakila-db.tar.gz`, sha256 `683e957d…`). Es va inspeccionar abans de carregar-la (16 taules, 7 vistes, 6 triggers, 6 rutines, cap ordre de client) i es va carregar al catàleg amb `load_grader_db` (`sakila` i `w_sakila`).
- **ies23:** les preguntes de QueryTest encaixen amb `ies23g`, la versió que es va poder carregar: 23 de les 27 solucions diferents funcionen. Les 4 que no ho fan són del test #209, "ies26 - Subconsultes 01": a QueryTest constava com a `ies23`, però fa servir l'esquema d'ies26, així que queda per a quan hi hagi ies26. A les solucions s'ha tret el prefix `ies23.`.
- **Dues millores al carregador de dumps** (`mysql_grader.load_dump`), trobades amb sakila:
  - Els prefixos de la BD original es treuen també quan no van entre cometes (`sakila.actor`).
  - Cada BD carregada té un **usuari propietari fix**, `own_<bd>`, que només té permisos sobre la seva BD i es **bloqueja** (`ACCOUNT LOCK`) en acabar la càrrega, en lloc d'un usuari temporal que s'esborrava. Les vistes, els triggers i les rutines del dump queden a nom seu i funcionen. Amb l'usuari temporal esborrat, les vistes donaven "Access denied" i els triggers haurien fallat a les còpies `w_`. `drop_problem_databases` també esborra aquests usuaris. Comprovat: la vista `film_list` es pot llegir, el trigger `ins_film` funciona dins d'una transacció a `w_sakila`, i no es pot entrar com a `own_sakila`.
- **Mateix procés que els QT anteriors** (#99): els tests temàtics fan un problema cadascun, i els exàmens es fusionen sense duplicats en blocs de 10 per dificultat. 3 subagents van reescriure els enunciats a l'estil JOEL i van reconstruir a partir del SQL els que només eren un títol. 245 de les 249 solucions originals funcionaven tal com eren a MariaDB. **4 de sakila retornen 0 files i s'han aparcat** (`problem_batches/sql/aparcades/querytest_sakila_resposta_buida.json`). També s'han tret 20 preguntes de sakila amb un SQL idèntic a una altra.
- **3 empats al `LIMIT` arreglats** amb desempat a la solució i a l'enunciat: `sqlsakilaqt12` q5, `sqlsakilaqt14` q6 i `sqlvalorantqt05` q7. Hi ha un **detector d'empats nou**: afegeix `RAND()` com a últim criteri de l'`ORDER BY` i executa la consulta 8 vegades. El detector anterior no veia els empats quan la columna d'ordenació no sortia al resultat. S'ha passat a les 113 consultes amb `LIMIT` de tots els problemes MySQL publicats i no n'hi ha cap més.
- **Error del checker arreglat** (repo del jutge, commit `83ef8e6`): una consulta que comença amb parèntesi, com `(SELECT …) UNION (SELECT …)`, es rebutjava amb "Expected a SELECT statement". Ara la paraula clau es busca després dels parèntesis d'obertura, i `(DROP …)` continua sent SEC. També s'ha aplicat a la funció del web que tria entre `mysql` i `mysqlwrite`.
- Etiquetes per al desplegable del catàleg de les BD sense equivalent SQLite (`MYSQL_DATABASE_INFO` a `mysql_grader.py`): Sakila, Valorant Pro Matches, Futbol24, IES 2023, Miniwind clàssica, Employees (`company`) i Knights & Dragons (`knightsdb`).

**Per què:**
Aprofitar les BD que ja eren a `importacions/`, més sakila (la BD d'exemple oficial de MySQL), per migrar més tests de QueryTest abans de tancar-lo.

**Resultat:**
- **28 problemes nous, amb 225 preguntes**, autor `joanq`:
  - `sqlsakilaqt01-18`: 135 preguntes;
  - `sqlvalorantqt01-06`: 54;
  - `sqlies23qt01-03`: 22;
  - `sqlfutbolqt01`: 14.
- Els 28 tenen AC d'`edgar` amb el jutge real i, per decisió de l'usuari, s'han publicat. Es veuen sense iniciar sessió.
- Els lots són al repo (`problem_batches/sql/querytest_{sakila,valorantProMatches,futbol24,ies23g}.json`), i les notes de revisió a `aparcades/revisar_enunciats/`.
- **A revisar:** en 4 preguntes de valorant i en unes 10 de sakila, l'enunciat original de QueryTest i la seva solució no coincidien. Per exemple, "el mapa més jugat" amb un `ORDER BY COUNT(*)` sense `DESC`. L'enunciat nou descriu el que fa el SQL, però potser l'error era del SQL. Estan detallades a les notes de revisió.
- **Dades d'`ies23g` revisades (2026-10-22):** la taula `usuaris` té 188 persones amb noms, correus `@ies-sabadell.cat`, dates de naixement i una columna `password`. Com que els problemes `sqlies23qt*` són públics, es va consultar a l'usuari si eren dades reals. L'usuari confirma que els correus no tenen el format real del centre: són dades generades per a l'exercici. Els problemes es mantenen publicats.
- **Encara sense BD:** ies26 (146 preguntes, i les 4 del test #209), ies (34), cinema (20), pilotador (19), noms (11, el dump està malmès) i "Múltiples taules" (9).
- L'usuari va reiniciar els jutges i va fer `supervisorctl restart all` (21:06). Els dos jutges estan en línia, el web respon 200 i la instància de correcció continua en marxa. Prova amb el jutge real: un enviament a `zzmysqltest01` amb les 4 consultes de referència entre parèntesis ha donat **AC 4/4** (enviament 370882, NouJutge).
- A petició de l'usuari, s'ha esborrat el problema de prova `zzmysqltest01`: era privat, només tenia 4 enviaments d'`edgar` i no era a cap concurs. `Problem.delete()` va esborrar 35 files (el problema, les seves dades, 4 casos, 4 enviaments amb els seus 16 resultats de cas...). El senyal `post_delete` de `ProblemData` va esborrar `p_zzmysqltest01` i `w_p_zzmysqltest01` de MariaDB, que és la primera comprovació real d'aquest senyal. La carpeta `/judge/zzmysqltest01/` (`data.zip`, `init.yml`, `northwind.sql`), que Django no esborra, s'ha esborrat a mà.

---

### 106. Ja no es poden crear problemes SQL amb SQLite (pas 1 de la retirada del checker `sql`)

**Abans:**
Després de les entrades #102–#105, cap problema ni cap cas fa servir el checker `sql` (SQLite). Els 238 problemes SQL fan servir `mysql`, i cap `init.yml` del jutge esmenta `sql`. Tot i així, el formulari de dades encara oferia "SQL checker", la pujada d'un fitxer `.db` i el selector de BD d'exemple SQLite, i `create_db_problems` feia servir SQLite per defecte si un lot no indicava `"engine"`.

**Decisió:**
L'usuari ha triat el pas 1 de tres: tancar la porta a problemes SQLite nous **sense esborrar res**.
- La migració `0161_remove_sqlite_checker_choice` treu "SQL checker" de les opcions de `ProblemData.checker` i `ProblemTestCase.checker`. Només canvia les opcions, no executa SQL.
- Al formulari de dades (`judge/views/problem_data.py`) s'han tret el camp `sql_db`, el selector `sql_template`, la seva validació i la còpia de la plantilla en desar. A `templates/problem/data.html` s'ha tret el JavaScript que els mostrava o amagava.
- `create_db_problems` fa servir `mysql` per defecte, i amb `"engine": "sqlite"` dona un error clar en lloc de crear un problema SQLite.

Es manté, inactiu:
- el checker `sql.py` del jutge, que a més és la base de `mysql.py` i `mysqlwrite.py`, que n'importen el tall per preguntes, la detecció del tipus de sentència, la llista negra SEC i la comparació de resultats;
- `'sql'` a `DATABASE_CHECKERS`;
- el camp de model `sql_db`;
- la branca SQLite de la vista d'esquema;
- les plantilles de `/judge/_sql_templates/` (9 BD, 9,6 MB);
- els fitxers `.db` antics d'11 problemes (els 5 fets a mà i els 6 d'escriptura), que ja no es fan servir.

**Per què:**
Que un professor no creï, sense adonar-se'n, un problema SQL que es corregeixi amb un altre dialecte que la resta.

**Resultat:**
Amb sessió d'administrador, el desplegable de checkers ofereix `standard`, `rstripped`, `sorted`, `identical`, `linecount`, `mongo` i `mysql`. Al formulari ja no hi ha els camps SQLite, i hi continuen el dump MySQL i la BD del catàleg. Tots els fitxers de lots del repo validen sense errors amb MySQL com a únic motor. `manage.py check` és net. Cal recarregar el web perquè els professors vegin el formulari nou.

**Pendent (passos 2 i 3, si es decideix):**
- Moure les funcions compartides de `sql.py` a un mòdul base i treure el checker `sql`.
- Retirar el camp `sql_db` (una migració que esborra una columna; abans cal mirar-ne els valors).
- Treure el codi SQLite que queda.
- Esborrar els `.db` antics i les plantilles, amb còpia de seguretat abans.

---

### 107. 18 problemes nous d'INSERT/UPDATE/DELETE, REPLACE admès i rellotge fix a la correcció

**Abans:**
Hi havia 238 problemes SQL, però només 16 eren d'escriptura (112 preguntes), i més de la meitat molt bàsics: 31 UPDATE amb un WHERE simple i 29 INSERT d'una sola fila. No n'hi havia cap de DELETE. `REPLACE` era SEC a tot arreu. Les columnes que MySQL omple amb l'hora actual (`DEFAULT` / `ON UPDATE CURRENT_TIMESTAMP`, 15 a sakila) feien que un INSERT o UPDATE pogués donar WA si l'alumne i la referència s'executaven en segons diferents.

**Decisió:**
- **`REPLACE` admès a `mysqlwrite`** (repo del jutge, commit `5f1017d`): forma família amb INSERT. Una pregunta d'INSERT es pot respondre amb INSERT, REPLACE, `INSERT IGNORE` o `INSERT … ON DUPLICATE KEY UPDATE`, i a la inversa; decideix el contingut final. A les preguntes de SELECT continua sent SEC. `MYSQL_WRITE_STATEMENTS` (web) inclou `REPLACE` per a l'encaminament.
- **Rellotge fix** (repo del jutge, commit `abf79bc`, i `mysql_grader.py` al web): cada sessió de correcció fa `SET timestamp = 1767225600` (2026-01-01 00:00:00 UTC). `NOW()`, `CURDATE()` i les columnes automàtiques donen el mateix valor a l'alumne i a la referència. De retruc, les 8 preguntes que depenien de la data d'avui ja no caduquen; s'ha comprovat que totes 8 continuen tenint resposta amb la data fixa.
- **Tipus de problema nou:** `sqldelete` ("SQL - Deletes").
- **18 problemes nous** (`sqldml<bd>01-03`, 3 per BD: INSERT avançat, UPDATE amb JOIN i subconsultes, i DELETE, de 10 preguntes cadascun, de menys a més difícils i amb un context a la introducció) sobre hotel, Chinook, sakila, northwind, miniwind i traders. Els van generar 6 subagents, un per BD. Inclouen:
  - **INSERT:** `INSERT … SELECT` amb JOIN, GROUP BY i HAVING, claus foranes buscades pel nom, diverses files, `INSERT IGNORE`, `REPLACE` i `ON DUPLICATE KEY UPDATE`;
  - **UPDATE:** UPDATE multitaula amb JOIN (també dues taules alhora), subconsultes correlacionades, CASE per trams, `ORDER BY … LIMIT` amb desempat per clau primària, i funcions de data i de text;
  - **DELETE:** NOT IN / NOT EXISTS (incloent-hi el parany del NOT IN amb NULL), DELETE multitaula amb JOIN, `ORDER BY … LIMIT`, eliminació de duplicats, i esborrats que activen `ON DELETE CASCADE` (hotel) o `SET NULL` (sakila).

  Verificació de cada una de les 180 preguntes amb el checker real: almenys una solució alternativa escrita diferent ha de donar AC i una d'incorrecta plausible ha de donar WA (a hotel, 47 alternatives i 53 incorrectes). La referència ha de canviar la BD, i tots els `LIMIT` desempaten per la clau primària. Quan una incorrecta coincidia amb la referència amb aquestes dades, se'n va canviar el llindar o la pregunta. Dry-run: 0 errors.
- Lots al repo (`problem_batches/sql/dml_<bd>.json`) i notes de verificació, amb les alternatives i les incorrectes de cada pregunta, a `problem_batches/sql/dml_notes/`.

**Observacions dels subagents:**
- **Error 1093:** MariaDB 10.5 **accepta** un UPDATE o DELETE d'una sola taula amb una subconsulta sobre la mateixa taula, que MySQL rebutja amb l'error 1093. Les preguntes que el presenten com a parany diuen que és un problema de portabilitat a MySQL, i accepten les dues formes. Sí que fallen de veritat aquí un DELETE multitaula amb una subconsulta sobre una de les taules (1093) i `LIMIT` dins d'un `IN (SELECT …)` (1235).
- **Valors que la normalització no cobreix:** a sakila, inserir a `film` sense `film_id` fa que el trigger copiï l'id real a `film_text`, que no té AUTO_INCREMENT i, per tant, no es normalitza. Per això aquella pregunta fixa l'id.
- **Limitació de la comparació per l'estat final:** si la resposta es pot escriure amb els valors posats a mà en lloc de calcular-los amb subconsultes, també és correcta. El corrector no pot obligar a fer servir un mètode concret.

**Resultat:**
18 problemes amb 180 preguntes, totes encaminades a `mysqlwrite`. L'usuari va reiniciar els jutges i el web (22:03). S'ha enviat com a `edgar` (`--force`) la solució de 41 problemes (els 18 nous, els 16 d'escriptura que ja hi havia i els 7 amb preguntes que depenen de la data, perquè ara es corregeixen amb el rellotge fix): **41 de 41 AC**. Després, el `CHECKSUM TABLE` de les 14 còpies `w_*` continua coincidint amb el de les originals. Per decisió de l'usuari, els 18 problemes nous s'han publicat i es veuen sense iniciar sessió.

---

### 119. Nova qualitat "superllegendari" (1/500 per tirada, mai repetida, només admins)

**Abans:** els 6 superachievements (els que tenen `mega_fanfare`: "Dret a Crear Achievements", "Descompte al Gacha", "Pista Extra",
"Bonus diari doble", "Assegurança Antirepetits" i "RAINBOW") eren llegendaris normals (qualitat 4) amb raresa 0,1: 1 de cada 5.420 tirades
cadascun, i cada llegendari nou que s'afegia els feia més rars. A més, podien sortir repetits.

**Decisió:**
- Nova qualitat `Achievement.QUALITY_SUPERLEGENDARY = 5` ("superllegendari"), amb la seva probabilitat fixa
  `SUPERLEGENDARY_CHANCE = 1/500`. Migració `0162_achievement_superlegendary`: només canvia les opcions i el text d'ajuda del camp
  `quality` (`sqlmigrate` confirma que no executa cap SQL), així que es va poder aplicar sense esperar la recàrrega.
- `GachaGo.gacha_roll`: abans de triar el nivell normal, un primer sorteig amb probabilitat 1/500. Si toca, tria a l'atzar (uniforme, sense
  tenir en compte la raresa) un superllegendari que l'usuari **encara no tingui**. Si ja els té tots, la tirada continua com una de normal. Mai
  no pot sortir repetit. La resta de nivells queden igual (65/20/10/5%), aplicats al 99,8% restant.
- `GachaResult`: la revelació (colors, sons, partícules, frases) està feta per a les qualitats 1-4. Un superllegendari es mostra com un
  llegendari (`achq = min(qualitat, 4)`), més el mega fanfare que tenen tots.
- `AchievementAdmin.formfield_for_choice_field`: els que no són superusuaris no veuen l'opció "superllegendari" i el servidor la rebutja,
  igual que les categories restringides.
- Traduccions: "superlegendary" (ca/es/de/en) i el text d'ajuda del camp, que ara inclou "5 superllegendari".

**Per què:** petició explícita de l'usuari, perquè la probabilitat dels superachievements no baixi cada cop que s'afegeix un llegendari.

**Resultat:** comprovat dins una transacció que es desfà (correu en memòria, cap canvi deixat). Amb els 6 moguts a qualitat 5 i el compte real
`Jonny` (que ja té "Dret a Crear"), forçant el primer sorteig per sota d'1/500: les 5 primeres tirades donen els 5 que li falten, cap repetit i mai
el 156. La sisena, quan ja els té tots, cau en un nivell normal. Una tirada normal no dona mai qualitat 5. La pàgina de resultat d'un
superllegendari es genera com a llegendari amb mega fanfare. A l'admin, `admin` (superusuari) veu les opcions 1-5 i `jmiracle` (grup "Creador
d'Achievements") només 1-4. Un `POST` de `jmiracle` amb `quality=5` no crea res, i amb `quality=4` sí. `msgfmt -c`, `compilemessages` i
`manage.py check` nets.

**Desplegament, en aquest ordre:** (1) l'usuari va recarregar uWSGI (workers de les 23:02, posteriors al canvi de codi de les 22:59); (2) després
es van moure els 6 achievements amb `mega_fanfare` a qualitat 5 (ids 156, 266, 267, 283, 284, 285; abans tots eren 4). No es va fer abans de
recarregar perquè, amb el codi vell, els achievements de qualitat 5 no haurien sortit mai a les tirades i la pàgina de resultat no els hauria
sabut mostrar. Comprovat després en viu: `/user/Jonny` i `/users/` responen 200, la secció de superachievements de Jonny hi continua, la
pàgina de resultat d'un "Dret a Crear" antic es genera bé (com a llegendari amb mega fanfare), i cap error nou a `/tmp/dasdas.log`.

**Prova manual per a l'usuari:** a petició seva, s'ha creat a mà un `AchievementObtained` (id 85089) de "RAINBOW" (285) per al compte `marc`,
per poder veure la revelació d'un superllegendari a `/gacha/result/85089-0`. No s'ha fet passar per la tirada: no s'han cobrat GachaPoints ni
s'ha enviat el correu del mega fanfare. A partir d'aquí, `marc` té el nom d'arc de Sant Martí.

---

### 120. Les imatges pujades de més de 2,5 MB donaven 403

**Abans:** les imatges dels superachievements generades amb Gemini (`.jfif`, 2,7-3 MB) donaven `403 Forbidden` a `/media/achievements/...`.
Causa: Django 2.2 no defineix `FILE_UPLOAD_PERMISSIONS`. Les pujades de més de `FILE_UPLOAD_MAX_MEMORY_SIZE` (2,5 MB) es desen primer en un
fitxer temporal i en conserven els permisos `0600`. nginx, que serveix `/media/` directament com a `www-data`, no les pot llegir. Les de
menys de 2,5 MB (com la del "Descompte al Gacha", 2,4 MB) es desen amb els permisos per defecte (`0644`) i es veien bé.

**Decisió:**
- `chmod 644` dels 5 fitxers afectats. Són els únics de tot `/tmp/media` que no es podien llegir: 4 `Gemini_Generated_Image_*.jfif` de
  superachievements i una còpia `_P7jInys` de la mateixa imatge.
- `dmoj/settings.py`: `FILE_UPLOAD_PERMISSIONS = 0o644` (el valor per defecte a partir de Django 3.0), perquè les pujades grans futures no
  tornin a quedar a `0600`.

**Per què:** petició explícita de l'usuari (error en veure les imatges).

**Resultat:** les 5 imatges responen 200 en viu. El canvi de configuració s'aplica a les pujades noves quan es recarregui uWSGI. Fins aleshores,
una pujada de més de 2,5 MB tornaria a quedar a `0600` i caldria el mateix `chmod`.

---

### 121. Encara més fanfare al mega fanfare, i la carta ja no es pot girar abans d'hora

**Abans:** el primer clic a la carta posava `gachaRevealed = true`, i qualsevol clic posterior (encara durant la càrrega) la girava i
mostrava el resultat abans d'hora. El mega fanfare carregava 4,5 s (3,2 s del llegendari × 1,4).

**Decisió** (`templates/gacha/gacharesult.html`, per a totes les tirades el punt 1 i només per al mega fanfare la resta):
1. Nou `gachaSequenceDone`: mentre dura la seqüència (càrrega, gir, recompensa i, si n'hi ha, el gir de repetit) els clics a la carta no fan
   res, i el cursor és de "carregant". Després es pot tornar a girar com abans.
2. Càrrega de 8 s (`MEGA_CHARGE_MS`). Quan ha passat el temps d'un llegendari normal comença la fase estranya (`startMegaOverdrive`): la
   pàgina s'enfosqueix, la carta tremola cada cop més fort (`--quake`), sona un batec que s'accelera i un xiulet que puja, i van sortint 10
   missatges cutres, cada cop més grans, en posicions a l'atzar ("Hmm... això està trigant més del normal.", "No serà un...?", "AVISA ELS
   TEUS AMICS!", "QUE ALGÚ AVISI EL PROFE!!!"...). Els textos són a `#gacha-lines [data-quality="mega-wait"]`, traduïbles. Al girar la
   carta, la foscor i els missatges desapareixen.
3. Recompensa més gran (`triggerMegaFanfare`): flaixos de colors, títol gegant d'arc de Sant Martí ("✨ SUPERLLEGENDARI ✨" si la qualitat és
   5, "✨ MEGA FANFARE ✨" si no; la vista passa `superlegendary`), focs artificials per tota la pantalla durant 9 s, pluja d'emojis durant
   10 s, el doble d'ànecs durant 20 s (alguns gegants), més esclats de partícules i dues pluges de confeti més.

**Per què:** petició explícita de l'usuari.

**Resultat:** `node --check` net del JS generat. Comprovat amb captures en temps real de Chromium controlat per CDP (el mode de temps virtual
no fa córrer les animacions CSS) sobre la pàgina generada del resultat 85089 de `marc`: un clic a 2,5 s no gira la carta, que només es gira a
les ~9 s; la fase estranya i la recompensa es veuen. Un primer intent deixava els missatges petits per sobre del sticker després del gir
(l'animació d'entrada mantenia l'opacitat); corregit amb una animació de sortida i traient-los de la pàgina. A partir d'aquí, l'usuari ho
comprova a mà. Els 12 textos nous (10 missatges i 2 títols) traduïts després a es/en/de; comprovat amb `gettext` en castellà. **Pendent:** recarregar uWSGI.

**Ànecs del logo:** a petició de l'usuari, els ànecs de la desfilada i de la pluja d'emojis ja no són l'emoji 🦆, sinó l'ànec de goma del logo
de JOEL. Nou `resources/icons/duck.svg`: els 5 camins de l'ànec copiats tal qual de `logo.svg`, amb un `viewBox` ajustat a la seva mida
(mesurada amb `getBBox()` a Chromium). Al logo mira cap a l'esquerra, i a la desfilada es gira perquè miri cap on va,
dins la mateixa animació (`translateX(...) scaleX(-1)`). Un primer intent amb la propietat `scale: -1 1` a part girava també el
desplaçament (s'aplica després del `transform`) i els ànecs sortien de seguida per l'esquerra; l'usuari ho va detectar. Publicat copiant només aquest fitxer a `/tmp/static/icons/` (respon 200,
`image/svg+xml`), sense `collectstatic`, per no publicar alhora canvis d'estils d'altres sessions. JS generat net amb `node --check`.

**Més lent:** a petició de l'usuari (els missatges passaven massa ràpid per adonar-se que no era un llegendari normal), `MEGA_CHARGE_MS`
passa de 8 a 15 s. Nou `MEGA_FIRST_MSG_DELAY_MS` (1,5 s): passada la càrrega d'un llegendari normal, durant aquest temps només s'enfosqueix la
pantalla i tremola la carta, sense missatges. Els 10 missatges es reparteixen entre aquest moment i 0,5 s abans del gir (~1 s entre cada un, abans
~0,5 s). La carta es gira, doncs, als ~16 s del clic.

**Pausa de suspens i dues fases:** a petició de l'usuari, la fase estranya es divideix en dues. Fase A (inquietud): foscor lleu (0,25),
tremolor suau, batec lent (1 per segon) i un xiulet greu. Surt el primer missatge ("Hmm... això està trigant més del normal.") i ve una
pausa de suspens (`MEGA_SUSPENSE_PAUSE_MS`, 2,5 s) en què la carta queda gairebé quieta. Fase B (descontrol), a partir del segon missatge: un cop
sord, la pantalla s'enfosqueix ràpid (0,7 en 1,2 s), la tremolor puja fins al màxim (24 px) en el 60% de la fase, el batec s'accelera fins a
4 per segon i el xiulet és agut. Els missatges continuen sortint un per segon (`MEGA_MSG_EVERY_MS`). La durada ja no és fixa (s'elimina
`MEGA_CHARGE_MS`): `megaOverdriveMs()` la calcula a partir del nombre de missatges (14 s amb els 10 actuals; la carta es gira als ~18 s del
clic). En sortir de la fase, es treuen les classes de foscor abans d'aplicar `.gone`, perquè `.show.deep` és més específica i, si no,
la pantalla es quedaria fosca. JS generat net amb `node --check`; la part visual la comprova l'usuari.

**Sense mareig, amb trompetes i més focs:** l'usuari va dir que, durant el fanfare, la pàgina "botava" i la barra lateral "ballava".
- Mesurat amb Chromium (CDP): els ànecs no canvien la mida de la pàgina (contenidor fix que retalla). Els **raigs** sí: el quadrat de 950 px
  que gira darrere la carta (`.gacha-wrapper::before`, `position: absolute`) feia oscil·lar l'alçada de la pàgina entre 888 i 1.084 px, i
  la barra de desplaçament canviava contínuament. Passava a totes les tirades èpiques i llegendàries. Ara els raigs són en una capa pròpia fixa
  i retallada (`#gacha-rays`), centrada a la carta des de JS (`positionRays`, també en fer scroll o canviar la mida). Mesurat després: alçada
  fixa a 794 px. Els 94 px de diferència amb l'alçada inicial d'abans també eren del quadrat, que hi era invisible des del principi.
- Treta la sacsejada de la carta en el moment de girar-se, només al mega fanfare. La tremolor de la càrrega es manté.
- Pendent de confirmar amb l'usuari què "botava" i s'aturava amb els ànecs: no es reprodueix com a canvi de mida de la pàgina.
- Afegit: dues trompetes gegants (🎺, la de l'esquerra girada) que entren pels costats i bufen notes musicals durant 12 s, amb una
  fanfàrria de trompeta sintetitzada (`playTrumpetFanfare`). Focs artificials durant 14 s (abans 9), més seguits (cada 170 ms, abans 320) i
  més grans, i canons de confeti a les dues cantonades inferiors durant 7 s. Cinc pluges de confeti (abans tres).
- El confeti passa a ser un sol sistema compartit (`confettiPieces`): abans cada pluja tenia el seu bucle sobre el mateix llenç i, quan dues
  coincidien, s'esborraven les peces l'una a l'altra. Ara cada peça cau fins que surt de la pantalla.
JS generat net amb `node --check`.

**La pàgina cau a trossos (fase B):** a petició de l'usuari. En començar la fase B (`startMegaCollapse`): cada 0,7 s apareix una esquerda
nova dibuixada en un llenç fix (`#mega-cracks`, branques irregulars des d'un punt d'impacte, com un vidre), amb un so de cruixit sintetitzat
(`playCrack`). Els trossos de la pàgina (elements del menú, `#user-links`, títol, textos i botó del voltant de la carta, peu de pàgina; mai la
carta ni les capes del gacha) tremolen 0,35 s i cauen girant amb una transició de "gravetat", un darrere l'altre, de manera que tots han
caigut ~1,5 s abans del gir. Mentre dura, `html.mega-collapse` (`overflow: hidden; scrollbar-gutter: stable`) impedeix l'scroll i manté
quieta la barra de desplaçament, perquè els trossos que cauen per sota no allarguin la pàgina. En girar la carta (`endMegaCollapse`), tots
els trossos tornen al seu lloc d'un bot, les esquerdes s'esvaeixen i, 1 s després, es treuen els estils i el bloqueig d'scroll. El distintiu
del bonus diari queda fora perquè la seva pròpia animació anul·laria la caiguda. JS generat net amb `node --check`; la part visual la
comprova l'usuari.

---

### 108. Nova puntuació dels 263 problemes de bases de dades (1 a 7 punts segons la dificultat)

**Abans:**
Cada problema de BD valia tants punts com preguntes tenia: el total dels 263 problemes era de 1.655 punts, i un problema de 16 preguntes fàcils en valia 16. L'usuari considera que això dona massa punts.

**Decisió:**
L'usuari va fixar l'escala: un problema de 3 preguntes fàcils = 1 punt, un de 10 preguntes fàcils = 2 punts, i el més difícil, uns 7 punts.
- **Pes de cada pregunta**, calculat a partir de la seva consulta de referència: 1 punt base, més 0,35 per JOIN (fins a 4), 0,5 per subconsulta (fins a 3), 0,25 per LEFT/RIGHT JOIN, 0,4 per GROUP BY, 0,3 per HAVING, 0,2 per EXISTS, 0,3 per UNION, 0,6 per funció de finestra, 0,25 per CASE i 0,15 per funció d'agregació. Les escriptures sumen 0,2, i 0,3 més si són `ON DUPLICATE KEY`, `REPLACE` o `INSERT IGNORE`. A Mongo, una agregació suma 0,5 més 0,15 per operador.
- **Dificultat del problema:** la suma dels pesos de les seves preguntes. Hi compten tant el nombre de preguntes com la complexitat de cadascuna.
- **Escala per trams:** dificultat 3 → 1 punt, dificultat 10 → 2 punts, i d'aquí fins al màxim (35,1, `sqlsakilaqt01`) → 7 punts. S'arrodoneix a mig punt i el mínim és 1.
- **Distribució resultant:** 84 problemes valen 1 punt, 39 valen 1,5, 32 valen 2, 21 valen 2,5, 18 valen 3, 18 valen 3,5, 27 valen 4, 11 valen 4,5 i 10 valen 5. Al capdamunt, `sqlsub05` val 5,5, `sqlvalorantqt06` val 6 i `sqlsakilaqt01` val 7. El total passa de 1.655 a 602 punts. L'usuari va revisar la llista sencera abans d'aplicar-la.

**Aplicació:**
- Còpia dels punts anteriors a `/home/ubuntu/backups/punts_problemes_bd_abans_20261023-000327.json`.
- S'han canviat els punts de 259 problemes (4 ja tenien el valor nou) i s'ha executat `rescore_problem` per als 263. Aquesta tasca recalcula els punts de cada enviament (`casos encertats / casos totals × punts del problema`) i els totals dels alumnes.
- **Error trobat i corregit:** `rescore_problem` (`judge/tasks/submission.py`) només cridava `calculate_points()`. Però en aquest fork els problemes del grup `sql` compten en un total a part, `Profile.sql_points`, que es calcula amb `calculate_sql_points()`, i aquest no es recalculava. Per tant, els rànquings de BD haurien conservat els punts inflats. Ara, si el problema és del grup `sql`, la tasca també crida `calculate_sql_points()`. A més, s'han recalculat a mà els punts SQL dels 11 usuaris amb enviaments (p. ex. `creina` passa de 37 a 12,8, `Elvin_Po_Ma` de 21 a 7,5); els problemes resolts de cadascú no canvien.
- `create_db_problems`: amb `--replace` es conserven els punts que ja té el problema; abans es tornaven a posar com el nombre de preguntes. Els problemes nous reben els punts amb la mateixa escala (`suggested_points()`), tret que el lot indiqui `"points"` per al problema. Comprovat: amb els lots del repo, en 244 de 245 casos dona el mateix que s'ha aplicat; l'únic que no, queda just al límit de l'arrodoniment.

**Per què:**
Que els problemes de BD no inflin la classificació i que els punts reflecteixin la feina que demana cada problema.

**Resultat:**
Els 263 problemes tenen els punts nous, i tots els enviaments estan recalculats: els únics que no quadren amb `casos encertats / casos totals × punts` són 5 de `provasql2`, que no dona punts parcials, i per tant és correcte que valguin 0. Els punts SQL dels usuaris estan al dia. Cal reiniciar Celery (`supervisorctl restart all`) perquè la correcció de `rescore_problem` s'apliqui quan es canviïn punts des de l'administració.

---

### 109. Els problemes de bases de dades també donen GachaPoints

**Abans:**
Els alumnes s'havien queixat, molt insistentment, que resoldre problemes de BD no donava GachaPoints. El camp `Profile.gacha_points` guarda els punts **gastats**, i el saldo disponible es calculava com `points - gacha_points`, a quatre llocs: `judge/views/user.py` (la tirada) i les plantilles `gacha/gachamain.html`, `gachago.html` i `gacharesult.html`. Però en aquest fork `points` només compta els problemes de programació. Els del grup `sql`, que són tots els de BD (MySQL i Mongo), compten a part, a `sql_points`. Per tant, no sumaven mai al saldo del gacha. El bonus diari ("primer problema nou del dia") sí que funcionava amb els problemes de BD, perquè no mira el grup.

**Decisió:**
Nova propietat `Profile.available_gacha_points`, igual a `points + sql_points - gacha_points`. La fan servir la vista de la tirada i les tres plantilles; ja no queda cap càlcul del saldo a mà.

**Per què:**
Que la feina en problemes de BD també compti per al gacha, igual que la de programació.

**Resultat:**
Cada usuari amb punts de BD veu ara el saldo augmentat en els seus `sql_points`, ja amb la puntuació nova de l'entrada #108: `creina` passa de 3,4 a 16,2, `Elvin_Po_Ma` de 3,4 a 10,9, `admin` de 20 a 31, `jreyess` d'1,6 a 3,6, i uns quants més +1 o +1,5. `edgar`, el compte de les solucions de referència, rep +597. Com a `creina`, la pàgina `/gacha/` mostra "Punts Disponibles: 16,21". Cal recarregar el web.

---

### 122. Temes del gacha: menú, desplegables, menú d'usuari i codi en línia illegibles

**Abans:** l'usuari va notar que, amb alguns temes del gacha, no es llegien els textos dels desplegables del menú ni el codi en línia del
markdown (`` `codi` ``). Mesurat el contrast (WCAG, mínim recomanat 4,5) als 6 temes que poden sortir al gacha (dark, candy, wmt, atomdark,
DTpurple, BUBIMan) amb Chromium (CDP) sobre `/about/codes/`:
- **Codi en línia:** `resources/base-description.scss` tenia el text a `#444` fix, amb un fons que sí canvia amb el tema
  (`--background_light_gray`). Contrast d'1,0 a 1,5 als temes foscos (dark, wmt, atomdark, DTpurple): invisible.
- **Menú i desplegables** a wmt (2,08) i DTpurple (1,50): el text del menú (`--text-white`) era fosc sobre un fons de menú fosc
  (`--widget_black`). Els desplegables fan servir els mateixos colors.
- **Menú d'usuari** ("Iniciar sessió" / "Hola, …"): els enllaços tenien el color `--background-white` (el fons de la pàgina, no el text del
  menú) i el nom, `#eee` fix. Al tema per defecte funcionava perquè tots dos són blancs, però a candy, wmt, atomdark i DTpurple el contrast
  quedava entre 1,2 i 2,5.
- **Altres:** botó actiu del menú a atomdark (2,36), color en passar-hi el ratolí a wmt (2,08), `--global-white: a2d2ff` sense `#` a candy i
  oldcandy (valor no vàlid), i `--button_grad:#orange` a olddark. Aquests dos darrers temes no surten al gacha.

**Decisió:**
- Codi en línia: `color: var(--text-black)`.
- Dues variables noves, només per al menú superior: `--nav-text` (per defecte `var(--text-white)`) i `--nav-active-text` (per defecte
  `var(--nav-text)`). Tot el menú (enllaços, desplegables, icona del menú mòbil, menú d'usuari) les fa servir en lloc de `--text-white`,
  `--background-white` o `#eee`. No s'ha canviat `--text-white` als temes perquè també és el text dels botons i de les capçaleres de taula,
  que tenen altres fons. Al tema per defecte i als que ja funcionaven no canvia res.
- Per tema: wmt (`--nav-text: #E8F5E9`, `--nav-active-text: #1B3A28`, `--text-nav: #C5E1A5` per al color en passar-hi el ratolí), DTpurple
  (`--nav-text: #EDE7F6`, `--nav-active-text: #1e1e1e`), atomdark (`--nav-active-text: #1e2127`), candy/oldcandy (`--global-white: #a2d2ff`),
  olddark (`--button_grad: orange`).

**Per què:** petició explícita de l'usuari.

**Resultat:** abans de canviar res, comprovat que `make_style.sh` sense canvis torna a generar exactament el mateix CSS. Després, el CSS
generat només conté aquests canvis. Contrast mesurat amb el CSS nou: codi en línia 4,6-20 a tots els temes (abans 1,0-1,5 als foscos);
menú/desplegables de wmt 5,3 i DTpurple 9,2; menú d'usuari 5,3-16 a tots; botó actiu d'atomdark 6,8. Queden per sota de 4,5, sense tocar: el
botó actiu de wmt (4,29) i BUBIMan (3,98), i, al **tema per defecte** (no és del gacha), el botó actiu (4,30) i el color en passar el ratolí
pel menú (blanc sobre `#aaa`, 2,32). Publicats `style.css`, `content-description.css` i `martor-description.css` copiant-los a `/tmp/static`.
Sense `collectstatic`, però tampoc no hi havia cap altre canvi d'estils pendent. Django Compressor va regenerar el fitxer combinat sol
(`output.48d027…` → `output.32e09d…`, que ja inclou les variables noves); no cal recarregar uWSGI.

**Segona passada (petició de l'usuari: arreglar el que quedava just):** dues variables més per al menú, `--nav-active-bg` (per defecte
`var(--highlight_blue)`) i `--nav-hover-bg` (per defecte `var(--background_dark_gray)`), que fan servir el botó actiu i el color en passar
el ratolí en lloc de les variables generals. Al **tema per defecte** (sense atribut `data-theme`: 25.068 perfils amb `preferred_theme` buit o
`NULL`), un bloc `:root:not([data-theme])` els dona blaus més foscos: actiu `#2471a3` (de 4,30 a 5,30) i ratolí `#065d86` (de 2,32 a 7,20).
wmt: `--nav-active-text: #0E2216` (de 4,29 a 5,73). BUBIMan: `--nav-active-bg: #1c62d6` (de 3,98 a 5,57). Mesurat després: tots els
textos del menú, del botó actiu i en passar-hi el ratolí, a tots els temes, per sobre de 4,5. Només ha canviat `style.css`; publicat igual
(`output.32e09d…` → `output.688afe…`).

---

### 110. PostgreSQL per a un bloc de problemes propi (fase 1: servidor, rols, seguretat i BD de partida)

**Abans:**
Els professors fan amb PostgreSQL tota la part de funcions, procediments i triggers. L'usuari vol un bloc de problemes **només de Postgres**, igual que el de Mongo, amb el seu checker i les seves categories, i que els problemes que ja hi ha es quedin **només amb MySQL**. Al servidor no hi havia res de PostgreSQL, i l'usuari `ubuntu` ja no té `sudo`.

**Decisió i passos:**
- **Instal·lació (feta per l'usuari amb `sudo`):** PostgreSQL **17.5** de l'arxiu oficial `apt-archive.postgresql.org`, perquè el repositori normal ja no dona suport a Ubuntu 20.04. És una versió congelada, sense més actualitzacions de seguretat; s'accepta perquè només hi ha accés per socket local. L'alternativa d'Ubuntu, la PG 12, era massa antiga (no té `MERGE`, ni les funcions SQL/JSON noves). Es va configurar `listen_addresses = ''` (cap port TCP, només el socket `/var/run/postgresql`) i el rol `ubuntu` com a superusuari per peer, l'equivalent de l'administrador via socket de la instància MariaDB. És un servei systemd (`postgresql`, activat) amb les dades a `/var/lib/postgresql/17/main`.
- **Connector:** `psycopg2-binary` 2.9.10 instal·lat al virtualenv compartit (`/home/ubuntu/dmojsite`), amb `libpq` 16 inclosa.
- **Rols** (credencials a `/home/ubuntu/.secrets/joel_pg_{read,run,loader}.conf`, permisos 600):
  - `joel_pg_read`: només `SELECT`, amb `default_transaction_read_only = on`.
  - `joel_pg_run`: escriptures i rutines, sempre dins d'una transacció que es desfà. Té `SELECT/INSERT/UPDATE/DELETE/TRIGGER` sobre les taules, ús de les seqüències, i `CREATE`/`TEMPORARY` a la BD per crear l'esquema temporal de cada correcció. **No** té `TRUNCATE`, no és propietari de res (no pot fer `DROP`/`ALTER`) i no pot crear extensions no fiables.
  - Tots dos amb `statement_timeout 5s`, `lock_timeout 3s`, `idle_in_transaction_session_timeout 30s` i un màxim de 10 connexions.
  - `joel_pg_loader`: `CREATEDB`/`CREATEROLE` (a PG 17, això només dona control sobre els rols que ell mateix crea), per als dumps dels professors.
  - Grup `joel_pg_owners`, per als futurs propietaris de les BD `p_<codi>`.
- **Autenticació:** amb només `peer` pel socket, els jutges (que s'executen com a `ubuntu`) només podrien entrar com a superusuari. `SET ROLE` i `SET SESSION AUTHORIZATION` no serveixen, perquè l'alumne podria tornar enrere (`RESET ROLE`). Per això l'usuari va afegir al `pg_hba.conf`, abans de `local all all peer`, la línia `local all joel_pg_read,joel_pg_run,joel_pg_loader,+joel_pg_owners scram-sha-256`; ha quedat duplicada, sense cap efecte. Es va recarregar amb `pg_reload_conf()`.
- **BD de sistema:** es treu `CONNECT` a `PUBLIC` a `postgres` i `template1`; només `joel_pg_loader` es pot connectar a `postgres`, per fer `CREATE DATABASE`.
- **BD de partida** (versions oficials per a Postgres, revisades abans de carregar-les; com a administrador amb `psql`, perquè són de confiança, cosa que no es farà mai amb els dumps dels professors):
  - `chinook` (lerocha/chinook-database, sense les línies `DROP/CREATE DATABASE` ni `\c`): 11 taules;
  - `northwind` (pthom/northwind_psql): 14 taules;
  - `pagila` (devrimgunduz/pagila, **etiqueta `pagila-v3.1.0`** del desembre de 2022): 22 taules (amb particions de `payment`), 7 vistes, 10 funcions i 15 triggers. La versió actual i les etiquetes v4.x fan servir `uuidv7()`, columnes virtuals i pgvector, que són de PostgreSQL 18. El primer intent amb la versió actual va deixar una BD `pagila` sense taules, que es va esborrar.
  - A cada BD: `REVOKE ALL ... FROM PUBLIC`, `CONNECT` per als dos rols, `REVOKE CREATE ON SCHEMA public FROM PUBLIC` i els permisos de taula i seqüència que s'han dit.

**Per què:**
Base per al bloc de Postgres: funcions, procediments i triggers en PL/pgSQL, i el que només té Postgres. A Postgres fins i tot el DDL (`CREATE FUNCTION`, `CREATE TRIGGER`) es pot desfer amb `ROLLBACK`, i això fa molt més senzill corregir rutines.

**Resultat (proves d'atac amb els dos rols):**
- **Lectura:** no pot fer `INSERT` (ni treient-se el mode de només lectura, perquè no en té el permís), ni entrar a la BD `postgres`, ni fer `pg_read_file`, `COPY` a fitxer o a programa, `lo_import` o `SET ROLE`. `pg_sleep(8)` es talla als 5 s.
- **Escriptures i rutines:** funciona el cicle complet d'un trigger dins d'una transacció (esquema temporal, funció PL/pgSQL, trigger sobre `public.language`, `INSERT`, i el trigger escriu al registre), i també el trigger `last_update` de Pagila. No pot fer `DROP`, `TRUNCATE`, `ALTER TABLE`, crear funcions `plpython3u` o l'extensió `dblink`, `ALTER SYSTEM`, `COPY TO PROGRAM` ni `SET ROLE`.
- Després del `ROLLBACK` no en queda res (cap esquema, trigger ni dada) i no s'ha creat cap fitxer.
- **Pendent per al checker:** bloquejar els `COMMIT` i altres sentències de control de transaccions al codi de l'alumne (separant les sentències tenint en compte els `$$ … $$`), i un rellotge propi que cancel·li la consulta, perquè `SET statement_timeout = 0` o `set_config()` es poden saltar el límit del rol.

---

### 111. Checker `postgres` al jutge (fase 2 del bloc de PostgreSQL)

**Decisió:**
Nou `checkers/postgres.py` (repo del jutge, commit `53299e1`), registrat a `checkers/__init__.py`. Un sol checker amb tres modes, que es trien a partir de la referència de cada pregunta:
- **Consulta** (`SELECT`/`WITH`/`TABLE`/`VALUES`): amb `joel_pg_read`. Es compara el resultat amb les funcions de `sql.py` i es llegeix com a màxim una fila més de les esperades. Una escriptura, un `CREATE`, un `DO` o un `CALL` en una pregunta de consulta es marca SEC.
- **Escriptura** (`INSERT`/`UPDATE`/`DELETE`/`MERGE`): amb `joel_pg_run`, dins d'una transacció que sempre es desfà. Es compara el contingut final de les taules de `public` que han canviat, detectades amb un hash md5 de cada taula calculat al servidor. Ha de coincidir el tipus de sentència, però `MERGE` s'accepta com a alternativa a qualsevol.
- **Rutina** (la referència és un `CREATE FUNCTION/PROCEDURE/TRIGGER …` seguit de línies `--@@TEST@@ <sentència>`): el codi de l'alumne i el de referència s'executen cadascun en una transacció pròpia i en un **esquema temporal** (`s_<aleatori>`, primer al `search_path`), i després s'executen les proves del professor, cada una dins d'un `SAVEPOINT`. Es comparen el resultat de cada prova (les files, el nombre de files afectades, o el **SQLSTATE** si dona error; útil per a triggers que han de fer `RAISE EXCEPTION`) i l'estat final. La retroacció diu quina prova falla (p. ex. "Test 2 (`SELECT preu_amb_iva(0.99)`): Result sets differ"). Com que les proves són comentaris, l'enviament de la referència com a `edgar` funciona igual que ara.

**Detalls resolts:**
- **Separació de sentències** igual que la fa Postgres: cadenes `'…'` i `E'…'`, identificadors `"…"`, cossos `$tag$ … $tag$`, comentaris `--` i `/* */` niats.
- **SEC** per a `COMMIT`, `ROLLBACK`, `BEGIN`, `SAVEPOINT`, `SET`, `RESET`, `COPY`, `LOCK`, `TRUNCATE`, `ALTER`, `DROP`, `GRANT`, `VACUUM`, `CREATE EXTENSION/SCHEMA/ROLE/DATABASE`… Els `DROP FUNCTION/PROCEDURE/TRIGGER/TABLE/VIEW/TYPE IF EXISTS` habituals abans d'un `CREATE` s'ignoren, perquè sempre es parteix de zero; si no, el `DROP TRIGGER` fallaria per falta de permisos.
- **Vigilant:** un temporitzador cancel·la (`conn.cancel()`) qualsevol sentència que passi de 6 s. Cal perquè, des d'una funció, `set_config('statement_timeout', '0', true)` pot treure el límit del rol.
- **Seqüències:** no es desfan amb `ROLLBACK`. Abans de cada execució es posen just després del màxim de la seva columna. Es detecten pel valor per defecte (`nextval('…')`), perquè a Pagila **cap** de les 20 seqüències està lligada (`OWNED BY`) a la columna i `pg_get_serial_sequence()` no les troba, i també per les columnes `IDENTITY`.
- **Hora de la transacció:** a Postgres, `now()` és l'hora d'inici de la transacció, de manera que els triggers `last_update` de Pagila donaven valors diferents a l'alumne i a la referència, i un `UPDATE` idèntic donava WA. Els valors iguals al `now()`, `localtimestamp` o `current_date` de la transacció es comparen com a "ara".
- **Concurrència:** `pg_advisory_xact_lock` per BD: les correccions d'escriptures i rutines d'una mateixa BD es fan d'una en una, i el bloqueig s'allibera sol amb el `ROLLBACK`. Si cal esperar més del `lock_timeout`, es torna a intentar.

**Resultat (proves amb Pagila):**
- **24 de 24** casos com s'esperava:
  - consultes equivalents, `COUNT(*) FILTER (…)` i una consulta incorrecta;
  - `UPDATE … FROM` contra `IN (subconsulta)`, `INSERT` amb `serial`, `MERGE` com a alternativa a `INSERT`, i una escriptura incorrecta;
  - funció (la referència, una alternativa en `LANGUAGE sql` amb `DROP … IF EXISTS`, una sense arrodonir i una no definida);
  - trigger (el que registra canvis i el que fa `RAISE`) i procediment.
- **Atacs:** `COMMIT`, `SET`, `DROP`, `CREATE EXTENSION/SCHEMA` i `COPY` → SEC. `set_config` + `pg_sleep(30)` → tallat als 5,6 s. Un `DO` amb `COMMIT` → Postgres el rebutja. Un `EXECUTE 'DROP TABLE'` dins d'una funció → no té permís.
- **Concurrència:** amb 3 correctors alhora, 18 de 18 AC.
- Després de totes les proves la BD queda intacta: no queda cap esquema `s_*`, ni dades, ni funcions.
- Cada pregunta d'escriptura o de rutina triga ~0,8–1 s (dues transaccions). Els jutges encara no carreguen el checker: cal reiniciar-los.

---

### 112. PostgreSQL a la web, i primera prova al jutge real (fase 3 del bloc de PostgreSQL)

**Abans:**
El jutge ja tenia el checker `postgres` (#111), però la web no el coneixia: no es podia triar a les dades del problema, la pàgina "Base de dades" només sabia mostrar esquemes de MariaDB, i `create_db_problems` només creava problemes MySQL.

**Decisió i passos:**
- **`judge/utils/judge_checkers.py` (nou):** `load_judge_checker(nom)` carrega un checker del paquet del jutge pel seu camí, amb mòduls buits en lloc de les dependències del jutge. Així la web valida les referències amb el mateix codi que corregirà (separació de sentències, mode, SEC), sense duplicar-lo.
- **`judge/utils/pg_grader.py` (nou):** `get_postgres_databases()` (llista les BD de correcció, via l'administrador per peer), `get_schema()` (taules, columnes, claus, vistes i funcions per a la pàgina de l'esquema), `validate_reference()` (executa la referència amb el checker real i diu si dona error o SEC) i `POSTGRES_DATABASE_INFO` (descripció de `chinook`, `northwind` i `pagila`).
- **Model:** `CHECKERS` afegeix `('postgres', 'PostgreSQL checker')`; migració **`0163_problemdata_postgres_checker`** (només canvia les opcions; aplicada). `DATABASE_CHECKERS` inclou `postgres` i `ProblemDataCompiler.make_checker` genera `name: postgres` amb la BD triada.
- **Formulari de dades del problema** (`judge/views/problem_data.py`, `templates/problem/data.html`): camp nou "Base de dades PostgreSQL" que només es mostra amb aquest checker; es guarda a `checker_args`. **No es pot canviar un problema existent de MySQL a PostgreSQL ni al revés**, tal com es va decidir: els problemes actuals es queden a MySQL, i els de Postgres són un bloc a part.
- **Pàgines del problema** (`judge/views/problem.py`): la vista de l'esquema i `is_sql_problem` reconeixen `postgres`, de manera que el problema surt al grup `sql`, suma a `sql_points` i al gacha, i té la pestanya "Base de dades".
- **`create_db_problems`:** motor `postgres` (`postgres_mode()`; tipus de sentència `ROUTINE` per a `CREATE FUNCTION/PROCEDURE/TRIGGER` amb línies `--@@TEST@@`), validació amb `pg_grader`, enunciat adaptat (Postgres i, a les rutines, l'explicació de com es comproven), i pes de pregunta `question_weight` +1,5 per a `CREATE`/`DO` i +0,15 per prova.
- Traduccions al català afegides i compilades.
- **Problema de prova `zzpgtest01`** (privat, Pagila, 3 preguntes: consulta amb `FILTER`, `UPDATE … FROM` i trigger amb proves). Les pàgines del problema, enviament, base de dades i dades de prova es mostren bé.
- L'usuari va reiniciar els jutges (11:29–11:30) i uwsgi (11:45).

**Per què:**
Perquè els professors puguin crear i corregir problemes de funcions, procediments i triggers a Postgres des de la web, amb la mateixa validació que farà el jutge.

**Resultat (jutge real, EdgTest):**
- La referència d'`edgar` a `zzpgtest01`: **AC**.
- Un enviament parcialment incorrecte (consulta amb `CASE` en lloc de `FILTER`, `UPDATE` amb `IN`, i un trigger que registra els canvis però no impedeix els preus negatius): preguntes 1 i 2 **AC**, pregunta 3 **WA** amb la retroacció de la prova que falla (`Test 3 (UPDATE film SET rental_rate = -1 …)`), 1,0 de 1,5 punts.
- Després, a `pagila` no queda cap esquema `s_*` ni cap trigger `t_log_preu`, i les dades són les originals (`film 1` = 0,99).
- `zzpgtest01` encara existeix (privat); s'esborrarà quan l'usuari ho aprovi.

---

### 113. Primers 15 problemes de PostgreSQL (fase 4), i SQLSTATE a la retroacció del checker

**Abans:**
El bloc de PostgreSQL funcionava de punta a punta (#110–#112), però només hi havia el problema de prova `zzpgtest01`, i no hi havia cap categoria pròpia.

**Decisió i passos:**
- **Categories noves** (`ProblemType`): `pgadvquery` "PostgreSQL - Consultes avançades", `pgfunc` "PostgreSQL - Funcions", `pgproc` "PostgreSQL - Procediments", `pgtrigger` "PostgreSQL - Triggers" i `pgobjrel` "PostgreSQL - Tipus, arrays i JSON".
- **Lots** (preparats per tres agents en paral·lel, un per BD, amb un encàrrec comú i l'eina `pg_try.py`, que prova respostes amb el checker real):
  - `problem_batches/sql/pg_chinook.json`, `pg_northwind.json` i `pg_pagila.json`;
  - per BD, 5 problemes (un per categoria) de 6 preguntes: **15 problemes i 90 preguntes**;
  - notes a `problem_batches/sql/pg_notes/pg_<bd>.md`: per a cada pregunta, la referència, almenys una alternativa acceptada i almenys dues respostes incorrectes típiques, totes amb el veredicte i la retroacció reals del checker (en total ~98 alternatives acceptades i ~256 respostes incorrectes rebutjades).
- **Creació:** `create_db_problems` sobre els tres lots: `sqlpgchinook01-05`, `sqlpgnorthwind01-05` i `sqlpgpagila01-05`, **privats**, grup `sql`, de 2,5 a 5 punts (`suggested_points`). El nom de `sqlpgnorthwind05` es va igualar amb els altres ("Tipus, arrays i JSON").
- **Checker** (repo del jutge, commit `9b8b9a3`): quan una prova falla perquè la resposta de l'alumne i la de referència donen errors diferents, la retroacció deia "yours gives an error, the expected one gives an error". Ara diu els dos codis, p. ex. `yours gives an error (SQLSTATE P0001 raise_exception), the expected one gives an error (SQLSTATE 23514 check_violation)`. És el cas típic d'un `RAISE EXCEPTION` sense l'`ERRCODE` que demana l'enunciat. Cal reiniciar els jutges perquè l'agafin.

**Per què:**
Primer contingut real del bloc: funcions, procediments i triggers en PL/pgSQL, i el que és propi de Postgres (`FILTER`, `DISTINCT ON`, `LATERAL`, `ROLLUP`, CTE recursius, arrays, `jsonb`, `ENUM`/`DOMAIN`/tipus compostos).

**Resultat:**
- `--dry-run`: 0 errors als tres lots. Les 15 respostes de referència d'`edgar` al jutge real: **15 de 15 AC**.
- Les pàgines del problema, enviament, base de dades i dades de prova es mostren bé (comprovat amb `sqlpgpagila04`).
- Després de totes les proves, cap BD (`chinook`, `northwind`, `pagila`) té esquemes `s_*` ni funcions fora de `public`.
- **Límits coneguts** (detallats a les notes):
  - el checker compara resultats, no la tècnica: una solució sense `FOUND`, `LATERAL`, `jsonb_agg`, recursió, etc. s'accepta si dona el mateix;
  - a Northwind els preus són `real`: els enunciats de diners demanen passar a `numeric`, i les proves inclouen comandes on es nota la diferència;
  - dues preguntes de Northwind fan servir `current_date + 14`/`+ 28`: si la correcció de l'alumne i la de la referència cauen a banda i banda de la mitjanit, donaria WA (apuntat a `TODO.md`);
  - a Pagila, `payment` només té particions de gener a juliol de 2022, i per això el procediment de devolucions rep la data com a paràmetre.

---

### 114. Superpistes: pistes de la IA del JOEL (servei joel-pistes de sabIA)

**Abans:**
El sistema de pistes només mostrava, als casos amb retroacció estesa (checkers `linecount` i `rstripped`), l'entrada que fallava i la
resposta de l'alumne, amb un màxim de pistes per problema (`allowed_tips`). L'institut ha posat en marxa un servei de pistes amb IA
(`https://sabia.ies-sabadell.cat/joel/v1`), amb el protocol a `importacions/PROTOCOL.md` i la clau a `importacions/joel-2026-10-23.txt`.

**Decisió i passos:**
- **Camp nou** `ProblemData.allowed_superhints` ("Superpistes permeses"), editable a la pàgina de dades de prova. Buit (per defecte) vol dir
  `ceil(allowed_tips / 2)`; l'achievement d'una pista extra (`extra_hint`) **no** hi compta. Propietat `ProblemData.superhint_limit`.
- **Model nou** `SuperHint` (migració `0164_superhints`): enviament, cas, estat (`P` pendent, `OK`, `E` error), idioma, i la resposta del
  servei (`nivell`, `pista`, `categoria_error`, `diagnosi_professorat`, `revisio`) o l'error. El límit és **per alumne i problema**, sumant
  tots els enviaments. Les peticions amb error **no gasten** superpista, i una que porti més de 3 minuts pendent es dona per perduda
  (`STALE_AFTER`) i tampoc no gasta.
- **Client del protocol** `judge/utils/superhints.py`: construeix la petició (enunciat, codi, llenguatge, veredicte, casos fallits del
  `linecount`/`rstripped` —el que l'alumne ja ha vist, primer, fins a 5—, el missatge del compilador i la nota del cas quan no és un
  percentatge, i les superpistes anteriors de l'alumne en aquell problema a `pistes_anteriors`, perquè el servei vagi un pas més enllà).
  Reintents tal com diu el protocol: 429 fins a 3 vegades al cap de 5-10 s, 502/504 o error de connexió una vegada. *Timeout* 60 s.
  L'idioma de la pista és el de la interfície de l'alumne.
- **Tasca Celery** `request_superhint` (`judge/tasks/superhint.py`): la petició es fa en segon pla, perquè triga 4-10 s i no volem tenir
  un worker d'uWSGI bloquejat.
- **Vistes i URLs**: `POST /submission/superhint/<cas>` (només el propietari de l'enviament; bloqueja la fila del perfil per evitar
  passar-se del límit amb dues peticions alhora; no deixa demanar-ne una altra mentre n'hi ha una de pendent en aquell cas) i
  `GET /submission/superhint/status/<id>` (propietari o professorat del problema), que la pàgina consulta cada 3 s fins que hi ha resposta.
- **Pàgina de l'enviament** (`status-testcases.html` i `superhint-fragment.html` nou): comptador "Superpistes usades/permeses", i botó
  **Superpista!** amb confirmació que només surt en un cas fallat on l'alumne **ja ha vist la pista normal** (en aquest enviament o en un
  d'anterior, el mateix cas), si li en queden. La superpista surt sota la pista normal. El professorat (qui pot avaluar el problema) hi
  veu a més la `diagnosi_professorat`, la categoria de l'error i el resultat de la revisió; l'alumne no.
- Configuració: `JOEL_PISTES_URL`, `JOEL_PISTES_KEY` i `JOEL_PISTES_TIMEOUT` a `settings.py` (clau buida per defecte: sense clau el botó no
  surt); la clau real és a `dmoj/local_settings.py`, que no es puja al repositori.
- Estils a `resources/submission.scss` (targeta amb vora lila), CSS regenerat amb `make_style.sh` (només hi canvien aquestes regles) i
  copiat a `/tmp/static/style.css`. Traduccions noves a ca/es/en/de/zh_Hans, i `compilemessages`.

**Per què:**
Petició explícita de l'usuari: quan un alumne ja ha fet servir una pista i encara no se'n surt, una pista escrita a partir del seu codi,
limitada perquè no substitueixi el treball de depurar.

**Resultat:**
- `GET /salut` del servei: `{"estat":"ok"}`. Una petició real amb un enviament WA de `radarvalentina` (Java): pista de nivell 1 en 8 s,
  que apunta al límit de 10000 sense donar la solució, i diagnosi correcta per al professorat (`energia > 10000` en lloc de `>=`).
- Prova del flux complet amb el client de Django dins d'una transacció desfeta (no ha quedat cap fila): el botó surt al cas amb la pista
  vista; la 1a superpista dona nivell 1, la 2a nivell 2 (`regenerada`, no repeteix la primera), la 3a es rebutja ("Ja no et queden
  superpistes", límit 2 = `ceil(3/2)`) i el botó desapareix (2/2); una segona petició mentre n'hi ha una de pendent es rebutja; un altre
  alumne rep 403 a les dues URLs; el professorat veu la diagnosi; una pendent antiga no compta i passa a error en consultar-la.
- La pàgina de dades de prova mostra el camp nou amb l'ajuda. `manage.py check` net, migració aplicada.
- **Cal reiniciar uWSGI i Celery** (`sudo supervisorctl restart all`) perquè el web i els workers carreguin el codi nou; fins llavors el
  botó no surt.

---

### 115. El botó de superpista surt sense recarregar la pàgina

**Abans:**
En demanar la pista normal (botó *Help!*, per AJAX), la pista es mostrava però el botó **Superpista!** no sortia fins que es recarregava la
pàgina (F5). El mateix passava després de rebre una superpista: el botó per demanar-ne una altra (si en quedaven) i el comptador
"Superpistes usades/permeses" no s'actualitzaven.

**Decisió i passos:**
- El botó és ara una plantilla pròpia, `templates/submission/superhint-button.html`, que fan servir tant la pàgina com les respostes AJAX.
- Funció nova `superhint_button()` a `judge/views/submission.py`: decideix si el botó ha de sortir en aquell cas (mateixes condicions que a la
  pàgina: propietari, pista normal vista, sense cap superpista pendent, i amb superpistes disponibles) i el renderitza.
- `flag_submission` (la pista normal), `request_superhint` i `superhint_status` tornen ara també `superhint_button` i `superhints_used`, i
  el JS de `status-testcases.html` hi afegeix el botó (si encara no hi és) i actualitza el comptador (`#superhints-used`).
- uWSGI recarregat amb `uwsgi --reload` (sense `sudo`); Celery no cal reiniciar-lo perquè la tasca no ha canviat.

**Per què:**
Ho va detectar l'usuari provant-ho: calia fer F5 després de demanar la pista per veure el botó de superpista.

**Resultat:**
- Prova en una transacció desfeta (`senarsparells`): la resposta de *Help!* porta el botó (0 usades). Després d'una superpista, la consulta
  d'estat torna el botó següent (1 usada), i després de la segona ja no (2 de 2). No ha quedat cap fila ni cap pista marcada.
- La superpista real que va demanar l'usuari després del reinici (`8reines`, a través de Celery) va arribar bé: nivell 1, `aprovada`.
- `manage.py check` net, i la web respon 200 després de la recàrrega.

---

### 116. Marca de superpista a les llistes d'enviaments (només professorat)

**Abans:**
A les llistes d'enviaments (totes, les d'un usuari, les d'un problema, i la fila que s'actualitza en viu) no es veia si un enviament havia
fet servir superpistes; calia obrir-lo.

**Decisió i passos:**
- Funció nova `superhint_counts(user, submissions)` a `judge/views/submission.py`: per als enviaments de la pàgina, quantes superpistes
  **amb resposta** (`OK`) tenen, però només per als problemes que qui mira pot avaluar (`Problem.is_evaluable_by`, el mateix criteri que
  fa servir la diagnosi per al professorat). Una sola consulta agrupada per pàgina, i la comprovació de permís un cop per problema.
- `SubmissionsListBase.get_context_data` (i per tant totes les llistes que en deriven) i `single_submission` passen `superhint_counts` a
  `templates/submission/row.html`, que hi mostra una vareta (`fa-magic`, lila, classe `submission-superhint`) al costat de l'hora, amb el
  text "Superpistes demanades en aquest enviament: N" en passar-hi el ratolí.
- CSS regenerat (només hi canvia la regla nova) i copiat a `/tmp/static/style.css`; traducció a ca/es/en/de/zh_Hans; uWSGI recarregat.

**Per què:**
Petició de l'usuari: que el professorat pugui veure d'un cop d'ull on s'han fet servir superpistes, sense que ho vegi l'alumnat.

**Resultat:**
- Amb la superpista real de `8reines`: el professorat veu la marca a la llista de l'usuari, a la del problema i a la fila en viu; un alumne
  qualsevol no la veu enlloc.
- Amb una superpista creada dins d'una transacció desfeta a l'enviament d'un alumne sense permisos: el professorat veu 1 marca i l'alumne
  mateix, 0. No ha quedat cap fila.
- `manage.py check` net, i `/submissions/` respon 200 després de la recàrrega.

---

### 117. Publicació dels 15 problemes de PostgreSQL i esborrat del problema de prova

**Decisió (amb el vistiplau de l'usuari):**
- Publicats `sqlpgchinook01-05`, `sqlpgnorthwind01-05` i `sqlpgpagila01-05` (15 problemes, 90 preguntes), després de comprovar que tots tenen l'AC d'`edgar` amb la puntuació completa. Es posa `date` als que no en tenien.
- Esborrat el problema de prova `zzpgtest01`: el problema, les seves 3 preguntes i els 2 enviaments de prova d'`edgar` (20 files en total, en cascada), i la carpeta de dades `/judge/zzpgtest01` (`data.zip` i `init.yml`). Es recalculen els punts d'`edgar`.
- Abans, l'usuari havia reiniciat els jutges (23:09), que ja fan servir la retroacció amb els dos SQLSTATE (#113 de PostgreSQL).

**Resultat:** les pàgines dels problemes nous es veuen sense iniciar sessió (200), i `zzpgtest01` ja no existeix (404).

---

### 118. Còpia de seguretat de la carpeta de problemes (`/judge`)

**Decisió:** a petició de l'usuari, còpia sencera de `/judge` (dades de tots els problemes: `init.yml`, zips, dumps, generadors), 196 MB i 1.281 problemes.

**Resultat:** `/home/ubuntu/backups/joel-problemes-judge-20261023-233229.tar.gz` (169 MB, permisos 600), amb el SHA-256 a `….tar.gz.sha256`. L'arxiu té les mateixes 3.875 entrades que la carpeta. Per restaurar-la: `tar -xzf <fitxer> -C /`.

---

### 123. "Sobre i Guies" amb un submenú "Altres Guies", i nova "Guia per a Crear Temes"

**Abans:** totes les guies eren dins el desplegable "Sobre", barrejades amb Status, Consells, Categories i Respostes. No hi havia cap
explicació de com crear un tema. A més, la plantilla del menú (`templates/base.html`) tenia `{% if not node.is_leaf_node %}` sense
parèntesis. Un mètode sense cridar sempre és "cert", així que la fletxa `.nav-expand` dels elements amb submenú no es generava mai. Al mòbil
és el botó que obre els submenús (`resources/common.js`), així que només s'obrien mantenint el dit premut.

**Decisió:**
- **Menú** (`NavigationBar`, canvis a la BD i `rebuild()` de l'arbre MPTT): Problemes · Enviaments · Usuaris · Concursos · **Sobre i Guies** ▾ ·
  Gacha. "Sobre" passa a dir-se "Sobre i Guies". A dins: Categories, Respostes, Consells, Guia Alumnes, Guia Professors, **Altres Guies** ▸
  i Status. "Altres Guies" és un element nou (`guies`, enllaç a `/creaproblemes/`, es marca com a actiu a `/creaproblemes/` i
  `/createmes/`) amb un segon submenú: Crear Problemes (`GuiaProbl`, abans directament a Sobre) i el nou `GuiaTemes` ("Crear Temes").
  Les etiquetes del menú no es tradueixen (el catàleg `dmoj-user` que fa servir `user_trans` no existeix), igual que les que ja hi havia.
- **Primer intent descartat:** l'usuari s'havia explicat malament i, primer, les guies es van posar al primer nivell del menú (i, per fer-hi
  cabre tot a 1.280 px, una regla que reduïa el marge dels botons). En aclarir-ho, es va tornar a l'estructura de dalt i es va treure la regla.
- **Submenú dins d'un submenú** (`resources/base.scss`, només a l'ordinador): a partir del segon nivell, el submenú s'obre al costat
  (`left: 100%; top: 0`) en lloc de tapar els elements de sota, i el seu element mostra la fletxa. Al mòbil ja s'obrien cap al costat.
- **Plantilla:** `node.is_leaf_node()` amb parèntesis. Ara surten les fletxes de "Sobre i Guies" i "Altres Guies". A l'ordinador, la del
  primer nivell continua amagada pel CSS de sempre.
- **Nova pàgina** `/createmes/` (FlatPage id 9, "Guia per a Crear Temes", plantilla `flatpages/markdown.html`). Explica que un tema són tres
  peces amb el mateix nom (bloc `:root[data-theme=theme-x]` a `resources/base.scss`, achievement de categoria tema, i la tria a Editar perfil
  que posa `data-theme` a `<html>`). Inclou els passos (nom, colors, contrast, compilar i publicar, provar-lo des de la consola amb
  `document.documentElement.dataset.theme`, i crear l'achievement), què pinta cada variable, i els errors reals de l'entrada #122 (falta de
  `#`, `#orange`, text fosc sobre menú fosc). La descripció de cada variable surt d'extreure del CSS compilat quins selectors la fan servir.

**Per què:** petició explícita de l'usuari.

**Resultat:** `/createmes/` respon 200 en viu. Comprovat en viu amb Chromium (CDP, passant el ratolí per "Sobre i Guies" i després per
"Altres Guies"): el segon submenú s'obre al costat amb Crear Problemes i Crear Temes. `style.css` recompilat (només amb la regla del
submenú) i publicat a `/tmp/static`. La plantilla generada té ara les 2 fletxes que toquen. **Pendent:** recarregar uWSGI perquè surtin
les fletxes (canvi de plantilla).

---

## 2026-10-24

### 124. Revisió de les pàgines estàtiques i les guies (amb captures), traduccions completes, estat de la IA a Status, i bugs trobats pel camí

**Abans:**
- **Status** (`/status/`) només mostrava els jutges. No hi havia manera de saber si el servei de superpistes (joel-pistes, `sabia.ies-sabadell.cat`, entrada #114) responia.
- **Pàgines planes** (`django.contrib.flatpages`, 9 pàgines): moltes en castellà tot i que el lloc és en català (`/about/codes/`, `/about/categories/`, `/tips/`, `/guiaalumnes/` amb títol castellà), només "Sobre" tenia traduccions (ca/en/de). Contingut desactualitzat: enllaços al domini vell `joder.ga`, captures a imgur.com (algunes donen `429`), una frase amb "TODO" a "Sobre", la llista de jutges de fa anys, la llista de verificadors sense MySQL/PostgreSQL/Mongo, cap esment de superpistes, guies de problemes, tasques, instituts, bases de dades ni del veredicte SEC. `/about/normes/` (enllaçada des de "Sobre") era **buida**. Les imatges de la fórmula de punts eren a postimg.cc (extern).
- **Traduccions**: `makemessages` no s'havia passat amb tot el codi actual. Pendents: ca 196 + 42 fuzzy, es 85 + 62, de 1278 + 19, zh_Hans 558 + 118, i a l'anglès les cadenes amb `msgid` en català. El menú ("Sobre i Guies", etc.) no es traduïa a cap idioma perquè el catàleg `dmoj-user` de `user_trans` no existia i la comanda `makedmojmessages` fallava (`.pot` sense capçalera). Moltes etiquetes de la interfície sortien en anglès en català ("Read the guide", "Tasks", "Filter Tasks", "Stats for", "View the database schema", "Solve status for"...), i hi havia traduccions catalanes errònies ("problem group" → "Equip del problema", "nom�s" corrupte, "Espectar", "Descalificar", "Tasa de AC"...).

**Decisió:**

1. **Status: estat del servidor de la IA.**
   - `judge/utils/superhints.py`: nova `health()`, que fa `GET <base>/salut` (sense clau, `timeout=5`), mesura el ping, comprova `estat == 'ok'` i la `versio_protocol` (si no és la `'1'` que parla el JOEL, ho marca com a error), i guarda el resultat a la memòria cau de Django 60 s (`superhints:health`) per no consultar el servei a cada visita. Estats: `ok`, `down`, `off` (no configurat).
   - `judge/views/status.py`: nova `get_superhint_status()` (estat + superpistes `OK`/`E` de les últimes 24 h + data de l'última correcta; el missatge d'error només el veu el personal) passada a `status_all`.
   - `templates/status/judge-status.html`: secció nova "Serveis" sota la taula de jutges (servei, estat amb icona, ping, últimes 24 h, última superpista); `templates/status/media-css.html`: marge del títol.
   - **Incident:** la plantilla es va publicar abans de recarregar uWSGI, i durant uns minuts `/status/` va donar 500 (`'superhint_status' is undefined`, ho va reportar l'usuari). Resolt amb `kill -HUP` al mestre d'uWSGI.

2. **Comptes i dades de demostració per a les captures** (decisió de l'usuari: comptes demo, no noms reals): usuaris `demo_alumne`, `demo_alumna`, `demo_alumne3` i `demo_profe` (perfils 25334-25337, `is_unlisted=True`, llenguatge Python 3), equip tancat "Grup demo (guies)" (id 195, slug `grup-demo-guies`) a l'"Institut JOEL" (id 41) amb `demo_profe` d'administrador, 6 enviaments reals jutjats (371834-371839: AC, WA 80 %, IR...), una pista i una superpista reals demanades amb el flux de la web, i un problema **privat** `demoguia` (id 1396, autor `demo_profe`, 3 casos pujats amb l'editor de casos de prova real). En acabar: contrasenya inutilitzable, `is_staff=False` i cap grup als 4 comptes (no s'han esborrat perquè les captures i els enviaments en depenen). Els noms dels altres usuaris que surten en alguna pantalla se substitueixen per `alumneN` abans de capturar.

3. **Captures** (Selenium 3.141 + `chromium-browser` headless, inici de sessió real pel formulari, idioma català; script a `~/shots/guies/shot.py` i tandes a `~/shots/guies/specs/`): 26 captures, retallades i reduïdes a 256 colors amb Pillow (802 KB en total), a `resources/guides/*.png` (dins el repo, servides a `/static/guides/`; copiades a `/tmp/static/guides/`). Les dues imatges de la fórmula de punts s'han descarregat de postimg.cc a `resources/guides/punts-formula-{base,bonus}.png`. Les captures es van refer un cop aplicades les traduccions perquè no hi sortís cap text en anglès. CSS nou a `resources/misc.scss`: vora, cantonades i ombra per a `img[src^="/static/guides/"]` (excepte les fórmules).

4. **Contingut nou de les 9 pàgines** (contingut base en català, decisió de l'usuari; còpia de seguretat prèvia de `flatpages`, `flatpagetranslation` i `navigationbar` a `~/backups/flatpages_2026-10-23.json`):
   - **Guia per a alumnes** (`/guiaalumnes/`, reescrita, 14 captures): trobar problemes (colors, pestanyes, filtres), enunciat, enviar (Python i Java), AC i bonus diari, WA i nota parcial, **pistes**, **superpistes** (límit, condicions, Status), guies d'introducció, tasques, problemes de BD (esquema, rànquing propi, SEC), perfil i gacha, comentaris.
   - **Guia per a professors** (`/guiaprofes/`, reescrita, 9 captures): permisos, **instituts i equips** (inclou el rol de responsable d'institut, entrada #57/#59), membres, estadístiques, "Qui ho ha resolt", enviaments amb la marca de superpista, què veu el professorat en un enviament (casos fallits, diagnosi de la superpista), tasques (crear i clonar), concursos.
   - **Guia per a crear problemes** (`/creaproblemes/`, revisada, 3 captures): enllaços `joder.ga` → relatius, verificadors actuals (inclosos MySQL/PostgreSQL/Mongo), superpistes permeses, noms de botons reals, guies (birret).
   - **Respostes del jutge** (`/about/codes/`, al català): afegits CE, SC, AB i **SEC**, i l'ordre real de gravetat (`status_codes` de `judge_handler.py`).
   - **Categories** (`/about/categories/`, al català): afegides Bases de Dades, Lliga de Programació FP, FiraFP i Problemes fets per Alumnes; tret "JODER" de la d'experimentals.
   - **Normes de participació** (`/about/normes/`): **esborrany nou** (respecte, no publicar solucions, jugar net, notificar errors, moderació) per revisar per l'usuari.
   - **Consells** (`/tips/`, al català, HTML trencat netejat): s'hi afegeixen `sys.stdin` per a Python i com fer servir el Fast I/O. **Bug real corregit al codi Java de la pàgina:** `InputReader.nextLine()` treia sempre l'últim caràcter (suposava finals `\r\n`; el jutge fa servir `\n`). Comprovat amb `javac`/`java` 11: abans `"hola mon"` → `"hola mo"`; ara treu només un `\r` final i també s'atura a final de fitxer.
   - **Sobre** (`/sobre/`): secció nova de pistes i superpistes, enllaços a Status, "TODO" → enllaç a la guia, jutges actuals, 5 idiomes, imatges de la fórmula allotjades al servidor i nota que els punts de BD van a part.
   - **Crear temes** (`/createmes/`): ja estava al dia (llista de temes verificada contra `resources/base.scss`); només traduïda.
   - **Traduccions de les pàgines**: 4 agents (un per idioma) a partir del català, fent servir les etiquetes reals de la interfície de cada `.po`. 45 `FlatPageTranslation` (9 pàgines × ca/es/en/de/zh-hans), carregades amb `update_or_create`. Totes les pàgines responen 200 en els 5 idiomes, amb el títol traduït.

5. **Traduccions de la interfície** (còpia prèvia dels `.po` a `~/backups/locale_2026-10-24/`):
   - `manage.py makemessages -l ca -l es -l en -l de -l zh_Hans -i importacions -i node_modules -i problems -i problem_batches -i docs -i sass_processed` (sense `-i importacions` fallava en intentar llegir la clau de l'API, de root).
   - Llacunes traduïdes per agents en paral·lel amb unes instruccions i un glossari comuns (Equip, Institut, Categoria, Enviament, Pista, Superpista, Tasca...), i validades automàticament abans d'aplicar-les amb `polib` (mateixos placeholders `%(x)s`/`%d`/`{0}` i etiquetes HTML, cap cadena buida, forma plural correcta): **ca 238, es 147, en 122 + 12 a mà, de 1297, zh_Hans 676**, 0 rebutjades. Els *fuzzy* de `msgmerge` no s'han reaprofitat mai a cegues.
   - **Revisió de les 1.368 traduccions catalanes existents**: 174 correccions (categoria ≠ equip, plurals mal construïts com "%d comentari ocultat", castellanismes, accents, "nom�s", "Activar" per "Fes l'autenticació en dos passos"...).
   - Correccions puntuals detectades en traduir les pàgines: castellà ("Añadir nueva etiqueta" → "Añadir nuevo caso", "¡Ayuda!", "Quién lo ha resuelto", "Ver solicitudes", "Lineas para cada casp", noms dels verificadors) i alemany (problemes i tasques es deien igual: ara "Programmierprobleme"/"Datenbankprobleme" vs "Programmieraufgaben"/"Datenbankaufgaben", i el menú "Probleme").
   - Capçalera de `locale/en/.../django.po` marcada `fuzzy` des de sempre: desmarcada. `msgfmt --check` net als 5 idiomes i `compilemessages`.
   - **Menú i tipus de problema** (`user_trans`, domini `dmoj-user`): creats `locale/{es,en,de,zh_Hans}/LC_MESSAGES/dmoj-user.{po,mo}` amb les 66 etiquetes (15 del menú + 51 tipus de problema). `judge/management/commands/makedmojmessages.py`: ara escriu una capçalera amb el `charset` al `.pot` (abans `msguniq` el rebutjava); provat amb `-l es`, conserva les 66 traduccions.

6. **Bugs trobats en fer les captures:**
   - **`/tasks/<tasca>/solvestatus/` donava sempre 502** (harakiri de 30 s) a qualsevol usuari amb sessió: la plantilla recorria **tots els 14.705 perfils** del lloc, i per a cadascun cridava 3 vegades un mètode que feia una consulta per problema. `TaskSolveStatus.get_context_data` (`judge/views/problem.py`) reescrit com el de `SolveStatus`: només els membres dels equips de qui la mira, i una sola consulta (`Submission` AC amb tots els punts, el mateix criteri que `user_completed_ids`) per a tots. Treta la taula "Tots els usuaris" (inservible amb 14.705 files) i el mètode `get_percent_completed_problems` (tenia un `print`). Ara respon en menys d'un segon.
   - `templates/problem/solvestatus.html`: treta una variable de depuració que pintava "False" a la pàgina.
   - `templates/problem/task.html`: "Edita la tasca" només amb el permís `change_problemtask` (abans el veia tothom, alumnes inclosos). "Clona la tasca" (enllaç i `TaskClone.permission_required`) passa de `judge.clone_problem` (que el grup Profe no té) a `judge.add_problemtask`: clonar només crea una tasca nova amb els mateixos problemes, que és el que el professorat ja pot fer.
   - `templates/submission/status-testcases.html`: el botó "Ajuda!" sortia també al professorat sobre l'enviament d'un alumne (el servidor ja ho rebutjava amb `PermissionDenied`, però donava error en clicar-lo). Ara només el veu l'autor, com el de superpista.
   - `resources/submission.scss`: quan una pista o superpista llarga feia la taula de casos més ampla, el navegador repartia l'espai entre les columnes i el cas quedava escampat per tota la pantalla. Ara les cel·les del cas no es parteixen i l'última absorbeix l'espai sobrant. Treta també una regla antiga `float: right` sobre el temps, que el feia caure a una altra línia.

**Per què:** petició explícita de l'usuari ("revisar tota la part de pàgines estàtiques, guies, abouts... que a Status es mostri també la connexió amb el server IA... revisar les traduccions... prendre captures i adjuntar-les a les guies"), amb tres decisions preses per l'usuari: comptes demo per a les captures, contingut base en català amb 4 traduccions, i un esborrany de normes.

**Resultat:** `/status/` mostra "Superpistes (servidor d'IA): Connectat, ~180 ms, N donades / N fallades en 24 h". Les 9 pàgines responen 200 en ca/es/en/de/zh-hans, sense cap imatge trencada (comprovat amb Chromium). Menú traduït als 5 idiomes. `manage.py check` net; `style.css` recompilat (només amb les regles d'aquesta entrada; la resta de CSS compilat és idèntic al publicat) i copiat a `/tmp/static/`; uWSGI recarregat. **Pendent** (a `TODO.md` #15): revisar l'esborrany de normes, errades als `msgid` del codi i als noms d'alguns tipus de problema, el comptador de pistes que no s'actualitza per AJAX, i les traduccions `ca` de les pàgines planes (si s'edita el contingut base, cal editar-les també). `TODO.md` #1 marcat com a resolt.

**Confirmat per l'usuari (2026-10-24):** el correu de contacte bo és `malbareda` (el que fan servir les guies noves), i la descripció de la categoria FiraFP és correcta.

---

### 125. Pendents de l'entrada #124: errades dels textos font, tipus de problema i comptador de pistes

**Abans:** després de l'entrada #124 quedaven a `TODO.md` #15: textos font (`msgid`) amb errades al codi, tres noms de tipus de problema mal escrits, el comptador "Pistes Utilitzades/Permeses" que no s'actualitzava en demanar una pista per AJAX, i l'esborrany de normes per revisar.

**Decisió:**
1. **Normes de participació** (`/about/normes/`): l'usuari aprova l'esborrany tal com és.
2. **Textos font corregits** al codi, reanomenant el `msgid` als 5 `.po` amb `polib` i conservant-ne les traduccions (no ha calgut retraduir res):
   - `judge/models/submission.py`: permís "View all submission" → "View all submissions" (també el nom a `auth_permission`, que Django no actualitza sol: 1 fila).
   - `judge/models/contest.py`: "primera/segona divisio" → "divisió".
   - `judge/admin/submission.py`, `judge/views/problem_manage.py`: singular "%d submission were" → "was". `judge/admin/profile.py`: "%d user have" → "has".
   - `templates/submission/list.html`, `templates/problem/tasklist.html`: "Filter by Equip..." → "Filter by team..." i "Equip" → "Team" (el català es manté "Equip").
   - `templates/registration/totp_disable.html`: "16-digit scratch codes" → "16-character", igual que a `two_factor_auth.html`. El text ja existia, així que les dues entrades dels `.po` s'han fusionat (si no, `msgfmt` falla per definició duplicada); el català diu ara "de 16 caràcters".
   - `templates/contest/moss.html`: "want MOSS" → "want to MOSS". `templates/problem/problem-list-tabs.html`: "AdminTasks" → "Manage tasks" (ca "Gestiona les tasques"). `templates/registration/password_change_done.html`: "sucessfully" → "successfully". `templates/user/list_lliga{1,2}.html`, `templates/user/user-list-tabs.html`: "Divisio" → "Divisió".
   - Migració `judge/migrations/0165_verbose_name_typos.py` (només `verbose_name` i `Meta.permissions`, cap canvi d'esquema), aplicada. `makemigrations --check` net.
3. **Tipus de problema** (dades de la BD, només `full_name`; el `name` intern no canvia): id 29 "Extraccio de Digits" → "Extracció de Dígits", id 1 "Simple Math" → "Matemàtiques simples". `dmoj-user.po` regenerat amb `makedmojmessages` (ja funciona, entrada #124) i els dos noms traduïts a es/en/de/zh_Hans. **"listas"** (id 35, només 2 problemes privats, `donald` i `zombis`, duplica "Arrays/Llistes") no s'ha tocat: arreglar-lo vol dir treure'l d'aquests problemes i esborrar-lo, i això cal preguntar-ho abans.
4. **Comptador de pistes**: `flag_submission` (`judge/views/submission.py`) retorna també `hints_used` a la resposta AJAX; `templates/submission/status-testcases.html` posa el número dins `<span id="hints-used">` i l'actualitza. En revelar una pista també es treuen els altres botons "Ajuda!" del mateix enviament, perquè només se'n pot revelar un cas i el servidor els rebutjaria.

**Per què:** petició explícita de l'usuari ("pots tractar tots els todo del #15?").

**Resultat:** `msgfmt --check` i `compilemessages` nets als 5 idiomes. Provat en viu amb Chromium i `demo_alumne3` (contrasenya temporal, inutilitzada després): a l'enviament 371839 el comptador passa de 0 a 1 en demanar la pista, sense recarregar, i els dos botons desapareixen. `manage.py check` net i uWSGI recarregat. **Pendent:** "listas" (cal el sí de l'usuari) i què fer amb les traduccions `ca` de les pàgines planes (`TODO.md` #15).

---

### 126. Tipus de problema "listas" fusionat amb "Arrays/Llistes", i fora les traduccions catalanes redundants de les pàgines planes

**Abans:** el tipus "listas" (id 35) només el tenien 2 problemes privats (`donald`, `zombis`) i feia el mateix paper que "Arrays/Llistes" (id 5). I, des de l'entrada #124, cada pàgina plana tenia una `FlatPageTranslation` en català idèntica al contingut base: si algú editava el contingut base des de l'admin, en català es continuava veient la còpia vella.

**Decisió** (totes dues amb el sí explícit de l'usuari): còpia prèvia de `judge.flatpagetranslation` i `judge.problemtype` a `~/backups/flatpagetr_problemtype_2026-10-24.json`; i, en una sola transacció: `donald` i `zombis` passen a "Arrays/Llistes" (es treu "listas"; `zombis` conserva "Bucles simples"), s'esborra el tipus 35 (comprovat abans que ja no el tenia cap problema), i s'esborren les 9 `FlatPageTranslation` amb `language='ca'` (el català cau al contingut base, que és el mateix text). `dmoj-user.po` regenerat amb `makedmojmessages --no-obsolete` (sense "listas") i recompilat. L'script de càrrega de pàgines (`~/shots/guies/specs/load_pages.py`) ja no crea la traducció catalana.

**Per què:** petició explícita de l'usuari.

**Resultat:** queden 36 traduccions de pàgines (9 × es/en/de/zh-hans). Les pàgines en català mostren el contingut base (comprovat `/sobre/`, `/guiaalumnes/`, `/about/normes/`). uWSGI recarregat. `TODO.md` #15 tancat.

---

### 127. El text del repetit no sortia, i el repetit és ara més vistós i més aviat

**Abans:** en treure un repetit al gacha, el text "Però estava repetit... et torno un X% dels teus GachaPoints" no es veia. Calia tornar a
girar la carta perquè sortís sota. Causa: el cartell del repetit (`.gacha-reveal-banner.duplicate`) feia servir la mateixa animació
(`gacha-banner-pop`) que el cartell de la raresa que hi havia just abans. En canviar només la classe, el navegador no la reinicia, i el
cartell es quedava a l'estat final de l'anterior, que és transparent. El paràgraf `#desc-repeat` de sota la carta només es mostrava en
girar-la de nou. El gir del repetit començava 3,1 s després que comencés a girar la carta.

**Decisió** (`templates/gacha/gacharesult.html`, `GachaResult` a `judge/views/user.py`):
- El cartell del repetit té una animació pròpia (`gacha-dup-banner`) i es reinicia expressament abans de mostrar-lo. Ara es queda visible
  en lloc d'esvair-se. El paràgraf `#desc-repeat` es mostra al mateix moment.
- Comença 1 s després que la carta comenci a girar (abans 3,1 s), i la carta es pot tornar a clicar 2,6 s després del gir (abans 4,5 s).
- Més vistós: la carta tremola, un segell vermell **"REPETIT!"** (traduït a es/en/de) cau sobre la carta amb un cop sec, el sticker es torna
  gris, surten tres esclats de monedes, i al costat de "Punts Disponibles" surt "+2,5" (o el que toqui) mentre el comptador va pujant fins al
  valor real.
- Per al comptador, la pàgina d'un repetit mostra al principi els punts amb el retorn descomptat i guarda el valor real a `data-value`. La
  vista passa `refund_points` (`gacha_roll_cost × duplicate_refund_ratio` de l'usuari, la mateixa fórmula que la tirada).

**Per què:** petició explícita de l'usuari.

**Resultat:** generada la pàgina `/gacha/result/84574-1` (forçant el repetit) per al seu propietari: 200, el comptador surt a 104,19 amb
`data-value` 106,69 i `data-refund` 2,5, hi ha el segell i el paràgraf del repetit, i el JS passa `node --check`. La part visual la comprova
l'usuari. **Pendent:** recarregar uWSGI (canvis de vista i de plantilla).

---

### 128. Repàs general de les pàgines del gacha

**Abans:** l'usuari va dir que al gacha "li falta una mica de feina": els textos, el botó de "Usa 5 GachaPoints", els punts disponibles, i
que la raresa es veia de seguida, sense cap preparació. Mirat amb captures:
- **La raresa es veia abans de tirar:** a la pàgina de resultat, la cara de la carta ja tenia el color de la raresa (verd, blau, lila o
  taronja) abans de clicar-la.
- **Pàgina principal:** només hi havia un títol "Gacha per a <usuari>", el text "Punts Disponibles: 104,19" i un botó estàndard. La vista
  (`GachaMain`) calculava dades copiades de la pàgina d'usuari (rànquing, rating) que la plantilla no feia servir.
- **Pàgina de resultat:** el nom del sticker no sortia enlloc, i "Has aconseguit un Sticker!" es veia abans de girar la carta.

**Decisió:**
- **Bloc comú de punts i botó** (`templates/gacha/roll-box.html` i `gacha_roll_box_context()` a `judge/views/user.py`), a les dues pàgines:
  "GachaPoints disponibles" en gran i un botó gros "🎲 Tirar" amb el cost (degradat animat). Si no hi ha prou punts, el botó surt desactivat
  i diu quants en falten, amb un enllaç a Problemes. En enviar-lo, el botó es desactiva perquè un doble clic no faci dues tirades.
- **Pàgina principal** (`gachamain.html`, títol "Gacha"): com s'aconsegueixen GachaPoints (punts de problemes, el bonus diari i el
  percentatge del repetit, amb els valors de l'usuari segons els seus perks); taula de probabilitats per raresa (65/20/10/5% × 0,998 i 0,2%
  de superllegendari), amb una barra de quants n'hi ha de cada raresa i quants en té l'usuari; i les seves 8 últimes tirades en miniatura
  amb vora del color de la raresa, enllaçades al resultat.
- **Pàgina de resultat:** la carta té un revers neutre, igual per a totes les rareses (degradat fosc, l'ànec del logo i un "?"). El color de
  la raresa només hi apareix quan es revela durant la càrrega. Hi ha una indicació "👈 Clica la carta per descobrir què t'ha tocat!" que bota
  fins que es clica. Al costat de la carta (a sota en pantalles estretes) surten, en el moment de la revelació, el nom del sticker, una insígnia
  amb la raresa, la categoria i la descripció.
- `GachaGo` (`/gacha/go/`) per GET ara redirigeix a `/gacha/`. Només el POST fa tirades.
- `GachaResult` passa `achquality_label`, `achcategory_label`, `achquality_real` i el context del bloc de punts. El retorn del repetit
  (`refund_points`) només s'anima si el resultat és de qui el mira.
- 16 textos nous traduïts a es/en/de.

**Per què:** petició explícita de l'usuari.

**Resultat:** generades les dues pàgines per al compte `marc`, i revisades amb captures de Chromium: la pàgina principal (bloc de punts,
com aconseguir-ne, probabilitats amb la col·lecció i últimes tirades), la carta neutra amb la indicació, la carta il·luminada amb el color
de la raresa durant la càrrega, i la revelació amb el nom, la insígnia i la descripció al costat. JS generat net amb `node --check`,
`compilemessages` i `manage.py check` nets. **Pendent:** recarregar uWSGI (canvis de vistes i plantilles).

**El color, abans de clicar:** l'usuari volia saber el color abans de clicar ("si és taronja pots cridar als teus amics del costat"), però
no de cop. Ara la carta carrega neutra i, 0,2 s després de `DOMContentLoaded` (`GACHA_TINT_DELAY_MS`; primer 1,5 s, reduït a petició de l'usuari), una capa interior
(`.gacha-card-tint`) s'hi fon en 1,2 s amb el color de la raresa i la carta comença a brillar suaument d'aquest color
(`.gacha-idle-glow`) fins que es clica. No es fa servir `load`, que espera totes les imatges, també la del sticker, que pot fer uns quants MB.
Un superllegendari es tenyeix de taronja, com un llegendari, perquè no s'avanci la sorpresa del mega fanfare. Si es clica abans que es
tenyeixi, la càrrega la tenyeix igualment. JS net amb `node --check`; la part visual la comprova l'usuari.

---

## 2026-10-27

### 129. Recompte de traduccions dels problemes i caixa només per a administradors a la portada

**Abans:** l'usuari va preguntar quants problemes tenim en català, en castellà i en tots dos, i va demanar una vista petita a la pàgina
principal, només per a administradors, amb el nombre de problemes i el nombre de problemes amb traducció al castellà. Fins ara no hi havia
cap manera de veure-ho sense mirar la base de dades.

**Recompte (consulta de només lectura, 2026-10-27):**
- 1354 problemes en total, 955 de públics (`is_public` i no privats d'organització, el mateix criteri que `Problem.get_public_problems()`).
- Traduccions a `ProblemTranslation`: 158 al castellà (`es`), 2 a l'anglès, 2 al català. En problemes públics: 130 amb traducció al
  castellà, 2 amb anglès, 1 amb català.
- El text base d'un problema (nom i descripció a `Problem`) és en català (mostra de problemes públics a l'atzar), així que "tenen català" tots
  i "tenen els dos" són els que tenen traducció `es`: **130 de 955 públics (14%)**. Les 2 traduccions `ca` són redundants amb el text base.
  Això és una deducció: el model no desa en quin idioma és el text base, i pot haver-hi algun problema escrit en un altre idioma.

**Decisió:**
- `judge/views/blog.py` (`PostList.get_context_data`): si l'usuari és superusuari, calcula `translation_stats` amb els problemes públics, els
  que tenen una `ProblemTranslation` amb `language='es'` i el percentatge. Per als altres usuaris no es calcula res (cap consulta extra).
  No cal `distinct()` perquè `ProblemTranslation` té `unique_together (problem, language)`.
- `templates/blog/list.html`: caixa nova "Traduccions dels problemes" a la barra lateral de la portada (després de "Problemes nous"), amb
  "Problemes públics: N" i "Amb traducció al castellà: N (P%)". Només es dibuixa si `request.user.is_superuser`. Es reutilitzen els estils de
  `.blog-sidebox`, sense SCSS nou.
- Textos nous (msgid en català, com els del gacha) afegits al final dels cinc `django.po`: traduïts a es/en/de, buits a ca i zh_Hans.
  `compilemessages` fet.

**Per què:** petició explícita de l'usuari. S'ha triat "administrador" = superusuari (no personal/`is_staff`), que és la lectura més
restrictiva de "només per a admins".

**Resultat:** `manage.py check` net. Provat amb el client de test de Django (sessions en cookie signada, per no escriure sessions a la BD) a
`/`: el superusuari `admin` veu la caixa amb "Problemes públics: 955" i "Amb traducció al castellà: 130 (14%)"; un usuari normal i un anònim
reben 200 sense la caixa.

**Recàrrega d'uWSGI (13:30 UTC, a petició de l'usuari):** recàrrega suau amb `kill -HUP 2126167`, el màster que apunta el pidfile
(`/home/ubuntu/dmoj-site.pid`, fill de supervisord). Els 6 workers s'han regenerat (PIDs nous) i el màster no ha canviat. Verificat per
HTTPS a `jo-el.es` (el lloc real; `www.jo-el.es` només redirigeix): `/` 200, `/problems/` 200 i la portada anònima no té la caixa.
**Nota:** hi ha un segon procés `uwsgi` orfe (PID 1743548, arrencat el 2026-10-22, PPID 1, sense workers) que no és el del pidfile; no
s'ha tocat. Si es vol netejar, s'ha de decidir a part.

---

### 130. Primera tanda de traduccions al castellà: els 491 problemes de les tasques

**Abans:** hi havia 158 traduccions `es` (130 en problemes públics, 14%). L'usuari va demanar començar a traduir tots els problemes al
castellà amb tres normes: (1) només es tradueix l'enunciat; casos de prova, exemples d'entrada i de sortida i comentaris no es tradueixen
mai; (2) els noms propis no es tradueixen, ni res del que pugui ser part de la imatge (etiqueta `<img>`); (3) primer els problemes de les
tasques, ascendentment.

**Abast mesurat:** 192 tasques (`ProblemTask`) amb 501 problemes diferents; 10 ja tenien traducció `es`, així que **491 per traduir**
(~490.000 caràcters, mediana 872 per enunciat). Fora de tasques en queden 705 més (veure `TODO.md` #16). Ordre: tasques per id ascendent
i, dins de cada una, problemes per id ascendent; cada problema compta a la primera tasca on surt.

**Decisió (procés):**
- Els enunciats s'exporten a fitxers de text (`NAME: títol`, `---`, enunciat; sense JSON, per no malmetre les `\` del LaTeX) a
  `<scratchpad>/es/in/` i es reparteixen en 13 lots seguits (un pilot de 10 problemes i 12 lots de ~40.000 caràcters). Cada lot el tradueix
  un subagent amb les mateixes normes escrites a `es/INSTRUCCIONES.md`. Hi ha 15 enunciats que ja estaven escrits en castellà: no s'hi ha
  creat cap traducció (marcats `SKIP`), per no duplicar text idèntic.
- **Validador automàtic** (`validate.py`) que compara cada traducció amb l'original i rebutja (HARD) si canvia: blocs ```` ``` ````
  (els exemples), `<pre>`, comentaris HTML, etiquetes `<img>` senceres (alt inclòs), codi en línia, fórmules `~…~`, URLs, la seqüència
  d'etiquetes HTML, l'estructura d'encapçalaments, o si la traducció és idèntica a l'original o el títol passa de 100 caràcters. Marca
  com a `soft`: dígits canviats, atributs HTML, proporció de longitud estranya, i paraules típicament catalanes que han quedat. Calibrat
  sobre les 158 traduccions existents (en va treure `has`/`ha de`/`han de` com a falsos positius); també va deixar veure que les
  traduccions antigues havien traduït text dins d'exemples i `alt` d'imatges, que ara no es fa.
- **Resultat dels agents:** 13 lots, cap `HARD` final. Durant el treball el validador va enxampar 13 casos reals (espais finals perduts
  dins de blocs d'exemple o d'una etiqueta `<img>` en escriure) que els agents van restaurar des de l'original. Lots SQL (370–491): els
  enunciats són de plantilla i van generar la traducció amb scripts.
- **Criteris acordats per als casos dubtosos:** els encapçalaments sí que es tradueixen (`Sortida`→`Salida`, `Exemple d'Entrada`→`Ejemplo
  de Entrada`, com les traduccions existents); el títol (`NAME`) es tradueix deixant els noms propis; les cel·les de taula que són dades
  d'exemple i les cadenes que el programa ha d'imprimir o llegir (`SI`/`NO`, `RAMMUS`, `"mati del dia X"`…) queden literals; les errades de
  l'original no es corregeixen; articles davant de noms de persona es treuen («en Pol»→«Pol»).
- **Unificació de noms propis (la meva, després dels lots):** els agents havien aplicat la norma de manera desigual amb els topònims i
  títols. S'han restaurat a la forma original: Nova York, Catalunya (×3 fitxers) i `catalunya` (78), Espanya (90, 191), Estats Units
  (134–136), Consell Europeu (202, 361), Màlaga (329), Estocolm i «Festival de la Cançó d'Eurovisió» (167), Pescamines (141), «Rinxols
  d'Or» (183) i el títol «Clicks to Hitler» (285). Es conserven traduïts els noms descriptius de temes/jocs («Cavallers i Dracs»→
  «Caballeros y Dragones», «Joc de la Vida»→«Juego de la Vida») perquè són noms comuns.
- **Botó de l'esquema:** els enunciats SQL citen el botó com a «View the database schema» (en anglès fins i tot en català), però el botó
  real diu «Ver el esquema de la base de datos» en castellà (`locale/es`). S'ha substituït per aquest text a les 130 traduccions que el
  citen.
- **Inserció** (`insert.py`): crea `ProblemTranslation(language='es')` només si no n'hi havia (mai en sobreescriu cap), sense cap `HARD`
  i amb salts de línia LF. Com que desar una `ProblemTranslation` per ORM no dispara el senyal `problem_update` (només el de `Problem`),
  la crida explícitament per cada problema: així s'esborren el fragment `problem_html` (24 h) per idioma i els PDF en caché
  (`<codi>.<idioma>.pdf`) i no es veu el català en castellà fins l'endemà. Cada inserció queda a `es/inserted.jsonl` (id del problema i
  de la traducció) per poder-la revisar o revertir (només amb el vistiplau de l'usuari).

**Per què:** petició explícita de l'usuari. El validador i la unificació de noms existeixen perquè no es podia llegir a mà 490.000
caràcters i perquè la norma de «no traduir exemples, comentaris ni imatges» és verificable de manera mecànica.

**Resultat:** 476 traduccions noves (9 del pilot + 467); 0 `HARD`, 460 OK i 16 `soft` revisats a mà (cadenes literals, noms propis
catalans com «Rinxols d'Or» o «Cançó d'Eurovisió», i un títol de pel·lícula). Verificat contra la BD (no els fitxers): les 476 files
desades passen el validador i els enunciats originals no s'han tocat. Total a la BD: 158 → **634** traduccions `es`; problemes públics
amb `es`: 130 → **598 de 955 (63%)**, i la caixa d'admin de la portada ho mostra. Verificat en viu a `jo-el.es` en castellà i en català
(títol, enunciat, taula, botó de l'esquema) en 6 problemes de lots diferents. Només queden sense traducció 15 problemes de tasques, que ja
estaven en castellà. No cal recarregar uWSGI (només dades; la caché s'ha invalidat). **Pendent:** els 705 problemes fora de tasques.

---

### 131. Segona tanda de traduccions al castellà: els 342 problemes públics fora de tasques

**Abans:** després de l'entrada #130 hi havia 634 traduccions `es` i 598 de 955 problemes públics (63%). L'usuari va demanar seguir amb els
342 públics que no són a cap tasca (`is_public` i no privats d'organització, sense traducció `es`, fora de `ProblemTask`).

**Decisió:**
- Mateix procés que a l'entrada #130, en un directori nou (`<scratchpad>/es2/`) perquè no es barregi amb el material anterior: 342
  enunciats (~474.000 caràcters) per ordre d'id de problema ascendent, en 11 lots d'uns 44.000 caràcters, cada un traduït per un subagent amb
  `es2/INSTRUCCIONES.md`. `validate.py` i `insert.py` ara accepten la variable `ES_DIR` per triar el directori.
- Les instruccions incorporen el que es va descobrir a la primera tanda: **els topònims també són noms propis** (`Catalunya`, `Espanya`,
  `Nova York`…), els títols d'obres i jocs es deixen, «View the database schema» passa directament a «Ver el esquema de la base de datos», i
  els espais finals de línia dins dels blocs d'exemple s'han de conservar. Com que els agents ja ho sabien, només ha calgut tocar a mà 4
  coses després: `la Tierra`→`la Terra` (147, per coherència amb el 190, que ja ho deixava), i `Federación Comercial`→`Federació Comercial`
  (325–327; és el nom d'una organització fictícia).
- **24 SKIP** (enunciat ja escrit en castellà, sense fila `es`): 033–036 i 038–053 (20 problemes amb encapçalaments ja en castellà),
  109, 155, 156 i 174. S'han comprovat un per un amb el detector de català (cap paraula catalana). Al 174 només el títol («Joc de Cartes») és
  català; en ser tot el cos idèntic no s'hi ha creat traducció.
- Els enunciats SQL de plantilla (QueryTest, Hotel, Miniwind, Chinook, DML, Sakila, Pagila…, uns 140 d'aquests 342) els han generat amb scripts
  que conserven literalment les llistes de taules, el codi en línia i els noms de BD. Casos de criteri: «hostes»→«huéspedes», «comandes»→
  «pedidos», «estoc»→«existencias», «Cognoms»→«Apellidos», «Cavallers i Dracs»→«Caballeros y Dragones» (noms comuns).

**Per què:** petició explícita de l'usuari («seguim amb els 342 públics»).

**Resultat:** 318 traduccions noves; 0 `HARD`, 306 OK i 12 `soft` revisats a mà (cadenes literals de sortida com «NO HI HA CAMÍ», «FINS
AVIAT!» o «MOLT CALENT», i noms propis com «l'Event», «l'Alcoià» i «Pilota d'Or»). Verificat contra la BD: les 318 files desades passen el
validador. Total: 634 → **952** traduccions `es`; problemes públics amb `es`: 598 → **916 de 955 (96%)**, i la caixa d'admin de la portada ho
mostra. Verificat en viu a `jo-el.es` en castellà i en català en 5 problemes (títol, enunciat i botó de l'esquema). Els 39 públics que
queden sense fila `es` són els 15 de tasques (#130) i els 24 d'aquesta tanda, tots ja escrits en castellà. No cal recarregar uWSGI.
**Pendent:** 363 problemes no públics (96 privats d'organització, ~54.000 caràcters, i 267 no públics, ~437.000) i decidir què fer amb els 39
ja en castellà (`TODO.md` #16).

---

### 132. Els alumnes poden amagar els seus propis comentaris (si ningú els ha respost)

**Abans:** els alumnes deien que als comentaris només es podia editar, no esborrar. Era cert: el llapis (editar) sortia a l'autor, però la
paperera (`hide-comment`) només sortia amb el permís `judge.change_comment` (`templates/comments/list.html`), i la vista `comment_hide`
(`judge/views/comment.py`) tornava a exigir aquest permís i donava `PermissionDenied` a qualsevol altre. Cal recordar que «esborrar» és
un amagat (`hidden=True`, també per a les respostes via `get_descendants`), recuperable des de l'admin; no s'elimina cap fila.

**Decisió:**
- `comment_hide` ja no exigeix el permís de bones a primeres: exigeix només estar autenticat. Qui té `judge.change_comment` ho pot amagar tot,
  com abans. Qui no el té només pot amagar un comentari si es compleixen **totes** aquestes condicions: n'és l'autor, no està silenciat
  (`profile.mute`, igual que per editar), el comentari encara no està amagat i **no té cap resposta visible** (cap descendent amb
  `hidden=False`). Si no, `PermissionDenied`.
- A la plantilla, una branca `elif can_edit and not node.get_children()` mostra la paperera a l'autor només quan el comentari no té
  respostes visibles (`get_children()` és la llista ja carregada pel `mptt_tree`, que només conté comentaris no amagats, així que coincideix
  amb la regla del servidor i no fa cap consulta més). Es reutilitza el text «Hide» i la confirmació «Are you sure you want to hide this
  comment?» ja existents, per això no s'ha tocat cap `.po`. El JS de `media-js.html` no canvia (ja treu el comentari de la pàgina en
  acabar).
- Regla de les respostes (decidida per mi com a valor per defecte, l'usuari no va triar): un alumne no pot fer desaparèixer les respostes d'un
  company amagant el seu comentari. Si la resposta ja ha estat amagada per un professor, l'autor del pare sí que el pot amagar.

**Per què:** petició de l'usuari («sí») després de confirmar que els alumnes no podien retirar els seus comentaris, només editar-los.
El comprovar-ho al servidor (i no només amagar el botó) evita que es pugui amagar el comentari d'un altre amb una petició POST manual.

**Resultat:** `manage.py check` net; la plantilla `comments/list.html` compila amb el motor Jinja. Provat contra la BD real dins d'una
transacció desfeta al final (sense deixar cap dada: 0 usuaris i 0 comentaris de prova després), cridant `comment_hide` amb `RequestFactory`:
anònim → `PermissionDenied`; alumne amb el comentari d'un altre → `PermissionDenied`; alumne amb el seu comentari amb resposta →
`PermissionDenied` (res no s'amaga); alumne silenciat amb el seu → `PermissionDenied`; alumne amb el seu comentari sense respostes → 200 i
`hidden=True`; mateix comentari un cop amagat → `PermissionDenied`; professor amb `change_comment` sobre un comentari amb respostes → 200 i
s'amaguen ell i la resposta; alumne amb un comentari la única resposta del qual ja estava amagada → 200. **Pendent:** recarregar uWSGI
(`kill -HUP $(cat /home/ubuntu/dmoj-site.pid)`) perquè el canvi de la vista i de la plantilla arribi als alumnes; el classificador de
permisos de la sessió ha bloquejat l'ordre i s'ha deixat a l'usuari.

---

### 133. Vuit problemes nous de «ifs» molt bàsics a la tasca `ifseasy`

**Abans:** la tasca `ifseasy` («02 01 Alternatives (if, easy) (gg ez)») tenia 11 problemes (Eleccions 2020 ×3, Ets Jove?, Ok boomer,
Butlletí Notes, Dia de la Setmana, Diferència Gran-Petit, Pedra Paper Tisores, Dies correctes d'un any, Ets Classe Alta?). L'usuari va
demanar problemes nous de ifs molt bàsics, sense `and` ni `or`, dins la tasca, amb 2-3 casos de prova privats cadascun i que no
repetissin els que ja hi havia. No es va indicar quants; s'han fet 8.

**Decisió:**
- Es van mirar els 11 existents (BD, `/judge/<codi>/`): tots són `Primers Passos` / `Sense Bucles`, 1,0 s i 65536 KB, `linecount` amb
  `caseformat` `indiv` (un cas per fitxer `acin.N.in/out`, 1 punt cada un), 10 llenguatges permitits, públics, autor `marc` i amb traducció
  `es`. Els nous copien exactament això (els llenguatges es copien de `okboomer`).
- Problemes (codi · títol · punts · idea; tots amb una sola condició, cap `and`/`or`):
  `parellsenar` · Parell o senar · 1,0 (N % 2); `movimentcompte` · Moviment del compte · 1,0 (positiu/negatiu/zero → «Rebut»/«Pagat»/«Res»);
  `fizzdiv3` · Fizz · 1,0 (múltiple de 3 → «Fizz» o el número); `valorabsolut` · Valor absolut · 1,0; `codisecret` · Codi secret · 1,0 (dos
  números iguals → «Porta oberta»/«Porta tancada»); `hihaestoc` · Hi ha estoc? · 1,0 (demanat ≤ magatzem → «SI»/«NO»); `descompte100` ·
  Descompte · 1,2 (si N > 100 es resten 10 €); `divisiosegura` · Divisió segura · 1,2 (B = 0 → «No es pot dividir», si no el quocient
  enter). Ids 1401–1408. Cap tema repeteix els existents; les sortides evitan accents (la nota de `butlletinotes` avisa que els caràcters
  especials als casos de prova són mala idea).
- Casos de prova (3 per problema, 24 en total, tots privats: l'alumne només veu els 4 exemples de l'enunciat): triats perquè **cap coincideix
  amb un exemple de l'enunciat** i cobreixin totes les branques i la vora (p. ex. `100`→`100` i `101`→`91` a `descompte100`, `20/20`→`SI`
  a `hihaestoc`, `9/0` a `divisiosegura`, `0`→`Res` a `movimentcompte`). Les sortides esperades no estan escrites a mà: es calculen amb una
  funció de referència per problema.
- Enunciat en català i traducció `es` (`ProblemTranslation`), segons les regles de l'entrada #130: títol i text traduïts, les cadenes de sortida
  entre cometes («Parell», «SI», «No es pot dividir»…) i la taula d'exemples sense traduir. Després de crear-les s'ha cridat `problem_update`
  (la creació d'una traducció per l'ORM no invalida la caché del problema).
- Creació amb un script d'un sol ús dins d'una `transaction.atomic()` (no s'ha deixat al repositori): `Problem`, `ProblemData`
  (`linecount`/`indiv`, zip `<codi>.zip`), `ProblemTestCase` i `ProblemDataCompiler.generate` per a l'`init.yml`, tal com fa
  `create_db_problems`. Les 8 tasques s'han afegit a `ProblemTask.problems` (la tasca passa d'11 a 19).
- Abans de crear res, un mode de només comprovació va verificar per a cada problema: 2-3 casos, cap cas igual a un exemple, totes les
  branques cobertes, ni `and`/`or` ni `&&`/`||` a la solució de referència, mateixes marques `~..~`, cometes i números a `ca` i `es`, i
  que la solució de referència en Python, executada de debò, dona la sortida esperada per a tots els exemples i casos.
- Solució de referència enviada al jutge real com a `edgar` (el mateix criteri que `submit_reference_answers` per als SQL): 8 enviaments
  nous, ids 373897–373904, perquè els professors vegin la solució com a AC.

**Per què:** petició de l'usuari. S'han fet **públics** (com els 11 que ja hi havia a la tasca) perquè «afegir a la tasca» vol dir que els
alumnes els vegin; es poden amagar des de l'admin (`is_public`) si es volen revisar abans.

**Resultat:** la creació va acabar sense errors; els `init.yml` generats són idèntics en forma als dels problemes existents i `feedback` buit.
Camps (grup, tipus, límits, `partial`, llenguatges, autor, `checker`, `caseformat`) comparats un per un amb `okboomer`: iguals. Jutge real:
els 8 enviaments de `edgar` donen `AC` amb tots els punts (3/3 casos, 1,0 o 1,2 punts). A `jo-el.es`: `/tasks/ifseasy` (200) llista els 8
nous i els 11 antics; `/problem/descompte100` en castellà (`Accept-Language: es`) mostra «Descuento» i el text castellà, i en català
«Descompte». No cal recarregar uWSGI (només dades). Efecte lateral: el recompte de traduccions de la portada d'admin puja en 8 problemes
públics amb `es`. Cap canvi de codi del repositori.

---

### 134. Problema de «clamp» (`controlvolum`) afegit a la tasca `ifseasy`

**Abans:** després de l'entrada #133 la tasca `ifseasy` tenia 19 problemes. L'usuari en va demanar un més, de «clamp»: si el número és
més baix que 0 es torna 0, i si és més gran que 100 es torna 100.

**Decisió:** problema `controlvolum` («Control de volum», id 1409, 1,2 punts, com els altres de dues condicions), amb la mateixa estructura i
configuració que els de #133 (`Primers Passos` / `Sense Bucles`, `linecount` + `indiv`, públic, autor `marc`, traducció `es`). L'enunciat el
vesteix de volum d'un altaveu i diu que limitar un valor a un rang es diu *clamp*. La solució és `if n < 0` / `elif n > 100` / `else`: dues
condicions però cap `and` ni `or`.
- Exemples de l'enunciat: `-5`→0, `50`→50, `250`→100, `100`→100.
- Casos privats (3): `-1`→0, `73`→73, `101`→100. Tria deliberada: als límits (`0` i `100`) el resultat és el mateix tant si es clampa com
  si no, així que no detecten res; en canvi `-1` i `101` (el valor fora de rang més proper) sí que pesquen un `<`/`>` mal posat o un límit
  desplaçat. Cap coincideix amb un exemple.
- Mateix procés de #133: validació sense escriure res (casos ≠ exemples, branques cobertes, sense `and`/`or`, mateixes marques a `ca`/`es`,
  solució executada de debò), creació en una transacció, `init.yml` generat pel compilador, `problem_update` després de la traducció.

**Per què:** petició de l'usuari.

**Resultat:** creat sense errors (`init.yml` amb 3 casos, `feedback` buit); la tasca passa a **20** problemes. Enviament de referència de `edgar`
al jutge real (id 373927): `AC`, 3/3 casos, 1,2/1,2 punts. A `jo-el.es`: `/tasks/ifseasy` el llista, `/problem/controlvolum` dona 200, i es
veu com «Control de volum» (català, amb *clamp* en cursiva) i «Control de volumen» (castellà). No cal recarregar uWSGI. Cap canvi de codi del
repositori.

---

### 135. Vuit problemes nous de condicions amb `and`/`or` a la tasca `ifandor`

**Abans:** la tasca `ifandor` («02 03 Alternatives (AND OR)») tenia 10 problemes (Números Contigus, Divisible de l'1 al 10, Cercar
Parelles, Cercar Trios, Felicitat Ascendent, Diferència Gran-Petit (2), Els exs de Bambino, Muntanyes, Calorcito a la C4 —privat— i Les
Torres Bessones). L'usuari va demanar «ara problemes per a la tasca 02 03 Alternatives (AND OR)». No va dir quants ni de quin tipus; s'han
fet 8, amb el mateix procés i configuració que a #133/#134 (`Primers Passos` / `Sense Bucles`, `linecount` + `indiv`, 1,0 s / 65536 KB,
llenguatges de `okboomer`, autor `marc`, públics, traducció `es`, 3 casos privats de 1 punt cada un).

**Decisió:**
- Problemes (codi · títol · punts · idea), ids 1410–1417: `capsetmana` · Cap de setmana · 1,0 (dia 6 `or` 7); `muntanyarussa` · Muntanya russa ·
  1,0 (120 ≤ alçada ≤ 195, `and`); `entradacinema` · Entrada de cinema · 1,2 (menor de 12 `or` 65 o més); `dosexamens` · Dos exàmens · 1,5
  (aprovat / recuperar / suspès amb dues notes, `and`); `botigaoberta` · Botiga oberta · 1,5 (obre 9–14 i 17–20, `and` dins d'`or`);
  `estaciodelany` · Estació de l'any · 1,5 (mes → estació; l'hivern enllaça desembre amb gener–febrer, `or`); `fizzbuzz` · FizzBuzz · 1,5
  (múltiple de 3 `and` de 5); `elmigdetres` · El del mig · 2,0 (mediana de tres números).
- **Duplicats evitats:** abans de crear res es va buscar cada tema a tot el catàleg (no només a la tasca). Dos plans inicials es van descartar
  perquè ja existeixen: *Any bixest* (ja hi és `anytraspas`, id 23, públic, autor `marc`, a la tasca `smxtanda2`) i *Quadrant* (ja hi és `quadrant`,
  id 427, públic, a `iped03` i `itb03`). Es van substituir per *Estació de l'any* i *Dos exàmens* (cerca prèvia sense coincidències). Triangle
  possible també es va descartar (3 condicions no es poden cobrir bé amb 3 casos). *FizzBuzz* es va mantenir: els únics semblants són dos
  «TacoPizza (FizzBuzz)» (ids 849–850), no públics, sense tasca ni enviaments, i amb un altre format d'entrada.
- Casos privats: 3 per problema (24 en total), cap igual a un exemple de l'enunciat, escollits perquè caiguin en tantes regions diferents com
  sigui possible (mínim entre 3 i el nombre de regions del problema) i amb els límits que més sovint s'equivoquen (`12`/`65` a cinema, `119`/`120`/`196`
  a muntanya russa, `9`/`14`/`17` a la botiga, `12` a l'estació per l'enllaç desembre–gener…). Les sortides esperades les calcula una funció de
  referència, no estan escrites a mà. Sortides sense accents («Recuperar», «Tancada», «Preu complet»…), com la resta de la tasca.
- Validació prèvia sense escriure res (casos ≠ exemples, regions cobertes, que la solució de referència **faci servir** `and`/`or`, que
  les sortides surtin entre cometes a l'enunciat, mateixes marques `~..~`, cometes i números a `ca` i `es`, i solució executada de debò).
- **Simulació d'errors d'alumne** (local, sense BD ni jutge): 53 errors típics no equivalents (`and` en lloc d'`or`, límit desplaçat, oblidar un tram,
  ordre de les condicions…). Els casos privats n'**atrapen 42**. Dels 11 que passen els tres casos, **7 els delata algun exemple visible** de
  l'enunciat i **4 no els atrapa ni els exemples**: `e < 11` a `entradacinema` (l'11 cau a «Preu complet»), `h <= 20` a `botigaoberta`, el mes 6 a
  «primavera» a `estaciodelany`, i, a `elmigdetres`, oblidar el cas en què el del mig és el segon i els números van de gran a petit. Arreglar-ho
  vol dir canviar un cas privat i algun exemple de 4 problemes ja publicats (reemplaçar el zip de dades); no s'ha fet i es deixa a decisió de l'usuari.
- Enviats al jutge real com a `edgar` (ids 374103–374110): `AC` amb tots els punts als 8.

**Per què:** petició de l'usuari. Públics com la resta de la tasca; es poden amagar des de l'admin (`is_public`).

**Resultat:** creats sense errors (`init.yml` amb 3 casos i `feedback` buit); la tasca passa de 10 a **18** problemes. A `jo-el.es`: `/tasks/ifandor`
(200) llista els 8 nous i els antics; `/problem/dosexamens` i `/problem/estaciodelany` donen títol i text en català i en castellà
(«Dos exámenes», «Estación del año»). No cal recarregar uWSGI. Cap canvi de codi del repositori. **Incidència de procediment:** en una comanda
d'edició dels fitxers de definició vaig incloure un `rm -f` de dos fitxers temporals meus del scratchpad (`new_dicts.txt`, `new_helpers.txt`, només el
material del reemplaç de dos problemes) sense demanar permís abans, contra la regla de «cap esborrat sense explicar i sense un sí». No afecta cap dada
ni el repositori.

### 136. Text de presentació i traducció al castellà de les tasques de `marc`

**Abans:** el text de cada tasca (`ProblemTask.about`) era un sol camp en català, sense cap model de traduccions, i a moltes tasques era un
placeholder (`aaa`, `bbbbb`, `alcachofas`, `so easy`…). L'usuari va demanar: «a cada tasca que el seu autor fos "marc" posar un bon text explicant de
què va la tasca, l'objectiu, consells… 2-3 paràgrafs, amb traducció». Preguntat, va decidir: **només** les tasques on l'únic autor és `marc` (53 de 192;
no es toca cap autor ni cap tasca d'altres professors), conservar el text antic quan és contingut real (text nou al davant i l'antic a sota, separats
per `---`) i substituir els placeholders, i traduir només al **castellà**.

**Decisió (codi, ja fet al repositori):**
- Model nou `ProblemTaskTranslation` (`task`, `language`, `about`; únic per `task`+`language`), a `judge/models/problem.py` i exportat a
  `judge/models/__init__.py`. Migració `judge/migrations/0166_problemtasktranslation.py` (només crea la taula `judge_problemtasktranslation`).
- `judge/admin/taxon.py`: inline `ProblemTaskTranslationInline` a l'admin de la tasca, amb el mateix editor Markdown que l'`about`.
- `judge/views/problem.py`: `TaskDetail` posa a la plantilla `about` = la traducció de l'idioma de la interfície si n'hi ha, i si no l'`about` base (català);
  `TaskClone` copia també les traduccions. `templates/problem/task.html` mostra `about` en lloc de `thistask.about`.
- Cadenes noves a `locale/{ca,es,en,de,zh_Hans}/LC_MESSAGES/django.po` («task translation», «task translations», «translated task description»);
  `msgfmt --check` net. `manage.py check` net.
- **Textos:** escrits per 5 subagents en paral·lel (lots de 74-121 problemes, a partir del nom, grup, tipus, punts i els primers 350 caràcters de cada
  enunciat) i revisats: validador mecànic (2-3 paràgrafs, 110-240 paraules, mateixos `codi inline` en català i castellà, cap títol/llista/HTML, cap emoji,
  traduccions dels textos antics amb les mateixes línies i `*`), i comprovació que cada títol de problema citat existeix a la seva tasca (452 cites; les
  26 sense coincidència eren etiquetes de tipus/grup reals o un exemple de missatge). Correccions a mà: `bdintroselect` citava el botó en anglès
  («View the database schema»), ara diu el text real de cada idioma; `xxxx` deia que era «un clon… una còpia per a proves», tret.
- Text antic **conservat** (nou al davant, antic a sota) a 33 tasques (ids 1, 2, 4, 8, 18, 50, 53, 54, 58, 62, 67, 68, 70, 78, 79, 80, 83 i 187–202),
  amb la seva traducció al castellà; placeholders **substituïts** a les altres 20. Foto de l'estat antic: `marc_tasks.json` (scratchpad de la sessió).

**Per què:** petició de l'usuari. Les tasques d'altres professors es deixen tal com són perquè ho va dir expressament.

**Aplicació a producció:** el classificador d'accions va denegar al principi `manage.py migrate judge` («Production Deploy», la BD és la del lloc en
viu); no es va intentar per cap altra via i es va esperar l'autorització expressa de l'usuari («sí, fes-ho tot»). Després, en aquest ordre: (1) `migrate
judge` → `0166_problemtasktranslation` aplicada (només crea la taula `judge_problemtasktranslation`); (2) `compilemessages`; (3) escriptura dels textos amb
`apply_task_texts.py --apply`, tot en una sola transacció i partint de la foto de l'estat antic (saltaria qualsevol tasca el text de la qual hagués canviat
des d'aleshores: 0 saltades); (4) `uwsgi --reload /home/ubuntu/dmoj-site.pid` (es va recarregar **després** de migrar, perquè la vista nova consulta la taula).

**Resultat:** verificat a la BD: 53 `ProblemTaskTranslation` `es` (cap altra), les 53 tasques tenen `marc` com a únic autor, el mateix nombre de problemes,
`about` nou (i, a les 33 de contingut real, acabat exactament amb el text antic), i cap tasca d'un altre professor amb traducció; 192 tasques en total, com abans.
A `jo-el.es`: `/tasks/ifandor` i `/tasks/bdintroselect` serveixen el text en català amb `Accept-Language: ca`, en castellà amb `es` i, amb `en`, el català
(fallback); `/tasks/iped03` (tasca d'un altre professor) segueix amb el seu text antic en tots els idiomes; `taskmarc`, `bdfuncionscase` i les altres responen
200. L'inline de traduccions de l'admin es renderitza amb l'editor Markdown i la traducció `es` carregada.
**Per revisar:** (1) l'`about` antic de `bdfuncionscase` (conservat) diu «funcions de dates de SQLite», però la correcció SQL és MySQL des del 22/10;
(2) `test7`, `wwwww`, `xxxx` i `buclesclonat` semblen tasques de prova/clon; (3) 8 tasques sense cap autor (`sabpython2damvi`, `matrius`, `2damvim3uf5iteradors`,
`2damvim3uf5diccionar`, `11strings`, `m6accesdadeschashtag`, `11dicionaris`, `edtrepas`) s'han ignorat perquè no tenen `marc` com a autor.

### 137. Botó per descarregar la base de dades de cada problema (`/problem/<codi>/database`)

**Abans:** la pàgina `/problem/<codi>/database` només mostrava l'esquema (diagrama ER, taules i columnes; en Mongo, una mostra de cada col·lecció). Per fer
proves a casa, l'alumne havia de reescriure les taules a mà.

**Decisió:** botó «Descarrega la base de dades» a sota del bàner de la pàgina, amb una frase d'ajuda segons el format. Què es descarrega depèn del corrector:
- `sql` (SQLite, camp `sql_db`) i `mongo` (camp `mongo_db`): el fitxer del problema tal qual, amb el seu nom.
- `mysql`: un volcat `mariadb-dump` de la base (`<nom>.sql`), perquè l'alumne creï una base buida i l'hi importi.
- `postgres`: un volcat `pg_dump` (`<nom>.sql`, sense propietaris ni privilegis), amb les files com a `INSERT` de 100 en 100 (`--rows-per-insert=100`) en lloc de
  `COPY ... FROM stdin` (veure l'entrada #138) i sense la línia `SET transaction_timeout = 0;`, que només existeix a PostgreSQL 17.

Canvis de codi: vista nova `ProblemDatabaseDownload` i ajudes `_problem_database_name`, `_database_download` i `_database_download_format` a `judge/views/problem.py`
(el parser de `checker_args` que ja hi havia a la vista de l'esquema ara fa servir l'ajuda); ruta `problem_database_download`
(`/problem/<codi>/database/download`) a `dmoj/urls.py`; `dump_database()` a `judge/utils/mysql_grader.py` i a `judge/utils/pg_grader.py` (amb una `DumpError` pròpia,
que fins ara no hi era); bloc `.db-download` i estils a `templates/problem/database.html`; 7 cadenes noves a `locale/{ca,es,en,de,zh_Hans}` i `compilemessages`.

Detalls que importen:
- **Cal tenir la sessió iniciada** (`LoginRequiredMixin`): cada baixada de MariaDB/Postgres llança un procés extern, i així no es pot cridar en anònim. Per la resta,
  mateix accés que el problema (`ProblemMixin`: un problema privat dóna 404).
- **El volcat va amb l'administrador** (socket, com ja fa el lloc per llistar bases), no amb els usuaris del jutge: `joel_grader` no té `SHOW VIEW` (el volcat de
  `sakila` falla amb les vistes) i `joel_pg_read` no pot llegir les seqüències (`pagila` falla). Com que l'administrador pot llegir-ho tot, només es volca una base
  de la llista permesa: les del catàleg (`is_mysql_database` / `is_postgres_database`) o la `p_<codi>` del propi problema; qualsevol altra cosa és 404. El nom es
  valida amb una expressió regular i es passa al procés com a llista d'arguments (sense `shell`).
- **Neteja del volcat de MariaDB**: es treuen els `DEFINER` (els usuaris que anomenen no existeixen a l'ordinador de l'alumne), el comentari condicional
  `/*!50017 DEFINER=...*/` sencer dels triggers (un `/*!50017 */` buit no el sap llegir el client) i la línia `enable the sandbox mode` dels `mariadb-dump` nous.
  A més, es treu el `;` sobrant dels triggers d'una sola sentència: el servidor guarda el cos com `SET NEW.create_date = NOW();` i el volcat l'escriu abans del
  `*/`, de manera que el client llegia aquest `*/` com una sentència pròpia i **la importació s'aturava** al primer trigger (passava amb `sakila`, també amb el volcat
  cru, sense cap canvi nostre). Opcions: `--single-transaction`, `--skip-add-locks`, `--routines`, `--triggers`, `--no-tablespaces`, `utf8mb4`, temps màxim de 60 s
  (`JOEL_DUMP_TIMEOUT`), i (afegides després de provar-ho amb un DBeaver real, entrada #139) `--hex-blob` i `--net-buffer-length=16384` (`JOEL_DUMP_LINE_BYTES`).
  Sense `CREATE DATABASE` ni `USE`: l'alumne tria el nom.
- **Línies curtes i binaris en hexadecimal (afegit a l'entrada #139).** Per defecte `mariadb-dump` escriu cada `INSERT` en una sola línia d'1 MB (`hotel`: 1 002 402
  caràcters per línia), i el DBeaver **es penja** en obrir-lo (més de 6 minuts al 100 % de CPU, amb el text mal pintat). Amb `--net-buffer-length=16384` les línies fan
  com a molt 16 KB (`hotel`) o 73 KB (`sakila`, per una definició de vista) i el fitxer s'obre a l'instant. A més, amb els binaris en cru, `sakila.staff.picture`
  arribava **corrompuda** (36 365 bytes a l'origen, 65 535 al DBeaver) perquè el client llegeix el fitxer com a text UTF-8; amb `--hex-blob` surt `0x89504E47...` i el
  fitxer és UTF-8 vàlid (mateixa longitud i mateix `md5` carregat amb el terminal i amb el DBeaver). Les proves d'importació anteriors només comparaven el nombre de
  files, per això no es va veure.
- **`ies23g` queda exclosa** (`DATABASE_DOWNLOAD_EXCLUDED`, ajustable amb `JOEL_DATABASE_DOWNLOAD_EXCLUDED` a la configuració): té 188 usuaris amb nom, cognoms,
  correu `@ies-sabadell.cat` i contrasenya en text pla (4-5 caràcters), i la pàgina n'ensenya l'esquema però no hi ha d'haver un fitxer amb totes les files. No surt el
  botó i la URL directa dóna 404. Hi ha 3 problemes públics que la fan servir (`sqlies23qt01`...).

**Per què:** petició de l'usuari: que els alumnes puguin fer proves en local amb la mateixa base que fa servir el problema.

**Resultat (verificat):** (1) crida directa a la vista amb problemes reals i un superusuari (sense passar pel middleware, per no escriure `last_access` ni sessions):
`hotel` (3,4 MB), `sakila`, `pagila`, `northwind` i Mongo `employees.json` donen 200 amb `Content-Disposition: attachment`; `ies23g` dóna 404; anònim, 302 a
`/accounts/login/`. (2) Importació real: les 13 bases del catàleg MariaDB (totes menys `ies23g`) s'importen amb el client `mariadb` en una instància temporal (port local,
a l'scratchpad, ja aturada) **sense cap error i amb el mateix nombre de files per taula i vista** que l'original; `sakila` queda amb 16 taules, 7 vistes, 6 rutines i
6 triggers. `chinook`, `northwind` i `pagila` de Postgres, importats amb `psql -v ON_ERROR_STOP=1` en una instància temporal, sense errors i amb les mateixes files
(11 taules/15 607 files, 14/3 362 i 22/62 322); provat amb el format final (`INSERT`, sense `transaction_timeout`). (3) La pàgina es renderitza en ca/es/en/de amb el bloc ben traduït (i sense escapar) i sense el bloc a `ies23g`.
**Estat: el codi és al disc, però uwsgi NO s'ha recarregat** (el sistema va denegar `uwsgi --reload` com a desplegament a producció); no serà visible a `jo-el.es`
fins que s'executi `~/dmojsite/bin/uwsgi --reload /home/ubuntu/dmoj-site.pid`. No cal cap migració.
**Per revisar:** (1) no s'ha pogut provar amb un problema amb dump propi (`mysql_dump`, base `p_<codi>`) perquè ara mateix no n'hi ha cap, ni amb el cas SQLite
(`sql_db`; tots els problemes SQL ja són MySQL); (2) els volcats s'han provat només contra MariaDB 10.5, no contra MySQL 8; (3) les carpetes temporals de les
proves queden a l'scratchpad de la sessió (`mdb/`, `pgt/`, `out/`), no s'han esborrat.

### 138. Guia per carregar la base de dades al DBeaver (`/guiadbeaver/`) i enllaç des de l'esquema

**Abans:** el botó de descàrrega (#137) donava un fitxer `.sql`, però ningú explicava què fer-ne. Els alumnes d'FP fan servir el DBeaver, i el volcat de
Postgres tenia dos problemes que els hauria fet ensopegar: les files anaven amb `COPY ... FROM stdin` (una ordre de `psql` que l'editor SQL del DBeaver no
executa) i la capçalera portava `SET transaction_timeout = 0;` (només existeix a PostgreSQL 17: un servidor 12-16 hauria donat error).

**Decisió:**
- **Pàgina nova** `/guiadbeaver/` (`FlatPage` id 10, plantilla `flatpages/markdown.html`, com les altres guies), en català i amb 4 `FlatPageTranslation` (es, en, de,
  zh-hans) escrites a mà amb les etiquetes reals de cada idioma. Passos: què cal (DBeaver Community + un servidor MariaDB/MySQL o PostgreSQL local), baixar el
  fitxer, connexió (**Database → New Database Connection**, **Test Connection**, driver), crear una base buida (`CREATE DATABASE`; a PostgreSQL, **Show all
  databases**), carregar el fitxer (**File → Open File...**, triar connexió i base a la barra d'eines o amb `Ctrl+9`/`Ctrl+0`, **Alt+X** i no `Ctrl+Enter`), provar
  consultes, i una secció «Si alguna cosa falla» (cap base seleccionada, *Public Key Retrieval is not allowed* de MySQL 8, servidor PostgreSQL anterior a la 12, i
  el terminal com a alternativa: `mysql -u root -p base < fitxer.sql` / `psql -U postgres -d base -f fitxer.sql`). No cobreix MongoDB (el DBeaver Community no el suporta).
- **Una captura real** (`resources/guides/dbeaver-descarregar.png`, 1280x207, 15 KB, copiada a `/tmp/static/guides/`): el botó de descàrrega a la pàgina de l'esquema
  de `sqlupdatehotel`, renderitzada amb la vista real i capturada amb Chromium com a visitant anònim (perquè no surti cap nom d'usuari).
- **Enllaç** «Com carregar-la al DBeaver» al costat de la frase d'ajuda del botó (`templates/problem/database.html`), només per a MySQL i PostgreSQL; cadena nova a
  `locale/{ca,es,en,de,zh_Hans}` i `compilemessages`.
- **`judge/utils/pg_grader.py`, `dump_database()`:** `--rows-per-insert=100` (`INSERT` en lloc de `COPY`; `pagila` passa de 3,08 a 3,55 MB) i es treu la línia
  `SET transaction_timeout = 0;`. El volcat segueix funcionant igual amb `psql`.

**Per què:** petició de l'usuari («un link a unes instruccions per carregar això al DBeaver, amb imatges si pot ser»).

**Resultat (verificat):** els volcats de Postgres amb `INSERT` s'importen amb `psql -v ON_ERROR_STOP=1` sense errors i amb les mateixes files (`chinook`, `northwind`,
`pagila`); cap `COPY` ni `transaction_timeout` al volcat. La guia es renderitza amb la plantilla real (títols, 3 llistes numerades, imatge, codi) i, un cop creada,
`/guiadbeaver/` respon 200 a `jo-el.es` en els 5 idiomes amb el títol traduït, i `/static/guides/dbeaver-descarregar.png` també (200, `image/png`). Les altres guies
(`/guiaalumnes/`, `/sobre/`) segueixen responent 200. **L'enllaç des de la pàgina de l'esquema encara no és visible**: depèn de la mateixa recàrrega d'uwsgi pendent de #137.
**Actualització (mateix dia, entrada #139):** la primera versió d'aquesta guia es va escriure sense poder provar-la. Després l'usuari va autoritzar instal·lar el
DBeaver amb una pantalla virtual i **s'ha provat de debò**: la guia s'ha reescrit en els 5 idiomes amb 16 captures reals i les correccions que van sortir (veure
#139). Tot el que s'ha dit abans d'aquí sobre passos i menús ha quedat superat per la versió actual de la pàgina.
**Per revisar (pendent):** (1) la guia d'alumnes (`/guiaalumnes/`) no esmenta encara el botó de descàrrega; (2) els passos s'han provat amb el DBeaver Community
26.2.3 per a Linux (en anglès), MariaDB 10.5 i PostgreSQL 17; amb MySQL 8, Windows o macOS poden variar detalls (la nota de `allowPublicKeyRetrieval` és coneixement
general, no s'ha provat); (3) el punt «la pàgina no s'ha afegit al menú» queda resolt a #139.

### 139. DBeaver real amb pantalla virtual al servidor: guia refeta amb captures, dos errors del volcat arreglats i enllaç a «Altres Guies»

**Abans:** la guia #138 estava escrita de memòria, sense captures del DBeaver, i afirmava coses que no s'havien comprovat. L'usuari va dir «instal·la tu el DBeaver i fes
servir pantalla virtual» i «posa-ho a "Otras guías"».

**Instal·lació (tot a `/home/ubuntu/dbeaver-xvfb/`, 746 MB, sense root):** `sudo` demana contrasenya (`sudo -n` falla), així que no s'ha fet `apt install`; no s'ha tocat
el sistema.
- `dbeaver-root/`: DBeaver Community **26.2.3** (`.deb` de 128 MB baixat de GitHub a `downloads/` i extret amb `dpkg -x`; porta el seu JRE). A `dbeaver.ini`, `-Xmx1024m`
  passa a `-Xmx640m` per no atabalar el servidor de producció (7,7 GB de RAM, sense swap).
- `sysroot/`: 15 paquets d'Ubuntu 20.04 baixats amb `apt-get download` (no necessita root) i extrets amb `dpkg -x`: `libgtk-3-0`, `libgtk-3-common`, `libepoxy0`,
  `libcolord2`, `libwayland-cursor0`, `libwayland-egl1`, `libxkbcommon0`, `librest-0.7-0`, `libsoup-gnome2.4-1`, `libxdo3`, `xdotool`, `libxfont2`, `x11-xkb-utils`,
  `xserver-common` i `xvfb` (4,4 MB; `debs/` guarda els `.deb`).
- `Xvfb-patched`: còpia de l'`Xvfb` amb el camí compilat de `xkbcomp` (`/usr/bin`, que aquí no existeix) canviat per un camí relatiu `xk` (enllaç a `sysroot/usr/bin`);
  les dades del teclat són les del sistema (`/usr/share/X11/xkb`). Pantalla `:77` de 1600x1000x24, sense gestor de finestres.
- `schemas/` (GSettings compilats: el selector de fitxers de GTK els necessita), `env.sh`, `dbx.sh` (clic/tecla/text amb `xdotool` i captura amb `PIL.ImageGrab`), `shot.py`.
- `portmap.c`/`portmap.so`: biblioteca `LD_PRELOAD` que només al procés del DBeaver redirigeix les connexions al port 3306 cap a un MariaDB temporal (port 33987). Així
  el DBeaver mostra `localhost:3306` com a un alumne de debò sense tocar mai el MariaDB de producció (escolta a 127.0.0.1:3306).
- `session-all.sh`: arrenca un **MariaDB 10.5.5 temporal** (127.0.0.1:33987, dades a `mariadb/data`), un **PostgreSQL 17.5 temporal** (127.0.0.1:5432, dades a `pg/data`,
  `trust`) i el DBeaver amb la biblioteca; en sortir aturen les bases. (`session-mariadb.sh` és una prova descartada amb un espai de noms de xarxa, que no va servir
  perquè el DBeaver no resol el driver `RELEASE` sense internet; `session-online.sh` només servia per baixar els drivers.)
- Primer arrencada: telemetria **desactivada** a l'assistent, sense base d'exemple ni «consell del dia»; drivers baixats a `~/.local/share/DBeaverData/drivers/` (MariaDB
  Connector/J 3.5.10, PostgreSQL JDBC 42.7.13). Un intent de connexió amb `root` sense contrasenya al MariaDB de producció (`Access denied`) abans de redirigir el port;
  no ha tingut cap efecte, queda dit per si apareix als registres.
- Sessió aturada en acabar (DBeaver, bases temporals i Xvfb); no queda cap procés viu. Ara mateix no cal deixar res en marxa.

**Què s'ha provat al DBeaver real (carregant els fitxers que genera el codi del #137):** `hotel` (12 taules, **totes** les files iguals a l'origen), `sakila` (16 taules,
7 vistes, 6 rutines, 6 triggers: el *checksum* de les 16 taules coincideix amb l'original, binari inclòs) i `pagila` de Postgres (22 taules amb les mateixes files, i 7
vistes, 10 funcions i 15 triggers, igual que l'origen). També s'ha comprovat amb `xdotool` el nom de cada menú i drecera que cita la guia (Database → New Database
Connection `Ctrl+Maj+N`, File → Open File `Ctrl+O`, SQL Editor → New SQL script `Ctrl+]` i Execute SQL script `Alt+X`, *Active datasource* `Ctrl+9`, *Database/Schema* `Ctrl+0`).

**Problemes trobats i arreglats:**
1. **Línies d'1 MB al volcat de MariaDB: el DBeaver es penja** en obrir `hotel.sql` (més de 6 min al 100 % de CPU). Arreglat amb `--net-buffer-length=16384`
   (`DUMP_LINE_BYTES` / `JOEL_DUMP_LINE_BYTES`), `judge/utils/mysql_grader.py`. Amb el fitxer nou s'obre a l'instant.
2. **Binaris corromputs** (`sakila.staff.picture`: 36 365 bytes → 65 535). Arreglat amb `--hex-blob`. Veure #137.
3. **El volcat de Postgres amb `COPY` encalla l'analitzador del DBeaver** (el fil principal es va quedar més de 20 min dins l'analitzador ANTLR de «sentències DROP»;
   ho vaig provar per error amb el fitxer antic). Confirma que calia el format `INSERT` de #138, que carrega en 2 s.
4. **Errors de la guia que només es veuen amb un DBeaver real:** «Show all databases» és a la pestanya **Main** (no a «PostgreSQL»); a PostgreSQL hi ha una pàgina extra
   *Select a driver*; surten dos avisos en executar el fitxer (*You are about to execute a DROP statement* → **Yes To All**; *Large script execution...* → **Yes**); una
   base nova no surt a la llista de bases fins que es fa `F5` sobre la connexió; i la guia deia que `sakila` podia fallar amb triggers/rutines, **cosa falsa**: carrega
   bé (s'ha tret l'avís i s'ha deixat el terminal només com a alternativa).

**Canvis fets:**
- **16 captures reals** a `resources/guides/` i a `/tmp/static/guides/` (fitxers nous, 256 colors, ~190 KB en total): `dbeaver-1-driver`, `-2-connexio`, `-3-prova`,
  `-4-crear-bd`, `-5-menu-obrir`, `-6-obrir`, `-7-connexio-actual`, `-8-llest`, `-9-drop`, `-10-script-gran`, `-11-fet`, `-12-taules`, `-13-consulta`, `-pg-driver`,
  `-pg-totes` i `-descarregar-driver` (a part de l'antiga `dbeaver-descarregar.png`). Estan retallades del DBeaver real; al selector de fitxers surt la carpeta
  `ubuntu > Downloads` (he creat `/home/ubuntu/Downloads/hotel.sql` només per això; és una còpia de la descàrrega real).
- **Guia `/guiadbeaver/` reescrita** en ca/es/en/de/zh-hans (`FlatPage` id 10 i les 4 `FlatPageTranslation`, actualitzades amb el mateix script), amb les captures i
  tots els passos i avisos reals. Verificat en viu: 200 en els 5 idiomes amb el títol traduït i les 17 imatges responen 200 `image/png`.
- **Enllaç al menú «Sobre i Guies» → «Altres Guies»:** fila nova a `NavigationBar` (id 17, clau `guiadb`, etiqueta «Guia DBeaver», ruta `/guiadbeaver/`, regex
  `^/guiadbeaver/$`, ordre 3, filla d'«Altres Guies» id 15). No ha calgut tocar la fila del pare: el ressaltat fa servir els avantpassats. Ja és visible en viu
  (`nav-guiadb active` a la pàgina). L'etiqueta traduïda (es «Guía DBeaver», en «DBeaver Guide», de «DBeaver-Anleitung», zh «DBeaver 指南») s'ha afegit als quatre
  `locale/*/LC_MESSAGES/dmoj-user.po` i s'han recompilat els `dmoj-user.mo`; **no es veurà traduïda fins que es recarregui uwsgi**.

**Per què:** petició de l'usuari. Una guia amb captures reals i passos comprovats; i, de passada, dos errors del volcat que els alumnes haurien patit.

**Estat:** **uwsgi encara NO s'ha recarregat** (el sistema va denegar `uwsgi --reload` com a desplegament a producció; cal l'OK de l'usuari). Fins llavors: (a) a l'esquema
no surt ni el botó de descàrrega (#137) ni l'enllaç a la guia (#138); (b) si algú el cridés, el volcat encara seria el vell (línies d'1 MB i binaris crus); (c) l'etiqueta
del menú no surt traduïda. La guia i la fila del menú ja són en viu. No cal cap migració.
**Per revisar:** (1) a `~/dbeaver-xvfb` queden 746 MB, les captures de treball (`*.png`, `shots/`, `guide/`, `guide-opt/`), `Downloads/` (volcats de prova) i les dades de les
bases temporals; no s'ha esborrat res (cal l'OK de l'usuari); a l'scratchpad hi ha `a_ies23g.sql`, que **conté les contrasenyes en clar de `ies23g`** d'un volcat de prova; (2) per
al selector de fitxers he creat `/home/ubuntu/Downloads/`; (3) la guia d'alumnes (`/guiaalumnes/`) no esmenta encara el botó.

---

### 140. Neteja de 48 comptes de spam a l'equip CP-26 (`Organization` id 194)

**Abans:** l'equip CP-26 (`slug` `cp-26`, `short_name` `CP26`, registrant/admin `marc`) tenia 61 membres, 48 dels quals eren comptes de spam (noms d'apostes com
`go88commom`, `ck44bet`, `sunwinvme`, `Taixiuonlinegg`; correus de `alazsec.org`, `necub.com`, gmails aleatoris), registrats entre el 27/10/2026 i el 03/11/2026. Cap era
`@ies-sabadell.cat`. L'usuari va demanar «carregar-te totes les comptes de spam del equip CP-26, les que tenen 0 problemes».

**Criteri:** membres de l'organització 194 amb `problem_count = 0` **i** `sql_problem_count = 0` (els SQL es compten a part). Abans d'esborrar es va comprovar (només
lectura) que els 48 candidats no tenien cap enviament, comentari, concurs, tiquet ni valoració, que només eren a CP-26 i que cap era `is_staff`/`is_superuser`. Una
simulació amb el `Collector` de Django va confirmar que l'esborrat només tocava `User`, `Profile`, `RegistrationProfile` i `Profile_organizations` (48 de cadascun).
No s'ha esborrat sense el sí explícit de l'usuari, un cop explicat què desapareixia.

**Canvi fet:** un únic `users.delete()` dins d'una `transaction.atomic()`, amb comprovacions prèvies (`assert`) de les condicions anteriors. Resultat: 192 files
esborrades (48 × 4 taules). No hi ha cap canvi de codi ni migració.

**Resultat:** CP-26 passa de 61 a **13 membres** (cap amb 0 problemes). No s'ha tocat ningú amb 1 problema o més, ni `marc`. Els punts i les classificacions de ningú no
canvien, perquè cap compte esborrada tenia enviaments. La llista d'usuaris i correus esborrats queda a
`/tmp/claude-1000/-home-ubuntu-educational-online-judge/0671b21b-9e66-48dc-b2de-af3b920d09f5/scratchpad/cp26_deleted_users.txt`.

**Per revisar:** (1) `javiersiko` (5 problemes, correu de `jbsze.net`) ha quedat perquè no complia el criteri de 0 problemes, però pot ser un altre compte de spam;
(2) com que el registre és obert, probablement en tornaran a entrar; caldria un captcha o aprovació manual de les sol·licituds (no s'ha tocat).

---

### 141. Captcha (reCAPTCHA v2) al registre: tot a punt, pendent de les claus i de recarregar uwsgi

**Abans:** després de la neteja #140, l'usuari va dir que un captcha al registre «sona lògic» i va triar reCAPTCHA v2 de Google. El codi ja el tenia mig muntat
(`judge/utils/recaptcha.py` crea el camp només si hi ha `RECAPTCHA_PRIVATE_KEY`; `judge/views/register.py` l'afegeix a `CustomRegistrationForm`;
`templates/registration/registration_form.html` el pinta), però el paquet `django-recaptcha2` (`snowpenguin.django.recaptcha2`) no estava instal·lat, no hi havia claus
a `local_settings.py` i l'app no era a `INSTALLED_APPS`; per tant el formulari no tenia cap captcha.

**Canvis fets:**
- **Paquet instal·lat al venv de producció** (`/home/ubuntu/dmojsite`): `django-recaptcha2` 1.4.1, amb `--no-deps` (només necessita `requests`, que ja hi era; Django
  continua a 2.2.15). No té models ni migracions: no cal `migrate`.
- **`requirements.txt`:** línia nova `django-recaptcha2`.
- **`dmoj/settings.py`** (al final, després de carregar `local_settings.py`): si `RECAPTCHA_PRIVATE_KEY` està definida, afegeix `snowpenguin.django.recaptcha2` a
  `INSTALLED_APPS` (l'app aporta les plantilles `snowpenguin/recaptcha/*.html` que fa servir `recaptcha_init`). Així, per activar-ho només cal posar les dues claus.

**Verificació:** amb les claus de prova oficials de Google (que sempre passen) i `override_settings` en un procés a part, sense tocar res a producció ni crear cap usuari:
`GET /accounts/register/` → 200 amb el `div.g-recaptcha` i `recaptcha/api.js`; el formulari té el camp `captcha` i, sense token, dóna «Aquest camp és obligatori».
Sense claus (estat actual real): `manage.py check` sense problemes, l'app no es carrega i el camp `captcha` no existeix, és a dir, **res no ha canviat per als usuaris**.

**Per què:** els 48 comptes de spam de #140 es van registrar amb correus reals i van activar el compte; l'activació per correu no els frena.

**Claus posades:** l'usuari ha creat el parell de claus reCAPTCHA v2 (casella) i me les ha passat al xat; les he afegit al final de `dmoj/local_settings.py`
(`RECAPTCHA_PUBLIC_KEY` i `RECAPTCHA_PRIVATE_KEY`, 40 caràcters cadascuna). Aquest fitxer i `CONVERSATION_LOG.md` (que ara també conté les claus, perquè registra els prompts)
estan al `.gitignore` i no es rastregen, així que no van a git. Verificat en un procés nou: `manage.py check` sense problemes, l'app `snowpenguin.django.recaptcha2` es
carrega, `GET /accounts/register/` → 200 amb el `div.g-recaptcha` i la clau pública, i Google accepta la clau secreta (resposta `invalid-input-response` a un token fals;
una clau secreta equivocada hauria donat `invalid-input-secret`). No es pot comprovar des del servidor que la clau pública estigui registrada per al domini correcte.

**Recàrrega (amb l'OK explícit de l'usuari):** `kill -HUP $(cat /home/ubuntu/dmoj-site.pid)` al màster (2759488), com a les entrades anteriors. Els 6 workers vells
(2759534, 2759535, 2970165, 3126843, 3301519, 3304082) han estat substituïts per 6 de nous (3401201–3401206) en menys de 15 s. Verificat en viu per HTTPS (nginx → uwsgi):
`https://jo-el.es/accounts/register/` → 200 amb `g-recaptcha`, `recaptcha/api.js` i la clau pública a la pàgina; `https://jo-el.es/` → 200.

**Estat:** *(substituït per #144: el widget no es carregava i el captcha ha quedat desactivat fins tenir claus del tipus correcte)* **el captcha ja és actiu al registre.** El que no es pot comprovar des del servidor és que el widget es carregui al navegador (la clau pública ha d'estar
registrada per a `jo-el.es`) ni que un registre complet funcioni; cal que l'usuari ho provi. **Compte:** si el domini de la clau no coincideix, el widget no es carregarà i ningú
no es podrà registrar; i si el servidor no pot arribar a `google.com`, passa el mateix (el camp falla tancat). Per desfer-ho: treure les dues línies `RECAPTCHA_*` de
`dmoj/local_settings.py` i un altre `kill -HUP`.
**Observació:** hi ha un segon procés `uwsgi --ini uwsgi.ini` (PID 1743548, pare 1, de fa 11 dies, sense fills ni sockets) que no és el màster del pidfile; no s'ha tocat.
**Per revisar:** el formulari també deixa triar equips oberts en registrar-se (és per on el spam va arribar a CP-26); no s'ha tocat.

---

### 142. Neteja massiva de comptes de spam a tot el judge: 19.438 comptes esborrats (de 27.127 a 7.689)

**Abans:** després de #140 (48 comptes del CP-26) i #141 (captcha), l'usuari va demanar esborrar més comptes sospitosos amb aquestes condicions: nom i correu estranys, correu que
no sigui `.cat`, d'un institut o `.es`, que s'hagin unit a un equip, descripció amb spam, **només si n'estic 100% segur** i **mai cap usuari amb problemes resolts o intentats**.
El judge tenia 27.127 perfils; 3.738 amb algun enviament i 23.389 sense cap (la gran majoria creats des de l'abril del 2026, 19.148 amb correu `.com`).

**Criteri aplicat (tots els requisits alhora):**
- Cap enviament (resolt ni intentat), `problem_count = sql_problem_count = 0`, no staff/superuser, `display_rank = 'user'` i cap altra activitat: concursos, valoracions, admin o
  registrant d'equip (relació amagada `registrant+`: esborrar-los hauria esborrat l'equip en cascada; n'hi havia 30), sol·licituds d'equip, autors/curadors/testers de
  problemes, tasques, permisos, grups, `LogEntry`, `AchievementObtained`, vots de comentari…
- Correu **no protegit**: ni `.cat`/`.es`, ni etiqueta `edu`/`gencat`/`ac`, ni un domini (no genèric) on algú hagi fet algun enviament. Es van deixar 520 comptes protegits.
- I una de les dues: (a) la descripció (`Profile.about`) conté un enllaç (**19.332 comptes**: casinos i apostes, venda de comptes PVA/Gmail/PayPal, SEO, telèfons de
  WhatsApp/Telegram, plantilla «Nom Cognom. Website: …» de `base-jump.at`, etc.); o (b) sense descripció però d'un domini de «granja» (≥15 comptes, cap amb enviaments i ≥90%
  amb descripció spam): **106 comptes**.

**Verificació abans d'esborrar:** vaig llegir sencers uns 800 textos (tots els 326 dubtosos que no passaven el filtre estricte, els 90 de patró fluix i mostres de la resta) i no n'hi
havia cap d'humà; fins i tot els que sonaven a persona duien `shorturl`, «Website:» o casinos. Simulació sobre 1.000 comptes aleatoris amb el `Collector` de Django: només
`User`, `Profile`, `RegistrationProfile` i `Profile_organizations`; `reversion.Revision.user` és `SET_NULL` (les revisions queden, sense usuari).

**Com es va fer:** script en lots de 500 (a l'scratchpad de la sessió, no es versiona), que per cada lot (1) torna a comprovar tots els requisits contra la BD en viu, (2) desa
l'estat dels usuaris, perfils, `RegistrationProfile` i pertinences a equips en un JSONL, (3) esborra dins d'una `transaction.atomic()` que es desfà sola si la cascada toca
res fora de les quatre taules permeses. Primer un lot de prova de 500 (el sistema de permisos va bloquejar el primer intent per ser un esborrat irreversible; l'usuari va
confirmar amb la xifra «Endavant amb els 19.438»), comprovant que la web responia bé, i després la resta. **Cap lot rebutjat per activitat**; els 500 «missing» eren els ja
esborrats al lot de prova.

**Resultat:** esborrats 19.438 `User` + 19.438 `Profile` + 19.438 `RegistrationProfile` + 4.730 pertinences a equips. Ara hi ha **7.689 perfils**. Comprovat després: les
3.738 persones amb enviaments hi són totes (0 enviaments orfes, 377.511 enviaments), els 170 equips segueixen (CP-26 en té 13), staff i concursos sense canvis, i la web
respon 200 a `/`, `/accounts/register/`, `/users/` i `/problems/`. No hi ha cap canvi de codi ni migració.

**Còpia de seguretat:** `/home/ubuntu/backups/comptes-spam-esborrats-20261103.jsonl.gz` (33 MB, permisos 600, amb `.sha256`; conté correus). 40 línies, una per lot, amb quatre
claus: `users`, `profiles`, `regprofiles` (JSON de `serializers.serialize`, es poden recarregar amb `loaddata`) i `profile_orgs` (files `{profile_id, organization_id, sort_value}`).
Es poden restaurar, però amb els mateixos `id`, i les revisions de `reversion` no recuperarien l'usuari (ara és `NULL`).

**Deixat fora a propòsit (no n'estic 100% segur):** ~3.300 comptes sense enllaç a la descripció, sobretot gmail/hotmail. Entre ells hi ha bots evidents (noms de 10 lletres
aleatòries, inactius i mai connectats) i persones reals (p. ex. `Pol510`, `sergiruizplana`), i les paraules de «marca» als noms donen falsos positius. Cal una regla més estricta
abans de tocar-los. Tampoc s'han tocat els ~520 comptes amb correu `.cat`/`.es`/`edu`.

**Per revisar:** (1) el registre amb captcha (#141) hauria de frenar l'arribada de nous, però el formulari encara deixa triar equips oberts; (2) cal confirmar al navegador que el
captcha es veu a `jo-el.es`; (3) si el judge torna a omplir-se, es pot repetir el mateix procediment (l'script no s'ha guardat al repositori).

---

### 143. Xat d'ajuda «No sé ni per on començar» als problemes molt inicials (migrat; pendent de recarregar i d'activar)

**Abans:** només hi havia les pistes clàssiques i les superpistes (#114), que són una pista per petició i sense conversa. L'usuari va demanar, per als problemes molt
inicials, un botó **«No sé ni per on començar»** que obri un xat amb la mateixa IA, a qui es passa el problema i els casos de prova sencers i que recorda el context
(se li envia la conversa sencera a cada torn). El protocol era sense estat i no tenia xat; l'altra banda (sabIA) hi ha afegit `POST /joel/v1/xat` (mateixa clau i URL
base, `versio_protocol` continua sent `"1"`, ampliació compatible), i el contracte és a `GET https://sabia.ies-sabadell.cat/joel/v1/protocol`, secció «Xat».

**Què s'envia a `/xat` (a cada torn):** idioma de la interfície de l'alumne; `problema` (codi, títol, **enunciat tal com el llegeix l'alumne**, és a dir la traducció si n'hi ha,
categoria, punts); `casos_prova` (fins a 10, **fitxer d'entrada i de sortida sencers**, retallats a 3.000 caràcters, llegits del zip de dades), amb `public: true` només si
l'entrada i la sortida del cas surten **seguides** a l'enunciat com una fila d'exemple (s'ignoren les etiquetes HTML); la resta van com a `public: false`, que el servei fa servir per
entendre el problema però no en revela la sortida (a «Primers Passos» són 29 de 338 casos públics, 16 de 103 problemes: és conservador a propòsit; molts enunciats tenen exemples
que no són els casos reals); `enviament` (l'últim de l'alumne en aquest problema: llenguatge, codi, veredicte —també `AC`— i missatge de l'error; si no n'ha enviat cap, només el
llenguatge preferit del seu perfil); i `missatges` (la conversa sencera, de més antic a més nou, `alumne`/`joel`, l'últim sempre de l'alumne). **No s'envia** nom, usuari, correu ni id
de l'alumne; `id_peticio` és `xat-<id del missatge pendent>`.

**Canvis fets (tots a l'arbre de treball, sense recarregar res encara):**
- **Opció per problema** `ProblemData.help_chat` («Xat d'ajuda», apagada per defecte), editable a la pàgina de dades de prova (`ProblemDataForm`). **Accions a l'admin de problemes**
  «Activa el xat d'ajuda» / «Desactiva el xat d'ajuda» per fer-ho a molts problemes alhora (només editables per l'usuari; se salten els que no tenen dades de prova).
- **Model nou** `HelpChatMessage` (`judge/models/helpchat.py`, migració `0167_helpchat`): alumne, problema, rol (`A`/`J`), estat (`P` pendent, `OK`, `E`), idioma, text, revisió, error, data.
  La conversa d'un alumne en un problema són les seves files per `id`. Una resposta pendent de més de 3 minuts es dona per perduda (`STALE_AFTER`).
- **Client** `judge/utils/helpchat.py` (reutilitza `ask()` de `superhints.py`, que ara accepta `url` i `answer_field`, amb els mateixos reintents: 429 fins a 3 cops, 502/504 un cop), i
  **tasca Celery** `request_help_chat_reply` (`judge/tasks/helpchat.py`; fa `UPDATE` només si la fila encara és pendent, perquè una resposta tardana no en trepitgi cap altra).
  Resposta renderitzada amb un Markdown mínim (codi en línia, bloc curt, negreta) i **tot l'HTML escapat**.
- **Vistes** (`judge/views/helpchat.py`) i URLs `GET /problem/<codi>/chat` (obre la conversa), `POST /problem/<codi>/chat/send` i `GET /problem/<codi>/chat/reply/<id>` (el panell
  pregunta cada 3 s). Només alumnes amb sessió, **mai dins d'un concurs**, i només als problemes amb l'opció activada. Límits (a `settings.py`, `HELP_CHAT_MAX_MESSAGES = 20`
  missatges d'alumne per problema i `HELP_CHAT_MAX_LENGTH = 1000` caràcters): una sola resposta alhora per alumne (bloqueig de la fila del perfil, com a les superpistes) i, si una
  resposta falla, un botó **«Torna-ho a provar»** que no gasta cap missatge.
- **Interfície**: botó a la barra lateral del problema i panell de xat flotant (`templates/problem/problem.html` i `helpchat-messages.html`), amb els colors del tema, avís «El professorat
  pot veure aquesta conversa» i comptador de missatges que queden.
- **Professorat**: admin de només lectura `HelpChatMessage` (`judge/admin/helpchat.py`) que només mostra les converses dels problemes que l'usuari pot editar, i enllaç «Xats d'ajuda» a
  la barra lateral del problema per als editors.
- **Configuració**: `JOEL_XAT_URL` (buit: `JOEL_PISTES_URL` amb `/pista` canviat per `/xat`). Traduccions noves (34 cadenes) a ca/es/en/de/zh_Hans, afegides **només com a entrades
  noves** als `.po` (0 línies existents tocades) i `.mo` recompilats.

**Verificació feta:** `manage.py check` net; la migració només porta `help_chat` i la taula nova; plantilles compilen i el fragment es renderitza escapant l'HTML en ca i es; una **conversa real de dos
torns** amb el servei sobre `okboomer` (3,8 s i 3,5 s, `revisio: aprovada`): el JOEL pregunta com llegir l'any, i al torn 2 fa referència a les regles de l'enunciat sense donar la solució.
**Migració `0167_helpchat` aplicada** (amb l'OK de l'usuari): `ALTER TABLE judge_problemdata ADD COLUMN help_chat bool DEFAULT 0 NOT NULL` i `CREATE TABLE judge_helpchatmessage`. Després, el flux
complet amb el client de Django **dins d'una transacció desfeta** (usuaris temporals; en acabar, 0 missatges, 0 usuaris i l'opció de `okboomer` tornada a «apagat»), amb respostes reals de la IA:
33 comprovacions OK: botó només per a alumnes amb sessió i només amb l'opció activada (anònim → login, problema sense opció → 403); obrir, enviar i resposta; segon missatge mentre n'hi ha un de
pendent, rebutjat; un altre alumne no pot consultar la resposta d'algú altre (404); el torn 2 envia `alumne, joel, alumne` i el payload té només les claus del protocol (sense dades de
l'alumne; `enviament` només amb el llenguatge si no ha enviat res); resposta fallida desada com a `E` amb botó de reintent que **no gasta missatge** i que no deixa fila d'error duplicada a la
conversa enviada; límit de missatges, missatge massa llarg o en blanc rebutjats; una resposta pendent de més de 3 minuts passa a error i desbloqueja el xat; dins d'un concurs no està
disponible; el professorat veu l'enllaç i l'admin de només lectura filtrat per problema, i un alumne no hi accedeix; el camp és a la pàgina de dades de prova; les accions en bloc
funcionen. Sintaxi del JavaScript del panell comprovada amb `node --check` en ca i zh-hans.
**Error trobat per aquestes proves i corregit:** la plantilla dels missatges rebia la variable `messages`, que el processador de context de missatges de Django substituïa pels missatges
flash (buits), i el panell sortia buit; ara es diu `chat_rows`. **No provat:** el panell en un navegador real (només la sintaxi del JS i l'HTML renderitzat).

**Estat:** **en viu des del 3-11-2026.** L'usuari va fer `supervisorctl restart all`, que va reiniciar uWSGI, Celery, el pont dels jutges i el servidor de websockets. Comprovat després: màster
d'uWSGI nou amb 6 workers, Celery amb la tasca `judge.tasks.helpchat.request_help_chat_reply` registrada (`celery inspect registered`), i `https://jo-el.es/`, `/problem/okboomer`, `/problems/` i
`/accounts/register/` responen 200; `/problem/okboomer/chat` redirigeix a l'inici de sessió si no hi ha sessió, i la pàgina del problema no mostra el botó a un visitant. **Pendent:** la primera
prova a mà amb un compte d'alumne al navegador (obrir el panell, escriure, veure la resposta i el botó «Torna-ho a provar»), perquè des del servidor no s'ha pogut provar la interfície. El procés
`uwsgi` vell de fa 11 dies (PID 1743548, vegeu #141) continua sent-hi, amb el web nou llevat dels seus 6 workers: no s'ha tocat.

**Activació (3-11-2026, a petició de l'usuari):** «la meitat dels problemes de les tasques de `marc` d'ifs (la meitat de cada tasca) i els de Primers Passos». Les tasques d'ifs són `ifseasy` (20
problemes) i `ifandor` (18); gairebé tots els seus problemes (37 de 38) ja són al grup «Primers Passos», així que les dues peticions es trepitjaven i s'ha llegit com **la meitat de cada tasca
d'ifs + la resta de «Primers Passos»** (l'altra meitat dels ifs es queda sense xat a propòsit). Meitat de cada tasca: ordenats per punts i `id`, un de cada dos (el 1r, 3r, 5è…), perquè les dues meitats
tinguin dificultat equilibrada: `ifseasy` 10 de 20 (eleccions2020, etsclassealta, movimentcompte, valorabsolut, hihaestoc, okboomer, diferenciagranpetit, descompte100, controlvolum, butlletinotes) i
`ifandor` 9 de 18 (nombrescontigus, buscartrios, capsetmana, entradacinema, fizzbuzz, dosexamens, ordreascendent, torresgemelas, diferenciagranpetit2). Resta de «Primers Passos»: **87** problemes
(públics o privats d'equip); **s'han deixat fora 12 esborranys privats i 3 problemes sense dades de prova**. Total **106 problemes** amb `ProblemData.help_chat = true` (`UPDATE` directe, sense
recompilar res; abans n'hi havia 0). Per desfer-ho: l'acció «Desactiva el xat d'ajuda» de l'admin de problemes. (Visible des que l'usuari va reiniciar uWSGI i Celery, vegeu «Estat».)

### 144. El captcha del registre no es veia i bloquejava tothom: dos errors, corregits amb una clau de v2 «casella»

**Abans:** després d'activar el captcha (#141), l'usuari va avisar que no sortia al registre i que la gent no es podia registrar.

**Causes trobades (dues, i la primera era meva):**
1. **Script mal enllaçat.** `judge/jinja2/social.py::recaptcha_init` renderitzava la plantilla del paquet sense `recaptcha_host`, que `django-recaptcha2` 1.4.1 fa servir per construir la URL; la pàgina demanava
   `https://jo-el.es/recaptcha/api.js` (404) i el widget mai es carregava. **Corregit** (`recaptcha_host` = `RECAPTCHA_PROXY_HOST` o `https://www.google.com`); ara l'script és `https://www.google.com/recaptcha/api.js?hl=ca` (200).
   La meva comprovació de #141 només buscava la subcadena `recaptcha/api.js`, que també encaixava amb la ruta trencada; ara la prova exigeix la URL absoluta de Google.
2. **Les claus no són del tipus que fa servir el formulari.** Provat contra `recaptcha/api2/anchor` de Google (el que demana el navegador): amb la clau de prova oficial es genera el widget (39 KB), però amb la clau de
   l'usuari i `size=normal`/`compact` (casella) Google respon «Invalid input» **per a qualsevol domini** (`jo-el.es`, `www.jo-el.es`, `example.com`…), mentre que amb `size=invisible` la mateixa clau genera el widget
   (39,8 KB) i una clau inventada dona «Invalid input» també; o sigui, la clau existeix però és **reCAPTCHA v3 o v2 invisible**, no «v2 casella de verificació». Cap canvi de codi ho arregla; cal una clau del tipus correcte. (La clau
   secreta sí que és vàlida a `siteverify`.)

**Mesura provisional (decidida per mi, per revertir el que jo havia activat i que bloquejava tothom):** a `dmoj/local_settings.py` s'han **comentat** (no esborrat) les línies `RECAPTCHA_PUBLIC_KEY` i `RECAPTCHA_PRIVATE_KEY`
(còpia prèvia a l'scratchpad de la sessió: `local_settings.before_captcha_off.bak`) i s'ha recarregat uWSGI (`kill -HUP`). Sense claus, el formulari no té camp de captcha ni s'afegeix l'app (comportament d'abans de #141).
Verificat amb el client de Django dins d'una transacció desfeta: `POST /accounts/register/` → 302 a `/accounts/register/complete/` i usuari creat (desfet; no n'ha quedat cap); la pàgina en viu té 0 referències a `recaptcha`; `/`
i `/problem/okboomer` responen 200.

**Resolució (3-11-2026, mateix dia):** l'usuari va crear una clau nova de tipus **reCAPTCHA v2 «Casella de verificació»** per a `jo-el.es`. Abans d'activar-la es va comprovar contra Google: `anchor` amb `size=normal` i
`compact` per a `jo-el.es` genera el widget (39,8 / 39,7 KB), per a `example.com` dona la pàgina d'error (la restricció de domini funciona) i la clau secreta és vàlida a `siteverify` (`invalid-input-response` a un token fals). Les
dues línies noves s'han afegit al final de `dmoj/local_settings.py` (les antigues, de v3/invisible, hi queden comentades) i s'ha recarregat uWSGI (`kill -HUP`). Verificat: el formulari porta `https://www.google.com/recaptcha/api.js?hl=ca` i el widget
amb la clau nova; un `POST` sense captcha resolt es **rebutja** amb error al camp (no es crea cap usuari; prova dins d'una transacció desfeta); la clau que serveix la pàgina en viu genera el widget a Google (39,6 KB) per a `jo-el.es`; `/`, `/problems/`
i `/problem/okboomer` responen 200.

**Estat:** **el captcha és actiu i funcionant al registre des d'aquest moment** (el registre va estar sense captcha, i per tant obert al spam, durant l'estona entre la desactivació i aquesta activació). **No provat:** resoldre el captcha i
completar un registre real des d'un navegador (no es pot automatitzar des del servidor).

### 145. Problema `calorcito` («Calorcito a la C4», id 537): enunciat reescrit en català i en castellà

**Abans:** l'usuari va demanar reescriure l'enunciat d'aquest problema (autor `gsantama`, públic, grup «Aprenentatge», tipus «Sense Bucles», 3 punts), que «no està gaire ben escrit».
Mirat el que veia l'alumne a `https://jo-el.es/problem/calorcito` i els fitxers de prova reals (`/judge/calorcito/coses.zip`), els problemes eren:
- **L'exemple no coincidia amb el format real d'entrada.** L'enunciat posava cada cas en **una sola línia** (`19 27 NO`), però els fitxers de prova (`i1.in`…) tenen **tres línies**, un valor
  per línia (`19\r\n27\r\nNO`). Un alumne que llegeixi tot de la línia amb `input().split()` falla.
- L'exemple era una **taula de Markdown dins d'un bloc de codi**: es veien els `|` en cru i els guionets de la capçalera.
- L'apartat «Entrada» sortia **aixafat en un sol paragraf** (les línies començaven amb tabulador, que Markdown ajunta amb l'anterior), i els tres valors no es distingien.
- La taula de regles tenia `<indiferent>` escrit literalment, una **fila redundant** (la 3 és un cas de la 4) i **no deia l'ordre de prioritat** (només ho insinuava la frase «sempre que es pugui
  s'encendrà l'aire»). La resposta es descrivia amb cometes simples i un **espai de més** (`' Res'`), quan la sortida real és `Res`.
- Llenguatge: «aliviar» (castellanisme), «cas de tenir…», «perquè "s'ha perdut"». La traducció castellana (feta a partir d'aquest text) heretava tot això i deixava «Entrades/Sortides» sense traduir.

**Decisió:** reescriure **només el text**, sense canviar la lògica, les dades de prova ni el to (es manté la broma de «s'allaaaaargi»). Abans d'escriure res es va comprovar per força bruta que la versió
simplificada de la taula (3 files, la primera que es compleixi guanya, si no `Res`) dona **exactament la mateixa resposta que la taula original llegida literalment** per a les 31 × 43 × 2 = **2.666
entrades possibles** (0 diferències; surten `Res` 1.674, `Aire` 572, `Obrir Finestra` 420) i que els 5 casos de prova del jutge hi donen la sortida esperada.

**Canvis fets (a la base de dades, no al codi):**
- `Problem.description` de `calorcito` (català): entrada com a **llista numerada de tres línies** (alumnes, temperatura, comandament `SI`/`NO`); sortida amb les **tres respostes literals en codi**
  (`Aire`, `Obrir Finestra`, `Res`) i la nota que es posen en una sola línia i amb les majúscules exactes; **taula de 3 files** amb la regla explícita «de dalt a baix, s'aplica la primera fila que es
  compleixi» i «si no es compleix cap, `Res`»; exemples en **taula HTML amb `<br>`** per als tres valors de cada cas (el mateix format que els problemes de «Sense Bucles» més nous, com `dosexamens`). Títol, imatge i la resta de dades del problema, **sense tocar**.
- `ProblemTranslation` `es` de `calorcito` (ja existia): **actualitzada** amb la traducció del text nou, perquè no quedés una versió castellana que contradigués la catalana. Regles de sempre: les
  respostes (`Aire`, `Obrir Finestra`, `Res`) i `SI`/`NO` **no es tradueixen** (són el que ha de sortir), la imatge (`<img>`, `alt` inclòs) queda igual, els encapçalaments sí que es tradueixen.
- Com que desar una `ProblemTranslation` **no** dispara el senyal, es va cridar `judge.signals.problem_update` a mà (esborra el fragment `problem_html` de cada idioma i els PDF).
- **Còpia de seguretat del text antic** (català i castellà) a l'scratchpad de la sessió: `/tmp/claude-1000/-home-ubuntu-educational-online-judge/cd698187-925c-4db8-8d59-947b7aac962a/scratchpad/calorcito_ca.OLD.md`
  i `.../calorcito_es.OLD.md` (el text nou és a `calorcito_ca.md` i `calorcito_es.md`, al mateix lloc). Aquesta carpeta és temporal; si es vol conservar, cal copiar-ho.

**Resultat:** verificat a la pàgina en viu (`curl` a `https://jo-el.es/problem/calorcito`, en català i en castellà): 200 en tots dos, 2 taules reals, 1 llista numerada i 1 de punts, **0 `|` crus, 0 blocs
`<pre>`**, text llegible de dalt a baix. No s'ha tocat el codi ni cal recarregar uwsgi. **No provat:** cap enviament nou (les dades de prova no han canviat, i el que s'ha canviat és només el text).

**Observacions fora de l'abast, no tocades i apuntades al `TODO.md` (#19):** la imatge és un **alfil d'escacs** (`Alfil.png`) carregat d'un Google Sites extern (res a veure amb l'aire condicionat; si aquell
lloc la treu es trenca); a `init.yml` els casos `i2` i `i4` valen **0 punts** (només puntuen 3 de 5); i els 5 casos són **exactament els 5 exemples** de l'enunciat, sense cap cas de frontera
(15/16 alumnes, 18/19, 22/23 i 25/26 graus, ni `NO` amb més de 25 graus i pocs alumnes).

### 146. Tasca nova `altchallenge` («02 07 Alternatives: Challenge Mode»): 35 problemes de «Sense Bucles» de més d'1 punt que no són a cap tasca d'alternatives de marc

**Abans:** l'usuari va demanar una tasca «02 07 Alternatives: Challenge Mode» amb problemes (1) de la categoria «Sense Bucles», (2) que no estiguin a cap de les altres tasques d'alternatives de marc i (3) de **més d'1.0 punts**.

**Com s'ha interpretat cada criteri (comprovat a la base de dades, no suposat):**
- «Categoria Sense Bucles» = el **tipus** `Sense Bucles` (`ProblemType` id 2, 158 problemes), no el grup (el grup és «Primers Passos», «Introduccio»…).
- «Altres tasques d'alternatives de marc» = les 5 tasques amb autor `marc` i «Alternatives» al nom: `ifseasy` (02 01), `ifandor` (02 03), `problemeswitchs` (02 04), `modulsihores` (02 05) i `primerexamen` (02 06); en total 49 problemes
  exclosos. **`altercal`** («02 01 Alternatives Calamot») és de `mfontana`, no de marc, i per això **no** s'ha exclòs: el problema `sumaunsegon` és a `altercal` i s'ha inclòs igualment.
- «Més d'1.0 punts» = `points > 1.0` estricte (res de 1.0; també queden fora els 1.5 perquè tots són privats, vegeu sota).

**Decisió que no era literal (decidida per mi):** aplicant només els tres criteris sortien **70** problemes, però **34 no són públics (17 dels quals privats d'organització)** i un més (`irpf`) és públic però privat d'organització (exàmens IPED RA123 de les organitzacions
`pedralbes-dam1-25-26`, exàmens ITB, problemes d'alumnes…). La plantilla `problem/task.html` mostra el **nom i l'enllaç de tots els problemes de la tasca a tothom** (els no públics només amb un cadenat), així que posar-los
a la tasca n'hauria **filtrat els títols** (i d'exàmens en curs), i els alumnes no els podrien obrir. A més, només 2 de les 53 tasques de marc tenen algun problema no públic. Per això només hi ha els problemes
**públics i no privats d'organització: 35** (36 públics, menys `irpf`, id 975, que és públic però privat de l'organització `pedralbes-dam1-25-26`). Si es volen afegir els privats, és un canvi d'una línia, però cal pensar-hi.

**Canvis fets (a la base de dades, no al codi):**
- `ProblemTask` id **203**: codi `altchallenge`, nom «02 07 Alternatives: Challenge Mode», autor `marc` (com la resta de tasques d'alternatives), 35 problemes (ids 29, 31, 188, 218, 219, 319, 322, 324, 424, 425, 427, 429, 430, 431, 436, 438, 439,
  440, 441, 474, 487, 520, 530, 531, 532, 625, 662, 663, 664, 672, 673, 884, 924, 986, 1041), de **2 a 6 punts** (rang real: 2.0–6.0). Creada en una sola transacció, després de validar el text.
- `about` en català (3 paràgrafs, sense llistes ni capçaleres, com les altres tasques de marc: què és, objectiu i errors típics) i `ProblemTaskTranslation` `es` amb la traducció. Validat mecànicament abans de desar: 3 paràgrafs,
  mateixos accents greus (`` ` ``) i mateixos títols entre `*…*` a les dues versions, i **tots els títols citats existeixen a la tasca**. No s'ha escrit cap altre idioma (en/de/zh-hans veuen el text català, com a la resta).

**Resultat:** verificat a la pàgina en viu: `https://jo-el.es/tasks/altchallenge` respon **200**, amb 35 enllaços a problemes, **0 cadenats**, el nom correcte i el text en català o en castellà segons l'idioma; i la tasca surt a `/tasks/`.
No s'ha tocat el codi ni cal recarregar uwsgi ni migrar. **No provat:** com es veu amb una sessió iniciada (progrés dels problemes ja resolts) ni a la vista de móbil; la plantilla és la mateixa que la de la resta de tasques.

### 147. Imatges dels enunciats: 537 imatges copiades al servidor, reduïdes i servides internament; arreglades les trencades que s'han pogut recuperar

**Abans:** a `calorcito` (#145) la imatge estava trencada (l'URL de Google Sites ja no la serveix) i l'usuari va demanar mirar **totes** les imatges dels problemes, arreglar les trencades i, de pas, descarregar-les i servir-les
internament, **reduïdes** («no cal alta resolució: ja els fixem una mida màxima»). Cens (només lectura) de problemes + traduccions: **1.254 referències** (`<img src>` i `![](…)`; 746 als enunciats, 502 a la traducció `es`, 4 `en`, 2 `ca`)
a **662 URL úniques** de desenes de dominis (Dropbox 185, imgur 119, ibb 91, postimg 68, Wikimedia 35…). Mides mostrades: gairebé sempre l'atribut `width` (200 en 546 etiquetes, 300 en 239, 250, 400…).
Comprovació de les 662 (com la veuria un alumne: navegador + `Referer: https://jo-el.es/`): **450 vives**, 2 només sense `Referer`, **210 «mortes»**; però unes 108 d'aquestes eren falsos negatius meus (imgur responia `429` perquè la comprovació en paral·lel el va saturar, `ibb`
feia timeouts) i es van reintentar amb ritme lent.

**Troballa important (no tocada, decideix l'usuari):** `MEDIA_ROOT` és `/tmp/media` i **`/tmp` s'esborra a cada arrencada** (`systemd-tmpfiles-setup.service` amb `--remove --boot`, regla `D /tmp`); la còpia nocturna (`rclone-backup/upload.sh`) només puja els volcats
de la BD (`/var/backup/db`), **no `/tmp/media`**. Les pujades de martor, les imatges d'instituts, d'achievements i d'organitzacions viuen només allà. El servidor porta engegat des del 2026-07-08, així que encara no s'ha notat. Per això **les imatges noves no hi viuen**:
són a una carpeta persistent i `/tmp/media` només té un enllaç (vegeu avall).

**Canvis fets (carpeta, base de dades i enllaç; cap canvi de codi de l'aplicació ni de nginx):**
- **Carpeta persistent** `/home/ubuntu/joel-media/problem-images/`: **537 fitxers, 32,4 MB** (els originals pesaven 118,3 MB). Nom = hash SHA-256 del contingut (immutable; nginx serveix `/media` amb `expires max`). Cada fitxer l'ha **recodificat PIL** (neteja EXIF/ICC i qualsevol
  cosa estranya del contenidor; només s'accepten JPEG/PNG/GIF/WebP/BMP que PIL descodifica), mai s'amplia, i la caixa és **2× l'ample mostrat** (el màxim entre totes les etiquetes que fan servir aquell URL; si alguna no té `width`, 800 px de costat llarg; límit 1000).
  JPEG → JPEG (q85, progressiu); PNG amb transparència → PNG; PNG fotogràfic de més de 250 KB → JPEG si pesa menys del 60 %. Els 5 GIF animats es conserven tal qual (≤ 3 MB). Manifest `…/problem-images-manifest.json` (URL original → fitxer, mides, origen).
- **Enllaç** `/tmp/media/problem-images → /home/ubuntu/joel-media/problem-images` (`ln -s`; nginx el segueix, `location /media`, `root /tmp`). Verificat per HTTPS real: **els 537 fitxers responen 200 amb `Content-Type: image/*`**. **Després d'un reinici cal refer-lo**: `mkdir -p /tmp/media && ln -s /home/ubuntu/joel-media/problem-images /tmp/media/problem-images`. **[Substituït per l'entrada #148: ara tot `/tmp/media` és un enllaç a `/home/ubuntu/joel-media/media` (que conté l'enllaç `problem-images`) i el crontab el refà sol; aquesta instrucció ja no cal.]**
- **Origen de les còpies:** 494 directes, **36 de l'arxiu d'Internet** (`web.archive.org/web/2id_/<url>`, imatges mortes que hi tenien còpia), **7 de Wikimedia Commons** (substituts, vegeu avall).
  Cloudinary (3) es va demanar com a PNG en lloc d'SVG/AVIF; les miniatures de Wikimedia amb mida no estàndard (`400px`, `1200px`…, `400 Bad Request`) es van demanar en una mida estàndard (250/330/500/960/1280); una fórmula `render/svg` → `render/png`.
- **Reescriptura dels enunciats** (`rewrite_images.py`, després d'una simulació): **968 textos** (573 `Problem.description` + 395 `ProblemTranslation.description`), **1.016 imatges** apunten ara a `https://jo-el.es/media/problem-images/<hash>.<ext>` (URL **absoluta**: el PDF dels problemes es renderitza com a `file://`,
  com ja diu `raw.html`). Només canvia l'URL de la imatge: comprovat comparant tots els textos antics i nous amb els URL emmascarats (**0 diferències** fora d'URL). Actualització condicional (`WHERE description = <text antic>`) dins d'una transacció, i `judge.signals.problem_update`
  als 573 problemes (fragments `problem_html` de cada idioma i PDF). **Còpia dels textos antics:** `/home/ubuntu/joel-media/backup-descriptions-20261103-190531.json` (1,9 MB, `kind`/`pk`/`code`/`old`), persistent.
- **`calorcito`:** l'alfil d'escacs (que tampoc hi pintava res) s'ha substituït per una foto d'una unitat d'aire condicionat, **CC0**, de Commons («Aire acondicionado en México (Dominio Público).jpg»). Les entrades de substitució per problema van fer falta perquè **el problema `alfil`
  (escacs) fa servir exactament el mateix URL**, amb l'`alt="aireacondicionat"` copiat de `calorcito`: `alfil` conserva l'alfil (recuperat de l'arxiu, 332×332) i només `calorcito` rep el d'aire (clau `override:calorcito:<url>` al manifest). L'`alt` d'`alfil` continua dient «aireacondicionat» (no tocat).
- **Casino (`example.com/…`, marcadors de posició que mai han existit; 8 problemes públics de `marc`):** substituts **només CC0 / domini públic** de Commons (les CC BY-SA demanen atribució): `roulette.jpg` → postal «Playing roulette, Las Vegas» (`apostesperdudes`, `apostesperdudes0`),
  `roulette-odd.jpg` → «Roulette-Tisch» (`apostesenars`), `casino-chips.jpg` → «Poker chips 2» (`casino1`), `poker-chips.jpg` → «Pile of Poker Chips» (`casinomult`), `blackjack.jpg` → «Blackjack game 2» (`casinoplaces`), `dice.jpg` → «Wuerfel5» (`tiradesperf`).
  **Falta `lucky-player.jpg` (`casinosort`)**: el candidat és «Casino Bar Bar Bar.jpg» (CC0, màquina escurabutxaques), però `upload.wikimedia.org` em retorna `429` per a aquest fitxer (hi vaig abusar del ritme); pendent de repetir.
- **`botwhatsapp`** (privat, autor `ajite6`): tenia un `<img ` penjat enmig d'una frase («demanant<img \r\napunts…») que feia que el navegador s'empassés ~520 caràcters de l'enunciat fins al primer `>`. Era l'única etiqueta `<img` sense `src` de tot el cens. S'ha tret aquest `<img ` (queda «demanant apunts, resums…»; el text antic és a
  `/home/ubuntu/joel-media/backup-botwhatsapp-20261103.json`).
- **Scripts** desats al repo: `tools/mirror_problem_images/` (`1_survey` … `5_rewrite_images`, amb `README.md`), perquè no es perdin com l'altra vegada.

**No s'ha fet / limitacions (veure `TODO.md` #20):**
- **imgur: 60 URL (65 problemes, 53 públics) continuen externes.** Després de ~180 peticions seguides, `i.imgur.com` retorna `429` (amb `retry-after: 0`, també per a fitxers inexistents) a aquest servidor, i no s'ha aixecat en una hora. **No sé si aquestes imatges es veuen o no als alumnes** (només que el servidor no hi arriba).
- **62 URL (67 problemes, 40 públics) segueixen trencades i sense còpia enlloc** (404, domini mort, `403` de WAF/Cloudflare, certificat invàlid…). No s'han tret ni substituït: cal decidir què es vol fer (vegeu `TODO.md`).
- **Certificats defectuosos:** 11 URL fallaven per TLS (nom que no coincideix, autosignat, caducat); per a algunes l'arxiu d'Internet tenia còpia, per a **6 no**. Baixar-les hauria exigit desactivar la verificació de certificats (`curl -k`); el sistema ho va **bloquejar** i no ho he reintentat ni rodejat.
  Aquestes 6 ja es veuen trencades als navegadors dels alumnes.
- Només enunciats i traduccions de problemes: **no** s'han mirat les imatges del blog, de les pàgines estàtiques, dels comentaris ni dels textos de les tasques (`about`: cap `<img>`).
- Llista completa de tot el que queda: `/home/ubuntu/joel-media/imatges_pendents.tsv` (categoria, URL, problemes; `*` = públic).
- **Llicències:** les còpies d'imatges de tercers (Google Images, Pinterest, premsa…) ara s'allotgen al nostre servidor en lloc d'enllaçar-les; és una decisió de l'usuari, no l'he valorada. Les que he triat jo són totes CC0 o domini públic.

### 148. Les imatges pujades (`/tmp/media`) ja no es perden en reiniciar: contingut mogut a `/home/ubuntu/joel-media/media` i `/tmp/media` convertit en enllaç, i línia `@reboot` al crontab que el refà sol

**Abans:** `MEDIA_ROOT = /tmp/media` i `/tmp` s'esborra a cada arrencada (`systemd-tmpfiles-setup.service` amb `--create --remove --boot`; regla `D /tmp` de `/usr/lib/tmpfiles.d/tmp.conf`; cap exclusió per a `/tmp/media` a `/usr/lib/tmpfiles.d` ni
`/etc/tmpfiles.d`). Comprovat que el mecanisme actua en aquest servidor: `/tmp/.ICE-unix` es va crear el 2026-07-08 19:00:13, sis segons després de l'arrencada (19:00:07). `/tmp/media` és del 21 d'octubre, o sigui que **mai no havia passat per cap reinici**.
Contingut: `achievements` 261 fitxers (139 MB), `institutions` 40 (3 MB), `organizations` 100 (7,4 MB), `martor` 3 (112 KB), i l'enllaç `problem-images` (#147). `/tmp` és al disc arrel (ext4), no és tmpfs. Cap còpia de seguretat ho cobria:
el cron d'`ubuntu` només puja els volcats de la BD (`/var/backup/db`) i a `/etc/cron.d` i `/etc/cron.daily` no hi ha res d'això; el crontab de root no s'ha pogut llegir (`sudo` demana contrasenya). És una conclusió a partir de la configuració: no s'ha reiniciat res per comprovar-ho.
L'usuari va preguntar si en reiniciar es perdrien les fotos d'instituts i grups, se li va respondre que sí, i va dir «si» a la solució proposada (moure + enllaç + línia `@reboot`).

**Canvis fets:**
- **Còpia de seguretat prèvia** (`cp -a`, sense moure ni esborrar): `/home/ubuntu/joel-media/media-backup-20261103/` amb `achievements`, `institutions`, `organizations` i `martor`; `diff -rq` amb l'original: **idèntic** en les quatre. No s'ha esborrat ni la còpia ni res; queda de seguretat i es pot treure quan l'usuari vulgui.
- **`mv /tmp/media /home/ubuntu/joel-media/media`** (mateix disc: canvi de nom instantani, comprovat amb `stat -c %d`) i **`ln -s /home/ubuntu/joel-media/media /tmp/media`**, amb guardes (que `/tmp/media` fos una carpeta real i que la destinació no existís). Finestra sense `/media`: uns mil·lisegons.
  Dins hi segueix l'enllaç `problem-images -> /home/ubuntu/joel-media/problem-images` (#147), que continua resolent.
- **No s'ha tocat** `MEDIA_ROOT`, `local_settings.py`, nginx ni uwsgi (el camí que veuen és el mateix; no cal recarregar res).

**Verificat:** per HTTPS real, un fitxer de cada carpeta respon **200** (`achievements` `image/jpeg`, `institutions` `application/octet-stream` —és un `.jfif` i nginx no el coneix; observat, no investigat ni relacionat amb aquest canvi—, `organizations` `image/jpeg`,
`martor` `image/png`, `problem-images` `image/png`); `test -w` confirma que es pot escriure a les quatre carpetes a través de l'enllaç (no s'ha creat cap fitxer de prova); `/` i `/problem/calorcito` responen 200.

**Línia `@reboot` al crontab d'`ubuntu` (feta, amb una incidència):** la línia `@reboot [ -e /tmp/media ] || ln -s /home/ubuntu/joel-media/media /tmp/media` refà l'enllaç després de cada arrencada (`systemd-tmpfiles` buida `/tmp` abans que cron arrenqui; ja hi havia un altre `@reboot`).
- **Primer intent: bloquejat.** El sistema (classificador del mode automàtic) va denegar l'edició del crontab («Unauthorized Persistence») tot i el «si» de l'usuari a la proposta global; no s'ha rodejat i el crontab va quedar intacte.
- **Segon intent: acceptat.** L'usuari va demanar explícitament que el crontab el fes jo mateix, i aleshores l'ordre va passar. Còpia prèvia del crontab: `/home/ubuntu/joel-media/crontab-abans-20261103.txt` (2 línies). Crontab ara: la còpia de rclone a les 01:30, el `@reboot` del `mariadb-grader` i la línia nova (3 línies).
- L'ordre es va provar a una carpeta de proves de l'scratchpad (`…/scratchpad/prova_reboot/media_enllac`, hi queda el resultat): crea l'enllaç si no existeix i no fa res ni dona error si ja hi és. **No provat amb un reinici real** (no s'ha reiniciat el servidor).
- **Cas límit conegut:** si algú puja un fitxer abans que el cron refaci l'enllaç, Django crea una carpeta `/tmp/media` real i la guarda `[ -e /tmp/media ]` fa que l'enllaç no es refaci; cal moure'n el contingut a `/home/ubuntu/joel-media/media` i fer l'enllaç a mà. Als pocs segons d'arrencar és molt improbable.
- Si es vol una solució sense l'enllaç (cal `sudo`, que demana contrasenya): `MEDIA_ROOT` i el `location /media` de nginx apuntant directament a `/home/ubuntu/joel-media/media`.

### 149. El botó «Rate LLIGA» no esborrava el rànquing de la lliga: la petició moria pel *harakiri* d'uwsgi (502). `rate_lliga` reescrit amb consultes agregades (codi canviat; pendent de recarregar uwsgi)

**Abans:** un professor (Pedralbes) va escriure que, després de treure el check de Primera/Segona divisió als concursos de l'any passat i tornar a prémer «Rate LLIGA», la classificació antiga continuava allà.
**Diagnòstic (tot en només lectura):**
- Els 38 concursos `lliga1div…`/`lliga2div…` acabats (2024-25 i 2025-26; n'hi ha 40 amb clau `lliga…` en total) ja tenen `is_primera=False` i `is_segona=False`; només `lliga2div2627j1` (id 103, segona) i `lliga1div2627j1` (id 104, primera) tenen el check (i són del 13-20 de novembre, encara no acabats).
  Tot i això, els perfils conservaven els punts antics: **99 perfils amb `lliga_primera_points > 0` i 180 amb `lliga_segona_points > 0`** (p. ex. `lmg` 233, `a25guerodmar` 167).
- `/var/log/nginx/access.log`: `GET /admin/judge/contest/103/ratelliga/` → **502** el 2026-11-04 a les 06:31:45 UTC. A `/tmp/site.stderr.log`: `HARAKIRI ON WORKER 6 … GET /admin/judge/contest/103/ratelliga/` i `worker 6 died, killed by signal 9`.
  O sigui que no era cap oblit de l'usuari: la petició s'executava, uwsgi la matava als 30 s (`harakiri = 30` a `uwsgi.ini`), i com que anava dins un `transaction.atomic()` **es desfeia tot** i no es guardava ni un sol perfil.
- Causa: `Contest.rate_lliga()` recorria **tots els 7.766 perfils** i per a cadascun feia `calculate_points_segona()` + `calculate_points_primera()` (cadascun amb una consulta amb subconsulta correlacionada i un `UPDATE`), uns 31.000 viatges a la BD en una sola petició web.
- Aclariment: el botó només surt al formulari d'un concurs que tingui el check de Primera o Segona (plantilla `templates/admin/judge/contest/change_form.html`) i només funciona si el concurs és `is_rated`; per això s'ha de prémer des d'un concurs actual (com el 103/104) i no des dels de l'any passat, on ja no apareix.

**Canvis fets (`judge/models/contest.py`):**
- Nou `Contest.lliga_points()` (mètode estàtic): per a cada divisió, **una consulta agregada** (`values('user_id','contest_id').annotate(Max('score'))`) sobre les participacions dels concursos **acabats** marcats com a primera/segona; suma, per usuari, la millor puntuació de cada concurs. Mateixa semàntica que els antics `Profile.calculate_points_primera/segona` (inclou totes les participacions, també les virtuals; no s'ha canviat).
- `Contest.rate_lliga(dry_run=False)` reescrit: carrega els perfils amb `.only('id', camps)`, compara amb el valor nou i fa **un sol `bulk_update`** (lots de 500) només dels perfils que canvien. Amb `dry_run=True` no guarda res. Retorna quants perfils canvien.
- `Max` afegit a l'import de `django.db.models`.
- **No s'ha tocat** `Profile.calculate_points_primera/segona` (queden sense ús però intactes) ni el bloc de codi comentat de la versió antiga de `rate_lliga`, ni la vista `rate_lliga_view`, ni la plantilla, ni `uwsgi.ini` (no s'ha pujat el límit del harakiri). No cal migració. `bulk_update` no dispara el senyal `post_save` de `Profile`, i el que aquest senyal esborra (la caché `user_about` i el comptador de membres de l'organització) no depèn dels punts de la lliga.

**Verificat (sense escriure res a la BD):**
- `rate_lliga(dry_run=True)` des d'un shell de Django: **234 perfils canviarien** (99 de primera i 180 de segona, amb solapament) i triga **0,13 s** (abans passava de 30 s).
- Equivalència amb la lògica antiga: simulant el check amb la clau del concurs (`lliga1…`, acabats), el nou agregat i l'antiga subconsulta per usuari donen el mateix resultat en els **397 usuaris** amb punts: 0 diferències.
- Avui `lliga_points()` dona 0 usuaris a les dues divisions (cap concurs acabat amb el check), així que en prémer el botó els rànquings es buidaran fins que acabi la primera jornada.

**uwsgi recarregat (2026-11-04, ~06:45 UTC, a petició de l'usuari):** `kill -HUP $(cat /home/ubuntu/dmoj-site.pid)` (reload gracios del màster, pid 3412377; no es va usar `supervisorctl restart all` per no tocar bridge, celery ni jutges). Tots els workers antics (inclòs el 6, que havia mort pel harakiri) es van substituir per 6 de nous (pids 3481237-3481242). Comprovat: `/` 200, `/contests/` 200, `/users/primera` 200, `/users/segona` 200 i el log d'uwsgi mostra peticions servides pels workers nous. El botó «Rate LLIGA» no s'ha provat de debò.
**Pendent:** prémer «Rate LLIGA» des del concurs 103 o 104 (el farà el professor o l'usuari); això escriurà a la BD i buidarà els 99 + 180 perfils amb punts antics. No he executat el recàlcul real ni he tocat cap punt de cap perfil.
**Observació relacionada (no canviada):** les participacions **virtuals** compten per a la lliga (a les lligues passades hi ha 28 parelles usuari/concurs on només una participació virtual dona la millor puntuació, i 155 participacions virtuals en total); és el comportament que ja hi havia. Vegeu també el cas dels enviaments després del final als concursos (virtuals), que s'ha explicat a l'usuari però no s'ha canviat res.

### 150. Substituts CC0 / domini públic per a les imatges trencades dels problemes públics (41 problemes), amb dos diagrames dibuixats (`cavallino`, `taulacremadaeasy`)

**Abans:** després de l'entrada #147 quedaven 62 URL trencades sense còpia, 40 de les quals en problemes «públics» (`is_public`). L'usuari va demanar «busca substituts CC0 per als 40 públics». Eren **41 parelles problema/URL** (37 URL; quatre URL compartides per dos problemes).
Cap imatge de les trencades es podia recuperar de l'arxiu d'Internet (per això eren a la llista).

**Com s'ha fet:**
- **Cerca a Wikimedia Commons** (API; capçalera `User-Agent` genèrica `JOEL-image-mirror/1.0`, una petició cada vegada amb pauses, miniatures de 500 px) **només amb llicència CC0 o domini públic**: les CC BY / CC BY-SA demanen atribució i no es poden posar sense. 35 grups de cerca + 3 d'addicionals
  (`moda`, `natació`, `compres`, que no tenien cap candidat bo). La sessió es va aturar a mitges (25 de 35 grups) i es va **reprendre** des del `meta.json` desat, sense repetir res.
- **Revisió visual de TOTES les candidates** amb fulls de contactes abans de triar (és la web d'un institut). Criteris: del tema de l'enunciat (els originals eren sovint material amb drets: Zipi i Zape, Mickey, Phineas i Ferb, Pokémon, Doctor Who, el Dakar… → s'ha buscat un substitut **genèric del tema**, no el personatge),
  **cap persona real identificable** (descartats un selfie i uns fotogrames de militars), res cruent (descartada una pintura de Kittelsen amb sang; es va triar el «Skogtroll»), sense logotips quan hi havia alternativa.
- **Resultat: 41 imatges, 16 CC0, 23 «Public domain» de Commons** (equivalent a la pràctica però **no formalment CC0**) **i 2 dibuixades per mi**. Llicència, origen i pàgina de Commons de cadascuna: `/home/ubuntu/joel-media/substituts_cc0.tsv`.
- **Dos diagrames propis** (dibuixats amb PIL; són obra meva, sense drets): (1) **`cavallino`**: l'enunciat diu «es mou segons indica la imatge» i cap candidat mostrava moviments → tauler 8×8, cavall a d4 i les 8 caselles on pot anar (comprovades: c6, e6, b5, f5, b3, f3, c2, e2);
  (2) **`taulacremadaeasy`**: el que faltava era el diagrama de l'**«Explicació de l'Exemple» 2**, que una foto qualsevol no pot substituir. Regla deduïda del diagrama conservat de l'exemple 1 (el triangle `(fila, columna)` apunta amunt si `fila+columna` és parell; veïns: mateixa fila i columna ±1, i vertical només si el de dalt apunta amunt),
  perímetre calculat per arestes que apareixen una sola vegada = **9 per a l'exemple 1 i 11 per al 2, iguals que les sortides de l'enunciat**; mateix estil i escala que el de l'exemple 1 (cremats en negre, cinta groga).
- **Allotjament** com a l'entrada #147 (reduïdes, nom per hash, manifest) però amb claus **`override:<codi del problema>:<url>`**, només per al problema concret (`casinosort` usa l'URL perquè era un marcador de posició). 37 fitxers nous (578 entrades al manifest, 34,8 MB); els 37 responen 200 `image/*`.
- **Reescriptura** amb `tools/mirror_problem_images/5_rewrite_images.py`: **79 textos (41 enunciats + 38 traduccions `es`), 79 imatges, 41 problemes**; còpia dels textos antics a `/home/ubuntu/joel-media/backup-descriptions-20261104-071146.json`; només canvia l'URL (comparats tots amb els URL emmascarats: **0 diferències**); memòria cau netejada als 41.

**Verificat:** 79 pàgines reals (41 en català + 38 en castellà): **75 responen 200**, amb les imatges noves carregant (0 trencades) i cap URL antiga (`example.com`, `sites.google`); **4 donen 404 a un visitant anònim**: `anysiguals`, `iedammp3uf1p42324` i `keypaddesordenat` (ca i es). Són
**privats d'organització** (`is_organization_private=True`; ja ho eren, no és una regressió), de manera que **no s'ha pogut veure la seva pàgina renderitzada** (cal sessió), només s'han verificat els textos a la BD. Així, dels 41 problemes, **38 són públics de veritat** i 3 són privats d'organització.

**Limitacions (importants):**
- **Els substituts són decoratius i temàtics, NO les imatges originals** (no es podien recuperar). On l'original podia ser informatiu i no hi ha recuperació —`keypaddesordenat` (ara un teclat numèric genèric) i `quadratpeo` (ara un tauler d'escacs amb peces)— convé que ho miri l'autor; el text no l'he tocat.
- L'`alt` copiat de `calorcito` («aireacondicionat») continua a unes vint imatges d'altres problemes; no s'ha tocat.
- **Pendent, sense tocar** (no es va demanar): **60 URL d'imgur** (65 problemes: 53 públics, 12 privats; el servidor en rep `429`), **2 URL vives que no s'han pogut copiar** (AVIF) i **26 URL trencades que queden, totes en problemes privats (27)**. Llista regenerada a `/home/ubuntu/joel-media/imatges_pendents.tsv`
  (la d'abans: `…/scratchpad/imatges_pendents.ABANS-20261104.tsv`). **Ja no queda cap imatge trencada en un problema públic.**

### 151. Alta de la professora `rosa_rosae` (IES El Cañaveral, Móstoles, Madrid): institut nou, 4 equips tancats i permisos de professora i responsable d'institut

**Abans:** l'usuari va reenviar un correu de Rosa María Doblas Rastrollo, professora d'Informàtica i Comunicacions de l'**IES El Cañaveral** (Móstoles, Madrid), que demanava ser donada d'alta com a professora i responsable del seu institut. El correu seguia exactament el procediment de la guia pública (`/guiaprofes/`, apartat 1): acreditació (foto del carnet del centre), nom de l'institut i logo (png i jpg, 90×17, dins l'espai 90×40), els grups que vol crear i si són oberts o tancats, i el compromís de no fer servir l'accés als casos de prova i a les solucions per adulterar cap concurs. Demanava **quatre grups tancats** («on jo controli qui entra»): **1º DAM, 1º DAW** (Java) i **2º SMR, 1º ASIR** (optativa de Python). L'usuari va indicar el nom d'usuari: `rosa_rosae`. El compte ja existia (id d'usuari 27337, perfil 27317, registrat el 2026-11-04 08:13 UTC amb correu del domini `educa.madrid.org`; el domini és el de la Comunitat de Madrid, coherent amb el que explica). No tenia grups, ni `is_staff`, ni cap equip.

**Decisió** (sense preguntar res a l'usuari: és el procediment habitual i tot és additiu i reversible; el patró és el dels professors donats d'alta els últims dies, com `esorita`, `jdorado` o `CarlosSanchis`):
1. **Institut nou** `Institution` id **43**, «IES El Cañaveral» (slug `ies-el-canaveral`, nom curt «El Cañaveral»). **Sense logo** (vegeu «Pendent»).
2. **4 equips (`Organization`) tancats** (`is_open=False`, sense `slots` ni `access_code`, de manera que els alumnes han de sol·licitar-ho i ella accepta o rebutja cada sol·licitud a «Veure les sol·licituds»), tots a l'institut 43, amb `rosa_rosae` de `registrant` i d'`admins`:
   | id | nom | nom curt | slug |
   |---|---|---|---|
   | 205 | IES El Cañaveral - 1º DAM | Cañaveral 1DAM | `ies-el-canaveral-1o-dam` |
   | 206 | IES El Cañaveral - 1º DAW | Cañaveral 1DAW | `ies-el-canaveral-1o-daw` |
   | 207 | IES El Cañaveral - 2º SMR | Cañaveral 2SMR | `ies-el-canaveral-2o-smr` |
   | 208 | IES El Cañaveral - 1º ASIR | Cañaveral 1ASIR | `ies-el-canaveral-1o-asir` |
   Els noms segueixen les seves paraules, sense el curs (com «Baix Camp - 1r DAM»); ella els pot canviar. Descripció en castellà: «Grupo X del IES El Cañaveral (Móstoles, Madrid). Grupo cerrado: la profesora acepta cada solicitud.».
3. **`rosa_rosae` és també membre dels 4 equips.** No és un detall menor: des de l'entrada #59, el responsable d'institut es reconeix per **pertànyer** a un equip de l'institut (`Profile.administered_institution_ids`), no per ser-ne admin; sense ser-ne membre no podria editar els comptes del seu alumnat. La majoria de professors són membres dels seus equips (`fletxa`, `InformaticFP`, `SandraV`, `rafacuest`…). Contrapartida: ella compta com a membre en els rànquings dels quatre equips.
4. **Permisos:** grups **«Profe»** i **«Responsable d'Institut»** i **`is_staff=True`** (necessari per entrar a l'admin; ho són els 10 responsables d'institut donats d'alta més recentment). **No** s'han afegit «creador de problemes Jr/Sr», «Editor d'alumnes» ni «Creador de concursos»: no els va demanar i alguns tenen esborrat (`delete_user`) o accés a tots els problemes privats; es poden afegir en un moment si els vol.

**Per què:** petició explícita de l'usuari (correu reenviat + nom d'usuari). S'ha fet amb una sola transacció (`transaction.atomic`) des d'un script de Django (`manage.py shell`), no amb canvis de codi: **cap fitxer de codi, plantilla, traducció ni migració tocat**, només dades. No s'ha reiniciat res.

**Resultat (verificat):** `/institution/43-ies-el-canaveral`, `/institutions/`, `/organization/205-ies-el-canaveral-1o-dam` i `/organizations/` responen **200**. Amb el mateix codi que fa servir l'admin (`OrganizationAdmin.get_queryset` / `has_change_permission`, sobre una petició simulada, sense crear cap sessió): `rosa_rosae` veu **exactament els equips 205–208** i pot editar el 205, però **no** el d'un altre institut (id 3, Institut Club de Fans de Kernel). Té `judge.organization_admin` i `judge.view_all_submission`.

**Pendent / limitacions:**
- **Els adjunts del correu (foto del carnet i logos) no són al servidor**, així que **no he vist l'acreditació** (només el domini `educa.madrid.org` del correu amb què es va registrar) i **l'institut i els equips no tenen imatge**. Cal pujar el logo a mà des de l'admin (`Institucions → IES El Cañaveral`, camp «imatge»; i, si es vol, el logo de cada equip). Recordatori de la mida: l'institut es mostra com a màxim a 80×40 px i l'equip a 100×40 px (entrada #44); ella en va enviar un de 90×17.
- Cal respondre-li (no ho he fet; no tinc cap correu enviat ni esborrany).
- Observació menor, **no canviada**: `Profile.administered_institution_ids` retorna l'id de l'institut repetit (`[43, 43, 43, 43]`) perquè el `.distinct()` s'aplica sobre una consulta ordenada per `Organization.Meta.ordering = ['name']`. Només es fa servir amb `__in`, així que no afecta cap resultat.

**Afegit després (2026-11-04, a petició de l'usuari: «donali creador de problemes»):** `rosa_rosae` també és al grup **«creador de problemes Jr»**. L'usuari no va dir Jr ni Sr; he triat el **Jr** (mínim privilegi: `add_problem`, `edit_own_problem`, `view_problem`, `add_problemdata`/`add_problemtestcase`/`add_problemtranslation`; només crea i edita els **seus** problemes) en lloc del **Sr** (que a més veu tots els problemes privats —`see_private_problem`—, esborra problemes i casos de prova i pot canviar la visibilitat pública). Verificat: `add_problem` i `edit_own_problem` → sí; `see_private_problem` → no. Grups actuals: `creador de problemes Jr`, `Profe`, `Responsable d'Institut`. Si es vol el Sr, cal treure-la del Jr i posar-la al Sr (només dades, sense reiniciar res).

### 152. Tres alumnes més al grup «Creador d'Achievements» (`CarolyneBocanegra`, `isbebo`, `matheus_kirk`)

**Abans:** l'usuari va enganxar tres correus d'avís automàtics del gacha (entrada #51, `mail_admins` a `judge/views/user.py`): `matheus_kirk` (2026-10-26, resultat 86128), `isbebo` (2026-11-03, 87934) i `CarolyneBocanegra` (2026-11-04, 88384) havien tret l'sticker **«Dret a Crear Achievements»** (id 156). La descripció d'aquest sticker els diu que enviïn un correu perquè l'administrador els «passi la guia de crear achievements», i el que s'ha fet fins ara amb els 49 membres del grup «Creador d'Achievements» és donar-los el grup i `is_staff`. Els tres comptes no tenien cap grup ni `is_staff`.

**Decisió:** afegits al grup «Creador d'Achievements» i `is_staff=True` (el mateix patró dels 49 existents: tots `is_staff`, cap superusuari). Fet des d'un script de Django (`manage.py shell`), en una transacció. **No s'han donat més permisos.**
- Verificat abans que els tres tenien de debò l'sticker (`AchievementObtained` amb els ids dels correus) i que el grup només porta `add/change/delete/view_achievement`.
- El primer intent el va **bloquejar el mode automàtic de Claude Code** (concessió de permisos sense una instrucció explícita: només hi havia els correus enganxats). Vaig parar, ho vaig explicar i l'usuari va dir «sí, fes-ho»; llavors es va executar.

**Resultat (verificat):** els tres tenen `add_achievement` i `change_achievement` i **no** `add_problem` ni `organization_admin`; el grup passa de 49 a **52 membres**. Cap canvi de codi.

**Pendent (no fet, no tinc correu):** enviar-los la guia (vegeu #153) o dir-los que ja la poden veure; ho ha de fer l'usuari.

### 153. «Guia de crear achievements»: pàgina plana restringida per permís, entrada de menú condicional, i 5 idiomes

**Abans:** els qui guanyen el «Dret a Crear Achievements» (entrades #51, #54, #55, #91) només rebien la guia per correu. No hi havia cap pàgina que expliqués com crear un achievement, i les pàgines planes (`django.contrib.flatpages`) només saben exigir «haver entrat» (`registration_required`), no un permís.

**Decisió** (a petició de l'usuari: «una static page com la de guia de crear problemes... traduïda... només poden veure-la els creadors d'achievements... només et surt al menú d'altres guies si tens el permís»):
1. **Pàgina plana `/creaachievements/`** (id 11), títol «Guia de crear achievements», plantilla `flatpages/markdown.html`, base en català i 4 `FlatPageTranslation` (es, en, de, zh-hans), com la resta de guies. Seccions: què és un achievement (sticker o icona i on es veuen), qualitat i probabilitats del gacha, la imatge, com crear-lo pas a pas (amb captura), i què passa en desar-lo (entra al gacha a l'instant, només edites/esborres els teus, esborrar-lo el fa desaparèixer als qui ja el tenien, els admins poden editar-ho tot).
2. **Restricció per permís** a `judge/flatpage_permissions.py` (nou): un diccionari `{'/creaachievements/': 'judge.add_achievement'}`, font única per a les dues peces següents. El permís és `add_achievement`: el té el grup «Creador d'Achievements» i, com sempre, els superusuaris (els admins la veuen).
   - **La pàgina**: `judge/flatpage_i18n.py` (el `render_flatpage` ja parcheat per a les traduccions) comprova el permís. **Sense sessió → redirecció al login** (com `registration_required`); **amb sessió però sense permís → 404** (la pàgina ni apareix com a existent; `FlatpageFallbackMiddleware` converteix l'`Http404` en el 404 normal del lloc). Una professora sense el permís (`rosa_rosae`) també rep el 404.
   - **El menú**: `judge/template_context.py` (`general_info`) treu del queryset `nav_bar` les entrades les rutes de les quals estan restringides per al qui mira (`exclude(path__in=hidden_flatpage_paths(request.user))`). `mptt_tree` (`get_cached_trees`) construeix els desplegables a partir d'aquest mateix queryset, així que l'entrada desapareix també del seu pare.
3. **Entrada de menú** `NavigationBar` id 18, clau `GuiaAch`, «Crear Achievements», sota «Altres Guies» (id 15), quarta (després de «Guia DBeaver»), regex `^/creaachievements/$`. **Etiquetes traduïdes** afegides a `locale/{es,en,de,zh_Hans}/LC_MESSAGES/dmoj-user.po` (Crear Achievements / Create Achievements / Achievements erstellen / 创建 Achievement) i `.mo` recompilats amb `msgfmt --check`.
4. **Captura** `resources/guides/achievements-admin.png` (copiada també a `/tmp/static/guides/`; serveix `200 image/png`). **Sense tocar cap permís ni compte demo:** el formulari «Afegir achievement» es va renderitzar com el veu un creador real (client de test de Django, GET, **sessió en cookie signada** perquè no s'escrigui cap fila de sessió ni es toqui `last_login`), amb el nom d'usuari real substituït per `alumne1` i l'avatar amagat, i es va fotografiar amb Chromium (l'HTML es va desar a `~/shots/guies/ach_add.html`, perquè el Chromium *snap* no llegeix `/tmp/claude-1000/...`). El que hi ha escrit («Ànec de goma»...) és un exemple inventat.
5. **Fets comprovats abans d'escriure'ls** (no suposats): la descripció es mostra com a **text pla** al resultat del gacha (`{{ achdesc }}`, escapat; el Markdown només es renderitza per als *super achievements*), el sticker es pinta a 200×200 i la carta a 500×500 amb `background-size: cover` (per això es recomana la imatge quadrada), la icona a 50×50, les probabilitats 65/20/10/5 % (`GachaMain.GACHA_TIER_CHANCES`, `gacha_roll`), i `AchievementObtained.achievement` és `CASCADE` (esborrar-lo el treu a tothom). Els textos de les etiquetes (`Nom de la fita`, `Qualitat de la fita`...), les opcions i el botó de desar (**Desa** / Guardar / Save / Speichern / 保存) són els que **renderitza de veritat** l'admin en cada idioma, extrets del formulari real.

**Per què:** petició explícita de l'usuari.

**Resultat (verificat amb la pila completa de Django i la BD real, sessions en cookie signada, sense escriure res):** anònim → **302** al login; alumne sense permís (`demo_alumne`) i professora (`rosa_rosae`) → **404**; creadors (`CarolyneBocanegra`, `isbebo`) i superusuari (`marc`) → **200**; l'enllaç al menú només hi surt per a aquests tres (`/sobre/`); les guies de sempre (`/creaproblemes/`, `/guiaprofes/`) i el seu menú, intactes per a tothom. Títol, contingut, imatge i etiqueta de menú correctes en **ca, es, en, de i zh-hans**. En viu, un anònim rep el 302 des de `https://jo-el.es/creaachievements/`. `manage.py check` net. **uwsgi recarregat dues vegades** (`kill -HUP` del màster, 13:45 i ~13:50 UTC; la primera abans de crear la pàgina perquè no hi hagués cap moment amb la pàgina visible per a tothom, la segona per carregar els `.mo` nous). Abans del primer reload es va comprovar que cap fitxer s'havia modificat després del reload de les 06:45, així que només es van carregar aquests canvis. Cap migració.

**Limitacions:**
- Els textos en es/en/de/zh-hans els he escrit jo, sense revisió d'un parlant nadiu; **només el català s'ha vist en una captura** (la resta s'ha comprovat per text renderitzat, no visualment).
- «PNG o JPG», «500×500» i «no més d'1 MB» són **recomanacions** de la guia, no límits que apliqui el sistema (nginx accepta fins a 50 MB i no hi ha cap validació de mida o format més enllà de que sigui una imatge vàlida).
- Els canvis de codi són a l'arbre de treball **sense commit** (com la resta del que hi ha pendent). El fitxer `dmoj-user.po` tampoc és al git (ja era així).
- Restes anotades a `TODO.md` #22 (entre elles, que «Achievements» no surt al menú lateral de l'admin, i per això la guia dona l'enllaç directe).

---

## 2026-11-05

### 154. «Roda de la pissarra» dels equips: problema d'una tasca + alumne a l'atzar, i GachaPoints amb límit diari (model `GachaPointGrant`, migració 0168)

**Abans:** no hi havia cap eina per triar a l'atzar qui surt a la pissarra. I donar GachaPoints a un alumne només es podia fer a mà des de l'admin de Django editant `Profile.gacha_points` (restant el valor, perquè aquest camp compta el que l'usuari **ha gastat**; disponibles = `points + sql_points − gacha_points`), sense límit i sense deixar cap rastre de qui havia donat què.

**Decisió** (a petició de l'usuari; interpretat «froe» = «profe», que és l'etiqueta del permís `judge.see_extended_answers`, «Veure Informació per a Profes (Profe)»):
1. **Nova pàgina `/organization/<id>-<slug>/wheel`** (`OrganizationWheel`, `judge/views/organization.py`; plantilla `templates/organization/wheel.html`; enllaç «🎡 Roda de la pissarra» a la barra lateral de la pàgina de l'equip, `templates/organization/home.html`, només si `can_wheel`). Dues rodes dibuixades en un `<canvas>`: **problema** (de la tasca que el professor tria en un camp amb cerca, `<datalist>`) i **alumne** (membres de l'equip). Botó gros «Gira!» (gira les dues amb parada esglaonada: 4,2 s i 6,4 s), i botons «Només el problema» / «Només l'alumne». El resultat es decideix **abans** de l'animació amb `crypto.getRandomValues`.
   - **Vistosa i còmica:** marc daurat amb bombetes que parpellegen, clavilles, un punter amb **ulls** que es marejen mentre gira i salta amb cada clavilla, cara 🤪/😵/🤩 al centre, bafarades amb frases (8 mentre gira, 8 en guanyar), fons d'escenari amb emojis flotants, targeta de guanyador amb nom en degradat arc de Sant Martí, confeti + emojis, sacsejada de pantalla, i **sons amb WebAudio** (sense fitxers: tic, «swoosh», ding, fanfàrria, botzina de pallasso, moneda), amb botó de silenci (`localStorage` `wheel-muted`, dins `try/catch`). Respecta `prefers-reduced-motion`. Mòbil: les rodes s'apilen.
   - **Alumnes de la roda:** membres de l'equip **menys** els admins, el `registrant`, els `is_unlisted` i qui gira (no es pot premiar a un mateix). Cada alumne és un xip que es pot treure/posar (absents); casella «No repetir alumnes» (activa per defecte: l'escollit es treu de la roda) i «Marcar-los tots». Només alumnes: els problemes sempre són tots a la roda.
   - Tot el text dinàmic s'insereix amb `textContent` (noms d'usuari i de problema són dades d'usuari); la configuració arriba en un bloc `json_script` (escapa `<`, `>`, `&`).
2. **Permisos** (`can_use_organization_wheel`, `judge/views/organization.py`): cal el permís **`judge.see_extended_answers`** (Profe) **i** ser **admin o registrant de l'equip** (el mateix criteri que `can_edit_organization`). **Els superusuaris poden fer servir la roda de qualsevol equip** (decisió meva: un superusuari ja pot tocar qualsevol cosa a l'admin; si es vol restringir als seus equips, és una línia).
3. **Donar GachaPoints:** `POST /organization/<id>-<slug>/wheel/grant` (`OrganizationWheelGrant`, JSON) amb `student` i `amount` (1–5 per clic). Resta `amount` de `Profile.gacha_points` amb `F('gacha_points') - amount` (a la base de dades, perquè no trepitgi un bonus diari o una tirada que acabin al mateix moment). **Límit: 5 GachaPoints per alumne i dia per professor** (el límit és **per professor**: dos professors poden donar 5 cada un al mateix alumne; el dia és el de **Europe/Madrid**, `Profile.madrid_today`, com el bonus diari). **Els superusuaris se salten el límit** (poden repetir els clics; segueix sent 1–5 per clic). El servidor comprova: sessió, permís, que l'alumne sigui **de l'equip de la URL** (`org.members`), que no sigui el mateix professor, `amount` enter 1–5. Dins `transaction.atomic()` **bloqueja la fila de l'alumne** (`select_for_update`) abans de sumar el que ja s'ha donat avui, de manera que dos clics simultanis no poden passar-se del límit. Errors en JSON (`403`, `404`, `400`, `409` amb `given`/`left`).
4. **Model nou `GachaPointGrant`** (`judge/models/profile.py`, exportat a `judge/models/__init__.py`): `giver`, `receiver`, `organization` (`SET_NULL`), `points`, `day` (data de Madrid), `created`; índex `(giver, receiver, day)`. És alhora el registre d'auditoria i el que fa complir el límit. `GachaPointGrant.given_today()` fa servir `.order_by()` perquè `Meta.ordering` s'afegiria al `GROUP BY` (Django 2.2) i partiria les sumes. **Migració `judge/migrations/0168_gachapointgrant.py`** (només `CreateModel` + `AddIndex`; `makemigrations --dry-run` no detectava cap altra deriva).
5. **`GET .../wheel/task/<codi>`** (`OrganizationWheelTask`, JSON): els problemes de la tasca **que el professor pot veure** (`Problem.get_visible_problems`), amb el nom traduït a l'idioma de la interfície si n'hi ha (`ProblemTranslation`).
6. **Admin:** `GachaPointGrantAdmin` (`judge/admin/achievement.py`, registrat a `judge/admin/__init__.py`), **només lectura** (sense afegir ni canviar), amb filtre per dia/equip i cerca per professor/alumne.
7. **Traduccions:** 69 cadenes noves (interfície, frases còmiques, missatges d'error, noms de camps) a `locale/{ca,es,en,de,zh_Hans}/LC_MESSAGES/django.po`, afegides al final dels fitxers (sense reescriure'ls); validades amb `msgfmt --check --check-format`. Els msgids nous són en català, com la resta de la UI del gacha. Vocabulari coherent amb el ja existent (es «tarea», de «Aufgabe», zh «任务»).
8. **Dues correccions que vaig trobar provant:** (a) la roda quedava **en blanc fins a 330 ms** en carregar la pàgina (`lastDraw` inicial a 0 amb un límit de repintat); ara `lastDraw = -1e9`. (b) El missatge «Tothom ha sortit» sortia només si havien sortit **tots** els de la llista; ara surt si ja n'ha sortit algun i no en queda cap per girar.
9. **Conflicte amb el CSS global del web, trobat en carregar la pàgina real** (les primeres captures feien servir un `base.html` simplificat i no ho podien mostrar). `resources/widgets.scss` dona estil a **tots** els `<button>`: `display: block`, `color: var(--text-white) !important`, fons blau i `:hover` blau; i `h2 { font-weight: 400 }`. Efectes: els botons +1…+5 s'apilaven en columna, «GIRA!» quedava a l'esquerra i es tornava blau en passar-hi el ratolí, «Marcar-los tots» era text blanc sobre blanc, i els títols perdien el negreta. **Correcció** (a `templates/organization/wheel.html`): `#wheel-app button` passa a `inline-block` amb `text-decoration: none !important`; cada botó fixa el seu `color` amb `!important` (l'únic que guanya a l'`!important` del web) i el seu propi `:hover`; els xips desactivats recuperen el `line-through` amb `!important`; `.wheel-box h2` amb `font-weight: 900`. Verificat amb l'estil calculat sobre la pàgina real (`display: inline-block`, color del botó de premi `rgb(5, 59, 28)`, pes del títol 900, ratllat dels xips) i amb captura.

**Per què:** petició explícita de l'usuari. La taula de registre és imprescindible: sense saber què s'ha donat avui no es pot fer complir «5 per alumne i dia», i a més deixa constància de qui ha donat què.

**Resultat (verificat; les proves de servidor sobre la base de dades real són dins d'una transacció que es desfà sempre):**
- **63 comprovacions** del servidor (`test_wheel_views.py`, al directori temporal de la sessió) amb el client de proves de Django, la pila completa de middleware i una **SQLite en memòria** (taules creades amb `schema_editor.create_model`; hi ha un `assert` que avorta si no és `:memory:`). Cobreixen: matriu de permisos (professor registrant ✔, co-professor admin ✔, superusuari no-admin ✔, Profe no-admin de l'equip ✘ 403, admin sense Profe ✘ 403, alumne ✘ 403, anònim → login); la roda exclou professors/`unlisted`/no membres; 3+2 = 5 i el 6è es rebutja (409, `left` correcte, res no es dona); límit per alumne i per professor; el dia nou el reinicia; superusuari 5×4 sense límit; `amount` 0/6/−3/«abc»/2,5/buit, alumne inexistent o d'un altre equip, un mateix → rebutjats sense canviar cap perfil; l'endpoint de tasques (privat ocult per al professor, visible per al superusuari; tasca buida; inexistent); admin renderitza. **Resultat: tot OK.**
- **Navegador real** (Chromium headless conduït per CDP en temps real, servidor de proves amb la plantilla real i el mateix comportament de límit): carrega de tasca, gir, guanyador amb enllaç al problema, botons de premi (3+2 → es bloquegen), superadmin repeteix +5, no-repetir (3 tirades → 3 alumnes diferents, xips ✔), sense tasca (només alumne), tasca desconeguda/buida/d'un sol problema, sense alumnes, i vista mòbil de 390 px. Captures revisades.

**Pendent / limitacions (honest):**
- **Desplegat el 2026-11-05.** L'usuari va donar l'OK explícit («sí, fes-ho»). (1) `manage.py compilemessages`: verificat abans amb fitxers temporals que només afegeix els 69 msgids nous per idioma i que cap traducció existent canvia. (2) `manage.py migrate judge 0168`: **el va denegar el classificador del mode automàtic de Claude Code** («Production Deploy») malgrat l'OK, i no s'ha provat de saltar-s'ho; **l'usuari l'ha executat ell mateix** al prompt amb el prefix `!` → `Applying judge.0168_gachapointgrant... OK` (abans: era l'única migració pendent de totes les apps; SQL additiu; es desfà amb `migrate judge 0167`). La taula `judge_gachapointgrant` existeix, buida. (3) **Proves contra la MariaDB real**, tot dins d'una transacció que es desfà sempre (comptes `zzwheel_*` falsos; caché en memòria i sessions en cookie perquè no toqui la caché de producció): les mateixes comprovacions de permisos/límit/superadmin/validacions més l'endpoint de tasques amb una **tasca real** (`intro00`: el professor veu exactament els problemes que `get_visible_problems` li permet, cap de privat) i la pàgina amb les **193 tasques reals** → **63 PASS, tot OK**, i recomptes idèntics abans i després (7871 usuaris, 7871 perfils, 174 equips, 0 donacions). **Prova del bloqueig de fila amb dues connexions** (només lectura d'un perfil real inactiu): mentre A té el bloqueig, B rep `1205 lock wait timeout`; quan A el lliura, B l'obté a l'instant → `select_for_update` serialitza de debò en aquesta MariaDB. (4) `uwsgi --reload /home/ubuntu/dmoj-site.pid`, **dues vegades** (01:04:15 i, després de la correcció d'estils de l'ítem 9, 01:08:27); mateix màster (3412377), 6 workers nous cada cop. (5) **Proves de fum al web en viu** (`https://jo-el.es`, peticions anònimes, sense escriure res): la pàgina de l'equip, `/`, `/problems/`, `/tasks/`, `/organizations/` → 200; `/wheel` → 302 al login; `/wheel/task/…` → 403 JSON; `/wheel/grant` → 405 (només POST). (6) Pàgina real renderitzada per a un professor fals i carregada amb el CSS real del web: gir complet (tasca → guanyador → botons de premi) sense errors, sense desplaçament horitzontal. **Nota:** els recomptes es desfan, però els `INSERT` desfets **consumeixen valors d'`AUTO_INCREMENT`** (forats als ids de `auth_user`, `judge_profile`, `judge_organization`…): és inofensiu però és el rastre d'aquestes proves.
- **Els sons no s'han pogut escoltar** (Chromium headless); només s'ha comprovat que no llancen errors i que el botó de silenci funciona. L'animació s'ha vist en captures i a velocitat real, però no en un projector.
- Les traduccions en en/de/zh-hans són meves, sense revisió d'un parlant natiu.
- Un alumne **no rep cap avís** quan rep GachaPoints: només veu que el saldo puja.
- Restes (inclòs un `has_perm('see_extended_answers')` sense el prefix `judge.` a `vote_submission`, trobat de passada) a `TODO.md` #23.
- Canvis a l'arbre de treball **sense commit**, com la resta del que hi ha pendent.

**Seguiment (5-11-2026): el captcha frena ben poc el spam.** L'usuari va observar que seguia entrant spam. Dades (només lectura): des que el captcha va tornar a estar actiu (3-11 ~18:00 UTC) fins al 5-11 01:00, **161 comptes
noves, 155 amb enllaç de spam a la descripció (96%)**, unes 120 al dia (a l'octubre eren ~170 al dia i creixent); totes pel formulari (0 per login social; `accounts/register/` és l'única porta); els registres legítims són ~6 en 31 h. **No hi
ha escletxa:** una petició real al web en viu sense captcha és rebutjada («Aquest camp és obligatori» al camp del captcha; contrasenyes diferents a propòsit perquè no es pogués crear cap compte), `RECAPTCHA_DISABLE` no és a
l'entorn d'uWSGI i les claus són les bones; per tant els bots **resolen el captcha** (serveis de resolució de pagament). Perfil: 74% gmail.com, 16% `alazsec.org` (+ altres dominis de granja), 103 IPs diferents per a 155 comptes (rangs de
Bangladesh/Sud-est asiàtic), els 155 activats i amb sessió iniciada. Per això un bloqueig per IP o per domini només en tallaria una part. Els enllaços de la descripció ja surten amb `rel="nofollow"`, però el text continua públic.
No hi ha cap canvi de codi ni de configuració en aquest seguiment. Opcions proposades a l'usuari: (1) bloquejar enllaços a la descripció fins al primer problema resolt, (2) comanda de purga programada amb el mateix criteri estricte de #142,
(3) llista de dominis de granja al registre, (4) codi d'accés d'equip obligatori al registre.

### 145. Contra el spam del registre: enllaços al perfil fins al primer problema resolt, dominis de granja i bloqueig per països (en viu)

**Abans:** el captcha (#144) no frena els bots, que el resolen (155 de 161 altes en 31 h eren spam). L'usuari va triar les opcions 1 (enllaços fins al primer problema resolt) i 3 (dominis de granja) i va proposar bloquejar IP del sud-est asiàtic.

**1. Enllaços a la descripció del perfil (`judge/forms.py`, `ProfileForm`).** Un compte sense cap enviament `AC` no pot afegir enllaços a la descripció (`https?://`, `www.` o un nom amb un dels TLD que fa servir el spam: com, net, org, io, vn, us, bet,
vip, xyz…); hi val qualsevol compte amb un `AC`, el professorat (`edit_own_problem`) i el staff. Només compten els enllaços **nous** respecte de la descripció desada, de manera que una descripció antiga mai es rebutja en editar-ne una altra cosa, i els
enllaços interns relatius (`/problem/…`) no compten. L'error és **general** (`clean()`), no del camp, perquè la plantilla d'«Edita el perfil» només mostra `non_field_errors` (un error de camp hauria sortit com una caixa vermella buida).

**2. Dominis de granja (`dmoj/settings.py`, `judge/views/register.py`).** Paràmetres nous `SPAM_MAIL_DOMAINS` (39 dominis, amb subdominis: p. ex. `xintaitong.com`, `rehearsalk.com`, `proschools.it.com`, `base-jump.at`, `tokmail.net`) i `SPAM_MAIL_DOMAIN_REGEX` (la família
`azh*`/`alaz*`/`aazh*` `.org`/`.com`, i **tot `.us`**: de 3.700+ usuaris amb enviaments, cap n'hi té, i la granja fa dominis nous cada dia). Són paràmetres propis perquè `local_settings.py` sobreescriu `BAD_MAIL_PROVIDERS` amb un conjunt buit. Criteri de la llista (només lectura,
sobre els comptes d'abans de la purga #142): domini no genèric, cap usuari amb enviaments, ≥5 comptes i ≥80% amb enllaç a la descripció. `clean_email` del registre ho rebutja amb el missatge ja existent («Your email provider is not allowed…»). Ara mateix hi ha 135
comptes a la BD amb un d'aquests dominis (spam que ja hi era).

**3. Bloqueig del registre per països.** Dades (només lectura, rangs d'APNIC, públics): dels 155 spammers de després del captcha, **113 de Bangladesh, 28 del Vietnam, 1 de Tailàndia i 13 d'IP de fora d'APNIC**; dels 3.755 usuaris reals amb enviaments, **0** hi són (3.753 són de fora d'APNIC).
Nota: Bangladesh és el gruix i no és sud-est asiàtic; s'hi ha inclòs per les dades. `judge/utils/geoblock.py` (cerca per `bisect` en rangs IPv4/IPv6) + comanda `manage.py update_geoblock` (descarrega la llista d'APNIC o llegeix `--file`, escriu `judge/utils/geoblock_ranges.txt`: **22.925 rangs, 12 països**: BD, VN, TH, ID, PH, MY, KH, LA, MM, BN, TL, SG) +
paràmetre `REGISTRATION_BLOCKED_COUNTRIES` + control a `RegistrationView.dispatch` (`REMOTE_ADDR`, que és la IP que ja es desa a `Profile.ip`): des d'una IP d'aquests països, **només la pàgina de registre (GET i POST)** respon 403 amb «Registre no disponible… parla amb el teu professor»;
l'inici de sessió, la portada i la resta funcionen igual (qui ja té compte hi entra des de qualsevol lloc). Cobertura sobre els spammers actuals: **142 de 155 (92%)**; usuaris reals que es bloquejarien: **0 de 3.756**. Per apagar-ho: `REGISTRATION_BLOCKED_COUNTRIES = ()`; treure un país del paràmetre aixeca el bloqueig a l'acte; afegir-ne un demana tornar a executar `update_geoblock`.
**Límits honestos:** és fàcil de saltar-se amb un proxy d'un altre país (no cobreix les 13 IP de fora d'APNIC ni els gmail europeus), així que l'efecte real caldrà mesurar-lo; la mesura 1 és la que els treu el motiu.

**Verificació (dins de transaccions desfetes, sense deixar cap fila):** 33/33 comprovacions de dominis i enllaços (22 dominis bloquejats/permesos, 0 dels 3.743 usuaris reals amb enviaments afectats; enllaç refusat a un compte nou, text net acceptat, descripció antiga amb enllaç acceptada, enllaç nou refusat, alumne amb `AC` i professorat acceptats; cap rastre després);
bloqueig per països: IPv4 i IPv6 correctes, GET/POST des de Bangladesh 403 amb el missatge, des d'Espanya 200 amb captcha, inici de sessió i portada des de Bangladesh 200, i apagar-ho per paràmetre funciona. (Un control del meu test fallava per una línia de capçalera mal llegida; refet a part amb un rang IPv6 real: OK.)
Traduccions: 3 cadenes noves a ca/es/en/de/zh_Hans, afegides com a entrades noves (0 línies existents tocades) i `.mo` recompilats. `manage.py check` net; no hi ha migracions.

**Estat:** **en viu** (5-11-2026). El primer intent de `kill -HUP` va ser bloquejat pel sistema de permisos com a desplegament a producció; l'usuari va demanar després que el fes jo, i es va fer just després de la purga de #146. Comprovat en viu:
`/`, `/accounts/register/`, `/accounts/login/`, `/problem/okboomer`, `/problems/` i `/users/` responen 200; el registre porta el captcha; una petició real amb contrasenyes diferents (no pot crear cap compte) i correu `@alazsec.org` o `@ghkali.us` és
**rebutjada** amb «El teu proveïdor de correu electrònic no està permès…», i amb `@gmail.com` el domini s'accepta. **No provat en viu:** el bloqueig per països (`REMOTE_ADDR` no es pot falsejar des de fora; provat amb el client de Django) ni la regla dels enllaços del perfil
(cal una sessió); tots dos validats a les proves de transacció desfeta.

### 146. Segona purga de comptes de spam: 2.241 esborrats (de 7.871 a 5.631 perfils)

**Abans:** després de #142 (19.438) el spam continuava entrant (#144/#145). L'usuari va demanar «una bona netejada» amb aquests criteris: nom aleatori, descripció de spam, IP del sud-est asiàtic, cap enviament ni permís, no haver tornat mai després de la primera vegada
i correu «spammy»; i **mai** esborrar qui tingui enviaments, permisos o correu `.cat`, `.es` o d'institut.

**Anàlisi (només lectura):** dels 4.115 comptes sense cap enviament, 3.380 eren elegibles (descartats: 196 amb staff/permisos/altra activitat i 616 amb correu protegit; 2 més per ser d'un equip tancat). Senyals calculats per compte: descripció amb enllaç; nom aleatori (model de bigrames de lletres entrenat amb els
noms d'usuari reals; marca el 96% dels noms de bot coneguts i l'1% dels reals, i **només compta si a més ningú no ha iniciat mai sessió**); IP de Bangladesh/sud-est asiàtic (rangs d'APNIC); correu de domini de granja (`SPAM_MAIL_DOMAINS`/regex de #145); «no ha tornat» (cap inici de sessió, o última visita dins del dia del registre).
Es va llegir a mà el que quedava fora de la regla de #142: el grup més gran són comptes amb nom de 10 lletres aleatòries i **correus recollits** de gent i empreses angloparlants (EUA, Regne Unit, Canadà) que o no s'han activat mai o s'han «activat» sols (els filtres antispam dels correus d'empresa cliquen l'enllaç) i no han iniciat mai sessió.

**Regla aplicada (tots els requisits «durs» i, a més, almenys un grup):** cap enviament, punts ni problemes resolts; no staff i rang `user`; cap altra activitat (concursos, valoracions, admin/registrant d'equip, sol·licituds, problemes com a autor, xats d'ajuda…); correu no `.cat`/`.es`/`edu`/`gencat`/`ac` ni d'un domini genèric on algú hagi fet enviaments;
no ser d'un equip tancat; i un d'aquests grups: **A** descripció amb enllaç (157); **N** nom aleatori + ningú ha iniciat mai sessió + fa 8 dies o més (1.989; 1.881 no activats mai); **E** domini de granja + no ha tornat (118); **S** IP de Bangladesh/sud-est asiàtic + no ha tornat + nom d'aspecte spam (151). Els grups es solapen: **2.241 comptes únics**.
**Deixats a propòsit (1.137 elegibles):** uns 689 no activats mai amb nom d'aspecte humà (poden ser persones reals que no van activar el correu) i uns 8 amb IP de Bangladesh/Vietnam però nom normal (p. ex. `almahamudkhan`).

**Com es va fer:** script en lots de 400 (a l'scratchpad de la sessió, no es versiona) que per cada lot torna a comprovar contra la BD en viu totes les condicions anteriors i que algun grup encara es compleix, desa còpia (JSONL) i esborra dins una transacció que es desfà si la cascada toca res fora de `User`/`Profile`/`RegistrationProfile`/`Profile_organizations`.
Simulació prèvia sobre els 2.241: 0 rebutjats i cascada només a aquestes quatre taules. L'usuari va confirmar amb la xifra davant («si»).

**Resultat:** esborrats 2.241 `User` + 2.241 `Profile` + 2.241 `RegistrationProfile` + 94 pertinències a equips (les revisions de `reversion` només perden l'usuari, `SET_NULL`). Perfils: 7.871 → **5.631** (un d'aquests és una alta nova arribada entremig). Comprovat després: les **3.756 persones amb enviaments hi són totes**, 0 enviaments orfes (378.918), 174 equips,
446 staff i 11 superusuaris, 3.879 participacions de concurs, 1.992 comentaris, i 2.747 perfils amb correu `.cat`/`.es` intactes. Cap rebutjat per activitat en cap lot.
**Còpia de seguretat:** `/home/ubuntu/backups/comptes-spam-esborrats2-20261105.jsonl.gz` (620 KB, permisos 600, amb `.sha256`), 6 línies (una per lot) amb `users`, `profiles`, `regprofiles` (restaurables amb `loaddata`), `profile_orgs` i `tiers` (el grup de cada compte). Es restauraria amb els mateixos `id`; l'usuari de les revisions no es recuperaria.

**Per revisar:** els 689 mai activats de nom humà es podrien netejar amb la comanda estàndard `cleanupregistration` de django-registration (esborra els no activats amb clau caducada), però no s'ha fet perquè no es va demanar; el registre ara té captcha, dominis i països bloquejats (#145) i el perfil no admet enllaços fins al primer problema resolt.

### 155. Slider «Over-the-top» a la roda de la pissarra: de «Mode biblioteca» (0) a «SUPERLLEGENDARI» (10)

**Abans:** la celebració en guanyar era sempre la mateixa (fanfàrria, botzina, 2 canons de confeti, pluja, sacsejada de l'escenari) i la roda sempre girava el mateix temps.

**Decisió** (a petició de l'usuari: «un slider de over-the-top; com més a la dreta, més exagerada l'animació, com en el superllegendari»). Fitxers: `templates/organization/wheel.html`, `judge/views/organization.py` (`get_js_strings`: `otNames` ×11 i `otLegend`), `locale/{ca,es,en,de,zh_Hans}/LC_MESSAGES/django.po` (15 msgids nous per idioma).
1. **El slider:** `<input type="range">` 0–10 a l'escenari, amb el nom del nivell en gran (creix amb el nivell; al 10 es torna arc de Sant Martí i tremola), i un botó «🎉 Prova» que fa la celebració sense girar. **Per defecte 5 = l'aspecte d'abans** (comprovat: confeti `18·L` = 90 per costat, potència `800+60·L` = 1100, pluja `14·L` = 70, que són els números antics). Es guarda a `localStorage` (`wheel-ot`, dins `try/catch`). Noms: 0 Mode biblioteca · 1 Sobri · 2 Discret · 3 Festiu · 4 Animat · 5 Festa major · 6 Exagerat · 7 Boig · 8 Caos · 9 Apocalipsi · 10 SUPERLLEGENDARI.
2. **Mentre gira:** durada ×(0,8+0,04·L) fins al 5 i ×(1+0,12·(L−5)) a partir d'aquí (al 10, ×1,6); des del 6, la roda **passa de llarg i torna enrere** (rebot de 0,3+0,25·(L−6) segments, màxim 0,9 rad; el resultat ja estava decidit, és només teatre) i hi ha **redoble de tambor** (1,4 s + «bum», programat amb el rellotge d'àudio); des del 7, l'escenari **tremola** (`--rumble`).
3. **En guanyar** (cada nivell afegeix efectes als de sota): ≥1 fanfàrria · ≥2 botzina · confeti i pluja escalats · ≥3 sacsejada (amplitud `L/5`, durada `0,5+0,12·L` s) · ≥6 flaix + **raigs** · ≥7 els colors de la roda giren pel cercle cromàtic, **ànecs** marxant (el `icons/duck.svg` del logo, passat a la plantilla per `data-duck`) i resplendor a la targeta · ≥8 **focs artificials**, **trompetes** amb notes, **onada d'arc de Sant Martí** a tota la pàgina i una segona fanfàrria · ≥9 **títol gegant** «nom!!!» + «És una llegenda!», sirena, segon flaix i sacsejada de **tota la pàgina** (`#wheel-app.quake`) · 10 «SUPERLLEGENDARI 🦆🌈», botzina i dues onades més de confeti/fanfàrria a +1,4 s i +2,8 s. És la mateixa escalada del gacha (`mega fanfare`: onada d'arc de Sant Martí, desfilada d'ànecs, focs, trompetes, títol).
4. **Accessibilitat:** amb `prefers-reduced-motion` el nivell efectiu **mai passa del 2**; els flaixos són suaus (opacitat ≤0,4, 0,9 s cada un) i com a màxim 4 en 3 s (≤1,4 Hz, per sota del límit de 3/s).
5. **Estructura:** els efectes de pantalla completa (`#wheel-fx`: flaix, raigs, onada, ànecs, trompetes, títol) i el canvas del confeti van **fora de `#wheel-app`**: una animació de `transform` en un ancestre converteix `position: fixed` en relatiu a ell, i la sacsejada de pàgina els hauria desplaçat.
6. **Rendiment** (va caldre; mesurat al Chromium sense GPU, que és pessimista): al principi el nivell 10 anava a **~6 fps** (9: 11, 8: 15; el 5: ~50). Canvis: emojis del confeti com a **sprites** en caché (abans `fillText` d'emoji per partícula i fotograma), `setTransform` en lloc de `save/translate/rotate/restore`, límit de **1800 partícules**, sense animar `box-shadow` (resplendor de la targeta = pseudo-element que només canvia d'opacitat), sense `filter: hue-rotate` a l'escenari (ara gira el matís de la paleta de la roda al canvas), sense `mask-image` als raigs (capa de 125vmax, que cobreix la diagonal), onada sense `mix-blend-mode` ni `background-position` (només opacitat i `transform`), text del títol sense animar, menys ànecs i `will-change`. Resultat: **nivell 10 ~17 fps, 9 ~15, 8 ~21–23, 6 ~34, 5 ~50** (a una GPU real hauria d'anar fluid). A més, un **governador**: si la mitjana de fotograma passa de ~45 ms, ànecs, focs, notes i onades deixen de generar-se (així un ordinador just no es penja).
7. **Robustesa durant el desplegament:** les plantilles es llegeixen del disc però el Python viu és vell fins al reload; amb la plantilla nova i el diccionari vell (sense `otNames`) el JS petava en pintar el slider. Ara els textos del slider són opcionals (`otName()` torna el número) i s'ha **provat simulant exactament aquest estat** (sense errors, la roda es pinta i gira).

**Per què:** petició explícita de l'usuari; el 5 per defecte perquè la versió anterior ja li agradava.

**Resultat (verificat):** regressió de servidor a SQLite en memòria (**63 OK**); Chromium conduït per CDP en temps real: nivells 0, 3, 5, 6, 7, 8, 9 i 10 (durades de gir, tremolor, efectes presents, **neteja total** al final: 0 ànecs, 0 trompetes, classes eliminades, canvas buit), botó «Prova», `prefers-reduced-motion` (nivell 10 → sense ànecs ni títol ni raigs, 61 fps), vista mòbil de 390 px, i la **pàgina real amb el CSS real del web** (slider, capes fixes per sobre de la barra del web, sense desplaçament horitzontal). `compilemessages` fet (els 15 msgids nous als 5 idiomes; de passada ha agafat «Registre no disponible», que **no he afegit jo**: algú altre l'ha afegit als `.po` mentrestant).

**Pendent / limitacions:**
- **Falta el `uwsgi --reload /home/ubuntu/dmoj-site.pid`**: el classificador del mode automàtic **el va denegar** («Production Deploy»; les recàrregues anteriors passaven perquè l'usuari havia dit «sí, fes-ho» al desplegament, aquest cop només havia demanat el slider). Fins al reload els workers continuen amb el Python vell: la plantilla nova ja funciona (punt 7) però el slider mostrarà números en lloc de noms i la lletra «És una llegenda!» no hi serà.
- **No s'ha vist amb una GPU real ni en un projector**, ni s'han **escoltat** els sons dels nivells alts (sirena, trompetes, botzina): només s'ha comprovat que no donen errors. La seguretat dels flaixos es valora per números, no amb una prova amb gent.
- Els noms dels nivells en en/de/zh són meus, sense revisió d'un parlant natiu.
- Per error vaig deixar una còpia de la plantilla a **`/tmp/wheel.live.copy.html`** (havia d'anar al directori temporal de la sessió). No l'he esborrada: cal el teu sí.
- Canvis a l'arbre de treball **sense commit**.

### 156. «Imatge del problema»: un camp per pujar la imatge de l'enunciat, que es mostra sola a la dreta (model `Problem.image`, migració 0169)

**Abans:** cada enunciat que té imatge porta escrit a mà un `<img src="..." style="float:right" width="200">` (683 de 1.371 enunciats tenen imatge; uns 620 d'aquests, ~91 %, fan servir `float:right`, però amb mides i marges diferents: 200 px, 300 px, 150 px, `margin:5px`, `margin-left:30px`...). Per pujar-la calia l'editor Markdown: si l'autor és *staff* va al nostre `/media/martor/`, si no, **a imgur** (`martor_image_uploader`), que és d'on venen la majoria de les 60 URL d'imgur de l'entrada #150 i el problema de les imatges que desapareixen.

**Decisió** (a petició de l'usuari: «poder posar, quan crees un problema, un "carregar imatge del problema" amb un upload d'imatge on poses la imatge i automàticament ja et fa el float right etc sense que t'hagis de preocupar»). Fitxers: `judge/models/problem.py`, `judge/migrations/0169_problem_image.py`, `judge/utils/problem_image.py` (nou), `judge/admin/problem.py`, `templates/problem/problem.html`, `templates/problem/raw.html`, `locale/{ca,es}/LC_MESSAGES/django.po` (+ `.mo` recompilats; els `.mo` no van a git).
1. **Model:** `Problem.image = ImageField(upload_to='problem-images/', max_length=150, blank=True, null=True)`. És **del problema, no de la traducció**: es veu igual en català, castellà, anglès... i al PDF. Es desa a `MEDIA_ROOT/problem-images/`, la mateixa carpeta que el mirall de l'entrada #147 (ja és persistent, #148).
2. **Migració 0169:** només un `AddField` nul·lable (comprovat amb `makemigrations --dry-run` que no arrossega cap altre canvi). És compatible amb el Python vell que corre ara: un `INSERT` del codi vell simplement deixa la columna a NULL.
3. **Reducció en pujar-la** (`shrink_problem_image`, cridada des de `ProblemForm.clean_image`): costat llarg **màxim 600 px** (el doble del que es mostra, per a pantalles denses; mai s'amplia), s'aplica la rotació EXIF i **s'esborren totes les metadades** (GPS, càmera), es queda amb el **més petit de PNG i JPEG** (PNG per a diagrames/transparència, JPEG per a fotos), el nom passa a ser un hash (`sha256[:20]`), no el de l'ordinador de l'autor. Els GIF animats es deixen tal qual (re-codificar-los matava l'animació) però amb límit de 2 MB. Es rebutja: fitxer >12 MB, no-imatge, i formats que no siguin JPEG/PNG/GIF/WebP (inclosos SVG i BMP).
4. **Admin:** camp «Imatge del problema» a la fitxa, just abans del text; amb el *clear* de Django per treure-la. Qualsevol autor amb permís d'edició la pot pujar.
5. **Es mostra sola, sense tocar el text:** a `problem.html`, dins del bloc de caché `problem_html` (la caché ja s'esborra en desar el problema: `problem_update`), un `<img class="problem-image" style="float:right; max-width:min(300px, 45%); max-height:300px; height:auto; margin:0 0 10px 20px">` abans del text. El `min(300px, 45%)` fa que en mòbil no ocupi més de la meitat de l'amplada. S'usa `style` en línia (com ja feien els enunciats) perquè **no cal reconstruir l'SCSS ni fer `collectstatic`**. A `raw.html` (el PDF, que es renderitza com a fitxer local) va amb **URL absoluta** (`urljoin(url, image.url)`) i mides fixes, sense `min()`, que el motor del PDF no entén.
6. **Traduccions:** 6 msgids nous (nom del camp, ajuda i 4 missatges d'error) en **català i castellà**; en/de/zh en surten en anglès.

**Per què:** el 91 % dels enunciats amb imatge fan el mateix; així l'autor només puja el fitxer, la mida i el lloc són uniformes (adéu a les 15 variants de `style`) i, de passada, les imatges noves **ja no van a imgur**.

**Resultat (verificat, sense tocar la base de dades real ni la carpeta de mitjans real):** 26 comprovacions contra SQLite en memòria i un `MEDIA_ROOT` temporal, **26 OK**: foto de 2400×1800 → 600×450 JPEG; RGBA transparent petit es manté PNG i no s'amplia; diagrama pla → PNG; rotació EXIF aplicada i metadades fora; GIF animat intacte; es rebutgen un fitxer de text, un BMP i un de 13 MB; WebP acceptat; el camp és al formulari d'admin abans de `description`; `clean_image` encongeix una pujada nova i deixa en pace `None`, «esborra» i el fitxer ja desat; el PDF (`raw.html`) porta `src="https://jo-el.es/media/problem-images/..."` i `float:right`, i sense imatge no surt cap `<img>`; la **pàgina real `/problem/<codi>`** (vista de debò, visitant anònim) mostra la imatge **abans** del text i, sense imatge, cap `<img>`. Les traduccions es carreguen (`ca`: «Imatge del problema»).

**Pendent / limitacions:**
- **Migració 0169 aplicada el 2026-11-05 (~01:43)**: la va executar l'usuari amb `!` (el classificador del mode automàtic la va tornar a denegar quan li la vaig intentar córrer jo, tot i que m'ho va demanar; no es va esquivar). Només hi havia aquesta pendent; SQL: `ALTER TABLE judge_problem ADD COLUMN image varchar(150) NULL`. **Prova a la base real** (cache `locmem` i `MEDIA_ROOT` temporal, tot en una transacció desfeta): **11 OK** (columna creada, cap dels 1.371 problemes té imatge, desar la imatge a `calorcito`, `/problem/calorcito` en català i castellà la mostra a la dreta, l'admin de canvi i d'alta de problema tenen el camp de pujada `multipart`, tot desfet després: `calorcito` sense imatge, 1.371 problemes, `/tmp/media/problem-images` sense fitxers nous, 574).
- **uwsgi recarregat el 2026-11-05 (01:44:25)**: l'usuari va executar `! ~/dmojsite/bin/uwsgi --reload /home/ubuntu/dmoj-site.pid`. Els workers nous (arrencats després del canvi de codi) responen: `/`, `/problems/`, `/problem/calorcito`, `/problem/buscamines` i `/admin/login/` donen 200. **Encara ningú ha pujat una imatge real des de l'admin** ni s'ha vist el resultat en un navegador/PDF/mòbil (vegeu TODO #24).
- **Cap enunciat existent ha canviat:** els que tenen `<img>` a mà segueixen igual. Si un enunciat té la imatge als dos llocs, en sortiran dues. No hi ha cap conversió automàtica dels ~620 (vegeu TODO #24).
- Només **una imatge** per problema i **una mida fixa** (màx. 300 px d'ample i d'alt); els que volien 400 px centrats (p. ex. `quadrant`) han de seguir amb l'`<img>` a mà.
- La **previsualització en viu de l'editor Markdown** no mostra la imatge (només renderitza el text); es veu en desar.
- **No l'he vist en un navegador real** (ni en mòbil): només el HTML generat i el raonament sobre el CSS. Tampoc he provat la pàgina d'un problema dins d'un concurs (usa la mateixa plantilla).
- En clonar un problema (`ProblemClone`) la còpia apunta **al mateix fitxer** d'imatge; no es duplica el fitxer.
- Canvis a l'arbre de treball **sense commit**.

### 157. Prova de la «Imatge del problema» amb 3 enunciats reals: `aireacondicionat`, `abusdemarxandatge`, `afinantlarpa` (dades; sense canvis de codi)

**Abans:** els tres enunciats duien la imatge escrita a mà al principi del text (`<img ... style="float:right" width="200">` i variants), en català i en la traducció al castellà.

**Decisió** (a petició de l'usuari: «aplica el canvi a 3 o així i provo», després de l'entrada #156). Tres casos de mida diferents per veure la diferència: `aireacondicionat` (`width=200`), `abusdemarxandatge` (`margin:5px`, imatge de 600×400) i `afinantlarpa` (sense `width` a l'atribut, imatge alta de 460×676). Script a la carpeta temporal de la sessió (`conv_apply.py`, no es desa al repo: és d'un sol ús).
1. Per cada problema (públic i no privat d'organització, sense imatge al camp, amb **una sola** `<img>` al text i **al principi**, de `https://jo-el.es/media/problem-images/...` i amb el fitxer ja al disc): s'escriu al camp `Problem.image` el camí `problem-images/<fitxer>` (**el fitxer ja era a la carpeta del mirall, no se'n copia cap ni se'n mou cap**) i es treu l'etiqueta `<img>` del començament del text.
2. **Les traduccions al castellà** que tenien exactament la mateixa imatge al principi, també (6 textos en total: 3 problemes + 3 traduccions). Si una traducció tenia una altra imatge o cap, es deixava (no ha passat).
3. Còpia de seguretat dels textos antics i de què s'ha escrit a cada camp: `/home/ubuntu/joel-media/backup-descriptions-imatgecamp-20261105-014546.json` (16 KB). Les actualitzacions són condicionals (`update(... description=<text antic>)`, dins una transacció): si el text hagués canviat entremig, no s'hauria tocat res. Després, `problem_update` per esborrar la caché del fragment i els PDF.
4. **El que es perd:** l'`alt` que tenien (`aireacondicionat`, el nom del problema...; el nou és buit, imatge decorativa) i la mida pròpia: ara tots surten **a la dreta, màxim 300 px d'ample i 300 d'alt** (l'original de `aireacondicionat`, a 200 px, queda una mica més gran: el fitxer és de 398×299).

**Per què:** que l'usuari pugui comprovar el resultat real abans de decidir si es converteixen la resta.

**Resultat (verificat):** les tres pàgines responen 200 i porten `<img class="problem-image" ... float:right ...>` amb el fitxer correcte, que serveix 200; l'enunciat té **una sola** imatge en català i en castellà (a `aireacondicionat` surten més `<img>` a la pàgina, però són els avatars i una imatge d'un comentari, no de l'enunciat); el PDF de `aireacondicionat` es genera (200, 51 KB, PDF vàlid). **No l'he vist amb els ulls** (ni la pàgina ni el PDF renderitzats): ho comprova l'usuari.

**Pendent / limitacions:**
- Amb aquesta mateixa regla en queden **357 problemes públics** convertibles (i molts privats, més els que tenen altres formes de la imatge: dues imatges, imatge enmig del text, `float:none`, etc.). No s'ha fet res amb ells: depèn de què digui l'usuari després de provar.
- **Per desfer-ho:** restaurar els 6 textos de la còpia de seguretat i posar `image` a NULL dels 3 problemes (cal el teu sí abans, com sempre).
- Canvis a la base de dades; cap canvi de codi nou. **Sense commit.**

### 158. Final de la tirada aleatori i còmic: la roda es passa, es queda curta, fa molla, falsa parada o rebobina (més caos com més «over-the-top»)

**Abans:** a partir del nivell 6 el «rebot» era sempre el mateix (es passava una mica i tornava enrere), amb una amplitud que només depenia del nivell.

**Decisió** (a petició de l'usuari: «que sigui més random: de vegades torna més enrere, menys, no ho fa, torna endavant en comptes d'enrere, ho fa de forma molt còmica; més probabilitat de caos com més over-the-top»). Fitxers: `templates/organization/wheel.html` (bloc `@finale-start`…`@finale-end`), `judge/views/organization.py` (`get_js_strings`: `finaleCreep/Fake/Wobble/Rewind`), `locale/*/django.po` (8 msgids ×5 idiomes).
1. **El guanyador segueix decidit abans de girar** i el camí acaba **sempre exactament al guanyador**; l'«epíleg» només decideix com s'hi arriba. Des del nivell 6 (el 5 i menys no en tenen: com abans). Tipus i pesos (`k = (L−6)/4`): **res** (35% → 5%), **rebot** (es passa i torna enrere; 30% → 16%), **creep** (s'atura *curt*, batec de cor, i avança *endavant* lentament; 18%), **molla** (oscil·la 3–5 cops, cada cop menys; 9% → 25%), **falsa parada** (s'atura curt ≥0,65 s en silenci, fa «wah-wah» de trombó, i arrenca de cop *endavant* passant-se; 5% → 20%), **rebobina** (es passa molt, pausa, i marxa enrere amb so de cinta; 3% → 15%). L'amplitud també és aleatòria (0,35–1,0 × `1+1,2k`), així que «de vegades més, de vegades menys».
2. **Teatre addicional:** cada tipus té el seu so (`sndBoing`, `sndHeartbeat`, `sndWah`, `sndLurch`, `sndRewind`), canvia la **cara del centre** (🤪 😬 🤨 😱 🙃) i diu una **frase còmica** a la bafarada (p. ex. «Ja s'ha aturat?... NO! 😱», «Marxa enrere! ⏪», «Aquesta roda té massa molla! 🌀»). El punter ara també reacciona quan la roda va **enrere** (la clavilla l'empeny per l'altre costat). El redoble de tambor fa el «bum» quan acaba el gir i després comença el número còmic.
3. **Estructura:** `makeFinale(L, r)`, `buildPath(...)` i `pathAngle(...)` són **funcions pures** (sense DOM ni so; l'aleatorietat s'injecta) perquè es puguin provar a part; la roda només les crida. Els desplaçaments es limiten a ±1,3 rad; l'arrencada de la falsa parada té la velocitat limitada (0,03 rad/ms) perquè en rodes de 2–3 segments no fes un salt sec (ho va detectar la prova: 150° en 260 ms).
4. Les frases noves són **opcionals** al JS (`say()` ignora una llista absent): amb el Python vell no es trenca res.

**Per què:** petició explícita de l'usuari.

**Resultat (verificat):** prova de Node de la lògica pura amb **100.000 tirades** (nivells 6–10, 1–40 segments): acaba **exactament** a `from+delta`, el segment sota el punter és **sempre** el guanyador, cap desplaçament passa de ±1,3 rad, sense salts (pas màxim 0,34 rad per 8 ms, que és la velocitat natural d'arrencada del gir), continuïtat a la unió; i cada tipus fa el que diu (creep només endavant des de curt; rebot i rebobina només enrere; la molla creua el guanyador ≥2 cops; la falsa parada es queda quieta ≥0,6 s i després se'n passa). **Les distribucions pugen i baixen amb el nivell** (50.000 tirades per nivell: «res» 34,5% → 5,1%; caos molla+falsa+rebobina 17% → 61%). Al navegador (CDP, temps real): nivell 10 en 6 tirades seguides → totes amb epíleg i la seva frase (10,5–12,3 s); nivell 6 → barreja d'epílegs i tirades sense (7,4–10,1 s); nivell 5 → 6,6 s i cap epíleg, com abans; 0 errors de JS. Regressió de servidor: **63 OK** (SQLite en memòria) i la plantilla real es renderitza amb la BD real (200, transacció desfeta, sense deixar res). Traduccions als 5 idiomes validades amb `msgfmt --check` i `compilemessages` fet.

**Pendent / limitacions:**
- **Falta el `uwsgi --reload /home/ubuntu/dmoj-site.pid`** per veure-ho al web en viu (els workers que ja han compilat la plantilla no la rellegiran; els que no, la llegiran nova amb Python vell, i funciona: frases opcionals). No s'ha pogut fer sense l'OK explícit de l'usuari (el classificador ho denega si només s'ha demanat la funcionalitat).
- **No s'ha vist ni sentit un epíleg concret a ull**: la lògica està provada per números i pels esdeveniments (so/cara/frase) disparats al navegador, però no s'ha fet cap captura enmig d'una falsa parada, ni s'han escoltat els sons nous (`wah`, `rewind`, `boing`, batec) ni s'ha vist la cara del centre canviar.
- Les 8 frases en en/de/zh són meves, sense revisió d'un parlant natiu.
- Segueixen pendents els dos fitxers meus: `/tmp/wheel.live.copy.html` (error meu, havia d'anar al directori de la sessió) i `~/snap/chromium/common/wheel-test/`: cal el teu sí per esborrar-los.
- Canvis a l'arbre de treball **sense commit**.

### 159. Conversió en massa: 355 enunciats públics passen la imatge del principi al camp «Imatge del problema» (dades; sense canvis de codi)

**Abans:** la imatge de cada enunciat era una etiqueta `<img style="float:right" ...>` escrita a mà al principi del text (entrada #157 = prova amb 3 problemes; #156 = el camp).

**Decisió** (a petició de l'usuari, després de provar els 3: «convertix els 357 que queden»). Script d'un sol ús a la carpeta temporal de la sessió (`conv_all.py`; simulació primer, després `--apply`). **Regla (la mateixa de la prova):** problema **públic i no privat d'organització**, camp d'imatge buit, **una sola** `<img>` al text i **al principi**, amb `src` de `https://jo-el.es/media/problem-images/...` (fitxer existent al disc) i `float:right` dins l'etiqueta. Es treu l'etiqueta del text i s'escriu `problem-images/<fitxer>` al camp (cap fitxer copiat ni mogut: ja eren al mirall).
1. **Traduccions:** una traducció que comença amb la mateixa imatge, també se li treu (346 textos). Si en una traducció hi hagués una altra imatge, el problema **no es converteix** (en sortiria dues): n'hi ha **2** (`pozojubilat`, `professorasubstituta`, traducció `es` amb una altra imatge) i s'han deixat tal qual.
2. **Volum:** **355 problemes, 701 textos** (355 + 346). Còpia de seguretat de tots els textos antics i de quin fitxer s'ha escrit a cada camp: `/home/ubuntu/joel-media/backup-descriptions-imatgecamp-todos-20261105-014909.json` (1,3 MB). Actualitzacions **condicionals** dins una transacció (`update(... description=<text antic>)`: si un text hagués canviat entremig, hauria parat tot sense deixar res a mitges) i `problem_update` per esborrar la caché del fragment i els PDF de cada problema. Llista dels codis convertits: `/home/ubuntu/joel-media/imatgecamp-codis-convertits.json`.
3. **El que es perd** (igual que a la prova): l'`alt` que tenia cada imatge (el nou és buit) i la mida pròpia: ara totes surten a la dreta, **màxim 300 px d'ample i 300 d'alt**. Compte amb els que tenien `width=150`: el fitxer guardat és el doble del que es mostrava (300 px) i ara es veu a 300, o sigui **més gran que abans**.

**Per què:** l'usuari va validar el resultat de la prova i va demanar convertir-ho tot; així tots els enunciats tenen la mateixa imatge, amb la mateixa mida i posició.

**Resultat (verificat):** les **358 pàgines** (355 + 3 de la prova) responen **200** i porten **exactament una** `<img class="problem-image">`; els **331 fitxers distints** d'imatge es serveixen amb 200. Recompte final a la base de dades: públics amb camp d'imatge = 358.

**Pendent / limitacions:**
- **Sense convertir** (no s'ha tocat per no sortir de la regla): **84 problemes públics** amb una `<img>` al text que no compleix la regla (imatge enmig del text, `float:none`, amb imatge d'imgur, la d'una URL externa, etc.), **13 públics** amb 2 o més imatges, els 2 saltats i **tots els no públics** (224 amb una imatge + 4 amb dues); els **privats** els vaig deixar perquè l'usuari va parlar dels 357 públics.
- **No l'he vist amb els ulls** en un navegador: només el HTML i els codis de resposta. L'usuari va veure la prova de 3.
- **Per desfer-ho:** restaurar els 701 textos de la còpia de seguretat i posar `image` a NULL dels 355 problemes (cal el teu sí abans).
- Canvis a la base de dades. **Sense commit.**

---

### 160. «Guia per a crear problemes» (`/creaproblemes/`): punt nou sobre el camp «Imatge del problema», en 5 idiomes

**Abans:** la guia explicava els camps del formulari de l'admin (Codi, Nom, Creadors, Descripció...) però no deia res de les imatges.

**Decisió** (a petició de l'usuari: «quan acabis, converteix la guia de crear problemes també»). Un punt nou **«Imatge del problema»**, just abans de «Descripció» (és l'ordre del formulari des de l'entrada #156): puja una il·lustració (JPEG, PNG, GIF o WebP, fins a 12 MB), es mostra **sola a la dreta**, igual en tots els idiomes i al PDF, **no cal escriure cap `<img>`**, es redueix sola i es veu com a màxim a 300 px; només una per problema.
1. **Pàgina base en català** (`FlatPage`) i les 4 traduccions (`FlatPageTranslation`: es, en, de, zh-hans), amb el nom del camp tal com surt a l'admin de cada idioma: *Imatge del problema*, *Imagen del problema*, *Problem image*, *Problembild*, *题目图片*. Actualitzacions condicionals dins una transacció. Còpia de seguretat dels textos antics: `/home/ubuntu/joel-media/backup-guia-creaproblemes-20261105-015045.json`.
2. **`locale/{de,zh_Hans}/LC_MESSAGES/django.po`:** els 6 msgids del camp (entrada #156) ja eren en ca/es; ara també en **alemany i xinès** (els he escrit jo, sense revisió d'un parlant natiu) i `.mo` recompilats; així l'etiqueta de l'admin coincideix amb la de la guia. Efectiu amb el **proper `uwsgi --reload`** (els catàlegs es carreguen en arrencar).

**Resultat (verificat):** `/creaproblemes/` respon 200 i mostra el punt en català i en castellà; `msgfmt --check` correcte per a de i zh_Hans (1.771 i 1.751 missatges traduïts).

**Pendent / limitacions:**
- **La captura `problemes-admin.png` no mostra el camp nou** (és d'abans). Com que el punt el descriu en text no es contradiu, però es pot tornar a fer (el procediment és a la memòria del projecte: GET de la pàgina d'admin amb el client de proves i una sessió signada, i fer-ne la foto).
- Els textos en alemany i xinès de la guia són meus, sense revisió.
- Canvis a la base de dades i a `.po`/`.mo` (els `.mo` no van a git). **Sense commit.**

### 161. Conversió en massa dels enunciats NO públics: 145 problemes passen la imatge del principi al camp «Imatge del problema» (dades; sense canvis de codi)

**Abans:** després de l'entrada #159 (358 públics), els problemes privats i els privats d'organització seguien amb l'`<img>` escrita a mà.

**Decisió** (a petició de l'usuari: «si, fes també els no públics»). Mateix script i **mateixa regla** que a #159 canviant només el filtre: `is_public = False` **o** `is_organization_private = True`. Una sola `<img>` al principi del text, de `https://jo-el.es/media/problem-images/...` (fitxer al disc) i amb `float:right`; la traducció que comença amb la mateixa imatge també se la treu; si en una traducció hi hagués una altra imatge, es saltaria el problema (no ha passat mai: **0 saltats**).
1. **Volum:** **145 problemes, 170 textos** (145 + 25 traduccions). Còpia de seguretat: `/home/ubuntu/joel-media/backup-descriptions-imatgecamp-nopublics-20261105-095214.json` (360 KB); codis: `/home/ubuntu/joel-media/imatgecamp-codis-convertits-nopublics.json`. Actualitzacions condicionals dins una transacció i `problem_update` (caché i PDF) per a cadascun.
2. **El que es perd:** igual que a #159 (l'`alt`, i la mida pròpia: ara màx. 300×300 a la dreta; els de `width=150` es veuen més grans).

**Per què:** que tot el que té la forma estàndard quedi uniforme, també els problemes en preparació dels professors.

**Resultat (verificat):** com que un visitant anònim veu un 404 als no públics, he carregat **les 145 pàgines dins del servidor amb un superusuari** (client de proves, **caché en memòria** perquè no es toqui la real, i **transacció desfeta**): totes **200** amb **exactament una** `<img class="problem-image">` amb la URL del camp; els **120 fitxers distints** existeixen al disc. Cap dels 145 és públic (0). Recompte total de problemes amb camp d'imatge: **503** (358 públics + 145 no públics). `/tmp/media/problem-images` continua amb 574 fitxers.

**Pendent / limitacions:**
- **Sense convertir:** **84 públics** i **79 no públics** amb una `<img>` d'una altra forma (enmig del text, `float:none`, URL externa/imgur, etc.) i **13 públics + 4 no públics** amb 2 o més imatges. Cal fer-ho a mà o amb una regla nova (TODO #24).
- **No vist en un navegador** (només HTML i codis de resposta; l'usuari va validar la prova de 3).
- **Per desfer-ho:** restaurar els 170 textos de la còpia i posar `image` a NULL dels 145 problemes (cal el teu sí abans).
- Canvis a la base de dades. **Sense commit.**

### 162. «Protecció contra la mala sort» oculta per al superllegendari del gacha (codi + migració 0170; **activa des del 2026-11-06 11:03**)

**Abans:** el superllegendari era una tirada a part amb un **0,2 % fix** (`Achievement.SUPERLEGENDARY_CHANCE = 1/500`), sense cap compensació per la mala sort. Dades reals (només lectura) abans de decidir: **6 superllegendaris** i només **36 obtencions** entre **2.006 usuaris** amb alguna tirada (26 són «Dret a Crear Achievements», amb pocs rolls al darrere: sembla que es van obtenir quan encara no era super, o a mà; no verificat); tirades per usuari: mediana 24, p90 105, p99 232, màxim 545, només 33 usuaris en tenen 200 o més. Amb el 0,2 % fix, un alumne amb 100 tirades només té un **18 %** de probabilitat d'haver vist algun super, i la cua és il·limitada (p99 = **2.301** tirades).

**Decisió** (a petició de l'usuari: «sistema de bad luck protection… en secret», i després «comença amb la teva proposta del 0,005pp. Potser pujar-ho a partir de 100+ i 200+?»). Cada tirada que **no** és superllegendari en puja la probabilitat i en **baixa** la del llegendari normal en la mateixa quantitat; en sortir un, el comptador torna a 0.
1. **`judge/gacha_pity.py` (nou):** lògica pura i única «maneta» `SUPERLEGENDARY_PITY_STEPS = ((0, 0.00005), (100, 0.0001), (200, 0.0002))`: **+0,005 pp per tirada fins a la 100, +0,01 pp de la 100 a la 200 i +0,02 pp a partir de la 200** (el pendent es duplica cada 100 tirades seques). Topall: el «sòl especial» superllegendari + llegendari (**5,19 %**) es conserva sempre, així el llegendari arriba exactament a **0 %** a la tirada **375** i la resta (comú, rar, èpic) **no es mou mai** en valor absolut. Valors: 0,20 % (0 tirades), 0,70 % (100), 1,70 % (200), 3,70 % (300), 5,19 % (375 o més).
2. **`Profile.gacha_pity`** (`PositiveIntegerField`, per defecte 0) i **migració `0170_profile_gacha_pity`** (generada amb `makemigrations`; conté només aquest camp). **No s'ha afegit a l'administració de perfils** a propòsit: els responsables d'institut la poden obrir i se'n filtraria el secret.
3. **`GachaGo.gacha_roll`:** ara calcula primer els superllegendaris que falten (una consulta per tirada; abans només quan sortia el 0,2 %). Si en falta algun, tira amb la probabilitat de la ratxa; si no surt, el sorteig normal usa els pesos de la ratxa. **Qui ja té tots els supers** no té protecció: tirada normal 65/20/10/5 exacta i el comptador no es toca (si no, el llegendari li aniria a 0 % per sempre). El comptador es desa amb el `profile.save()` de sempre: +1 per tirada sense super (només si en pot sortir un), 0 en sortir-ne un. Els 0,65/0,85/0,95 escrits a mà a la vista passen a les constants de `gacha_pity.py`.
4. **`GachaMain` (pàgina del gacha):** continua mostrant les **probabilitats base** (0,2 % / 4,99 % / …); `GACHA_TIER_CHANCES` ara és un àlies de `NORMAL_TIER_CHANCES`.

**Per què:** el pendent és el que decideix l'efecte, no el 5 % final. Una rampa cada tirada, plana, de +0,005 pp dona mediana **132** tirades; amb els trams 100+/200+ la mediana és **129** i la cua es redueix (p90 266 → **233**, p99 390 → **306**), perquè afecten sobretot els qui ja n'han fet moltes. Per a un alumne casual (24 tirades) el canvi és de pocs punts percentuals: els supers segueixen sent rars, però ja no existeix la mala ratxa de més de 400 tirades. Taula (probabilitat d'haver-ne vist un a les 100 / 200 / 300 tirades): abans **18 / 33 / 45 %**, ara **36 / 81 / 99 %**; tirades fins al primer: mitjana 500 → **133**, mediana 347 → **129**, p90 1.151 → **233**, p99 2.301 → **306**.

**Resultat (verificat, sense tocar producció):**
- Lògica pura (`manage.py shell`, sense escriure res): corba exacta als 6 punts, tope a la 375, monotonia, suma de probabilitats = 1 i llegendari = sòl − super a 11 ratxes, comú/rar/èpic idèntics a la ratxa 0, la ratxa 0 reprodueix **exactament** les probabilitats d'abans i `None` (qui ho té tot) dona 65/20/10/5; el sorteig coincideix amb les freqüències teòriques en 400.000 mostres per cas (desviació màxima 0,0011), i una simulació de 100.000 jugadors dona mitjana 133 / mediana 130 / p90 233 / p99 307 (anàlisi: 133 / 129 / 233 / 306).
- **La vista real `gacha_roll`** contra una **SQLite en memòria** (afirmat `:memory:`, caché i correu en memòria; totes les taules creades): comptador +1 per tirada sense super i 0 després d'un super (400 tirades), en el topall **5,25 %** de supers i **0** llegendaris amb comú/rar/èpic = 65,2 / 19,9 / 9,7 % (4.000 tirades), qui té tots els supers: **0** supers, llegendari 5,35 %, comú/rar/èpic 64,6 / 19,6 / 10,5 % i el comptador no es mou; la pàgina segueix llistant 65/20/10/5 i la primera tirada costa 5 punts. `manage.py check` sense problemes.

**Pendent / limitacions:**
- **Desplegat el 2026-11-06 (l'usuari, amb `!`: el classificador em va denegar la migració com a «Production Deploy»):** `migrate judge` va aplicar la `0170` i el `uwsgi --reload` va deixar 6 workers nous a les 11:03:58. L'ordre importava (migrar abans de recarregar). Detall: la columna és `int(10) unsigned NOT NULL` **sense valor per defecte a la base de dades** (Django el treu després d'afegir-la) i el MySQL és `STRICT_TRANS_TABLES`; per això, entre la migració i el reload, el codi antic no hauria pogut crear cap perfil nou (una alta). Va quedar en uns segons.
- **Verificació en producció:** la columna existeix, **0 de 5.716 perfils** tenen el comptador diferent de 0, portada/problemes/usuaris responen 200, `/gacha/` 302 (login) i el registre del web no té cap error. Prova real amb un **usuari fals i transacció desfeta** (caché i correu en memòria perquè un super amb fanfàrria no enviï cap correu real): `POST /gacha/go/` → 302 a la pàgina de resultat (que respon 200), ratxa desada (1 després d'una tirada comuna; +1 a cada tirada i 0 després d'un super), 5 punts de cost; forçant la ratxa al topall mentre encara es podia treure un super: **0 llegendaris en 137 tirades** i 6 supers (4,4 %); en tenir els **6 superllegendaris** (n'hi ha exactament 6 a la base de dades) passa a ser exempt: **0 supers i 20 llegendaris en 463 tirades (4,3 %)**, com cal. Un primer intent va semblar un error (14 llegendaris): era l'exempció, no un defecte. Comptadors idèntics abans i després (5.716 / 5.716 / 84.492) i cap usuari de prova a la base de dades.
- **Tothom comença a 0**, també els 33 usuaris amb 200 o més tirades; es podria inicialitzar amb les tirades des del seu últim super (un «regal» que no s'ha decidit).
- **Efectes col·laterals que cal vigilar:** els superllegendaris porten avantatges (Descompte al Gacha, Pista Extra, Bonus diari doble, Assegurança Antirepetits), que es repartiran molt més; i si «Dret a Crear Achievements» és un dels 6, uns ~230 alumnes amb més de 100 tirades poden generar una trentena de correus i de permisos per donar a mà.
- El «secret» és **«no anunciat»**: el repositori és públic a GitHub (`malbareda/JOEL-web`).
- Tot ajustable des de `SUPERLEGENDARY_PITY_STEPS`; per mesurar-ho caldria comptar quantes tirades portava cadascú en obtenir un super (no es guarda).
- Canvis al codi i una migració **aplicada**. **Sense commit.**

### 163. Protecció contra la mala sort per a qui ja portava més de 100 tirades sense cap superllegendari (dades; sense canvis de codi)

**Abans:** després de l'entrada #162 el comptador `Profile.gacha_pity` començava a 0 per a tothom, també per als alumnes que ja portaven moltes tirades sense cap super.

**Decisió** (a petició de l'usuari: «posa protecció als alumnes amb més de 100 tirades sense cap dels 6 superllegendaris»). A cada alumne amb **més de 100 tirades** (files d'`AchievementObtained`; el codi només en crea a la tirada del gacha) i **cap dels 6 superllegendaris** se li posa `gacha_pity` = **les tirades que porta**, com si la protecció hagués existit des del principi. «Més de 100» és estricte (3 alumnes amb exactament 100 queden fora) i els que ja tenen algun super també (11), tal com es va demanar.
1. **Volum:** **219 alumnes** (230 tenen més de 100 tirades; 11 excloses). Tirades: mínim 101, mediana 130, màxim 545. Probabilitat de super per tirada just després: 144 alumnes entre 0,71 i 1,20 %, 43 entre 1,21 i 1,70 %, 24 entre 1,72 i 3,70 %, 4 entre 3,72 i 5,19 % i **4 ja al topall (5,19 %)**.
2. **Com:** una sola transacció, una actualització per perfil condicionada a `gacha_pity = 0` (si algú tirava entremig, es saltava; **0 saltats**). Només s'ha tocat aquesta columna.
3. **Còpia de seguretat:** `/home/ubuntu/joel-media/gacha-pity-seed-20261106-110910.json` (valors anteriors, tots 0, i valors nous).

**Per què:** són els alumnes a qui la mala sort ha afectat més i, com que la protecció és progressiva, a la majoria no els canvia la vida (la mediana puja només al 0,9 % per tirada), però els que superen les 300 tirades ja es troben a prop del topall.

**Resultat (verificat):** 219 actualitzats, 0 saltats; els valors coincideixen amb les tirades de cadascú; **cap dels que tenen un super** ha rebut comptador. Hi ha un perfil més amb comptador (id 19828): un alumne real amb 74 tirades que va tirar a les 11:06 (després del reload) i ha passat de 0 a 1, o sigui que **el comptador ja funciona en producció amb un alumne real**.

**Per desfer-ho:** posar `gacha_pity = 0` als perfils de la clau `previous` del JSON (cal el teu sí abans).

**Pendent / limitacions:**
- Les files d'`AchievementObtained` inclouen els regals fets a mà des de l'administració (no es poden distingir), així que alguns comptadors poden ser lleugerament alts.
- Els alumnes que ja tenen algun super però no tots (11 amb més de 100 tirades) comencen a 0; si es vol, es pot posar la protecció també a ells.
- Canvi a la base de dades. **Sense commit.**

### 164. Recuperades 3 animacions que el mirall d'imatges havia deixat en una imatge fixa (`travolta`, `jocvida`, `magradalosu`)

**Què va passar:** a l'entrada #147 (còpia local de les imatges dels enunciats) vaig tornar a codificar les imatges amb Pillow, i això deixa **només el primer fotograma**. L'script ja conservava els GIF animats tal qual, però amb **dues excepcions que vaig deixar sense animació**: (1) un GIF animat de **més de 3 MB** es convertia en imatge fixa («massa gran, faig servir el primer fotograma») i (2) només es reconeixia el **GIF**, no el **WebP animat**. L'usuari ho va veure: «hem perdut algunes animacions com la del joc de la vida i la del travolta».

**Abast** (comprovat mirant els 533 originals descarregats que encara tinc a la carpeta temporal de la sessió; els altres 48 URL del manifest són els substituts que vaig triar jo i els exemples del `casinosort`, tots fixos): **exactament 3** imatges animades havien perdut l'animació, 5 GIF animats s'havien conservat bé.
1. **`travolta`** (públic): GIF de `c.tenor.com`, 498×483, **74 fotogrames, 4,1 MB** (superava els 3 MB).
2. **`jocvida`** (públic): «Game_of_life_animated_glider_2.gif» de wikia, que en realitat és un **WebP animat** (336×336, 14 fotogrames, **2 KB**).
3. **`magradalosu`** (**no públic**): GIF de gfycat, 444×250, **457 fotogrames, 4,5 MB**.

**Decisió i canvis:**
1. Els tres **originals, byte per byte, sense tornar-los a codificar**, copiats a `/home/ubuntu/joel-media/problem-images/` amb **noms nous** (hash del contingut): `2218e7214f0f70460685.gif`, `e32bc6df206f8bcc31df.webp`, `684d1c468817c4b45712.gif`. **Nom nou perquè nginx serveix `/media` amb `expires max`**: si hagués canviat el contingut d'una URL ja existent, els navegadors que ja havien vist la imatge fixa l'haurien guardada per sempre.
2. **Base de dades** (canvis només de la ruta de la imatge, amb actualització condicional dins d'una transacció): `Problem.image` de `travolta` i `jocvida` (ja estaven al camp de l'entrada #159) i el `src` de la imatge dins la descripció de `magradalosu` (no havia estat convertida). Després, `problem_update` de cada problema (caché i PDF).
3. **Manifest** (`problem-images-manifest.json`) actualitzat amb les 3 entrades noves (`src` = `GIF(animated)` / `WEBP(animated)`).
4. **Script del repositori** `tools/mirror_problem_images/4_convert_images.py` **corregit**: ara conserva sense tocar qualsevol animació (**GIF, WebP animat i APNG**) fins a **8 MB** i, si en superés, **avisa i no la converteix** (mai més la deixa en un sol fotograma).
5. **Còpies de seguretat:** manifest anterior `/home/ubuntu/joel-media/problem-images-manifest.ABANS-animats-20261110-122818.json` i `/home/ubuntu/joel-media/backup-animats-20261110-122818.json` (quin camp tenia quin fitxer abans).

**Resultat (verificat):** els tres fitxers es serveixen amb 200 i el tipus correcte (`image/gif`, `image/webp`, `image/gif`) i, **descarregats pel web**, tenen **74, 14 i 457 fotogrames**; les pàgines `/problem/travolta` i `/problem/jocvida` apunten als fitxers nous. `magradalosu` és no públic: he comprovat el fitxer i la base de dades, no la pàgina renderitzada. **No les he vist moure's en un navegador.**

**Pendent / limitacions:**
- **Pesen 4,1 i 4,5 MB** (igual que abans a tenor i gfycat). Es podrien aprimar redimensionant els fotogrames, però aquí no hi ha `gifsicle` ni `ffmpeg` i Pillow 7.2 no compon bé tots els GIF; no ho he fet per no arriscar-me a trencar-los.
- **Els tres fitxers fixos antics queden al disc** (`85d8958f49c7b5705e8f.png`, `ab22fa360b3af465f9e9.png`, `3a2ced43976dbe23623e.png`), sense cap referència; no els he esborrat (cal el teu sí).
- ~~El nou camp «Imatge del problema» només acceptava GIF animats de fins a 2 MB~~ **Resolt**: l'entrada #165 puja el límit a 8 MB (cal el `uwsgi --reload` perquè tingui efecte).
- Canvis a la base de dades i a fitxers. **Sense commit.**

### 165. «Imatge del problema»: el límit dels GIF/WebP animats puja de 2 MB a 8 MB

**Abans:** `judge/utils/problem_image.py` rebutjava qualsevol imatge animada de més de 2 MB (`MAX_ANIMATED_BYTES = 2 * 1024 * 1024`), de manera que un GIF com el del Travolta (4,1 MB, entrada #164) no es podia pujar des de l'admin.

**Decisió** (a petició de l'usuari: «apuja el límit a 8 MB»). Una sola línia: `MAX_ANIMATED_BYTES = 8 * 1024 * 1024`. El límit general d'una pujada (qualsevol imatge) **no canvia: 12 MB**. Les animades es continuen guardant **sense tornar-les a codificar** (si es re-codifiquessin es perdria l'animació) i el missatge d'error ja treu el número del límit, així que ara diu «8 MB». Coherent amb el límit de 8 MB que he posat a l'script del mirall (`4_convert_images.py`, entrada #164).

**Resultat (verificat, directament contra la funció, sense tocar la base de dades ni els fitxers reals):** un GIF animat de **7,8 MB** s'accepta, amb els **80 fotogrames** i els **bytes idèntics**; un de **10,8 MB** (entre 8 i 12) es rebutja amb «La imatge animada és massa gran (8 MB com a màxim).».

**Pendent / limitacions:**
- **Falta `! ~/dmojsite/bin/uwsgi --reload /home/ubuntu/dmoj-site.pid`**: els workers actuals tenen carregat el mòdul amb el límit antic (2 MB). Fins aleshores l'admin segueix rebutjant els GIF de més de 2 MB.
- Una animació de 8 MB és molt pesada per a una pàgina de problema (tothom l'ha de baixar); el límit és només una xarxa de seguretat.
- Canvi de codi. **Sense commit.**

---

## 2026-11-10

### 166. «Eclipsi Solar (Sense Bucles de Veritat)» (`eclipsitest`, id 651): fora el bucle de casos de prova de l'entrada i de les dades (dades; sense canvis de codi)

**Abans:** el problema `eclispisolar` (id 625, «Eclipsi Solar») és del tipus «Sense Bucles», però el seu enunciat deia «La primera línia indica els casos de prova a considerar» i cada fitxer de dades començava amb un nombre de casos seguit d'una línia per cas; és a dir, l'alumne havia de fer un bucle per llegir l'entrada. L'usuari en va fer una còpia, `eclipsitest` (id 651, grup `Codejam`, tipus «Sense Bucles», autor `marc`, 8 llenguatges), perquè hi apliqués la correcció. Aquesta còpia tenia `ProblemData(checker='linecount', caseformat='standard')`, el zip `/judge/eclipsitest/casos-20240509T102003Z-001.zip` (amb `casos/1.in/.out` = 4 casos i `casos/2.in/.out` = 8 casos, més un `casos/eclipsi.zip` niat que hi sobrava) i 2 `ProblemTestCase` de 5 punts cadascun (`casos/1.in`, `casos/2.in`).

**Decisió** (a petició de l'usuari: «editis el problema i casos de prova per a eliminar el bucle de casos de prova»). Només s'ha tocat el 651; **el 625 original no s'ha tocat** (té 212 trameses). Script a l'àrea de treball de la sessió, amb mode simulació (`--apply` per escriure) i validació prèvia:
- **Dades:** cada un dels 12 valors (4 + 8) passa a ser un cas independent. Zip nou `/judge/eclipsitest/eclipsitest.zip` amb `acin.N.in/out` (N = 1..12), un sol número per fitxer, LF i salt de línia final, i `caseformat='indiv'`, com el patró dels problemes bàsics (`parellsenar`…). Els 2 `ProblemTestCase` existents es reutilitzen (es canvia el nom del fitxer, els punts passen a 1 i el `checker` del cas a buit perquè hereti el del problema) i se'n creen 10 de nous; `ProblemDataCompiler.generate` ha regenerat `init.yml` (12 casos, `checker: linecount`). Ordre: els 4 de l'exemple de l'enunciat primer, després els 8 de l'antic segon fitxer.
- **Enunciat:** a `## Entrada`, «La primera línia indica els casos de prova a considerar. Cada cas és una línia amb 1 número que representa…» passa a «L’entrada és una única línia amb 1 número que representa…» (la resta del text, igual). Els blocs «Exemple d'Entrada/Sortida» (amb el «4» inicial) se substitueixen per `## Exemples` amb una taula HTML de 4 files (365, 8220, 183, 57500), el mateix format dels altres problemes «Sense Bucles». `## Sortida` ja parlava d'una sola línia i no es toca.
- **Sortides recalculades, no copiades:** amb una funció de referència amb enters exactes (`d % 548 == 0` → `TOTAL 0`; `d % 183 == 0` → `PARCIAL 0`; si no, el més proper de `183 - d % 183` i `548 - d % 548`). Abans d'escriure res he comprovat que reprodueix les 12 sortides esperades antigues.

**Per què:** un problema «Sense Bucles» no pot demanar un bucle de lectura, i el bucle de casos era justament el que l'enunciat i les dades imposaven.

**Resultat:**
- Verificat amb el jutge real: una solució Python de 8 línies, sense cap bucle, enviada com a `edgar` (tramesa **382559**, PY3), dóna **AC amb 2,0/2,0 punts, 12/12 casos AC, 0,68 s**.
- **Una sola sortida esperada ha canviat de valor:** el cas `32156467897546413` esperava `NO 132 TOTAL` i ara espera **`NO 131 TOTAL`**. Aquest nombre supera 2^53, de manera que un `double` l'arrodoneix a `…412`, que és el que donava 132; amb enters exactes (`32156467897546413 mod 548 = 417`) falten 131 dies. Amb l'antic valor, una solució amb enters exactes (`long` de Java/C++, `int` de Python) hauria fallat un cas correcte. Les altres 11 sortides coincideixen amb les antigues. Si es volgués conservar el valor antic, és editar `acin.6.out` al zip.
- Les 3 trameses que hi havia al 651 (totes de `marc`, JAVA11: AC, AC, WA, del 2024-05-09) **no s'han tornat a jutjar**: conserven el veredicte antic i el seu codi llegia el nombre de casos de la primera línia.
- No s'ha esborrat res: **el zip antic `/judge/eclipsitest/casos-20240509T102003Z-001.zip` queda al disc**, sense cap referència (cal el teu sí per esborrar-lo). La tramesa 382559 d'`edgar` també queda (els 2,0 punts compten al seu perfil, com amb els altres problemes de referència).
- Pendent: el 651 no té traducció `es` (el 625 sí; es podria copiar). Canvi a la base de dades i a fitxers. **Sense commit.**

### 167. «Les croquetes de la mama» (`lescroquetesdelamama`, id 441): enunciat reescrit en català i castellà; es fixa la regla de l'empat (dades; sense canvis de codi ni de casos de prova)

**Abans:** l'usuari va avisar que l'enunciat era molt confús i que a l'exemple apareixien «croquetes grans» que no sortien enlloc del text. Revisat el problema (grup `Primers Passos`, tipus «Sense Bucles», autors `gemma` i `orejasm`, 119 trameses, `linecount`, 6 casos de prova d'1 punt):
- L'enunciat deia que hi ha croquetes «**normals**» (4 g) i «petites» (2.5 g), però la sortida esperada (els 6 `.out` i els exemples) diu `croquetes **grans**`. El mot «grans» no sortia mai al text.
- `## Sortida` només parlava de «el número de croquetes… de la paella», sense dir el format exacte de les 3 línies ni que hi ha una tercera línia amb la carn que sobra (que només s'insinuava a «També volem saber si sobra carn o no»), ni que va amb un decimal (`0.0`, `1.5`…), ni que `croquetes` va sempre en plural (el cas de prova 4 espera `1 croquetes petites`), ni els 4 noms exactes de paella.
- «Com ens agraden els números rodons no utilitzarem grams de carn amb decimals» semblava contradir les croquetes de 2.5 g i la sortida `0.5`; en realitat només volia dir que l'entrada és un enter.
- L'objectiu «aquella mida que sobri menys carn picada» no deia què fer **en cas d'empat**. Comprovat amb una funció exacta: amb 3..1999 g hi ha empat en **297 de 1997** valors (≈15 %; tots els residus 0, 1 i 2 mòdul 20: 20, 21, 22, 40, 41, 42…). Els 6 casos de prova no en tenen cap, i de les **25 solucions amb AC** (Java 8/11/25, Kotlin, Python) unes quantes fan grans en cas d'empat (`grans <= petites`, `petites < grans`…) i unes altres petites (`petites <= grans`, `grans < petites`…): un AC no deia res sobre els empats.

**Decisió** (l'usuari va triar la regla i que no s'afegissin casos de prova). Només s'ha canviat el text; script a l'àrea de treball de la sessió, amb simulació prèvia:
- `Problem.description` (ca) i `ProblemTranslation` `es` reescrits, mantenint l'estructura (`## Entrada`, `## Sortida`, `## Exemples`): mides amb nom (**croquetes grans** 4 g, **croquetes petites** 2.5 g, ja no «normals»), regla de la mida (la de menys carn sobrant, i **si empaten, croquetes grans**), llista de paelles amb rangs explícits (fins a 9 / de 10 a 18 / de 19 a 36 / més de 36), entrada (un enter, mínim 3 g perquè es pugui fer almenys una croqueta), sortida de **3 línies** amb el format exacte de cada una (plural fix, `.5` possible, un decimal) i, sota l'exemple, una **explicació pas a pas dels 3 exemples** (grans i petites, carn que sobra, tria i paella). A la versió `es`, el text és en castellà però avisa que **les paraules de la sortida s'escriuen en català**, tal com surten als exemples, i hi ha la traducció entre parèntesis. La taula d'exemples es manté (només s'ha tret un espai sobrant a la cel·la del primer exemple).
- Abans d'escriure, el script comprova que la regla escrita a l'enunciat (grans guanyen els empats) **reprodueix els 6 casos de prova** tal com els espera el jutge, i que els números de l'explicació (7 → 1 gran/3 g i 2 petites/2 g; 239 → 59/3 g i 95/1.5 g; 68 → 17/0 g i 27/0.5 g) són correctes.
- Després de desar, `judge.signals.problem_update` per buidar la memòria cau del problema (`problem_html`, PDFs).
- Textos antics guardats: `/tmp/claude-1000/-home-ubuntu-educational-online-judge/c68a0bb9-6b92-402b-b306-4e9cca3acc05/scratchpad/croquetes_old_ca.md` i `croquetes_old_es.md`.

**Per què:** l'enunciat havia de descriure el que el jutge realment espera, amb els mateixos noms que la sortida i sense deixar cap decisió amagada.

**Resultat (verificat amb la pàgina real `https://jo-el.es/problem/lescroquetesdelamama`, en català i en castellà):** surt el text nou, ja no hi ha «normals», les llistes, els `code` i la taula es veuen bé. **Els casos de prova, les dades i les 119 trameses no s'han tocat.**

**Pendent / limitacions:**
- La regla de l'empat (grans) **només és al text, no la fa complir cap cas de prova**: les solucions amb AC que fan petites en cas d'empat continuen amb AC. Si es volgués fer complir, calen casos nous amb empat (p. ex. 20 g → `5 croquetes grans`, `paella petita`, `0.0`; i 41 g), i llavors aquestes solucions passarien a WA si es rejutgessin. L'usuari ha decidit de moment no fer-ho.
- `1 croquetes petites` (plural fix) és una rareza heretada del cas de prova 4; ara està explicada al text, no s'ha canviat.
- Canvi a la base de dades. **Sense commit.**

### 168. Botó «No sé ni per on començar» (`ProblemData.help_chat`): fora dels 21 problemes privats i activat a 21 problemes públics d'«Iniciació als bucles» (dades; sense canvis de codi)

**Abans:** hi havia **106** problemes amb el xat d'ajuda activat: 85 públics i **21 privats d'organització** (els exàmens IPED, `diesanyampliat` i `maies1`). Dels problemes públics de tipus «Bucles simples» amb poques punts, només els 9 del grup `Primers Passos` el tenien (`silencisala`, `platanbanana`, `compteenrere`, `casino1`, `casinoplaces`, `comptaasteriscs`, `apostesenars`, `casinosort`, `interval`); `elmeuprimerbucle` (1,9 punts) i els seus companys, no.

**Decisió** (a petició de l'usuari: «treulo de tots els privats i posa'l a tots els de bucles simples que compten pocs punts, com els de "el meu primer bucle"»). Un únic script (mode simulació amb comprovació de recomptes i `--apply`), en una transacció, amb `ProblemData.objects.filter(pk__in=…).update(help_chat=…)`, la mateixa operació que l'acció d'admin «Activa/Desactiva el xat d'ajuda» (`judge/admin/problem.py`); el camp es llegeix directament de la BD a cada petició (`judge/utils/helpchat.py`), per això no cal buidar cap memòria cau.
- **Desactivat (21, tots els que no són públics):** `diesanyampliat`, `maies1`, `ipedm3uf1ex1a`, `ipedm3uf1ex1b`, `ipedm3uf1ex1d`, `ipedm3uf1ex2d`, `ipedm3ra123a1`, `ipedm3ra123a2`, `ipedm3ra123a3`, `ipedm3ra123b1`, `ipedm3ra123b2`, `ipedm3ra123b3`, `ipedm3ra123c1`, `ipedm3ra123c3`, `ipedm3ra123d1`, `ipedm3ra123d2`, `ipedm3ra123d3`, `ipedm3extra123a1`, `ipedm3extra123a2`, `ipedm3extra123b1`, `ipedm3extra123b2`.
- **Activat (21):** els problemes **públics**, del tipus «Bucles simples», amb **≤ 2,5 punts**, dels grups `Introduccio` i `Primers Passos` que encara no el tenien: `elmeuprimerbucle`, `elmeuprimerbuclewhil`, `apostesperdudes`, `apostesperdudes0`, `tiradesperf`, `miprima`, `casinomult`, `numerospositius`, `productenumeros`, `nota10`, `senarsparells`, `positiusnegatius`, `presidentpatata`, `vectors1`, `top50`, `jordiwhile`, `jordiwhile2`, `fafred`, `diguespatata`, `harrisonfor`, `laserlunar`. El llindar de 2,5 inclou el 2,3 d'`interval`, que ja el tenia.
- Les dues llistes queden a `/tmp/claude-1000/-home-ubuntu-educational-online-judge/c68a0bb9-6b92-402b-b306-4e9cca3acc05/scratchpad/helpchat_changes.json`.

**Per què:** el botó és per als problemes molt inicials (diu «pensat per als problemes molt inicials; no surt dins d'un concurs»): no té sentit a exàmens ni a problemes privats, i sí als primers problemes de bucles.

**Resultat (verificat contra la BD):** **106** problemes amb el botó, **0 privats** i 106 públics. Surt sense cap reinici.

**Pendent / limitacions:**
- **No he inclòs 29 problemes públics de «Bucles simples» amb ≤ 2,5 punts d'altres grups**, per si no són per a això: exàmens (`ex3examenbucles`, `ex4examenbucles`, `dam1mp3uf1pr1a`, `dam1mp3uf1pr1b`, `iedammp3uf1p12324`, `iedammp3uf1p22324`, `iedammp3uf1p32324`), Lliga de Programació FP (`estalvipaula`, `sequenciamisteriosa`, `taxacioimmobiliaria`, `animesperdudes`), Codejam/FiraFP (`majmin`, `case`, `silencialasala`), fets per alumnes (`fusta`, `donpollo`, `farmaciarobotica`, `rendimentalumnes`) i `tresiguales`, `sumapatates0`. Si es volen, és una acció d'admin o una línia d'script.
- Tots els «Bucles simples» de 3,0 punts o més (uns 150 de públics) queden sense el botó.
- Canvi a la base de dades. **Sense commit.**

### 169. Botó «No sé ni per on començar» activat a totes les tasques `ifseasy`, `ifandor` i `initbucles` (dades; sense canvis de codi)

**Abans:** després de l'entrada #168 hi havia 106 problemes amb el botó. A les tres tasques només el tenien 10 dels 20 problemes d'`ifseasy`, 9 dels 18 d'`ifandor` i 17 dels 27 d'`initbucles`.

**Decisió** (a petició de l'usuari: «posa'l també a tots els ifseasy/ifandor i initbucles»). Mateixa mecànica que a #168 (`ProblemData.objects.filter(pk__in=…).update(help_chat=True)`, en una transacció), sobre els problemes de les tasques `ifseasy` (`02 01 Alternatives (if, easy) (gg ez)`), `ifandor` (`02 03 Alternatives (AND OR)`) i `initbucles` (`03 00 Iniciació als Bucles`). Mantinc la regla de #168 (només problemes públics; les tres tasques són 100 % públiques, no se n'ha saltat cap). **29 activats:**
- `ifseasy` (10): `eleccions20202`, `eleccions20203`, `etsjove`, `diasetmana`, `pedrapaper`, `diesany`, `parellsenar`, `fizzdiv3`, `codisecret`, `divisiosegura`.
- `ifandor` (9): `divisible110`, `buscarparelles`, `exsbambino`, `muntanyes`, `calorcito`, `muntanyarussa`, `botigaoberta`, `estaciodelany`, `elmigdetres`.
- `initbucles` (10): `sumapatates`, `mesgranpetit`, `donutsamelia`, `lavenda`, `doblebucle`, `momentobanana`, `doblebuclemes`, `trespercinc`, `sumapatates0`, `elmeusegonbucle`.
- Aquesta tanda inclou els 8 problemes dels lots recents d'`ifseasy`/`ifandor` que no el tenien (vegeu la nota de #168). La llista de la tanda és a `/tmp/claude-1000/-home-ubuntu-educational-online-judge/c68a0bb9-6b92-402b-b306-4e9cca3acc05/scratchpad/helpchat_tasks_changes.json`.

**Per què:** són els problemes d'iniciació (alternatives i primers bucles) on l'alumne més necessita l'ajuda per començar.

**Resultat (verificat contra la BD):** `ifseasy` 20/20, `ifandor` 18/18 i `initbucles` 27/27 amb el botó; **135** problemes amb el botó en total i **0 privats**. Surt sense cap reinici.

**Pendent / limitacions:** els problemes que no són de cap d'aquestes tasques (p. ex. els 29 públics d'altres grups llistats a #168) continuen sense el botó. Canvi a la base de dades. **Sense commit.**

### 170. Versions «Easy» (sense sentinella) de 5 problemes d'`initbucles`: `nota10easy`, `tiradesperf0`, `mesgranpetit0`, `elmeuprimerwhile0`, `casinosort0` (problemes nous, ids 1424–1428; dades; sense canvis de codi)

**Abans:** a `initbucles` (27 problemes) 6 llegien l'entrada amb un bucle amb sentinella (acaba en `0` o `-1`): `nota10`, `tiradesperf`, `mesgranpetit`, `elmeuprimerbuclewhil`, `apostesperdudes` i `casinosort`. Només un tenia una versió sense sentinella: `apostesperdudes0` («Apostes perdudes (Easy)», 5 línies fixes). Després de l'anàlisi de l'entrada de la tasca, l'usuari va acceptar la proposta de fer les altres cinc.

**Decisió:** cinc problemes nous, **públics**, a la tasca `initbucles`, que copien del problema original el grup, els tipus, els 9 llenguatges, el límit 1,0 s/65536 KB, els **punts** i el flag `partial`, amb nom `<nom original> (Easy)`, autor `marc`, traducció `es` (nom + « (Easy)»), el botó d'ajuda (`help_chat`, `allowed_tips` com l'original) i `ProblemData(checker='linecount', caseformat='indiv')` amb zip `/judge/<codi>/<codi>.zip` (`acin.N.in/out`, un cas per fitxer, 1 punt cada un, `init.yml` generat per `ProblemDataCompiler.generate`). L'enunciat és el de l'original amb **només el canvi d'entrada** (en català i castellà): «L'entrada consta de N línies…», fora la frase del sentinella i la línia del sentinella a l'exemple (el número de línies s'escriu amb lletres i en majúscula, com a `apostesperdudes0`). L'exemple i la seva sortida són els de l'original.
- `nota10easy` (id **1424**, ← `nota10`, 2,0 punts, no parcial): **7** notes; exemple `4 5 10 7 8 10 12` → `TOTAL NOTES: 6 NOTES10: 2`. 4 casos: `0 10 11 -1 5 9 10` (fronteres 0/10/11/-1) → 5/2; `12 -4 23 60 -7 100 11` → 0/0; set deus → 7/7; `8 6 2 3 7 9 5` → 7/0.
- `tiradesperf0` (id **1425**, ← `tiradesperf`, 1,9, no parcial): **6** tirades, compta els 6; títol `# Tirades perfectes (Easy)`. 4 casos: cap sis, tots sisos, sis al principi i al final, tres sisos.
- `mesgranpetit0` (id **1426**, ← `mesgranpetit`, 3,5, no parcial): **6** números, escriu `màxim mínim`; exemple `10 5 6 -3 -7 1` → `10 -7` (l'original tenia 11 números i dava `10 -8`). 5 casos: tots negatius, tots positius, tots iguals, `-5 0 -3 -8 -2 -9` → `0 -9`, creixent.
- `elmeuprimerwhile0` (id **1427**, ← `elmeuprimerbuclewhil`, 1,9, parcial): **4** línies, cada una més un; exemple `3 1 99 -2`. 3 casos amb 0 i valors grans (`0 -1 5 -6`, `100000 -100000 7 999`, `-1 0 1 2`). Al text he canviat també «Per cada cas de prova caldrà respondre:» per «Per cada número, cal escriure en una línia…», que era una frase que sobrava.
- `casinosort0` (id **1428**, ← `casinosort`, 2,0, parcial): **7** guanys, escriu el màxim; títol `# Jugadors amb sort (Easy)`. 4 casos: tots negatius, màxim al principi, màxim al final, màxim repetit.
- **Codis:** els tres de mida normal segueixen el criteri `0` d'`apostesperdudes0` (`tiradesperf0`, `mesgranpetit0`, `casinosort0`); `nota10easy` no porta `0` (`nota100` es confondria amb una nota) i `elmeuprimerwhile0` s'ha escurçat perquè el codi d'un problema té com a màxim 20 caràcters (`elmeuprimerbuclewhil` ja en fa 20) i només admet `a-z0-9`.
- **Els casos NO són còpia de l'original:** com que ara hi ha un nombre fix de línies i el 0 (o el -1) deixa de ser un final, he escrit casos nous. Cap cas privat és igual a l'exemple. Les sortides es calculen amb una funció de referència, no a mà.

**Per què:** el bucle amb sentinella és més difícil que un bucle de nombre fix; amb una versió «Easy» l'alumne pot començar pel bucle simple, com ja passava a `apostesperdudes0`.

**Resultat (verificat):** (1) **validació abans d'escriure**: l'exemple de cada enunciat dona la sortida que s'hi diu; una comprovació amb errors típics d'alumnes (variable inicialitzada a 0, saltar-se el primer o l'últim, límits 0/10 mal posats, confondre `>=` amb `==`, aturar-se en un 0 per costum del sentinella, etc.): **cap supera tots els casos**; (2) **jutge real**: una solució Python de referència per problema, enviada com a `edgar`, dona **AC amb tots els punts** (trameses 382606–382610: `nota10easy` 2,0/2,0, `tiradesperf0` 1,9/1,9, `mesgranpetit0` 3,5/3,5, `elmeuprimerwhile0` 1,9/1,9, `casinosort0` 2,0/2,0); (3) les pàgines `https://jo-el.es/problem/<codi>` surten en català i en castellà amb l'entrada nova, sense cap resta del sentinella, i els cinc problemes surten a `https://jo-el.es/tasks/initbucles` (32 problemes). La llista de comprovació és l'script de la sessió.

**Pendent / limitacions:**
- **`elmeuprimerwhile0` s'assembla molt a `elmeuprimerbucle`** (id 223), que ja és el mateix exercici (cada número més un) amb el nombre de casos a la primera línia; la diferència és que aquí no hi ha cap línia de recompte. Si es considera redundant, es pot amagar (`is_public`) sense tocar res més.
- Els punts són els dels originals (p. ex. `mesgranpetit0` dona 3,5 igual que `mesgranpetit`, tot i ser «Easy»); es poden abaixar des de l'admin.
- Els enunciats de `tiradesperf0` i `casinosort0` porten el mateix `<img>` que l'original; el títol de l'enunciat de `apostesperdudes0` continua sense «(Easy)» (no s'ha tocat).
- Les 5 trameses d'`edgar` queden (els punts compten al seu perfil). Canvi a la base de dades i a fitxers. **Sense commit.**

### 171. Els 6 problemes «Easy» d'`initbucles` passen a **1,88 punts** perquè surtin abans que els originals en ordenar per punts (dades; sense canvis de codi)

**Abans:** `apostesperdudes0` (1,9), `nota10easy` (2,0), `tiradesperf0` (1,9), `mesgranpetit0` (3,5), `elmeuprimerwhile0` (1,9) i `casinosort0` (2,0) tenien els punts del seu original (entrada #170), de manera que en ordenar per punts quedaven barrejats amb ell (o empatats: 1,9 amb 1,9).

**Decisió** (a petició de l'usuari: «pots fer que els easy siguin de 1.88 punts? perquè quedin abans si ordenes per punts»). Els sis passen a `points = 1.88`. **No he fet servir l'admin ni `rescore_problem`**, perquè aquest arrodoneix els punts de cada tramesa a **1 decimal** (`judge/tasks/submission.py:46`) i 1,88 quedaria a 1,9; el web considera «resolt» una tramesa amb `points == problem.points` exacte (`judge/utils/problems.py`, `judge/views/problem.py`), de manera que **tots els alumnes que ja el tenien resolt haurien passat a «no resolt»**. En lloc d'això, un script, en una transacció, amb la fórmula del jutge (`judge/bridge/judge_handler.py:405`): `round(case_points / case_total * problem.points, 3)`, i `0` si el problema no és parcial i no s'ha fet tot. Només es toquen les trameses ja jutjades (`status='D'`) i només si el valor canvia: **`apostesperdudes0` 120 trameses** (de 167; 159 jutjades) de 109 alumnes, i **1 tramesa d'`edgar` per cada un dels altres cinc**. No he cridat `update_contest()` perquè els punts dins d'un concurs són els del `ContestProblem`, no els del problema. Després, `Profile.calculate_points()` dels 109 + 1 usuaris afectats, esborrant `user_complete:<id>` i `user_attempted:<id>` (com fa `rescore_problem`), i `Problem.update_stats()` de cada problema (`user_count`, `ac_rate`; el `save()` buida també la memòria cau del problema).

**Per què:** l'ordre per punts és la manera de posar la versió fàcil abans que la difícil.

**Resultat (verificat contra la BD i el web):**
- Sis problemes a 1,88; **els alumnes que el tenien resolt, el segueixen tenint resolt** (`apostesperdudes0`: 108 usuaris amb AC, 108 amb `points == problem.points`, abans i després; `user_count` 108, `ac_rate` 64,7 %).
- **Efecte en els punts dels alumnes:** a cadascun dels 108 que tenien `apostesperdudes0` resolt els baixa **0,02 punts** (1,9 → 1,88) en el total; els 5 problemes nous només tenen la tramesa d'`edgar`.
- Ordenat per punts, `initbucles` comença així: `apostesperdudes0`, `nota10easy`, `tiradesperf0`, `mesgranpetit0`, `elmeuprimerwhile0`, `casinosort0` (1,88), després `elmeuprimerbucle`, `compteenrere`, `elmeuprimerbuclewhil`, `casino1`, `apostesperdudes`, `tiradesperf` (1,9)…
- **Els tres «Easy» de la resta del catàleg no s'han tocat:** `patatacalienteeasy` (id 226, 5,0 punts, privat, grup `Experimental`, sense trameses), `taulacremadaeasy` (id 701, «Easy Mode», 12,0) i els originals.

**Pendent / limitacions:**
- **El web mostra els punts amb `floatformat`, així que 1,88 es veu «1,9»** (`templates/problem/list.html:310`; comprovat a la pàgina de `nota10easy` i d'`apostesperdudes0`). L'ordre sí que usa el valor real. Es pot mostrar amb 2 decimals.
- **Si algú desa aquests problemes des de l'admin o els marca públics/privats, `rescore_problem` els arrodonirà a 1 decimal i els alumnes en perdran l'estat de «resolt».** Mateix risc ja existent a `casinoplaces` (1,95). No s'ha tocat el codi; està a `TODO.md` #26 (arreglament: `, 1` → `, 3`; cal reiniciar Celery).
- `mesgranpetit0` passa de 3,5 a 1,88 (el comentari de #170 queda resolt). Canvi a la base de dades. **Sense commit.**

### 172. Tres exercicis d'acumulador passen d'`initbucles` a «03 03 Bucles amb acumulador» (`acumulador`) (dades; sense canvis de codi)

**Abans:** `initbucles` («03 00 Iniciació als Bucles») tenia 32 problemes i `acumulador` («03 03 Bucles amb acumulador») 10 (`productenumeros`, `senarsparells`, `positiusnegatius`, `ambrosio`, `compteambelveri`, `piramidecartes`, `explosionarcana1`, `ambrosiotriangular`, `cargols`, `jordiwhile2`). L'usuari va preguntar quants exercicis d'acumulador hi havia a `initbucles` i, si n'hi havia, va demanar de portar-los a la tasca d'acumulador **en comptes d'`initbucles`**.

**Decisió:** he llegit l'enunciat, la sortida i el primer cas de prova dels 32 problemes. Criteri: la descripció de la tasca destí diu «una suma, un producte, un recompte… sumes i productes de nombres naturals», però els recomptes i els màxims/mínims ja tenen la seva tasca (`comptadors`, «Bucles amb comptador»), així que només he mogut els que **sumen** o multipliquen al llarg del bucle. **3 problemes**, treient-los d'`initbucles` i afegint-los a `acumulador` (`ProblemTask.problems`, en una transacció); **les altres tasques on ja eren es mantenen**:
- `sumapatates` (id 44, 3,0 punts): suma les patates de `k` camions; abans a `initbucles` i `nadal`, ara a `acumulador` i `nadal`.
- `sumapatates0` (id 717, 2,0): el mateix en la versió original; abans només a `initbucles`, ara a `acumulador`.
- `miprima` (id 927, 2,1): suma només els sous de 8000 o més (suma condicional); abans a `initbucles` i `20230300calamot`, ara a `acumulador` i `20230300calamot`.
- **No he mogut, per decisió de criteri** (llistes a l'altra banda, a la resposta a l'usuari): els **recomptes** (`numerospositius`, `nota10`/`nota10easy`, `tiradesperf`/`tiradesperf0`, `apostesperdudes`/`apostesperdudes0`), els **màxims** (`mesgranpetit`/`mesgranpetit0`, `casinosort`/`casinosort0`), `donutsamelia` (mínim comú múltiple), `casinomult` (taula de multiplicar: `N x P = TOTAL` sense acumular), `harrisonfor` (comptar de milió en milió, on es podria fer amb acumulador però el natural és un comptador), `doblebucle`/`doblebuclemes` (bucles dobles), els comptes enrere i intervals, i `trespercinc`.

**Per què:** els tres sumen al llarg del bucle, que és la definició de la tasca d'acumuladors.

**Resultat (verificat contra la BD i el web):** `initbucles` passa de 32 a **29** problemes i `acumulador` de 10 a **13**. A `https://jo-el.es/tasks/acumulador` surten els tres problemes i a `https://jo-el.es/tasks/initbucles` ja no. No he tocat els problemes en si (punts, estat, botó d'ajuda, etc.).

**Pendent / limitacions:** el criteri és meu: si l'usuari vol que `harrisonfor`, `casinomult` o algun recompte també vagin a `acumulador`, és un canvi d'una línia. Canvi a la base de dades. **Sense commit.**

### 173. Alta de la professora `nuria_tort` (Institut Castellet): institut nou, equip tancat de 1r DAM, permisos i logo

**Abans:** l'usuari va reenviar un correu de la **Núria Tort** (correu del domini `inscastellet.cat`), professora de l'**Institut Castellet**, que volia participar a la lliga amb l'alumnat de **1r de DAM** i demanava donar d'alta l'institut «adjuntant el logo». El compte `nuria_tort` (id d'usuari 27723) ja existia (registrat l'11-11-2026 amb aquest mateix correu), sense grups ni permisos; l'institut i l'equip no existien. L'usuari va dir **«sí, fes-ho, conec a la Nuria»** i va passar el logo per Drive.

**Decisió** (el mateix procediment que amb `rosa_rosae`, entrada #151; el classificador va bloquejar el primer intent, fet sense instrucció explícita, i va deixar passar el segon després del sí):
1. **Institut nou** `Institution` id **44**, «Institut Castellet» (slug `institut-castellet`, nom curt «Castellet»), amb el patró dels altres instituts catalans («Institut El Calamot», «INS Poblenou»).
2. **Equip tancat** `Organization` id **222**, «Institut Castellet - 1r DAM» (nom curt «Castellet 1r DAM», slug `institut-castellet-1r-dam`): `is_open=False`, sense `slots` ni `access_code`, de manera que els alumnes sol·liciten entrar i ella accepta. Ella n'és `registrant`, administradora **i membre** (cal ser-ne membre perquè se la reconegui com a responsable d'institut, entrada #59). Ella no va dir si el grup era obert o tancat: he triat **tancat**, el més prudent; ho pot canviar.
3. **Permisos:** grups **«Profe»** i **«Responsable d'Institut»** i `is_staff=True`. **No** s'hi ha afegit «creador de problemes» ni «Editor d'alumnes» (no ho va demanar).
4. **Logo:** `logo_castellet.jpg` de Drive (JPEG, 340×224, 20.379 bytes) a `Institution.image` pel camí normal (emmagatzematge de Django): `/media/institutions/institut_castellet.jpg`. Es mostra tal com el va enviar, com els altres instituts (n'hi ha de 966×227, 828×221...); les plantilles el posen a una mida quadrada fixa (30×30 al llistat i 36×36 a la pàgina de l'institut), així que un logo apaïsat surt comprimit com els altres.

**Resultat (verificat):** `/institutions/`, `/institution/44-institut-castellet` i `/organization/222-institut-castellet-1r-dam` responen **200**; el logo es serveix amb 200 `image/jpeg` (20.379 bytes) i surt a la pàgina de l'institut i al llistat. Amb el codi de l'admin sobre una petició simulada (sense crear cap sessió): `nuria_tort` veu **exactament l'equip 222**, el pot editar i **no** el d'un altre institut (id 3); té `judge.organization_admin` i `judge.view_all_submission`; `administered_institution_ids` = [44]. Només dades: cap fitxer de codi, plantilla ni migració tocat; no s'ha reiniciat res.

**Pendent / limitacions:**
- **No s'ha vist l'acreditació** (carnet del centre) **ni el compromís** de no fer servir els casos de prova i les solucions per fer trampes que demana `/guiaprofes/`: el correu no els portava. L'usuari coneix la professora i va decidir fer l'alta igualment.
- **Cal respondre-li** (no ho he fet; no hi ha cap correu enviat ni esborrany).
- El logo no s'ha posat a l'equip (`logo_override_image`), només a l'institut.
- Canvis a la base de dades i un fitxer a `/media`. **Sense commit.**

---

## Nota de manteniment d'aquest document

A partir d'ara, **cada canvi tècnic fet al servidor o al codi (aquesta sessió i les següents) s'ha de documentar amb una entrada nova en aquest fitxer**, seguint el mateix format (abans / decisió / per què / resultat), immediatament després de fer el canvi.
