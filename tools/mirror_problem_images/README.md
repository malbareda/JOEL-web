# Còpia local de les imatges dels enunciats

Descarrega les imatges externes dels enunciats (i de les traduccions), les redueix i les serveix des del propi servidor.
Fet el 2026-11-03 (entrada #147 de `CANVIS_I_MILLORES.md`). **Els scripts depenen d'aquest ordre i s'executen amb el Python del virtualenv**
(`/home/ubuntu/dmojsite/bin/python`); les carpetes de treball (`dl_*`, `*.json`) són **temporals**: fes servir un `WORK` nou.

1. `WORK=/ruta/nova python 1_survey.py` → `img_rows.json` (totes les imatges `<img src>` i `![](...)` de problemes i traduccions; només llegeix la BD).
2. `WORK=/ruta/nova python -I 2_probe.py` → `probe.json` (només mira capçaleres: «viva», «només sense Referer» o «morta»).
3. Cal escriure un `jobs_*.json` (`[{"url": <original>, "fetch": <URL a baixar>, "ref": true}]`) i executar
   `python -I 3_fetch.py jobs.json <carpeta_nova> out.json` (amb `requests`, pausa per host i `Retry-After`) o `3b_fetch_curl.py` (mateix format, amb `curl`, que
   té una altra pila TLS). Cada passada necessita una carpeta de staging **nova**; hi arriben bytes no fiables que no s'executen mai.
   Per a imatges mortes: `fetch` = `https://web.archive.org/web/2id_/<url>` (Wayback, 4 s entre peticions).
4. `python -I 4_convert_images.py img_rows.json /home/ubuntu/joel-media/problem-images /home/ubuntu/joel-media/problem-images-manifest.json out.json ...`
   → redueix a ~2× l'ample amb què es mostra, recodifica amb PIL (neteja metadades), nom = hash del contingut. Clau del manifest = URL original;
   `override:<codi del problema>:<url>` serveix per a una imatge només per a un problema (cal quan un mateix URL té sentit diferent segons el problema; p. ex. `calorcito`/`alfil`).
5. `python -W ignore 5_rewrite_images.py <manifest.json>` fa una **simulació**; amb `--apply` escriu primer una còpia de seguretat de cada text i després els canvia
   (només l'URL de la imatge) i neteja la memòria cau de cada problema.

**On viuen els fitxers:** `/home/ubuntu/joel-media/problem-images/` (persistent). nginx els serveix com a `/media/problem-images/...` perquè `/tmp/media` és un enllaç a
`/home/ubuntu/joel-media/media`, que conté l'enllaç `problem-images -> /home/ubuntu/joel-media/problem-images` (entrada #148). **`/tmp` s'esborra a cada arrencada** (`systemd-tmpfiles --remove --boot`):
els fitxers no es perden i l'enllaç `/tmp/media` el refà sol una línia `@reboot` del crontab d'`ubuntu` (`ln -s /home/ubuntu/joel-media/media /tmp/media`; veure `TODO.md` #20).

**Pendents:** imgur (`429` des del servidor; torna-ho a provar amb pauses llargues) i la llista de `/home/ubuntu/joel-media/imatges_pendents.tsv`.
