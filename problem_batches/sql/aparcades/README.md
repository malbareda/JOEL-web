# Preguntes SQL aparcades

Preguntes que no s'han pogut crear com a problemes de JOEL i que queden aquí per revisar-les més endavant.
No són fitxers de lot: `create_db_problems` no els fa servir.

- `querytest_resposta_buida.json`: 24 preguntes de QueryTest la consulta de referència de les quals retorna
  0 files amb les dades actuals (p. ex. "factures amb un total que no quadra amb les línies": no n'hi ha cap).
  Amb una referència buida, qualsevol consulta que no retorni res treu AC, així que no s'han migrat.
  Cada entrada porta el codi i el nom del problema on anava, l'enunciat i el SQL original (MySQL).
- `lots_resposta_buida.json`: la pregunta 1 de `sqlsub04` (tematics_subconsultes.json). A SQLite retornava
  110 files per errors de coma flotant; a MySQL la resposta correcta és buida.
- `lots_escriptures.json`: la pregunta 4 de `sqlupd03` (tematics_updates.json). Demana posar 'Pending' a
  `Stays.PaymentType`, però a MariaDB aquesta columna és `ENUM('Card','Cash')` i no ho admet (a SQLite sí, perquè no
  hi ha tipus estrictes).
- `querytest_sakila_resposta_buida.json`: 4 preguntes de QueryTest sobre sakila la referència de les quals retorna 0 files
  amb la sakila oficial carregada (actors sense pel·lícules, clients sense lloguers, pagaments sense lloguer).
- `querytest_bolcat_complet.json`: bolcat complet dels 159 tests de QueryTest (1.460 preguntes, amb enunciat,
  solució i pista originals), descarregat el 2026-10-22 abans de tancar la plataforma. Inclou les bases de
  dades que JOEL encara no té (ies, ies26, sakila, valorantProMatches, cinema...).

Vegeu les entrades #99-#102 de CANVIS_I_MILLORES.md.

Els lots dels problemes migrats de QueryTest són a `../querytest_<bd>.json` (chinook, hotel, miniwind, traders,
northwind, lastnames, sakila, valorantProMatches, futbol24, ies23g) (motor `mysql`, autor `joanq`, codis
`sql<bd>qtNN` fixats amb el camp `code`). A `revisar_enunciats/` hi ha la llista d'enunciats que es van reconstruir
a partir del SQL (a QueryTest només hi havia un títol) o que fan servir funcions que convé revisar.
