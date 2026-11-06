# Chinook PostgreSQL — verificació amb el corrector real (postgres)

## Chinook — Consultes avançades (pgadvquery)

### 1. Per a cada gènere musical que tingui pistes, mostra el nom del gènere (`genre.name`), el nombre total de pistes, quantes d'aquestes pistes duren més de 5 minuts (`milliseconds > 300000`) i quantes no tenen compositor (`composer` és NULL). Fes servir `count(*) FILTER (WHERE ...)`. Columnes, en aquest ordre: nom del gènere, total de pistes, pistes llargues, pistes sense compositor.

Referència:
```sql
SELECT g.name, count(*), count(*) FILTER (WHERE t.milliseconds > 300000), count(*) FILTER (WHERE t.composer IS NULL) FROM genre g JOIN track t ON t.genre_id = g.genre_id GROUP BY g.genre_id, g.name
```

Alternativa (ACCEPTADA):
```sql
SELECT g.name AS genere, count(*) AS pistes, sum(CASE WHEN t.milliseconds > 300000 THEN 1 ELSE 0 END) AS llargues, count(*) - count(t.composer) AS sense_compositor FROM track t JOIN genre g USING (genre_id) GROUP BY g.name
```

Incorrecta (REBUTJADA: Result sets differ (comparing unordered)):
```sql
SELECT g.name, count(*), count(*) FILTER (WHERE t.milliseconds > 300000), count(t.composer) FROM genre g JOIN track t ON t.genre_id = g.genre_id GROUP BY g.name
```

Incorrecta (REBUTJADA: Result sets differ (comparing unordered)):
```sql
SELECT g.name, count(*), count(*) FILTER (WHERE t.milliseconds > 300000), count(*) FILTER (WHERE t.composer IS NULL) FROM genre g LEFT JOIN track t ON t.genre_id = g.genre_id AND t.milliseconds > 300000 GROUP BY g.name
```

### 2. Per a cada client, mostra la seva factura d'import més alt. Si un client tingués dues factures amb el mateix import màxim, queda't amb la més antiga (`invoice_date` més petita) i, si encara empaten, amb la d'`invoice_id` més petit. Resol-ho amb `DISTINCT ON`. Columnes, en aquest ordre: `customer_id`, nom complet del client (`first_name`, un espai i `last_name`), `invoice_id`, data de la factura com a `date` (`invoice_date::date`) i `total`.

Referència:
```sql
SELECT DISTINCT ON (c.customer_id) c.customer_id, c.first_name || ' ' || c.last_name, i.invoice_id, i.invoice_date::date, i.total FROM customer c JOIN invoice i ON i.customer_id = c.customer_id ORDER BY c.customer_id, i.total DESC, i.invoice_date, i.invoice_id
```

Alternativa (ACCEPTADA):
```sql
SELECT customer_id, nom, invoice_id, data, total FROM (SELECT c.customer_id, concat(c.first_name, ' ', c.last_name) AS nom, i.invoice_id, CAST(i.invoice_date AS date) AS data, i.total, row_number() OVER (PARTITION BY c.customer_id ORDER BY i.total DESC, i.invoice_date, i.invoice_id) AS n FROM customer c JOIN invoice i USING (customer_id)) x WHERE n = 1
```

Incorrecta (REBUTJADA: Result sets differ (comparing unordered)):
```sql
SELECT DISTINCT ON (c.customer_id) c.customer_id, c.first_name || ' ' || c.last_name, i.invoice_id, i.invoice_date::date, i.total FROM customer c JOIN invoice i ON i.customer_id = c.customer_id ORDER BY c.customer_id, i.total, i.invoice_date
```

Incorrecta (REBUTJADA: Result sets differ (comparing unordered)):
```sql
SELECT DISTINCT ON (c.customer_id) c.customer_id, c.first_name || ' ' || c.last_name, i.invoice_id, i.invoice_date::date, i.total FROM customer c JOIN invoice i ON i.customer_id = c.customer_id ORDER BY c.customer_id, i.invoice_date DESC
```

### 3. La gerència vol veure com va anar el desembre de 2025 dia a dia, també els dies sense vendes. Per a cada dia del 1 al 31 de desembre de 2025 (genera'ls amb `generate_series`), mostra el dia (tipus `date`), el nombre de factures d'aquell dia, l'import facturat aquell dia (0 si no n'hi ha cap) i l'import acumulat des de l'1 de desembre fins a aquell dia inclòs (funció de finestra `SUM() OVER`). Han de sortir exactament 31 files.

Referència:
```sql
SELECT d::date, count(i.invoice_id), coalesce(sum(i.total), 0), sum(coalesce(sum(i.total), 0)) OVER (ORDER BY d) FROM generate_series(date '2025-12-01', date '2025-12-31', interval '1 day') d LEFT JOIN invoice i ON i.invoice_date::date = d::date GROUP BY d
```

Alternativa (ACCEPTADA):
```sql
WITH dies AS (SELECT generate_series(date '2025-12-01', date '2025-12-31', '1 day')::date AS dia), vendes AS (SELECT invoice_date::date AS dia, count(*) AS n, sum(total) AS import FROM invoice GROUP BY 1) SELECT d.dia, coalesce(v.n, 0), coalesce(v.import, 0), sum(coalesce(v.import, 0)) OVER (ORDER BY d.dia ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) FROM dies d LEFT JOIN vendes v USING (dia)
```

Incorrecta (REBUTJADA: Wrong number of rows: got 6, expected 31):
```sql
SELECT invoice_date::date, count(*), sum(total), sum(sum(total)) OVER (ORDER BY invoice_date::date) FROM invoice WHERE invoice_date >= '2025-12-01' AND invoice_date < '2026-01-01' GROUP BY invoice_date::date
```

Incorrecta (REBUTJADA: Result sets differ (comparing unordered)):
```sql
SELECT d::date, count(*), coalesce(sum(i.total), 0), sum(coalesce(sum(i.total), 0)) OVER (ORDER BY d) FROM generate_series(date '2025-12-01', date '2025-12-31', interval '1 day') d LEFT JOIN invoice i ON i.invoice_date::date = d::date GROUP BY d
```

Incorrecta (REBUTJADA: Result sets differ (comparing unordered)):
```sql
SELECT d::date, count(i.invoice_id), coalesce(sum(i.total), 0), sum(coalesce(sum(i.total), 0)) OVER (ORDER BY d ROWS BETWEEN 1 PRECEDING AND CURRENT ROW) FROM generate_series(date '2025-12-01', date '2025-12-31', interval '1 day') d LEFT JOIN invoice i ON i.invoice_date::date = d::date GROUP BY d
```

### 4. Per als països de facturació (`billing_country`) `USA`, `Canada` i `Brazil`, mostra el nombre de factures i l'import total per país i any (`extract(year FROM invoice_date)`), amb una fila de subtotal per a cada país (any NULL) i una fila de total general (país i any NULL). Fes-ho amb `GROUP BY ROLLUP`. Columnes, en aquest ordre: país, any, nombre de factures, import total.

Referència:
```sql
SELECT billing_country, extract(year FROM invoice_date), count(*), sum(total) FROM invoice WHERE billing_country IN ('USA', 'Canada', 'Brazil') GROUP BY ROLLUP (billing_country, extract(year FROM invoice_date))
```

Alternativa (ACCEPTADA):
```sql
SELECT billing_country, extract(year FROM invoice_date) AS anyfact, count(*), sum(total) FROM invoice WHERE billing_country IN ('USA', 'Canada', 'Brazil') GROUP BY GROUPING SETS ((billing_country, anyfact), (billing_country), ())
```

Incorrecta (REBUTJADA: Wrong number of rows: got more than 19, expected 19):
```sql
SELECT billing_country, extract(year FROM invoice_date), count(*), sum(total) FROM invoice WHERE billing_country IN ('USA', 'Canada', 'Brazil') GROUP BY CUBE (billing_country, extract(year FROM invoice_date))
```

Incorrecta (REBUTJADA: Wrong number of rows: got 15, expected 19):
```sql
SELECT billing_country, extract(year FROM invoice_date), count(*), sum(total) FROM invoice WHERE billing_country IN ('USA', 'Canada', 'Brazil') GROUP BY billing_country, extract(year FROM invoice_date)
```

### 5. Cada client té assignat un agent de vendes (`customer.support_rep_id` → `employee`). Per a cada agent que tingui clients, mostra els seus 2 clients que més han gastat en total (suma de `invoice.total`); en cas d'empat, passa davant el de `customer_id` més petit. Fes-ho amb un `JOIN LATERAL` (o amb funcions de finestra). Columnes, en aquest ordre: nom de l'agent (`first_name`, un espai i `last_name`), `customer_id`, nom del client (`first_name`, un espai i `last_name`) i total gastat.

Referència:
```sql
SELECT e.first_name || ' ' || e.last_name, top.customer_id, top.nom, top.gastat FROM employee e CROSS JOIN LATERAL (SELECT c.customer_id, c.first_name || ' ' || c.last_name AS nom, sum(i.total) AS gastat FROM customer c JOIN invoice i ON i.customer_id = c.customer_id WHERE c.support_rep_id = e.employee_id GROUP BY c.customer_id ORDER BY gastat DESC, c.customer_id LIMIT 2) top
```

Alternativa (ACCEPTADA):
```sql
SELECT agent, customer_id, nom, gastat FROM (SELECT e.first_name || ' ' || e.last_name AS agent, c.customer_id, c.first_name || ' ' || c.last_name AS nom, sum(i.total) AS gastat, row_number() OVER (PARTITION BY e.employee_id ORDER BY sum(i.total) DESC, c.customer_id) AS pos FROM employee e JOIN customer c ON c.support_rep_id = e.employee_id JOIN invoice i ON i.customer_id = c.customer_id GROUP BY e.employee_id, c.customer_id) x WHERE pos <= 2
```

Incorrecta (REBUTJADA: Wrong number of rows: got more than 6, expected 6):
```sql
SELECT e.first_name || ' ' || e.last_name, top.customer_id, top.nom, top.gastat FROM employee e CROSS JOIN LATERAL (SELECT c.customer_id, c.first_name || ' ' || c.last_name AS nom, sum(i.total) AS gastat FROM customer c JOIN invoice i ON i.customer_id = c.customer_id WHERE c.support_rep_id = e.employee_id GROUP BY c.customer_id ORDER BY gastat DESC, c.customer_id LIMIT 3) top
```

Incorrecta (REBUTJADA: Result sets differ (comparing unordered)):
```sql
SELECT e.first_name || ' ' || e.last_name, c.customer_id, c.first_name || ' ' || c.last_name, sum(i.total) FROM employee e JOIN customer c ON c.support_rep_id = e.employee_id JOIN invoice i ON i.customer_id = c.customer_id GROUP BY e.employee_id, c.customer_id ORDER BY sum(i.total) DESC LIMIT 6
```

### 6. Mostra l'organigrama de l'empresa a partir de `employee.reports_to` amb un `WITH RECURSIVE`. Per a cada empleat, mostra `employee_id`, nom complet (`first_name`, un espai i `last_name`), el nivell (1 per a qui no té cap, 2 per als seus subordinats directes, etc.) i el camí de cognoms (`last_name`) des del cap de tot fins a l'empleat, separats per `' > '` (per exemple `Adams > Edwards > Peacock`; per al cap de tot, només el seu cognom). Columnes, en aquest ordre: `employee_id`, nom complet, nivell, camí.

Referència:
```sql
WITH RECURSIVE org AS (SELECT employee_id, first_name || ' ' || last_name AS nom, 1 AS nivell, last_name::text AS cami FROM employee WHERE reports_to IS NULL UNION ALL SELECT e.employee_id, e.first_name || ' ' || e.last_name, o.nivell + 1, o.cami || ' > ' || e.last_name FROM employee e JOIN org o ON e.reports_to = o.employee_id) SELECT employee_id, nom, nivell, cami FROM org
```

Alternativa (ACCEPTADA):
```sql
WITH RECURSIVE cadena(id, nom, nivell, cami) AS (SELECT employee_id, concat(first_name, ' ', last_name), 1, CAST(last_name AS text) FROM employee WHERE reports_to IS NULL UNION SELECT e.employee_id, concat(e.first_name, ' ', e.last_name), c.nivell + 1, concat(c.cami, ' > ', e.last_name) FROM cadena c JOIN employee e ON e.reports_to = c.id) SELECT * FROM cadena
```

Incorrecta (REBUTJADA: Result sets differ (comparing unordered)):
```sql
WITH RECURSIVE org AS (SELECT employee_id, first_name || ' ' || last_name AS nom, 0 AS nivell, last_name::text AS cami FROM employee WHERE reports_to IS NULL UNION ALL SELECT e.employee_id, e.first_name || ' ' || e.last_name, o.nivell + 1, o.cami || ' > ' || e.last_name FROM employee e JOIN org o ON e.reports_to = o.employee_id) SELECT employee_id, nom, nivell, cami FROM org
```

Incorrecta (REBUTJADA: Result sets differ (comparing unordered)):
```sql
WITH RECURSIVE org AS (SELECT employee_id, first_name || ' ' || last_name AS nom, 1 AS nivell, last_name::text AS cami FROM employee WHERE reports_to IS NULL UNION ALL SELECT e.employee_id, e.first_name || ' ' || e.last_name, o.nivell + 1, e.last_name || ' > ' || o.cami FROM employee e JOIN org o ON e.reports_to = o.employee_id) SELECT employee_id, nom, nivell, cami FROM org
```

## Chinook — Funcions (pgfunc)

### 1. Crea la funció `durada_mmss(p_ms integer) RETURNS text` que converteixi una durada en mil·lisegons al format `minuts:segons`, amb els segons sempre amb dues xifres i sense arrodonir (es descarten els mil·lisegons que sobren). Els minuts no tenen límit ni zeros a l'esquerra. Per exemple, `durada_mmss(343719)` és `'5:43'`, `durada_mmss(59999)` és `'0:59'` i `durada_mmss(5286953)` és `'88:06'`. Si el paràmetre és NULL, ha de retornar NULL.

Referència:
```sql
CREATE FUNCTION durada_mmss(p_ms integer) RETURNS text LANGUAGE sql IMMUTABLE AS $$ SELECT (p_ms / 60000) || ':' || lpad(((p_ms / 1000) % 60)::text, 2, '0') $$;
--@@TEST@@ SELECT durada_mmss(343719)
--@@TEST@@ SELECT durada_mmss(59999)
--@@TEST@@ SELECT durada_mmss(5286953)
--@@TEST@@ SELECT durada_mmss(NULL)
--@@TEST@@ SELECT track_id, durada_mmss(milliseconds) FROM track WHERE album_id IN (1, 229) ORDER BY track_id
```

Alternativa (ACCEPTADA):
```sql
CREATE OR REPLACE FUNCTION durada_mmss(p_ms integer) RETURNS text AS $$
BEGIN
  IF p_ms IS NULL THEN
    RETURN NULL;
  END IF;
  RETURN format('%s:%s', floor(p_ms / 60000.0), to_char(floor(p_ms / 1000.0)::int % 60, 'FM00'));
END;
$$ LANGUAGE plpgsql;
```

Incorrecta (REBUTJADA: Test 1 (SELECT durada_mmss(343719)): Result sets differ (comparing unordered)):
```sql
CREATE FUNCTION durada_mmss(p_ms integer) RETURNS text LANGUAGE sql AS $$ SELECT round(p_ms / 60000.0) || ':' || lpad(round((p_ms / 1000.0)::numeric % 60)::text, 2, '0') $$;
```

Incorrecta (REBUTJADA: Test 3 (SELECT durada_mmss(5286953)): Result sets differ (comparing unordered)):
```sql
CREATE FUNCTION durada_mmss(p_ms integer) RETURNS text LANGUAGE sql AS $$ SELECT (p_ms / 60000) || ':' || ((p_ms / 1000) % 60) $$;
```

Incorrecta (REBUTJADA: Test 1 (SELECT durada_mmss(343719)): Result sets differ (comparing unordered)):
```sql
CREATE FUNCTION durada_mmss(p_ms integer) RETURNS text LANGUAGE sql AS $$ SELECT to_char(make_interval(secs => p_ms / 1000), 'MI:SS') $$;
```

### 2. Crea la funció `preu_amb_iva(p_preu numeric, p_iva numeric DEFAULT 21) RETURNS numeric` que retorni el preu amb l'IVA aplicat (`p_iva` és un percentatge) arrodonit a 2 decimals: `round(p_preu * (1 + p_iva / 100), 2)`. Si no es passa el segon paràmetre, s'aplica el 21 %. Si `p_iva` és negatiu o més gran que 100, ha de llançar una excepció amb `ERRCODE = 'invalid_parameter_value'`. Si `p_preu` és NULL, retorna NULL.

Referència:
```sql
CREATE FUNCTION preu_amb_iva(p_preu numeric, p_iva numeric DEFAULT 21) RETURNS numeric LANGUAGE plpgsql AS $$
BEGIN
  IF p_iva < 0 OR p_iva > 100 THEN
    RAISE EXCEPTION 'IVA fora de rang: %', p_iva USING ERRCODE = 'invalid_parameter_value';
  END IF;
  RETURN round(p_preu * (1 + p_iva / 100), 2);
END $$;
--@@TEST@@ SELECT preu_amb_iva(0.99)
--@@TEST@@ SELECT preu_amb_iva(1.99, 10)
--@@TEST@@ SELECT preu_amb_iva(1.99, 0)
--@@TEST@@ SELECT preu_amb_iva(NULL)
--@@TEST@@ SELECT preu_amb_iva(1, -5)
--@@TEST@@ SELECT preu_amb_iva(1, 150)
--@@TEST@@ SELECT track_id, preu_amb_iva(unit_price) FROM track WHERE track_id IN (1, 2819) ORDER BY track_id
```

Alternativa (ACCEPTADA):
```sql
CREATE FUNCTION preu_amb_iva(p_preu numeric, p_iva numeric = 21) RETURNS numeric AS $$
BEGIN
  IF p_iva NOT BETWEEN 0 AND 100 THEN
    RAISE invalid_parameter_value USING MESSAGE = 'IVA incorrecte';
  END IF;
  RETURN round(p_preu + p_preu * p_iva / 100, 2);
END;
$$ LANGUAGE plpgsql;
```

Incorrecta (REBUTJADA: Test 1 (SELECT preu_amb_iva(0.99)): yours gives an error, the expected one returns rows):
```sql
CREATE FUNCTION preu_amb_iva(p_preu numeric, p_iva numeric) RETURNS numeric LANGUAGE plpgsql AS $$
BEGIN
  IF p_iva < 0 OR p_iva > 100 THEN
    RAISE EXCEPTION 'IVA fora de rang' USING ERRCODE = 'invalid_parameter_value';
  END IF;
  RETURN round(p_preu * (1 + p_iva / 100), 2);
END $$;
```

Incorrecta (REBUTJADA: Test 5 (SELECT preu_amb_iva(1, -5)): yours gives an error, the expected one gives an error):
```sql
CREATE FUNCTION preu_amb_iva(p_preu numeric, p_iva numeric DEFAULT 21) RETURNS numeric LANGUAGE plpgsql AS $$
BEGIN
  IF p_iva < 0 OR p_iva > 100 THEN
    RAISE EXCEPTION 'IVA fora de rang: %', p_iva;
  END IF;
  RETURN round(p_preu * (1 + p_iva / 100), 2);
END $$;
```

Incorrecta (REBUTJADA: Test 1 (SELECT preu_amb_iva(0.99)): Result sets differ (comparing unordered)):
```sql
CREATE FUNCTION preu_amb_iva(p_preu numeric, p_iva numeric DEFAULT 21) RETURNS numeric LANGUAGE sql AS $$ SELECT p_preu * (1 + p_iva / 100) $$;
```

### 3. Crea la funció `total_client(p_customer_id integer, p_any integer) RETURNS numeric` que retorni la suma dels imports (`invoice.total`) de les factures del client en aquell any (`extract(year FROM invoice_date)`). Si el client existeix però no té cap factura aquell any, ha de retornar 0 (no NULL). Si el client no existeix, ha de llançar una excepció amb `ERRCODE = 'no_data_found'`.

Referència:
```sql
CREATE FUNCTION total_client(p_customer_id integer, p_any integer) RETURNS numeric LANGUAGE plpgsql AS $$
DECLARE
  v_total numeric;
BEGIN
  PERFORM 1 FROM customer WHERE customer_id = p_customer_id;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'El client % no existeix', p_customer_id USING ERRCODE = 'no_data_found';
  END IF;
  SELECT coalesce(sum(total), 0) INTO v_total FROM invoice
   WHERE customer_id = p_customer_id AND extract(year FROM invoice_date) = p_any;
  RETURN v_total;
END $$;
--@@TEST@@ SELECT total_client(1, 2024)
--@@TEST@@ SELECT total_client(1, 2021)
--@@TEST@@ SELECT total_client(999, 2024)
--@@TEST@@ SELECT c.customer_id, total_client(c.customer_id, 2025) FROM customer c WHERE c.customer_id <= 5 ORDER BY c.customer_id
```

Alternativa (ACCEPTADA):
```sql
CREATE FUNCTION total_client(p_customer_id integer, p_any integer) RETURNS numeric AS $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM customer WHERE customer_id = p_customer_id) THEN
    RAISE no_data_found;
  END IF;
  RETURN (SELECT coalesce(sum(total), 0) FROM invoice
           WHERE customer_id = p_customer_id
             AND invoice_date >= make_date(p_any, 1, 1) AND invoice_date < make_date(p_any + 1, 1, 1));
END;
$$ LANGUAGE plpgsql;
```

Incorrecta (REBUTJADA: Test 2 (SELECT total_client(1, 2021)): Result sets differ (comparing unordered)):
```sql
CREATE FUNCTION total_client(p_customer_id integer, p_any integer) RETURNS numeric LANGUAGE plpgsql AS $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM customer WHERE customer_id = p_customer_id) THEN
    RAISE EXCEPTION 'no existeix' USING ERRCODE = 'no_data_found';
  END IF;
  RETURN (SELECT sum(total) FROM invoice WHERE customer_id = p_customer_id AND extract(year FROM invoice_date) = p_any);
END $$;
```

Incorrecta (REBUTJADA: Test 3 (SELECT total_client(999, 2024)): yours returns rows, the expected one gives an error):
```sql
CREATE FUNCTION total_client(p_customer_id integer, p_any integer) RETURNS numeric LANGUAGE sql AS $$
  SELECT coalesce(sum(total), 0) FROM invoice WHERE customer_id = p_customer_id AND extract(year FROM invoice_date) = p_any
$$;
```

### 4. Crea la funció `pistes_artista(p_artista text) RETURNS TABLE(album text, pista text, durada_seg integer)` que retorni, per a cada pista de l'artista amb aquest nom exacte (sense distingir majúscules de minúscules: `'r.e.m.'` ha de trobar `R.E.M.`, però no `R.E.M. Feat. Kate Pearson`), el títol de l'àlbum, el nom de la pista i la durada en segons sencers (`milliseconds / 1000`, divisió entera). Si l'artista no existeix, no retorna cap fila.

Referència:
```sql
CREATE FUNCTION pistes_artista(p_artista text) RETURNS TABLE(album text, pista text, durada_seg integer) LANGUAGE sql STABLE AS $$
  SELECT al.title, t.name, t.milliseconds / 1000
    FROM artist ar JOIN album al ON al.artist_id = ar.artist_id JOIN track t ON t.album_id = al.album_id
   WHERE lower(ar.name) = lower(p_artista)
$$;
--@@TEST@@ SELECT * FROM pistes_artista('Eugene Ormandy') ORDER BY 1, 2
--@@TEST@@ SELECT * FROM pistes_artista('r.e.m.') ORDER BY 1, 2
--@@TEST@@ SELECT count(*) FROM pistes_artista('AC/DC')
--@@TEST@@ SELECT count(*) FROM pistes_artista('Grup que no existeix')
```

Alternativa (ACCEPTADA):
```sql
CREATE FUNCTION pistes_artista(p_artista text) RETURNS TABLE(album text, pista text, durada_seg integer) AS $$
BEGIN
  RETURN QUERY
    SELECT al.title::text, t.name::text, (t.milliseconds / 1000)::integer
      FROM track t JOIN album al USING (album_id) JOIN artist ar USING (artist_id)
     WHERE ar.name ILIKE p_artista;
END;
$$ LANGUAGE plpgsql;
```

Incorrecta (REBUTJADA: Test 1 (SELECT * FROM pistes_artista('Eugene Ormandy') ORDER BY 1, 2): Wrong number of rows: got 4, expected 3):
```sql
CREATE FUNCTION pistes_artista(p_artista text) RETURNS TABLE(album text, pista text, durada_seg integer) LANGUAGE sql AS $$
  SELECT al.title, t.name, t.milliseconds / 1000
    FROM artist ar JOIN album al ON al.artist_id = ar.artist_id JOIN track t ON t.album_id = al.album_id
   WHERE ar.name ILIKE '%' || p_artista || '%'
$$;
```

Incorrecta (REBUTJADA: Test 1 (SELECT * FROM pistes_artista('Eugene Ormandy') ORDER BY 1, 2): Result sets differ (comparing unordered)):
```sql
CREATE FUNCTION pistes_artista(p_artista text) RETURNS TABLE(album text, pista text, durada_seg integer) LANGUAGE sql AS $$
  SELECT al.title, t.name, round(t.milliseconds / 1000.0)::integer
    FROM artist ar JOIN album al ON al.artist_id = ar.artist_id JOIN track t ON t.album_id = al.album_id
   WHERE ar.name = p_artista
$$;
```

### 5. Crea la funció `estadistiques_album(p_album_id integer, OUT num_pistes integer, OUT durada_min numeric, OUT preu_total numeric)` que, amb paràmetres `OUT`, retorni el nombre de pistes de l'àlbum, la durada total en minuts arrodonida a 2 decimals (`round(sum(milliseconds) / 60000.0, 2)`) i la suma dels preus (`unit_price`) de les seves pistes. Si l'àlbum no existeix, ha de llançar una excepció amb `ERRCODE = 'no_data_found'`. Es cridarà així: `SELECT * FROM estadistiques_album(1)`.

Referència:
```sql
CREATE FUNCTION estadistiques_album(p_album_id integer, OUT num_pistes integer, OUT durada_min numeric, OUT preu_total numeric) LANGUAGE plpgsql AS $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM album WHERE album_id = p_album_id) THEN
    RAISE EXCEPTION 'L''àlbum % no existeix', p_album_id USING ERRCODE = 'no_data_found';
  END IF;
  SELECT count(*), round(sum(milliseconds) / 60000.0, 2), sum(unit_price)
    INTO num_pistes, durada_min, preu_total
    FROM track WHERE album_id = p_album_id;
END $$;
--@@TEST@@ SELECT * FROM estadistiques_album(1)
--@@TEST@@ SELECT * FROM estadistiques_album(9)
--@@TEST@@ SELECT num_pistes, preu_total FROM estadistiques_album(3)
--@@TEST@@ SELECT * FROM estadistiques_album(99999)
```

Alternativa (ACCEPTADA):
```sql
CREATE FUNCTION estadistiques_album(p_album_id integer, OUT num_pistes integer, OUT durada_min numeric, OUT preu_total numeric) AS $$
BEGIN
  SELECT count(t.track_id), round(sum(t.milliseconds) / 60000.0, 2), sum(t.unit_price)
    INTO num_pistes, durada_min, preu_total
    FROM album a LEFT JOIN track t ON t.album_id = a.album_id
   WHERE a.album_id = p_album_id
   GROUP BY a.album_id;
  IF NOT FOUND THEN
    RAISE EXCEPTION USING ERRCODE = 'P0002', MESSAGE = 'Àlbum inexistent';
  END IF;
END;
$$ LANGUAGE plpgsql;
```

Incorrecta (REBUTJADA: Test 4 (SELECT * FROM estadistiques_album(99999)): yours returns rows, the expected one gives an error):
```sql
CREATE FUNCTION estadistiques_album(p_album_id integer, OUT num_pistes integer, OUT durada_min numeric, OUT preu_total numeric) LANGUAGE sql AS $$
  SELECT count(*)::integer, round(sum(milliseconds) / 60000.0, 2), sum(unit_price) FROM track WHERE album_id = p_album_id
$$;
```

Incorrecta (REBUTJADA: Test 1 (SELECT * FROM estadistiques_album(1)): Result sets differ (comparing unordered)):
```sql
CREATE FUNCTION estadistiques_album(p_album_id integer, OUT num_pistes integer, OUT durada_min numeric, OUT preu_total numeric) LANGUAGE plpgsql AS $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM album WHERE album_id = p_album_id) THEN
    RAISE EXCEPTION 'no existeix' USING ERRCODE = 'no_data_found';
  END IF;
  SELECT count(*), sum(milliseconds) / 60000, sum(unit_price) INTO num_pistes, durada_min, preu_total FROM track WHERE album_id = p_album_id;
END $$;
```

### 6. Volem gravar una playlist en un CD de capacitat limitada. Crea la funció `omple_cd(p_playlist_id integer, p_minuts integer) RETURNS TABLE(pista_id integer, pista text, acumulat_ms bigint)` que recorri les pistes de la playlist en ordre de `track_id` (amb un bucle `FOR ... IN SELECT`) i hi vagi afegint cada pista **si encara hi cap**: si la durada acumulada més la de la pista no supera `p_minuts * 60000` mil·lisegons, la pista entra; si no, se salta i es continua provant amb les següents (pot ser que una de més curta sí que hi càpiga). Per a cada pista que entra retorna el seu `track_id`, el seu nom i la durada acumulada fins a ella inclosa. Validacions: si `p_minuts` és NULL o no és positiu, excepció amb `ERRCODE = 'invalid_parameter_value'`; si la playlist no existeix, excepció amb `ERRCODE = 'no_data_found'`.

Referència:
```sql
CREATE FUNCTION omple_cd(p_playlist_id integer, p_minuts integer) RETURNS TABLE(pista_id integer, pista text, acumulat_ms bigint) LANGUAGE plpgsql AS $$
DECLARE
  r record;
  v_total bigint := 0;
BEGIN
  IF p_minuts IS NULL OR p_minuts <= 0 THEN
    RAISE EXCEPTION 'Capacitat incorrecta' USING ERRCODE = 'invalid_parameter_value';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM playlist WHERE playlist_id = p_playlist_id) THEN
    RAISE EXCEPTION 'La playlist % no existeix', p_playlist_id USING ERRCODE = 'no_data_found';
  END IF;
  FOR r IN SELECT t.track_id, t.name, t.milliseconds FROM playlist_track pt JOIN track t ON t.track_id = pt.track_id
            WHERE pt.playlist_id = p_playlist_id ORDER BY t.track_id LOOP
    IF v_total + r.milliseconds <= p_minuts * 60000 THEN
      v_total := v_total + r.milliseconds;
      pista_id := r.track_id;
      pista := r.name;
      acumulat_ms := v_total;
      RETURN NEXT;
    END IF;
  END LOOP;
END $$;
--@@TEST@@ SELECT * FROM omple_cd(16, 30) ORDER BY acumulat_ms
--@@TEST@@ SELECT * FROM omple_cd(16, 20) ORDER BY acumulat_ms
--@@TEST@@ SELECT * FROM omple_cd(17, 15) ORDER BY acumulat_ms
--@@TEST@@ SELECT count(*), max(acumulat_ms) FROM omple_cd(1, 74)
--@@TEST@@ SELECT * FROM omple_cd(16, 4)
--@@TEST@@ SELECT * FROM omple_cd(16, 0)
--@@TEST@@ SELECT * FROM omple_cd(16, NULL)
--@@TEST@@ SELECT * FROM omple_cd(999, 30)
```

Alternativa (ACCEPTADA):
```sql
CREATE OR REPLACE FUNCTION omple_cd(p_playlist_id integer, p_minuts integer) RETURNS TABLE(pista_id integer, pista text, acumulat_ms bigint) AS $$
DECLARE
  v_pista record;
  v_limit bigint;
BEGIN
  IF coalesce(p_minuts, 0) <= 0 THEN
    RAISE invalid_parameter_value;
  END IF;
  PERFORM * FROM playlist WHERE playlist_id = p_playlist_id;
  IF NOT FOUND THEN
    RAISE no_data_found;
  END IF;
  v_limit := p_minuts * 60000;
  acumulat_ms := 0;
  FOR v_pista IN SELECT pt.track_id AS id, t.name AS nom, t.milliseconds AS ms
                   FROM playlist_track pt JOIN track t USING (track_id)
                  WHERE pt.playlist_id = p_playlist_id ORDER BY pt.track_id LOOP
    CONTINUE WHEN acumulat_ms + v_pista.ms > v_limit;
    acumulat_ms := acumulat_ms + v_pista.ms;
    pista_id := v_pista.id;
    pista := v_pista.nom;
    RETURN NEXT;
  END LOOP;
END;
$$ LANGUAGE plpgsql;
```

Incorrecta (REBUTJADA: Test 3 (SELECT * FROM omple_cd(17, 15) ORDER BY acumulat_ms): Wrong number of rows: got 2, expected 3):
```sql
CREATE FUNCTION omple_cd(p_playlist_id integer, p_minuts integer) RETURNS TABLE(pista_id integer, pista text, acumulat_ms bigint) LANGUAGE plpgsql AS $$
DECLARE
  r record;
  v_total bigint := 0;
BEGIN
  IF p_minuts IS NULL OR p_minuts <= 0 THEN
    RAISE EXCEPTION 'Capacitat incorrecta' USING ERRCODE = 'invalid_parameter_value';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM playlist WHERE playlist_id = p_playlist_id) THEN
    RAISE EXCEPTION 'No existeix' USING ERRCODE = 'no_data_found';
  END IF;
  FOR r IN SELECT t.track_id, t.name, t.milliseconds FROM playlist_track pt JOIN track t ON t.track_id = pt.track_id
            WHERE pt.playlist_id = p_playlist_id ORDER BY t.track_id LOOP
    EXIT WHEN v_total + r.milliseconds > p_minuts * 60000;
    v_total := v_total + r.milliseconds;
    pista_id := r.track_id; pista := r.name; acumulat_ms := v_total;
    RETURN NEXT;
  END LOOP;
END $$;
```

Incorrecta (REBUTJADA: Test 3 (SELECT * FROM omple_cd(17, 15) ORDER BY acumulat_ms): Wrong number of rows: got 2, expected 3):
```sql
CREATE FUNCTION omple_cd(p_playlist_id integer, p_minuts integer) RETURNS TABLE(pista_id integer, pista text, acumulat_ms bigint) LANGUAGE sql AS $$
  SELECT * FROM (
    SELECT t.track_id, t.name::text, sum(t.milliseconds) OVER (ORDER BY t.track_id)::bigint AS acum
      FROM playlist_track pt JOIN track t ON t.track_id = pt.track_id
     WHERE pt.playlist_id = p_playlist_id) x
   WHERE acum <= p_minuts * 60000
$$;
```

Incorrecta (REBUTJADA: Test 7 (SELECT * FROM omple_cd(16, NULL)): yours returns rows, the expected one gives an error):
```sql
CREATE FUNCTION omple_cd(p_playlist_id integer, p_minuts integer) RETURNS TABLE(pista_id integer, pista text, acumulat_ms bigint) LANGUAGE plpgsql AS $$
DECLARE
  r record;
  v_total bigint := 0;
BEGIN
  IF p_minuts <= 0 THEN
    RAISE EXCEPTION 'Capacitat incorrecta' USING ERRCODE = 'invalid_parameter_value';
  END IF;
  FOR r IN SELECT t.track_id, t.name, t.milliseconds FROM playlist_track pt JOIN track t ON t.track_id = pt.track_id
            WHERE pt.playlist_id = p_playlist_id ORDER BY t.track_id LOOP
    IF v_total + r.milliseconds <= p_minuts * 60000 THEN
      v_total := v_total + r.milliseconds;
      pista_id := r.track_id; pista := r.name; acumulat_ms := v_total;
      RETURN NEXT;
    END IF;
  END LOOP;
END $$;
```

## Chinook — Procediments (pgproc)

### 1. Crea el procediment `alta_genere(p_nom text)` que doni d'alta un gènere a `genre` amb `genre_id` igual al màxim actual més 1 i amb el nom sense els espais del principi i del final (`btrim`). Validacions: si el nom és NULL o queda buit després de treure els espais, excepció amb `ERRCODE = 'check_violation'`; si ja existeix un gènere amb aquest nom sense distingir majúscules de minúscules (per exemple `'rock'` i `Rock`), excepció amb `ERRCODE = 'unique_violation'`.

Referència:
```sql
CREATE PROCEDURE alta_genere(p_nom text) LANGUAGE plpgsql AS $$
DECLARE
  v_nom text := btrim(p_nom);
BEGIN
  IF v_nom IS NULL OR v_nom = '' THEN
    RAISE EXCEPTION 'Cal un nom' USING ERRCODE = 'check_violation';
  END IF;
  IF EXISTS (SELECT 1 FROM genre WHERE lower(name) = lower(v_nom)) THEN
    RAISE EXCEPTION 'El gènere % ja existeix', v_nom USING ERRCODE = 'unique_violation';
  END IF;
  INSERT INTO genre (genre_id, name) SELECT coalesce(max(genre_id), 0) + 1, v_nom FROM genre;
END $$;
--@@TEST@@ CALL alta_genere('K-Pop')
--@@TEST@@ CALL alta_genere('  Flamenco  ')
--@@TEST@@ CALL alta_genere('rock')
--@@TEST@@ CALL alta_genere('k-pop ')
--@@TEST@@ CALL alta_genere('   ')
--@@TEST@@ CALL alta_genere(NULL)
--@@TEST@@ SELECT * FROM genre WHERE genre_id > 25 ORDER BY genre_id
```

Alternativa (ACCEPTADA):
```sql
CREATE OR REPLACE PROCEDURE alta_genere(p_nom text) AS $$
DECLARE
  v_id integer;
BEGIN
  IF coalesce(trim(p_nom), '') = '' THEN
    RAISE check_violation USING MESSAGE = 'Nom buit';
  END IF;
  PERFORM 1 FROM genre WHERE upper(name) = upper(trim(p_nom));
  IF FOUND THEN
    RAISE unique_violation USING MESSAGE = 'Gènere repetit';
  END IF;
  SELECT max(genre_id) + 1 INTO v_id FROM genre;
  INSERT INTO genre VALUES (v_id, trim(p_nom));
END;
$$ LANGUAGE plpgsql;
```

Incorrecta (REBUTJADA: Test 3 (CALL alta_genere('rock')): yours runs, the expected one gives an error):
```sql
CREATE PROCEDURE alta_genere(p_nom text) LANGUAGE plpgsql AS $$
BEGIN
  IF p_nom IS NULL OR btrim(p_nom) = '' THEN
    RAISE EXCEPTION 'Cal un nom' USING ERRCODE = 'check_violation';
  END IF;
  IF EXISTS (SELECT 1 FROM genre WHERE name = btrim(p_nom)) THEN
    RAISE EXCEPTION 'Ja existeix' USING ERRCODE = 'unique_violation';
  END IF;
  INSERT INTO genre (genre_id, name) SELECT max(genre_id) + 1, btrim(p_nom) FROM genre;
END $$;
```

Incorrecta (REBUTJADA: Test 7 (SELECT * FROM genre WHERE genre_id > 25 ORDER BY genre_id): Result sets differ (comparing unordered)):
```sql
CREATE PROCEDURE alta_genere(p_nom text) LANGUAGE plpgsql AS $$
BEGIN
  IF p_nom IS NULL OR btrim(p_nom) = '' THEN
    RAISE EXCEPTION 'Cal un nom' USING ERRCODE = 'check_violation';
  END IF;
  IF EXISTS (SELECT 1 FROM genre WHERE lower(name) = lower(btrim(p_nom))) THEN
    RAISE EXCEPTION 'Ja existeix' USING ERRCODE = 'unique_violation';
  END IF;
  INSERT INTO genre (genre_id, name) SELECT max(genre_id) + 1, p_nom FROM genre;
END $$;
```

Incorrecta (REBUTJADA: Test 3 (CALL alta_genere('rock')): yours gives an error, the expected one gives an error):
```sql
CREATE PROCEDURE alta_genere(p_nom text) LANGUAGE plpgsql AS $$
BEGIN
  IF EXISTS (SELECT 1 FROM genre WHERE lower(name) = lower(btrim(p_nom))) THEN
    RAISE EXCEPTION 'Ja existeix';
  END IF;
  INSERT INTO genre (genre_id, name) SELECT max(genre_id) + 1, btrim(p_nom) FROM genre;
END $$;
```

### 2. Crea el procediment `esborra_client(p_customer_id integer)` que doni de baixa un client: n'ha d'esborrar les línies de factura (`invoice_line`), les factures (`invoice`) i, finalment, el client (`customer`). Si el client no existeix, ha de llançar una excepció amb `ERRCODE = 'no_data_found'` (comprova-ho amb la variable `FOUND` després d'esborrar el client).

Referència:
```sql
CREATE PROCEDURE esborra_client(p_customer_id integer) LANGUAGE plpgsql AS $$
BEGIN
  DELETE FROM invoice_line WHERE invoice_id IN (SELECT invoice_id FROM invoice WHERE customer_id = p_customer_id);
  DELETE FROM invoice WHERE customer_id = p_customer_id;
  DELETE FROM customer WHERE customer_id = p_customer_id;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'El client % no existeix', p_customer_id USING ERRCODE = 'no_data_found';
  END IF;
END $$;
--@@TEST@@ CALL esborra_client(5)
--@@TEST@@ CALL esborra_client(5)
--@@TEST@@ CALL esborra_client(999)
--@@TEST@@ CALL esborra_client(NULL)
--@@TEST@@ INSERT INTO customer (customer_id, first_name, last_name, email) VALUES (60, 'Clara', 'Nova', 'clara@example.com')
--@@TEST@@ CALL esborra_client(60)
--@@TEST@@ SELECT count(*) FROM invoice WHERE customer_id = 5
```

Alternativa (ACCEPTADA):
```sql
CREATE PROCEDURE esborra_client(p_customer_id integer) AS $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM customer WHERE customer_id = p_customer_id) THEN
    RAISE no_data_found;
  END IF;
  DELETE FROM invoice_line il USING invoice i WHERE il.invoice_id = i.invoice_id AND i.customer_id = p_customer_id;
  DELETE FROM invoice WHERE customer_id = p_customer_id;
  DELETE FROM customer WHERE customer_id = p_customer_id;
END;
$$ LANGUAGE plpgsql;
```

Incorrecta (REBUTJADA: Test 1 (CALL esborra_client(5)): yours gives an error, the expected one runs):
```sql
CREATE PROCEDURE esborra_client(p_customer_id integer) LANGUAGE plpgsql AS $$
BEGIN
  DELETE FROM invoice WHERE customer_id = p_customer_id;
  DELETE FROM customer WHERE customer_id = p_customer_id;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'No existeix' USING ERRCODE = 'no_data_found';
  END IF;
END $$;
```

Incorrecta (REBUTJADA: Test 2 (CALL esborra_client(5)): yours runs, the expected one gives an error):
```sql
CREATE PROCEDURE esborra_client(p_customer_id integer) LANGUAGE sql AS $$
  DELETE FROM invoice_line WHERE invoice_id IN (SELECT invoice_id FROM invoice WHERE customer_id = p_customer_id);
  DELETE FROM invoice WHERE customer_id = p_customer_id;
  DELETE FROM customer WHERE customer_id = p_customer_id;
$$;
```

Incorrecta (REBUTJADA: Test 6 (CALL esborra_client(60)): yours gives an error, the expected one runs):
```sql
CREATE PROCEDURE esborra_client(p_customer_id integer) LANGUAGE plpgsql AS $$
BEGIN
  DELETE FROM invoice_line WHERE invoice_id IN (SELECT invoice_id FROM invoice WHERE customer_id = p_customer_id);
  DELETE FROM invoice WHERE customer_id = p_customer_id;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'No existeix' USING ERRCODE = 'no_data_found';
  END IF;
  DELETE FROM customer WHERE customer_id = p_customer_id;
END $$;
```

### 3. Crea el procediment `canvia_preu_genere(p_genere text, p_percent numeric, INOUT p_files integer DEFAULT NULL)` que modifiqui el preu (`unit_price`) de totes les pistes del gènere amb aquest nom exacte en el percentatge indicat (positiu apuja, negatiu abaixa), arrodonint el nou preu a 2 decimals: `round(unit_price * (1 + p_percent / 100), 2)`. Al final, `p_files` ha de valer el nombre de pistes actualitzades (obtingut amb `GET DIAGNOSTICS ... = ROW_COUNT`). Validacions: si `p_percent` és menor que -50 o major que 100, excepció amb `ERRCODE = 'check_violation'`; si el gènere no existeix, excepció amb `ERRCODE = 'no_data_found'`. Es crida així: `CALL canvia_preu_genere('Jazz', 10)`.

Referència:
```sql
CREATE PROCEDURE canvia_preu_genere(p_genere text, p_percent numeric, INOUT p_files integer DEFAULT NULL) LANGUAGE plpgsql AS $$
DECLARE
  v_genre_id integer;
BEGIN
  IF p_percent < -50 OR p_percent > 100 THEN
    RAISE EXCEPTION 'Percentatge fora de rang: %', p_percent USING ERRCODE = 'check_violation';
  END IF;
  SELECT genre_id INTO v_genre_id FROM genre WHERE name = p_genere;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'El gènere % no existeix', p_genere USING ERRCODE = 'no_data_found';
  END IF;
  UPDATE track SET unit_price = round(unit_price * (1 + p_percent / 100), 2) WHERE genre_id = v_genre_id;
  GET DIAGNOSTICS p_files = ROW_COUNT;
END $$;
--@@TEST@@ CALL canvia_preu_genere('Jazz', 10)
--@@TEST@@ CALL canvia_preu_genere('Opera', -50)
--@@TEST@@ CALL canvia_preu_genere('Science Fiction', 33.3)
--@@TEST@@ CALL canvia_preu_genere('Polka', 5)
--@@TEST@@ CALL canvia_preu_genere('Jazz', -60)
--@@TEST@@ CALL canvia_preu_genere('Jazz', 150)
```

Alternativa (ACCEPTADA):
```sql
CREATE PROCEDURE canvia_preu_genere(p_genere text, p_percent numeric, INOUT p_files integer = NULL) AS $$
BEGIN
  IF p_percent NOT BETWEEN -50 AND 100 THEN
    RAISE check_violation;
  END IF;
  UPDATE track t SET unit_price = round(t.unit_price * (100 + p_percent) / 100, 2)
    FROM genre g WHERE g.genre_id = t.genre_id AND g.name = p_genere;
  GET DIAGNOSTICS p_files = ROW_COUNT;
  IF NOT EXISTS (SELECT 1 FROM genre WHERE name = p_genere) THEN
    RAISE no_data_found;
  END IF;
END;
$$ LANGUAGE plpgsql;
```

Incorrecta (REBUTJADA: Test 4 (CALL canvia_preu_genere('Polka', 5)): yours returns rows, the expected one gives an error):
```sql
CREATE PROCEDURE canvia_preu_genere(p_genere text, p_percent numeric, INOUT p_files integer DEFAULT NULL) LANGUAGE plpgsql AS $$
BEGIN
  IF p_percent < -50 OR p_percent > 100 THEN
    RAISE EXCEPTION 'Fora de rang' USING ERRCODE = 'check_violation';
  END IF;
  UPDATE track SET unit_price = round(unit_price * (1 + p_percent / 100), 2) WHERE genre_id = (SELECT genre_id FROM genre WHERE name = p_genere);
  GET DIAGNOSTICS p_files = ROW_COUNT;
END $$;
```

Incorrecta (REBUTJADA: Test 1 (CALL canvia_preu_genere('Jazz', 10)): Result sets differ (comparing unordered)):
```sql
CREATE PROCEDURE canvia_preu_genere(p_genere text, p_percent numeric, INOUT p_files integer DEFAULT NULL) LANGUAGE plpgsql AS $$
BEGIN
  IF p_percent < -50 OR p_percent > 100 THEN
    RAISE EXCEPTION 'Fora de rang' USING ERRCODE = 'check_violation';
  END IF;
  UPDATE track SET unit_price = round(unit_price * (1 + p_percent / 100), 2) WHERE genre_id = (SELECT genre_id FROM genre WHERE name = p_genere);
  IF NOT FOUND THEN
    RAISE EXCEPTION 'No existeix' USING ERRCODE = 'no_data_found';
  END IF;
END $$;
```

### 4. Quan un agent de vendes marxa de vacances, els seus clients passen a un altre agent. Crea el procediment `reassigna_clients(p_de integer, p_a integer, INOUT p_moguts integer DEFAULT NULL)` que canviï el `support_rep_id` de tots els clients de l'empleat `p_de` a l'empleat `p_a` i deixi a `p_moguts` quants clients s'han mogut (0 si no n'hi havia cap). Validacions, en aquest ordre: si `p_de` i `p_a` són iguals, excepció amb `ERRCODE = 'invalid_parameter_value'`; si `p_a` no és un empleat amb el càrrec (`title`) `Sales Support Agent`, excepció amb `ERRCODE = 'check_violation'`.

Referència:
```sql
CREATE PROCEDURE reassigna_clients(p_de integer, p_a integer, INOUT p_moguts integer DEFAULT NULL) LANGUAGE plpgsql AS $$
BEGIN
  IF p_de = p_a THEN
    RAISE EXCEPTION 'Origen i destí iguals' USING ERRCODE = 'invalid_parameter_value';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM employee WHERE employee_id = p_a AND title = 'Sales Support Agent') THEN
    RAISE EXCEPTION 'L''empleat % no és agent de vendes', p_a USING ERRCODE = 'check_violation';
  END IF;
  UPDATE customer SET support_rep_id = p_a WHERE support_rep_id = p_de;
  GET DIAGNOSTICS p_moguts = ROW_COUNT;
END $$;
--@@TEST@@ CALL reassigna_clients(3, 4)
--@@TEST@@ CALL reassigna_clients(3, 5)
--@@TEST@@ CALL reassigna_clients(4, 4)
--@@TEST@@ CALL reassigna_clients(5, 2)
--@@TEST@@ CALL reassigna_clients(5, 99)
--@@TEST@@ SELECT support_rep_id, count(*) FROM customer GROUP BY support_rep_id ORDER BY support_rep_id
```

Alternativa (ACCEPTADA):
```sql
CREATE PROCEDURE reassigna_clients(p_de integer, p_a integer, INOUT p_moguts integer DEFAULT NULL) AS $$
DECLARE
  v_carrec text;
BEGIN
  IF p_de = p_a THEN
    RAISE invalid_parameter_value;
  END IF;
  SELECT title INTO v_carrec FROM employee WHERE employee_id = p_a;
  IF v_carrec IS DISTINCT FROM 'Sales Support Agent' THEN
    RAISE check_violation;
  END IF;
  SELECT count(*) INTO p_moguts FROM customer WHERE support_rep_id = p_de;
  UPDATE customer SET support_rep_id = p_a WHERE support_rep_id = p_de;
END;
$$ LANGUAGE plpgsql;
```

Incorrecta (REBUTJADA: Test 4 (CALL reassigna_clients(5, 2)): yours returns rows, the expected one gives an error):
```sql
CREATE PROCEDURE reassigna_clients(p_de integer, p_a integer, INOUT p_moguts integer DEFAULT NULL) LANGUAGE plpgsql AS $$
BEGIN
  IF p_de = p_a THEN
    RAISE EXCEPTION 'Iguals' USING ERRCODE = 'invalid_parameter_value';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM employee WHERE employee_id = p_a) THEN
    RAISE EXCEPTION 'No existeix' USING ERRCODE = 'check_violation';
  END IF;
  UPDATE customer SET support_rep_id = p_a WHERE support_rep_id = p_de;
  GET DIAGNOSTICS p_moguts = ROW_COUNT;
END $$;
```

Incorrecta (REBUTJADA: Test 1 (CALL reassigna_clients(3, 4)): Result sets differ (comparing unordered)):
```sql
CREATE PROCEDURE reassigna_clients(p_de integer, p_a integer, INOUT p_moguts integer DEFAULT NULL) LANGUAGE plpgsql AS $$
BEGIN
  IF p_de = p_a THEN
    RAISE EXCEPTION 'Iguals' USING ERRCODE = 'invalid_parameter_value';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM employee WHERE employee_id = p_a AND title = 'Sales Support Agent') THEN
    RAISE EXCEPTION 'No és agent' USING ERRCODE = 'check_violation';
  END IF;
  UPDATE customer SET support_rep_id = p_a WHERE support_rep_id = p_de;
END $$;
```

### 5. Crea el procediment `nova_factura(p_customer_id integer, p_track_id integer, INOUT p_invoice_id integer DEFAULT NULL)` que registri la compra d'una sola pista: crea una factura a `invoice` (`invoice_id` = màxim + 1, data `now()`, les columnes `billing_address`, `billing_city`, `billing_state`, `billing_country` i `billing_postal_code` copiades de `address`, `city`, `state`, `country` i `postal_code` del client, i `total` igual al preu de la pista) i una línia a `invoice_line` (`invoice_line_id` = màxim + 1, el preu actual de la pista i `quantity` 1). Al final, `p_invoice_id` ha de valer l'identificador de la factura nova. Si el client o la pista no existeixen, excepció amb `ERRCODE = 'no_data_found'` (sense crear res).

Referència:
```sql
CREATE PROCEDURE nova_factura(p_customer_id integer, p_track_id integer, INOUT p_invoice_id integer DEFAULT NULL) LANGUAGE plpgsql AS $$
DECLARE
  c customer%ROWTYPE;
  v_preu numeric;
BEGIN
  SELECT * INTO c FROM customer WHERE customer_id = p_customer_id;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'El client % no existeix', p_customer_id USING ERRCODE = 'no_data_found';
  END IF;
  SELECT unit_price INTO v_preu FROM track WHERE track_id = p_track_id;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'La pista % no existeix', p_track_id USING ERRCODE = 'no_data_found';
  END IF;
  SELECT max(invoice_id) + 1 INTO p_invoice_id FROM invoice;
  INSERT INTO invoice (invoice_id, customer_id, invoice_date, billing_address, billing_city, billing_state, billing_country, billing_postal_code, total)
  VALUES (p_invoice_id, c.customer_id, now(), c.address, c.city, c.state, c.country, c.postal_code, v_preu);
  INSERT INTO invoice_line (invoice_line_id, invoice_id, track_id, unit_price, quantity)
  SELECT max(invoice_line_id) + 1, p_invoice_id, p_track_id, v_preu, 1 FROM invoice_line;
END $$;
--@@TEST@@ CALL nova_factura(1, 1)
--@@TEST@@ CALL nova_factura(16, 2819)
--@@TEST@@ CALL nova_factura(999, 1)
--@@TEST@@ CALL nova_factura(1, 999999)
--@@TEST@@ SELECT * FROM invoice WHERE invoice_id > 412 ORDER BY invoice_id
--@@TEST@@ SELECT * FROM invoice_line WHERE invoice_line_id > 2240 ORDER BY invoice_line_id
```

Alternativa (ACCEPTADA):
```sql
CREATE PROCEDURE nova_factura(p_customer_id integer, p_track_id integer, INOUT p_invoice_id integer DEFAULT NULL) AS $$
DECLARE
  v_preu track.unit_price%TYPE;
BEGIN
  IF NOT EXISTS (SELECT 1 FROM customer WHERE customer_id = p_customer_id) THEN
    RAISE no_data_found;
  END IF;
  v_preu := (SELECT unit_price FROM track WHERE track_id = p_track_id);
  IF v_preu IS NULL THEN
    RAISE no_data_found;
  END IF;
  INSERT INTO invoice (invoice_id, customer_id, invoice_date, billing_address, billing_city, billing_state, billing_country, billing_postal_code, total)
  SELECT (SELECT max(invoice_id) + 1 FROM invoice), customer_id, now(), address, city, state, country, postal_code, v_preu
    FROM customer WHERE customer_id = p_customer_id
  RETURNING invoice_id INTO p_invoice_id;
  INSERT INTO invoice_line VALUES ((SELECT max(invoice_line_id) + 1 FROM invoice_line), p_invoice_id, p_track_id, v_preu, 1);
END;
$$ LANGUAGE plpgsql;
```

Incorrecta (REBUTJADA: Test 4 (CALL nova_factura(1, 999999)): yours gives an error, the expected one gives an error):
```sql
CREATE PROCEDURE nova_factura(p_customer_id integer, p_track_id integer, INOUT p_invoice_id integer DEFAULT NULL) LANGUAGE plpgsql AS $$
DECLARE
  c customer%ROWTYPE;
  v_preu numeric;
BEGIN
  SELECT * INTO c FROM customer WHERE customer_id = p_customer_id;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'No existeix' USING ERRCODE = 'no_data_found';
  END IF;
  SELECT unit_price INTO v_preu FROM track WHERE track_id = p_track_id;
  SELECT max(invoice_id) + 1 INTO p_invoice_id FROM invoice;
  INSERT INTO invoice VALUES (p_invoice_id, c.customer_id, now(), c.address, c.city, c.state, c.country, c.postal_code, v_preu);
  INSERT INTO invoice_line SELECT max(invoice_line_id) + 1, p_invoice_id, p_track_id, v_preu, 1 FROM invoice_line;
END $$;
```

Incorrecta (REBUTJADA: Test 5 (SELECT * FROM invoice WHERE invoice_id > 412 ORDER BY inv...): Result sets differ (comparing unordered)):
```sql
CREATE PROCEDURE nova_factura(p_customer_id integer, p_track_id integer, INOUT p_invoice_id integer DEFAULT NULL) LANGUAGE plpgsql AS $$
DECLARE
  c customer%ROWTYPE;
  v_preu numeric;
BEGIN
  SELECT * INTO c FROM customer WHERE customer_id = p_customer_id;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'No existeix' USING ERRCODE = 'no_data_found';
  END IF;
  SELECT unit_price INTO v_preu FROM track WHERE track_id = p_track_id;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'No existeix' USING ERRCODE = 'no_data_found';
  END IF;
  SELECT max(invoice_id) + 1 INTO p_invoice_id FROM invoice;
  INSERT INTO invoice VALUES (p_invoice_id, c.customer_id, current_date, c.address, c.city, c.state, c.country, c.postal_code, v_preu);
  INSERT INTO invoice_line SELECT max(invoice_line_id) + 1, p_invoice_id, p_track_id, v_preu, 1 FROM invoice_line;
END $$;
```

### 6. Crea el procediment `factura_playlist(p_customer_id integer, p_playlist_id integer, INOUT p_invoice_id integer DEFAULT NULL, INOUT p_linies integer DEFAULT NULL)` que faci que el client compri, en una sola factura, totes les pistes de la playlist que encara no hagi comprat mai (en cap factura anterior). Crea la factura a `invoice` com al procediment de compra d'una pista (`invoice_id` = màxim + 1, data `now()`, dades de facturació copiades del client) i, recorrent les pistes en ordre de `track_id` amb un bucle `FOR ... IN SELECT`, una línia a `invoice_line` per a cada pista, amb identificadors consecutius a partir del màxim + 1, el preu actual de la pista i `quantity` 1. El `total` de la factura ha de ser la suma de les línies. `p_invoice_id` ha de valer l'identificador de la factura nova i `p_linies` el nombre de línies creades. Validacions: si el client o la playlist no existeixen, excepció amb `ERRCODE = 'no_data_found'`; si no hi ha cap pista per comprar, excepció amb `ERRCODE = 'raise_exception'` (el valor per defecte de `RAISE EXCEPTION`) i no s'ha de crear cap factura.

Referència:
```sql
CREATE PROCEDURE factura_playlist(p_customer_id integer, p_playlist_id integer, INOUT p_invoice_id integer DEFAULT NULL, INOUT p_linies integer DEFAULT NULL) LANGUAGE plpgsql AS $$
DECLARE
  c customer%ROWTYPE;
  r record;
  v_linia integer;
  v_total numeric := 0;
BEGIN
  SELECT * INTO c FROM customer WHERE customer_id = p_customer_id;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'El client % no existeix', p_customer_id USING ERRCODE = 'no_data_found';
  END IF;
  PERFORM 1 FROM playlist WHERE playlist_id = p_playlist_id;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'La playlist % no existeix', p_playlist_id USING ERRCODE = 'no_data_found';
  END IF;
  SELECT max(invoice_id) + 1 INTO p_invoice_id FROM invoice;
  SELECT max(invoice_line_id) INTO v_linia FROM invoice_line;
  INSERT INTO invoice (invoice_id, customer_id, invoice_date, billing_address, billing_city, billing_state, billing_country, billing_postal_code, total)
  VALUES (p_invoice_id, c.customer_id, now(), c.address, c.city, c.state, c.country, c.postal_code, 0);
  p_linies := 0;
  FOR r IN SELECT t.track_id, t.unit_price FROM playlist_track pt JOIN track t ON t.track_id = pt.track_id
            WHERE pt.playlist_id = p_playlist_id
              AND NOT EXISTS (SELECT 1 FROM invoice_line il JOIN invoice i ON i.invoice_id = il.invoice_id
                               WHERE i.customer_id = p_customer_id AND il.track_id = t.track_id)
            ORDER BY t.track_id LOOP
    v_linia := v_linia + 1;
    INSERT INTO invoice_line (invoice_line_id, invoice_id, track_id, unit_price, quantity)
    VALUES (v_linia, p_invoice_id, r.track_id, r.unit_price, 1);
    v_total := v_total + r.unit_price;
    p_linies := p_linies + 1;
  END LOOP;
  IF p_linies = 0 THEN
    RAISE EXCEPTION 'El client ja té totes les pistes de la playlist';
  END IF;
  UPDATE invoice SET total = v_total WHERE invoice_id = p_invoice_id;
END $$;
--@@TEST@@ CALL factura_playlist(12, 16)
--@@TEST@@ CALL factura_playlist(1, 18)
--@@TEST@@ CALL factura_playlist(1, 18)
--@@TEST@@ CALL factura_playlist(999, 16)
--@@TEST@@ CALL factura_playlist(1, 999)
--@@TEST@@ SELECT * FROM invoice WHERE invoice_id > 412 ORDER BY invoice_id
--@@TEST@@ SELECT * FROM invoice_line WHERE invoice_line_id > 2240 ORDER BY invoice_line_id
```

Alternativa (ACCEPTADA):
```sql
CREATE PROCEDURE factura_playlist(p_customer_id integer, p_playlist_id integer, INOUT p_invoice_id integer DEFAULT NULL, INOUT p_linies integer DEFAULT NULL) AS $$
DECLARE
  v_pista record;
BEGIN
  IF NOT EXISTS (SELECT 1 FROM customer WHERE customer_id = p_customer_id)
     OR NOT EXISTS (SELECT 1 FROM playlist WHERE playlist_id = p_playlist_id) THEN
    RAISE no_data_found;
  END IF;
  p_linies := 0;
  FOR v_pista IN SELECT pt.track_id, t.unit_price FROM playlist_track pt JOIN track t USING (track_id)
                  WHERE pt.playlist_id = p_playlist_id
                    AND pt.track_id NOT IN (SELECT il.track_id FROM invoice_line il JOIN invoice i USING (invoice_id) WHERE i.customer_id = p_customer_id)
                  ORDER BY pt.track_id LOOP
    IF p_linies = 0 THEN
      p_invoice_id := (SELECT max(invoice_id) + 1 FROM invoice);
      INSERT INTO invoice (invoice_id, customer_id, invoice_date, billing_address, billing_city, billing_state, billing_country, billing_postal_code, total)
      SELECT p_invoice_id, customer_id, now(), address, city, state, country, postal_code, 0 FROM customer WHERE customer_id = p_customer_id;
    END IF;
    INSERT INTO invoice_line VALUES ((SELECT max(invoice_line_id) + 1 FROM invoice_line), p_invoice_id, v_pista.track_id, v_pista.unit_price, 1);
    UPDATE invoice SET total = total + v_pista.unit_price WHERE invoice_id = p_invoice_id;
    p_linies := p_linies + 1;
  END LOOP;
  IF p_linies = 0 THEN
    RAISE EXCEPTION 'Res a comprar';
  END IF;
END;
$$ LANGUAGE plpgsql;
```

Incorrecta (REBUTJADA: Test 1 (CALL factura_playlist(12, 16)): Result sets differ (comparing unordered)):
```sql
CREATE PROCEDURE factura_playlist(p_customer_id integer, p_playlist_id integer, INOUT p_invoice_id integer DEFAULT NULL, INOUT p_linies integer DEFAULT NULL) LANGUAGE plpgsql AS $$
DECLARE
  c customer%ROWTYPE;
  r record;
BEGIN
  SELECT * INTO c FROM customer WHERE customer_id = p_customer_id;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'No existeix' USING ERRCODE = 'no_data_found';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM playlist WHERE playlist_id = p_playlist_id) THEN
    RAISE EXCEPTION 'No existeix' USING ERRCODE = 'no_data_found';
  END IF;
  SELECT max(invoice_id) + 1 INTO p_invoice_id FROM invoice;
  INSERT INTO invoice VALUES (p_invoice_id, c.customer_id, now(), c.address, c.city, c.state, c.country, c.postal_code, 0);
  p_linies := 0;
  FOR r IN SELECT t.track_id, t.unit_price FROM playlist_track pt JOIN track t ON t.track_id = pt.track_id
            WHERE pt.playlist_id = p_playlist_id ORDER BY t.track_id LOOP
    INSERT INTO invoice_line SELECT max(invoice_line_id) + 1, p_invoice_id, r.track_id, r.unit_price, 1 FROM invoice_line;
    p_linies := p_linies + 1;
  END LOOP;
  UPDATE invoice SET total = (SELECT sum(unit_price) FROM invoice_line WHERE invoice_id = p_invoice_id) WHERE invoice_id = p_invoice_id;
END $$;
```

Incorrecta (REBUTJADA: Test 3 (CALL factura_playlist(1, 18)): yours returns rows, the expected one gives an error):
```sql
CREATE PROCEDURE factura_playlist(p_customer_id integer, p_playlist_id integer, INOUT p_invoice_id integer DEFAULT NULL, INOUT p_linies integer DEFAULT NULL) LANGUAGE plpgsql AS $$
DECLARE
  c customer%ROWTYPE;
  r record;
BEGIN
  SELECT * INTO c FROM customer WHERE customer_id = p_customer_id;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'No existeix' USING ERRCODE = 'no_data_found';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM playlist WHERE playlist_id = p_playlist_id) THEN
    RAISE EXCEPTION 'No existeix' USING ERRCODE = 'no_data_found';
  END IF;
  SELECT max(invoice_id) + 1 INTO p_invoice_id FROM invoice;
  INSERT INTO invoice VALUES (p_invoice_id, c.customer_id, now(), c.address, c.city, c.state, c.country, c.postal_code, 0);
  p_linies := 0;
  FOR r IN SELECT t.track_id, t.unit_price FROM playlist_track pt JOIN track t ON t.track_id = pt.track_id
            WHERE pt.playlist_id = p_playlist_id
              AND NOT EXISTS (SELECT 1 FROM invoice_line il JOIN invoice i ON i.invoice_id = il.invoice_id WHERE i.customer_id = p_customer_id AND il.track_id = t.track_id)
            ORDER BY t.track_id LOOP
    INSERT INTO invoice_line SELECT max(invoice_line_id) + 1, p_invoice_id, r.track_id, r.unit_price, 1 FROM invoice_line;
    p_linies := p_linies + 1;
  END LOOP;
  UPDATE invoice SET total = coalesce((SELECT sum(unit_price) FROM invoice_line WHERE invoice_id = p_invoice_id), 0) WHERE invoice_id = p_invoice_id;
END $$;
```

## Chinook — Triggers (pgtrigger)

### 1. Volem que els noms de les pistes i dels compositors es guardin nets. Crea la funció `f_neteja_pista()` i el trigger `t_neteja_pista` que s'executi **abans** de cada `INSERT` o `UPDATE` de cada fila de `track` i que: tregui els espais del principi i del final del nom (`name`) i del compositor (`composer`), i que, si el compositor queda buit (`''`), el deixi a NULL.

Referència:
```sql
CREATE FUNCTION f_neteja_pista() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  NEW.name := btrim(NEW.name);
  NEW.composer := nullif(btrim(NEW.composer), '');
  RETURN NEW;
END $$;
CREATE TRIGGER t_neteja_pista BEFORE INSERT OR UPDATE ON track FOR EACH ROW EXECUTE FUNCTION f_neteja_pista();
--@@TEST@@ INSERT INTO track (track_id, name, album_id, media_type_id, genre_id, composer, milliseconds, bytes, unit_price) VALUES (3504, '  Cançó nova  ', 1, 1, 1, '   ', 200000, 3500000, 0.99)
--@@TEST@@ INSERT INTO track (track_id, name, album_id, media_type_id, genre_id, composer, milliseconds, bytes, unit_price) VALUES (3505, 'Una altra', 1, 1, 1, ' Angus Young ', 210000, 3600000, 0.99)
--@@TEST@@ UPDATE track SET composer = '' WHERE track_id = 1
--@@TEST@@ UPDATE track SET name = name || '   ' WHERE album_id = 2
--@@TEST@@ SELECT track_id, name, composer FROM track WHERE track_id IN (1, 3504, 3505) OR album_id = 2 ORDER BY track_id
```

Alternativa (ACCEPTADA):
```sql
CREATE OR REPLACE FUNCTION f_neteja_pista() RETURNS trigger AS $$
BEGIN
  NEW.name = trim(NEW.name);
  IF trim(NEW.composer) = '' THEN
    NEW.composer = NULL;
  ELSE
    NEW.composer = trim(NEW.composer);
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER t_neteja_pista BEFORE UPDATE OR INSERT ON track FOR EACH ROW EXECUTE PROCEDURE f_neteja_pista();
```

Incorrecta (REBUTJADA: Test 5 (SELECT track_id, name, composer FROM track WHERE track_id...): Result sets differ (comparing unordered)):
```sql
CREATE FUNCTION f_neteja_pista() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  NEW.name := btrim(NEW.name);
  NEW.composer := nullif(btrim(NEW.composer), '');
  RETURN NEW;
END $$;
CREATE TRIGGER t_neteja_pista AFTER INSERT OR UPDATE ON track FOR EACH ROW EXECUTE FUNCTION f_neteja_pista();
```

Incorrecta (REBUTJADA: Test 5 (SELECT track_id, name, composer FROM track WHERE track_id...): Result sets differ (comparing unordered)):
```sql
CREATE FUNCTION f_neteja_pista() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  NEW.name := btrim(NEW.name);
  NEW.composer := nullif(btrim(NEW.composer), '');
  RETURN NEW;
END $$;
CREATE TRIGGER t_neteja_pista BEFORE INSERT ON track FOR EACH ROW EXECUTE FUNCTION f_neteja_pista();
```

Incorrecta (REBUTJADA: Test 5 (SELECT track_id, name, composer FROM track WHERE track_id...): Result sets differ (comparing unordered)):
```sql
CREATE FUNCTION f_neteja_pista() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  NEW.name := btrim(NEW.name);
  NEW.composer := btrim(NEW.composer);
  RETURN NEW;
END $$;
CREATE TRIGGER t_neteja_pista BEFORE INSERT OR UPDATE ON track FOR EACH ROW EXECUTE FUNCTION f_neteja_pista();
```

### 2. Crea la funció `f_valida_preu()` i el trigger `t_valida_preu` que, **abans** de cada `UPDATE` del preu (`UPDATE OF unit_price`) de cada fila de `track`, i només quan el preu canvia realment (condició `WHEN (NEW.unit_price IS DISTINCT FROM OLD.unit_price)`), comprovi que el preu nou no és negatiu ni més del doble del preu antic. Si no es compleix, ha de llançar una excepció amb `ERRCODE = 'check_violation'` (i la sentència falla sencera); si es compleix, el canvi es fa normalment.

Referència:
```sql
CREATE FUNCTION f_valida_preu() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.unit_price < 0 OR NEW.unit_price > OLD.unit_price * 2 THEN
    RAISE EXCEPTION 'Preu no permès per a la pista %: % -> %', OLD.track_id, OLD.unit_price, NEW.unit_price
      USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER t_valida_preu BEFORE UPDATE OF unit_price ON track FOR EACH ROW
  WHEN (NEW.unit_price IS DISTINCT FROM OLD.unit_price) EXECUTE FUNCTION f_valida_preu();
--@@TEST@@ UPDATE track SET unit_price = 1.49 WHERE track_id = 1
--@@TEST@@ UPDATE track SET unit_price = -0.5 WHERE track_id = 2
--@@TEST@@ UPDATE track SET unit_price = 2.50 WHERE track_id = 3
--@@TEST@@ UPDATE track SET unit_price = 1.98 WHERE track_id = 3
--@@TEST@@ UPDATE track SET unit_price = 0 WHERE album_id = 2
--@@TEST@@ UPDATE track SET unit_price = unit_price * 3 WHERE album_id = 1
--@@TEST@@ UPDATE track SET unit_price = unit_price * 1.5 WHERE genre_id = 2
--@@TEST@@ SELECT track_id, unit_price FROM track WHERE track_id <= 10 ORDER BY track_id
```

Alternativa (ACCEPTADA):
```sql
CREATE FUNCTION f_valida_preu() RETURNS trigger AS $$
BEGIN
  IF NEW.unit_price NOT BETWEEN 0 AND 2 * OLD.unit_price THEN
    RAISE check_violation USING MESSAGE = 'Preu incorrecte';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER t_valida_preu BEFORE UPDATE OF unit_price ON track FOR EACH ROW EXECUTE FUNCTION f_valida_preu();
```

Incorrecta (REBUTJADA: Test 1 (UPDATE track SET unit_price = 1.49 WHERE track_id = 1): yours gives an error, the expected one runs):
```sql
CREATE FUNCTION f_valida_preu() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.unit_price < 0 OR NEW.unit_price > OLD.unit_price * 2 THEN
    RAISE EXCEPTION 'Preu no permès' USING ERRCODE = 'check_violation';
  END IF;
END $$;
CREATE TRIGGER t_valida_preu BEFORE UPDATE OF unit_price ON track FOR EACH ROW
  WHEN (NEW.unit_price IS DISTINCT FROM OLD.unit_price) EXECUTE FUNCTION f_valida_preu();
```

Incorrecta (REBUTJADA: Test 4 (UPDATE track SET unit_price = 1.98 WHERE track_id = 3): yours gives an error, the expected one runs):
```sql
CREATE FUNCTION f_valida_preu() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.unit_price < 0 OR NEW.unit_price >= OLD.unit_price * 2 THEN
    RAISE EXCEPTION 'Preu no permès' USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER t_valida_preu BEFORE UPDATE OF unit_price ON track FOR EACH ROW
  WHEN (NEW.unit_price IS DISTINCT FROM OLD.unit_price) EXECUTE FUNCTION f_valida_preu();
```

Incorrecta (REBUTJADA: Test 2 (UPDATE track SET unit_price = -0.5 WHERE track_id = 2): yours gives an error, the expected one gives an error):
```sql
CREATE FUNCTION f_valida_preu() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.unit_price < 0 OR NEW.unit_price > OLD.unit_price * 2 THEN
    RAISE EXCEPTION 'Preu no permès';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER t_valida_preu BEFORE UPDATE OF unit_price ON track FOR EACH ROW
  WHEN (NEW.unit_price IS DISTINCT FROM OLD.unit_price) EXECUTE FUNCTION f_valida_preu();
```

### 3. Volem auditar els clients. Crea la taula `log_clients(id serial PRIMARY KEY, operacio text, customer_id integer, email_antic text, email_nou text, moment timestamp)`, la funció `f_audita_client()` i el trigger `t_audita_client`, que **després** de cada `INSERT`, `UPDATE` o `DELETE` de cada fila de `customer` hi afegeixi una fila amb l'operació (`TG_OP`: `INSERT`, `UPDATE` o `DELETE`), el `customer_id`, el correu (`email`) antic i el nou (NULL quan no n'hi ha: l'antic en un `INSERT`, el nou en un `DELETE`) i el moment (`now()`). Els `UPDATE` només s'han de registrar si el correu ha canviat.

Referència:
```sql
CREATE TABLE log_clients (id serial PRIMARY KEY, operacio text, customer_id integer, email_antic text, email_nou text, moment timestamp);
CREATE FUNCTION f_audita_client() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'INSERT' THEN
    INSERT INTO log_clients (operacio, customer_id, email_antic, email_nou, moment) VALUES (TG_OP, NEW.customer_id, NULL, NEW.email, now());
  ELSIF TG_OP = 'UPDATE' THEN
    IF NEW.email IS DISTINCT FROM OLD.email THEN
      INSERT INTO log_clients (operacio, customer_id, email_antic, email_nou, moment) VALUES (TG_OP, NEW.customer_id, OLD.email, NEW.email, now());
    END IF;
  ELSE
    INSERT INTO log_clients (operacio, customer_id, email_antic, email_nou, moment) VALUES (TG_OP, OLD.customer_id, OLD.email, NULL, now());
  END IF;
  RETURN NULL;
END $$;
CREATE TRIGGER t_audita_client AFTER INSERT OR UPDATE OR DELETE ON customer FOR EACH ROW EXECUTE FUNCTION f_audita_client();
--@@TEST@@ INSERT INTO customer (customer_id, first_name, last_name, email) VALUES (60, 'Clara', 'Nova', 'clara@example.com')
--@@TEST@@ UPDATE customer SET email = 'clara.nova@example.com' WHERE customer_id = 60
--@@TEST@@ UPDATE customer SET city = 'Sabadell' WHERE customer_id IN (1, 2)
--@@TEST@@ UPDATE customer SET email = upper(email) WHERE customer_id IN (3, 4)
--@@TEST@@ DELETE FROM customer WHERE customer_id = 60
--@@TEST@@ SELECT operacio, customer_id, email_antic, email_nou, moment FROM log_clients ORDER BY id
```

Alternativa (ACCEPTADA):
```sql
CREATE TABLE log_clients (id serial PRIMARY KEY, operacio text, customer_id integer, email_antic text, email_nou text, moment timestamp);
CREATE FUNCTION f_audita_client() RETURNS trigger AS $$
BEGIN
  CASE TG_OP
    WHEN 'INSERT' THEN
      INSERT INTO log_clients (operacio, customer_id, email_nou, moment) VALUES ('INSERT', NEW.customer_id, NEW.email, now());
    WHEN 'UPDATE' THEN
      INSERT INTO log_clients (operacio, customer_id, email_antic, email_nou, moment) VALUES ('UPDATE', NEW.customer_id, OLD.email, NEW.email, now());
    ELSE
      INSERT INTO log_clients (operacio, customer_id, email_antic, moment) VALUES ('DELETE', OLD.customer_id, OLD.email, now());
  END CASE;
  RETURN NULL;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER t_audita_client_ins AFTER INSERT OR DELETE ON customer FOR EACH ROW EXECUTE FUNCTION f_audita_client();
CREATE TRIGGER t_audita_client_upd AFTER UPDATE OF email ON customer FOR EACH ROW WHEN (OLD.email IS DISTINCT FROM NEW.email) EXECUTE FUNCTION f_audita_client();
```

Incorrecta (REBUTJADA: Test 6 (SELECT operacio, customer_id, email_antic, email_nou, mom...): Wrong number of rows: got 7, expected 5):
```sql
CREATE TABLE log_clients (id serial PRIMARY KEY, operacio text, customer_id integer, email_antic text, email_nou text, moment timestamp);
CREATE FUNCTION f_audita_client() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN
    INSERT INTO log_clients (operacio, customer_id, email_antic, email_nou, moment) VALUES (TG_OP, OLD.customer_id, OLD.email, NULL, now());
  ELSIF TG_OP = 'UPDATE' THEN
    INSERT INTO log_clients (operacio, customer_id, email_antic, email_nou, moment) VALUES (TG_OP, NEW.customer_id, OLD.email, NEW.email, now());
  ELSE
    INSERT INTO log_clients (operacio, customer_id, email_antic, email_nou, moment) VALUES (TG_OP, NEW.customer_id, NULL, NEW.email, now());
  END IF;
  RETURN NULL;
END $$;
CREATE TRIGGER t_audita_client AFTER INSERT OR UPDATE OR DELETE ON customer FOR EACH ROW EXECUTE FUNCTION f_audita_client();
```

Incorrecta (REBUTJADA: Test 6 (SELECT operacio, customer_id, email_antic, email_nou, mom...): Result sets differ (comparing unordered)):
```sql
CREATE TABLE log_clients (id serial PRIMARY KEY, operacio text, customer_id integer, email_antic text, email_nou text, moment timestamp);
CREATE FUNCTION f_audita_client() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN
    INSERT INTO log_clients (operacio, customer_id, email_antic, email_nou, moment) VALUES (TG_OP, OLD.customer_id, OLD.email, NULL, current_date);
  ELSIF NEW.email IS DISTINCT FROM OLD.email THEN
    INSERT INTO log_clients (operacio, customer_id, email_antic, email_nou, moment) VALUES (TG_OP, NEW.customer_id, OLD.email, NEW.email, current_date);
  END IF;
  RETURN NULL;
END $$;
CREATE TRIGGER t_audita_client AFTER INSERT OR UPDATE OR DELETE ON customer FOR EACH ROW EXECUTE FUNCTION f_audita_client();
```

### 4. El camp `invoice.total` és un camp calculat: ha de ser sempre la suma de `unit_price * quantity` de les línies de la factura (0 si no en té cap). Crea la funció `f_recalcula_total()` i el trigger `t_recalcula_total` que, **després** de cada `INSERT`, `UPDATE` o `DELETE` de cada fila de `invoice_line`, recalculi el `total` de la factura afectada. Atenció: un `UPDATE` pot moure una línia d'una factura a una altra, i llavors s'han de recalcular totes dues.

Referència:
```sql
CREATE FUNCTION f_recalcula_total() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP IN ('INSERT', 'UPDATE') THEN
    UPDATE invoice SET total = coalesce((SELECT sum(unit_price * quantity) FROM invoice_line WHERE invoice_id = NEW.invoice_id), 0)
     WHERE invoice_id = NEW.invoice_id;
  END IF;
  IF TG_OP IN ('UPDATE', 'DELETE') THEN
    UPDATE invoice SET total = coalesce((SELECT sum(unit_price * quantity) FROM invoice_line WHERE invoice_id = OLD.invoice_id), 0)
     WHERE invoice_id = OLD.invoice_id;
  END IF;
  RETURN NULL;
END $$;
CREATE TRIGGER t_recalcula_total AFTER INSERT OR UPDATE OR DELETE ON invoice_line FOR EACH ROW EXECUTE FUNCTION f_recalcula_total();
--@@TEST@@ INSERT INTO invoice_line (invoice_line_id, invoice_id, track_id, unit_price, quantity) VALUES (2241, 1, 3, 0.99, 2)
--@@TEST@@ UPDATE invoice_line SET quantity = 3 WHERE invoice_line_id = 3
--@@TEST@@ UPDATE invoice_line SET invoice_id = 4 WHERE invoice_line_id = 7
--@@TEST@@ DELETE FROM invoice_line WHERE invoice_id = 5
--@@TEST@@ SELECT invoice_id, total FROM invoice WHERE invoice_id <= 6 ORDER BY invoice_id
```

Alternativa (ACCEPTADA):
```sql
CREATE FUNCTION f_recalcula_total() RETURNS trigger AS $$
BEGIN
  UPDATE invoice i SET total = (SELECT coalesce(sum(l.unit_price * l.quantity), 0) FROM invoice_line l WHERE l.invoice_id = i.invoice_id)
   WHERE i.invoice_id IN (OLD.invoice_id, NEW.invoice_id);
  RETURN NULL;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER t_recalcula_total AFTER INSERT OR UPDATE OR DELETE ON invoice_line FOR EACH ROW EXECUTE FUNCTION f_recalcula_total();
```

Incorrecta (REBUTJADA: Test 5 (SELECT invoice_id, total FROM invoice WHERE invoice_id <=...): Result sets differ (comparing unordered)):
```sql
CREATE FUNCTION f_recalcula_total() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  UPDATE invoice SET total = (SELECT sum(unit_price * quantity) FROM invoice_line WHERE invoice_id = NEW.invoice_id) WHERE invoice_id = NEW.invoice_id;
  RETURN NULL;
END $$;
CREATE TRIGGER t_recalcula_total AFTER INSERT OR UPDATE OR DELETE ON invoice_line FOR EACH ROW EXECUTE FUNCTION f_recalcula_total();
```

Incorrecta (REBUTJADA: Test 5 (SELECT invoice_id, total FROM invoice WHERE invoice_id <=...): Result sets differ (comparing unordered)):
```sql
CREATE FUNCTION f_recalcula_total() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN
    UPDATE invoice SET total = total - OLD.unit_price * OLD.quantity WHERE invoice_id = OLD.invoice_id;
  ELSIF TG_OP = 'UPDATE' THEN
    UPDATE invoice SET total = total - OLD.unit_price * OLD.quantity + NEW.unit_price * NEW.quantity WHERE invoice_id = NEW.invoice_id;
  ELSE
    UPDATE invoice SET total = total + NEW.unit_price * NEW.quantity WHERE invoice_id = NEW.invoice_id;
  END IF;
  RETURN NULL;
END $$;
CREATE TRIGGER t_recalcula_total AFTER INSERT OR UPDATE OR DELETE ON invoice_line FOR EACH ROW EXECUTE FUNCTION f_recalcula_total();
```

### 5. Crea la funció `f_filtra_playlist()` i el trigger `t_filtra_playlist` que, **abans** de cada `INSERT` de cada fila de `playlist_track`, descarti la fila **sense error** (amb `RETURN NULL`) en dos casos: si la pista ja és a la playlist, i si la pista és un vídeo (tipus de fitxer, `media_type.name`, igual a `Protected MPEG-4 video file`) i la playlist no es diu `Music Videos`, `Movies` ni `TV Shows`. Les altres files s'insereixen normalment. Així, un `INSERT ... SELECT` que afegeixi moltes pistes no falla per les repetides i només insereix les que toca.

Referència:
```sql
CREATE FUNCTION f_filtra_playlist() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF EXISTS (SELECT 1 FROM playlist_track WHERE playlist_id = NEW.playlist_id AND track_id = NEW.track_id) THEN
    RETURN NULL;
  END IF;
  IF EXISTS (SELECT 1 FROM track t JOIN media_type m ON m.media_type_id = t.media_type_id
              WHERE t.track_id = NEW.track_id AND m.name = 'Protected MPEG-4 video file')
     AND NOT EXISTS (SELECT 1 FROM playlist WHERE playlist_id = NEW.playlist_id AND name IN ('Music Videos', 'Movies', 'TV Shows')) THEN
    RETURN NULL;
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER t_filtra_playlist BEFORE INSERT ON playlist_track FOR EACH ROW EXECUTE FUNCTION f_filtra_playlist();
--@@TEST@@ INSERT INTO playlist_track VALUES (16, 52)
--@@TEST@@ INSERT INTO playlist_track VALUES (16, 1)
--@@TEST@@ INSERT INTO playlist_track SELECT 16, track_id FROM track WHERE album_id = 164
--@@TEST@@ INSERT INTO playlist_track SELECT 18, track_id FROM track WHERE track_id BETWEEN 2815 AND 2825
--@@TEST@@ INSERT INTO playlist_track SELECT 9, track_id FROM track WHERE track_id BETWEEN 2815 AND 2825
--@@TEST@@ INSERT INTO playlist_track SELECT 10, track_id FROM track WHERE track_id BETWEEN 2815 AND 2825
--@@TEST@@ SELECT playlist_id, count(*) FROM playlist_track WHERE playlist_id IN (9, 10, 16, 18) GROUP BY playlist_id ORDER BY playlist_id
```

Alternativa (ACCEPTADA):
```sql
CREATE FUNCTION f_filtra_playlist() RETURNS trigger AS $$
DECLARE
  v_tipus text;
  v_playlist text;
BEGIN
  PERFORM 1 FROM playlist_track WHERE (playlist_id, track_id) = (NEW.playlist_id, NEW.track_id);
  IF FOUND THEN
    RETURN NULL;
  END IF;
  SELECT m.name INTO v_tipus FROM track t JOIN media_type m USING (media_type_id) WHERE t.track_id = NEW.track_id;
  SELECT name INTO v_playlist FROM playlist WHERE playlist_id = NEW.playlist_id;
  IF v_tipus = 'Protected MPEG-4 video file' AND v_playlist NOT IN ('Music Videos', 'Movies', 'TV Shows') THEN
    RETURN NULL;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER t_filtra_playlist BEFORE INSERT ON playlist_track FOR EACH ROW EXECUTE FUNCTION f_filtra_playlist();
```

Incorrecta (REBUTJADA: Test 4 (INSERT INTO playlist_track SELECT 18, track_id FROM track...): it changed 11 rows, expected 4):
```sql
CREATE FUNCTION f_filtra_playlist() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF EXISTS (SELECT 1 FROM playlist_track WHERE playlist_id = NEW.playlist_id AND track_id = NEW.track_id) THEN
    RETURN NULL;
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER t_filtra_playlist BEFORE INSERT ON playlist_track FOR EACH ROW EXECUTE FUNCTION f_filtra_playlist();
```

Incorrecta (REBUTJADA: Test 1 (INSERT INTO playlist_track VALUES (16, 52)): yours gives an error, the expected one runs):
```sql
CREATE FUNCTION f_filtra_playlist() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF EXISTS (SELECT 1 FROM playlist_track WHERE playlist_id = NEW.playlist_id AND track_id = NEW.track_id) THEN
    RAISE EXCEPTION 'Pista repetida';
  END IF;
  IF EXISTS (SELECT 1 FROM track t JOIN media_type m ON m.media_type_id = t.media_type_id WHERE t.track_id = NEW.track_id AND m.name = 'Protected MPEG-4 video file')
     AND NOT EXISTS (SELECT 1 FROM playlist WHERE playlist_id = NEW.playlist_id AND name IN ('Music Videos', 'Movies', 'TV Shows')) THEN
    RAISE EXCEPTION 'Vídeo en una playlist de música';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER t_filtra_playlist BEFORE INSERT ON playlist_track FOR EACH ROW EXECUTE FUNCTION f_filtra_playlist();
```

Incorrecta (REBUTJADA: Test 1 (INSERT INTO playlist_track VALUES (16, 52)): yours gives an error, the expected one runs):
```sql
CREATE FUNCTION f_filtra_playlist() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF EXISTS (SELECT 1 FROM playlist_track WHERE playlist_id = NEW.playlist_id AND track_id = NEW.track_id) THEN
    RETURN NULL;
  END IF;
  IF EXISTS (SELECT 1 FROM track t JOIN media_type m ON m.media_type_id = t.media_type_id WHERE t.track_id = NEW.track_id AND m.name = 'Protected MPEG-4 video file')
     AND NOT EXISTS (SELECT 1 FROM playlist WHERE playlist_id = NEW.playlist_id AND name IN ('Music Videos', 'Movies', 'TV Shows')) THEN
    RETURN NULL;
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER t_filtra_playlist AFTER INSERT ON playlist_track FOR EACH ROW EXECUTE FUNCTION f_filtra_playlist();
```

### 6. Volem un registre dels canvis de preus fets en bloc. Crea la taula `log_preus(id serial PRIMARY KEY, moment timestamp, pistes integer, increment_mitja numeric)`, la funció `f_log_preus()` i el trigger **de sentència** `t_log_preus` (`AFTER UPDATE ON track ... FOR EACH STATEMENT`) que, amb les taules de transició (`REFERENCING OLD TABLE AS antigues NEW TABLE AS noves`), afegeixi **una sola fila** per sentència a `log_preus` amb el moment (`now()`), el nombre de pistes el preu de les quals ha canviat realment i la mitjana de la diferència (preu nou - preu antic) d'aquestes pistes, arrodonida a 2 decimals. Si la sentència no ha canviat el preu de cap pista, no s'hi ha d'afegir res.

Referència:
```sql
CREATE TABLE log_preus (id serial PRIMARY KEY, moment timestamp, pistes integer, increment_mitja numeric);
CREATE FUNCTION f_log_preus() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
  v_pistes integer;
  v_mitja numeric;
BEGIN
  SELECT count(*), round(avg(n.unit_price - a.unit_price), 2) INTO v_pistes, v_mitja
    FROM antigues a JOIN noves n ON n.track_id = a.track_id
   WHERE n.unit_price <> a.unit_price;
  IF v_pistes > 0 THEN
    INSERT INTO log_preus (moment, pistes, increment_mitja) VALUES (now(), v_pistes, v_mitja);
  END IF;
  RETURN NULL;
END $$;
CREATE TRIGGER t_log_preus AFTER UPDATE ON track REFERENCING OLD TABLE AS antigues NEW TABLE AS noves
  FOR EACH STATEMENT EXECUTE FUNCTION f_log_preus();
--@@TEST@@ UPDATE track SET unit_price = unit_price + 0.10 WHERE genre_id = 2
--@@TEST@@ UPDATE track SET name = upper(name) WHERE album_id = 1
--@@TEST@@ UPDATE track SET unit_price = 1.99 WHERE album_id = 1 OR track_id = 2819
--@@TEST@@ UPDATE track SET unit_price = 0.49 WHERE track_id = 99999
--@@TEST@@ UPDATE track SET unit_price = CASE WHEN track_id % 2 = 0 THEN unit_price + 1 ELSE unit_price - 0.5 END WHERE album_id = 3
--@@TEST@@ SELECT moment, pistes, increment_mitja FROM log_preus ORDER BY id
```

Alternativa (ACCEPTADA):
```sql
CREATE TABLE log_preus (id serial PRIMARY KEY, moment timestamp, pistes integer, increment_mitja numeric);
CREATE FUNCTION f_log_preus() RETURNS trigger AS $$
BEGIN
  INSERT INTO log_preus (moment, pistes, increment_mitja)
  SELECT now(), count(*), round(avg(n.unit_price - a.unit_price), 2)
    FROM noves n JOIN antigues a USING (track_id)
   WHERE n.unit_price IS DISTINCT FROM a.unit_price
  HAVING count(*) > 0;
  RETURN NULL;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER t_log_preus AFTER UPDATE ON track REFERENCING NEW TABLE AS noves OLD TABLE AS antigues FOR EACH STATEMENT EXECUTE FUNCTION f_log_preus();
```

Incorrecta (REBUTJADA: Test 6 (SELECT moment, pistes, increment_mitja FROM log_preus ORD...): Wrong number of rows: got 5, expected 3):
```sql
CREATE TABLE log_preus (id serial PRIMARY KEY, moment timestamp, pistes integer, increment_mitja numeric);
CREATE FUNCTION f_log_preus() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  INSERT INTO log_preus (moment, pistes, increment_mitja)
  SELECT now(), count(*), round(avg(n.unit_price - a.unit_price), 2) FROM antigues a JOIN noves n ON n.track_id = a.track_id;
  RETURN NULL;
END $$;
CREATE TRIGGER t_log_preus AFTER UPDATE ON track REFERENCING OLD TABLE AS antigues NEW TABLE AS noves FOR EACH STATEMENT EXECUTE FUNCTION f_log_preus();
```

Incorrecta (REBUTJADA: Test 6 (SELECT moment, pistes, increment_mitja FROM log_preus ORD...): Wrong number of rows: got 143, expected 3):
```sql
CREATE TABLE log_preus (id serial PRIMARY KEY, moment timestamp, pistes integer, increment_mitja numeric);
CREATE FUNCTION f_log_preus() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.unit_price <> OLD.unit_price THEN
    INSERT INTO log_preus (moment, pistes, increment_mitja) VALUES (now(), 1, NEW.unit_price - OLD.unit_price);
  END IF;
  RETURN NULL;
END $$;
CREATE TRIGGER t_log_preus AFTER UPDATE ON track FOR EACH ROW EXECUTE FUNCTION f_log_preus();
```

Incorrecta (REBUTJADA: Test 6 (SELECT moment, pistes, increment_mitja FROM log_preus ORD...): Result sets differ (comparing unordered)):
```sql
CREATE TABLE log_preus (id serial PRIMARY KEY, moment timestamp, pistes integer, increment_mitja numeric);
CREATE FUNCTION f_log_preus() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  INSERT INTO log_preus (moment, pistes, increment_mitja)
  SELECT now(), (SELECT count(*) FROM noves), round(avg(n.unit_price - a.unit_price), 2) FROM antigues a JOIN noves n ON n.track_id = a.track_id
   WHERE n.unit_price <> a.unit_price HAVING count(*) > 0;
  RETURN NULL;
END $$;
CREATE TRIGGER t_log_preus AFTER UPDATE ON track REFERENCING OLD TABLE AS antigues NEW TABLE AS noves FOR EACH STATEMENT EXECUTE FUNCTION f_log_preus();
```

## Chinook — Tipus, arrays i JSON (pgobjrel)

### 1. Per a cada àlbum de l'artista `Led Zeppelin`, mostra el títol de l'àlbum i un array (`text[]`) amb els noms de les seves pistes ordenats per `track_id` (fes servir `array_agg(... ORDER BY ...)`). Columnes, en aquest ordre: títol, array de noms.

Referència:
```sql
SELECT al.title, array_agg(t.name::text ORDER BY t.track_id) FROM artist ar JOIN album al ON al.artist_id = ar.artist_id JOIN track t ON t.album_id = al.album_id WHERE ar.name = 'Led Zeppelin' GROUP BY al.album_id, al.title
```

Alternativa (ACCEPTADA):
```sql
SELECT al.title, ARRAY(SELECT t.name FROM track t WHERE t.album_id = al.album_id ORDER BY t.track_id) FROM album al WHERE al.artist_id = (SELECT artist_id FROM artist WHERE name = 'Led Zeppelin')
```

Incorrecta (REBUTJADA: Result sets differ (comparing unordered)):
```sql
SELECT al.title, string_agg(t.name, ', ' ORDER BY t.track_id) FROM artist ar JOIN album al ON al.artist_id = ar.artist_id JOIN track t ON t.album_id = al.album_id WHERE ar.name = 'Led Zeppelin' GROUP BY al.album_id, al.title
```

Incorrecta (REBUTJADA: Result sets differ (comparing unordered)):
```sql
SELECT al.title, array_agg(t.name ORDER BY t.name) FROM artist ar JOIN album al ON al.artist_id = ar.artist_id JOIN track t ON t.album_id = al.album_id WHERE ar.name = 'Led Zeppelin' GROUP BY al.album_id, al.title
```

### 2. Volem trobar els clients que han comprat alhora pistes de `Jazz` i de `Blues`. Per a cada client que hagi comprat pistes de tots dos gèneres (fes servir l'operador d'arrays `@>`), mostra el `customer_id`, el nom complet (`first_name`, un espai i `last_name`) i l'array (`text[]`) dels noms **diferents** dels gèneres que ha comprat, ordenat alfabèticament. Columnes, en aquest ordre: `customer_id`, nom complet, array de gèneres.

Referència:
```sql
SELECT c.customer_id, c.first_name || ' ' || c.last_name, array_agg(DISTINCT g.name::text ORDER BY g.name::text) FROM customer c JOIN invoice i ON i.customer_id = c.customer_id JOIN invoice_line il ON il.invoice_id = i.invoice_id JOIN track t ON t.track_id = il.track_id JOIN genre g ON g.genre_id = t.genre_id GROUP BY c.customer_id HAVING array_agg(g.name::text) @> ARRAY['Jazz', 'Blues']
```

Alternativa (ACCEPTADA):
```sql
WITH generes AS (SELECT i.customer_id, array_agg(DISTINCT g.name ORDER BY g.name) AS llista FROM invoice i JOIN invoice_line il USING (invoice_id) JOIN track t USING (track_id) JOIN genre g USING (genre_id) GROUP BY i.customer_id) SELECT c.customer_id, concat(c.first_name, ' ', c.last_name), gs.llista FROM customer c JOIN generes gs USING (customer_id) WHERE 'Jazz' = ANY (gs.llista) AND 'Blues' = ANY (gs.llista)
```

Incorrecta (REBUTJADA: Wrong number of rows: got more than 12, expected 12):
```sql
SELECT c.customer_id, c.first_name || ' ' || c.last_name, array_agg(DISTINCT g.name::text ORDER BY g.name::text) FROM customer c JOIN invoice i ON i.customer_id = c.customer_id JOIN invoice_line il ON il.invoice_id = i.invoice_id JOIN track t ON t.track_id = il.track_id JOIN genre g ON g.genre_id = t.genre_id GROUP BY c.customer_id HAVING array_agg(g.name::text) && ARRAY['Jazz', 'Blues']
```

Incorrecta (REBUTJADA: Result sets differ (comparing unordered)):
```sql
SELECT c.customer_id, c.first_name || ' ' || c.last_name, array_agg(g.name::text ORDER BY g.name::text) FROM customer c JOIN invoice i ON i.customer_id = c.customer_id JOIN invoice_line il ON il.invoice_id = i.invoice_id JOIN track t ON t.track_id = il.track_id JOIN genre g ON g.genre_id = t.genre_id GROUP BY c.customer_id HAVING array_agg(g.name::text) @> ARRAY['Jazz', 'Blues']
```

### 3. L'aplicació web dels agents de vendes vol rebre un document JSON per agent. Per a cada empleat que tingui clients assignats (`customer.support_rep_id`), retorna **una sola columna** de tipus `jsonb` amb un objecte amb aquestes claus: `"agent"` (nom complet de l'empleat: `first_name`, un espai i `last_name`), `"clients"` (nombre de clients que té assignats) i `"paisos"` (array JSON amb els països **diferents** dels seus clients, ordenats alfabèticament). Per exemple: `{"agent": "Jane Peacock", "clients": 21, "paisos": ["Brazil", "Canada", ...]}`. Fes servir `jsonb_build_object` i `jsonb_agg`.

Referència:
```sql
SELECT jsonb_build_object('agent', e.first_name || ' ' || e.last_name, 'clients', count(*), 'paisos', (SELECT jsonb_agg(DISTINCT c2.country ORDER BY c2.country) FROM customer c2 WHERE c2.support_rep_id = e.employee_id)) FROM employee e JOIN customer c ON c.support_rep_id = e.employee_id GROUP BY e.employee_id
```

Alternativa (ACCEPTADA):
```sql
SELECT jsonb_build_object('paisos', to_jsonb(array_agg(DISTINCT c.country ORDER BY c.country)), 'clients', count(DISTINCT c.customer_id), 'agent', concat(e.first_name, ' ', e.last_name)) FROM customer c JOIN employee e ON e.employee_id = c.support_rep_id GROUP BY e.employee_id, e.first_name, e.last_name
```

Incorrecta (REBUTJADA: Result sets differ (comparing unordered)):
```sql
SELECT jsonb_build_object('agent', e.first_name || ' ' || e.last_name, 'clients', count(*), 'paisos', jsonb_agg(c.country ORDER BY c.country)) FROM employee e JOIN customer c ON c.support_rep_id = e.employee_id GROUP BY e.employee_id
```

Incorrecta (REBUTJADA: Wrong number of columns: got 3, expected 1):
```sql
SELECT e.first_name || ' ' || e.last_name, count(*), jsonb_agg(DISTINCT c.country ORDER BY c.country) FROM employee e JOIN customer c ON c.support_rep_id = e.employee_id GROUP BY e.employee_id
```

Incorrecta (REBUTJADA: Result sets differ (comparing unordered)):
```sql
SELECT jsonb_build_object('agent', e.first_name || ' ' || e.last_name, 'clients', count(*), 'paisos', string_agg(DISTINCT c.country, ', ' ORDER BY c.country)) FROM employee e JOIN customer c ON c.support_rep_id = e.employee_id GROUP BY e.employee_id
```

### 4. Crea el tipus compost `fitxa_client AS (nom text, pais text, factures integer, total numeric)` i la funció `fitxa(p_customer_id integer) RETURNS fitxa_client` que retorni, per al client indicat, el nom complet (`first_name`, un espai i `last_name`), el país (`country`), el nombre de factures i la suma dels seus imports (0 factures i total 0 si no en té cap). Si el client no existeix, excepció amb `ERRCODE = 'no_data_found'`. Les proves criden la funció de maneres diferents, per exemple `SELECT (fitxa(1)).*` o comparant-ne el resultat amb una fila: `SELECT fitxa(1) = ROW('Luís Gonçalves', 'Brazil', 7, 39.62)::fitxa_client`.

Referència:
```sql
CREATE TYPE fitxa_client AS (nom text, pais text, factures integer, total numeric);
CREATE FUNCTION fitxa(p_customer_id integer) RETURNS fitxa_client LANGUAGE plpgsql AS $$
DECLARE
  f fitxa_client;
BEGIN
  SELECT c.first_name || ' ' || c.last_name, c.country,
         (SELECT count(*) FROM invoice i WHERE i.customer_id = c.customer_id),
         (SELECT coalesce(sum(i.total), 0) FROM invoice i WHERE i.customer_id = c.customer_id)
    INTO f FROM customer c WHERE c.customer_id = p_customer_id;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'El client % no existeix', p_customer_id USING ERRCODE = 'no_data_found';
  END IF;
  RETURN f;
END $$;
--@@TEST@@ SELECT (fitxa(1)).*
--@@TEST@@ SELECT fitxa(1) = ROW('Luís Gonçalves', 'Brazil', 7, 39.62)::fitxa_client
--@@TEST@@ SELECT (fitxa(6)).total, (fitxa(6)).factures
--@@TEST@@ SELECT f.nom, f.pais, f.total FROM customer c CROSS JOIN LATERAL fitxa(c.customer_id) f WHERE c.country = 'Canada' ORDER BY f.nom
--@@TEST@@ INSERT INTO customer (customer_id, first_name, last_name, country, email) VALUES (60, 'Clara', 'Nova', 'Spain', 'clara@example.com')
--@@TEST@@ SELECT (fitxa(60)).*
--@@TEST@@ SELECT fitxa(999)
```

Alternativa (ACCEPTADA):
```sql
CREATE TYPE fitxa_client AS (nom text, pais text, factures integer, total numeric);
CREATE FUNCTION fitxa(p_customer_id integer) RETURNS fitxa_client AS $$
DECLARE
  v_nom text;
  v_pais text;
BEGIN
  SELECT concat(first_name, ' ', last_name), country INTO v_nom, v_pais FROM customer WHERE customer_id = p_customer_id;
  IF NOT FOUND THEN
    RAISE no_data_found;
  END IF;
  RETURN (SELECT ROW(v_nom, v_pais, count(*), coalesce(sum(total), 0))::fitxa_client FROM invoice WHERE customer_id = p_customer_id);
END;
$$ LANGUAGE plpgsql;
```

Incorrecta (REBUTJADA: Test 6 (SELECT (fitxa(60)).*): Result sets differ (comparing unordered)):
```sql
CREATE TYPE fitxa_client AS (nom text, pais text, factures integer, total numeric);
CREATE FUNCTION fitxa(p_customer_id integer) RETURNS fitxa_client LANGUAGE sql AS $$
  SELECT c.first_name || ' ' || c.last_name, c.country, count(i.invoice_id)::integer, sum(i.total)
    FROM customer c LEFT JOIN invoice i ON i.customer_id = c.customer_id
   WHERE c.customer_id = p_customer_id GROUP BY c.customer_id
$$;
```

Incorrecta (REBUTJADA: Test 1 (SELECT (fitxa(1)).*): Result sets differ (comparing unordered)):
```sql
CREATE TYPE fitxa_client AS (nom text, factures integer, total numeric, pais text);
CREATE FUNCTION fitxa(p_customer_id integer) RETURNS fitxa_client LANGUAGE plpgsql AS $$
DECLARE
  f fitxa_client;
BEGIN
  SELECT c.first_name || ' ' || c.last_name, count(i.invoice_id), coalesce(sum(i.total), 0), c.country
    INTO f FROM customer c LEFT JOIN invoice i ON i.customer_id = c.customer_id
   WHERE c.customer_id = p_customer_id GROUP BY c.customer_id;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'No existeix' USING ERRCODE = 'no_data_found';
  END IF;
  RETURN f;
END $$;
```

### 5. Volem classificar els clients per nivells. Crea: el tipus enumerat `nivell_client` amb els valors `'bronze'`, `'plata'` i `'or'`, en aquest ordre (de menys a més); el domini `import_positiu` basat en `numeric(10,2)` que no admeti valors negatius (`CHECK (VALUE >= 0)`); i la funció `nivell(p_total import_positiu) RETURNS nivell_client` que retorni `bronze` si l'import és menor que 38.62, `plata` si és com a mínim 38.62 però menor que 42.62, i `or` si és 42.62 o més. Si l'import és NULL, ha de retornar NULL. Les proves fan, per exemple, `SELECT nivell(sum(total)) FROM invoice GROUP BY customer_id`, comparen nivells (`nivell(40) < 'or'`) i converteixen valors al domini (`SELECT (-1)::import_positiu` ha de donar error `check_violation`).

Referència:
```sql
CREATE TYPE nivell_client AS ENUM ('bronze', 'plata', 'or');
CREATE DOMAIN import_positiu AS numeric(10,2) CHECK (VALUE >= 0);
CREATE FUNCTION nivell(p_total import_positiu) RETURNS nivell_client LANGUAGE sql IMMUTABLE AS $$
  SELECT CASE WHEN p_total < 38.62 THEN 'bronze' WHEN p_total < 42.62 THEN 'plata' WHEN p_total >= 42.62 THEN 'or' END::nivell_client
$$;
--@@TEST@@ SELECT n, count(*) FROM (SELECT nivell(sum(total)) AS n FROM invoice GROUP BY customer_id) x GROUP BY n ORDER BY n
--@@TEST@@ SELECT nivell(38.62), nivell(42.61), nivell(42.62), nivell(0), nivell(NULL)
--@@TEST@@ SELECT nivell(40) < 'or', nivell(40) > 'bronze', 'plata'::nivell_client < 'or'::nivell_client
--@@TEST@@ SELECT 1.555::import_positiu, 0::import_positiu
--@@TEST@@ SELECT (-0.01)::import_positiu
--@@TEST@@ SELECT nivell(-5)
```

Alternativa (ACCEPTADA):
```sql
CREATE TYPE nivell_client AS ENUM ('bronze', 'plata', 'or');
CREATE DOMAIN import_positiu numeric(10,2) CONSTRAINT no_negatiu CHECK (VALUE >= 0);
CREATE FUNCTION nivell(p_total import_positiu) RETURNS nivell_client AS $$
BEGIN
  IF p_total IS NULL THEN
    RETURN NULL;
  ELSIF p_total >= 42.62 THEN
    RETURN 'or';
  ELSIF p_total >= 38.62 THEN
    RETURN 'plata';
  ELSE
    RETURN 'bronze';
  END IF;
END;
$$ LANGUAGE plpgsql;
```

Incorrecta (REBUTJADA: Test 3 (SELECT nivell(40) < 'or', nivell(40) > 'bronze', 'plata':...): Result sets differ (comparing unordered)):
```sql
CREATE TYPE nivell_client AS ENUM ('or', 'plata', 'bronze');
CREATE DOMAIN import_positiu AS numeric(10,2) CHECK (VALUE >= 0);
CREATE FUNCTION nivell(p_total import_positiu) RETURNS nivell_client LANGUAGE sql AS $$
  SELECT CASE WHEN p_total < 38.62 THEN 'bronze' WHEN p_total < 42.62 THEN 'plata' WHEN p_total >= 42.62 THEN 'or' END::nivell_client
$$;
```

Incorrecta (REBUTJADA: Test 4 (SELECT 1.555::import_positiu, 0::import_positiu): Result sets differ (comparing unordered)):
```sql
CREATE TYPE nivell_client AS ENUM ('bronze', 'plata', 'or');
CREATE DOMAIN import_positiu AS numeric CHECK (VALUE >= 0);
CREATE FUNCTION nivell(p_total import_positiu) RETURNS nivell_client LANGUAGE sql AS $$
  SELECT CASE WHEN p_total < 38.62 THEN 'bronze' WHEN p_total < 42.62 THEN 'plata' WHEN p_total >= 42.62 THEN 'or' END::nivell_client
$$;
```

Incorrecta (REBUTJADA: Test 1 (SELECT n, count(*) FROM (SELECT nivell(sum(total)) AS n F...): Result sets differ (comparing unordered)):
```sql
CREATE TYPE nivell_client AS ENUM ('bronze', 'plata', 'or');
CREATE DOMAIN import_positiu AS numeric(10,2) CHECK (VALUE >= 0);
CREATE FUNCTION nivell(p_total import_positiu) RETURNS nivell_client LANGUAGE sql AS $$
  SELECT CASE WHEN p_total <= 38.62 THEN 'bronze' WHEN p_total <= 42.62 THEN 'plata' ELSE 'or' END::nivell_client
$$;
```

### 6. La botiga rep els àlbums nous d'un proveïdor en format JSON, per exemple: `{"artista": "Rosalía", "album": "Motomami", "genere": "Latin", "pistes": [{"nom": "Saoko", "ms": 137000, "preu": 1.29}, {"nom": "Candy", "ms": 193000}]}`. Crea la funció `importa_album(p_dades jsonb) RETURNS integer` que: busqui l'artista pel nom exacte (`"artista"`) i, si no existeix, el creï a `artist` (`artist_id` = màxim + 1); creï l'àlbum a `album` (`album_id` = màxim + 1) amb el títol `"album"`; i creï una pista a `track` per a cada element de l'array `"pistes"`, en l'ordre de l'array i amb `track_id` consecutius a partir del màxim + 1, amb `name` = `"nom"`, `milliseconds` = `"ms"`, `unit_price` = `"preu"` (0.99 si l'element no té aquesta clau), `media_type_id` el del tipus `MPEG audio file`, `genre_id` el del gènere de nom `"genere"`, i `composer` i `bytes` a NULL. Ha de retornar el nombre de pistes creades. Validacions: si `"pistes"` no hi és o és un array buit, excepció amb `ERRCODE = 'invalid_parameter_value'`; si el gènere no existeix, excepció amb `ERRCODE = 'no_data_found'`.

Referència:
```sql
CREATE FUNCTION importa_album(p_dades jsonb) RETURNS integer LANGUAGE plpgsql AS $$
DECLARE
  v_artista integer;
  v_album integer;
  v_genere integer;
  v_media integer;
  v_track integer;
  v_pista jsonb;
  v_n integer := 0;
BEGIN
  IF jsonb_typeof(p_dades -> 'pistes') IS DISTINCT FROM 'array' OR jsonb_array_length(p_dades -> 'pistes') = 0 THEN
    RAISE EXCEPTION 'No hi ha pistes' USING ERRCODE = 'invalid_parameter_value';
  END IF;
  SELECT genre_id INTO v_genere FROM genre WHERE name = p_dades ->> 'genere';
  IF NOT FOUND THEN
    RAISE EXCEPTION 'El gènere % no existeix', p_dades ->> 'genere' USING ERRCODE = 'no_data_found';
  END IF;
  SELECT media_type_id INTO v_media FROM media_type WHERE name = 'MPEG audio file';
  SELECT artist_id INTO v_artista FROM artist WHERE name = p_dades ->> 'artista';
  IF NOT FOUND THEN
    SELECT max(artist_id) + 1 INTO v_artista FROM artist;
    INSERT INTO artist (artist_id, name) VALUES (v_artista, p_dades ->> 'artista');
  END IF;
  SELECT max(album_id) + 1 INTO v_album FROM album;
  INSERT INTO album (album_id, title, artist_id) VALUES (v_album, p_dades ->> 'album', v_artista);
  SELECT max(track_id) INTO v_track FROM track;
  FOR v_pista IN SELECT value FROM jsonb_array_elements(p_dades -> 'pistes') WITH ORDINALITY ORDER BY ordinality LOOP
    v_track := v_track + 1;
    INSERT INTO track (track_id, name, album_id, media_type_id, genre_id, composer, milliseconds, bytes, unit_price)
    VALUES (v_track, v_pista ->> 'nom', v_album, v_media, v_genere, NULL, (v_pista ->> 'ms')::integer, NULL,
            coalesce((v_pista ->> 'preu')::numeric, 0.99));
    v_n := v_n + 1;
  END LOOP;
  RETURN v_n;
END $$;
--@@TEST@@ SELECT importa_album('{"artista": "Rosalía", "album": "Motomami", "genere": "Latin", "pistes": [{"nom": "Saoko", "ms": 137000, "preu": 1.29}, {"nom": "Candy", "ms": 193000}, {"nom": "La Fama", "ms": 188000, "preu": 0.99}]}')
--@@TEST@@ SELECT importa_album('{"artista": "Queen", "album": "Live 2026", "genere": "Rock", "pistes": [{"nom": "Intro", "ms": 60000}]}')
--@@TEST@@ SELECT importa_album('{"artista": "Rosalía", "album": "El Mal Querer", "genere": "Pop", "pistes": [{"nom": "Malamente", "ms": 150000, "preu": 1.49}]}')
--@@TEST@@ SELECT importa_album('{"artista": "Ningú", "album": "Res", "genere": "Polka", "pistes": [{"nom": "Una", "ms": 1000}]}')
--@@TEST@@ SELECT importa_album('{"artista": "Ningú", "album": "Res", "genere": "Rock", "pistes": []}')
--@@TEST@@ SELECT importa_album('{"artista": "Ningú", "album": "Res", "genere": "Rock"}')
--@@TEST@@ SELECT * FROM artist WHERE artist_id > 275 ORDER BY artist_id
--@@TEST@@ SELECT * FROM album WHERE album_id > 347 ORDER BY album_id
--@@TEST@@ SELECT * FROM track WHERE track_id > 3503 ORDER BY track_id
```

Alternativa (ACCEPTADA):
```sql
CREATE FUNCTION importa_album(p_dades jsonb) RETURNS integer AS $$
DECLARE
  v_artista integer;
  v_album integer;
  v_genere integer;
  v_n integer;
BEGIN
  IF coalesce(jsonb_array_length(p_dades -> 'pistes'), 0) = 0 THEN
    RAISE invalid_parameter_value;
  END IF;
  v_genere := (SELECT genre_id FROM genre WHERE name = p_dades ->> 'genere');
  IF v_genere IS NULL THEN
    RAISE no_data_found;
  END IF;
  v_artista := (SELECT artist_id FROM artist WHERE name = p_dades ->> 'artista');
  IF v_artista IS NULL THEN
    INSERT INTO artist SELECT max(artist_id) + 1, p_dades ->> 'artista' FROM artist RETURNING artist_id INTO v_artista;
  END IF;
  INSERT INTO album SELECT max(album_id) + 1, p_dades ->> 'album', v_artista FROM album RETURNING album_id INTO v_album;
  INSERT INTO track (track_id, name, album_id, media_type_id, genre_id, milliseconds, unit_price)
  SELECT (SELECT max(track_id) FROM track) + p.n, p.pista ->> 'nom', v_album,
         (SELECT media_type_id FROM media_type WHERE name = 'MPEG audio file'), v_genere,
         (p.pista ->> 'ms')::integer, coalesce((p.pista ->> 'preu')::numeric, 0.99)
    FROM jsonb_array_elements(p_dades -> 'pistes') WITH ORDINALITY AS p(pista, n);
  GET DIAGNOSTICS v_n = ROW_COUNT;
  RETURN v_n;
END;
$$ LANGUAGE plpgsql;
```

Incorrecta (REBUTJADA: Test 4 (SELECT importa_album('{"artista": "Ningú", "album": "Res"...): yours returns rows, the expected one gives an error):
```sql
CREATE FUNCTION importa_album(p_dades jsonb) RETURNS integer LANGUAGE plpgsql AS $$
DECLARE
  v_artista integer;
  v_album integer;
  v_pista jsonb;
  v_n integer := 0;
BEGIN
  IF jsonb_array_length(p_dades -> 'pistes') = 0 THEN
    RAISE EXCEPTION 'No hi ha pistes' USING ERRCODE = 'invalid_parameter_value';
  END IF;
  SELECT max(artist_id) + 1 INTO v_artista FROM artist;
  INSERT INTO artist VALUES (v_artista, p_dades ->> 'artista');
  SELECT max(album_id) + 1 INTO v_album FROM album;
  INSERT INTO album VALUES (v_album, p_dades ->> 'album', v_artista);
  FOR v_pista IN SELECT * FROM jsonb_array_elements(p_dades -> 'pistes') LOOP
    INSERT INTO track (track_id, name, album_id, media_type_id, genre_id, milliseconds, unit_price)
    SELECT max(track_id) + 1, v_pista ->> 'nom', v_album, 1, (SELECT genre_id FROM genre WHERE name = p_dades ->> 'genere'),
           (v_pista ->> 'ms')::integer, coalesce((v_pista ->> 'preu')::numeric, 0.99) FROM track;
    v_n := v_n + 1;
  END LOOP;
  RETURN v_n;
END $$;
```

Incorrecta (REBUTJADA: Test 1 (SELECT importa_album('{"artista": "Rosalía", "album": "Mo...): yours gives an error, the expected one returns rows):
```sql
CREATE FUNCTION importa_album(p_dades jsonb) RETURNS integer LANGUAGE plpgsql AS $$
DECLARE
  v_artista integer;
  v_album integer;
  v_genere integer;
  v_pista jsonb;
  v_n integer := 0;
BEGIN
  IF jsonb_array_length(p_dades -> 'pistes') = 0 THEN
    RAISE EXCEPTION 'No hi ha pistes' USING ERRCODE = 'invalid_parameter_value';
  END IF;
  SELECT genre_id INTO v_genere FROM genre WHERE name = p_dades ->> 'genere';
  IF NOT FOUND THEN
    RAISE EXCEPTION 'No existeix' USING ERRCODE = 'no_data_found';
  END IF;
  SELECT artist_id INTO v_artista FROM artist WHERE name = p_dades ->> 'artista';
  IF NOT FOUND THEN
    SELECT max(artist_id) + 1 INTO v_artista FROM artist;
    INSERT INTO artist VALUES (v_artista, p_dades ->> 'artista');
  END IF;
  SELECT max(album_id) + 1 INTO v_album FROM album;
  INSERT INTO album VALUES (v_album, p_dades ->> 'album', v_artista);
  FOR v_pista IN SELECT * FROM jsonb_array_elements(p_dades -> 'pistes') LOOP
    INSERT INTO track (track_id, name, album_id, media_type_id, genre_id, milliseconds, unit_price)
    SELECT max(track_id) + 1, v_pista -> 'nom', v_album, 1, v_genere, (v_pista ->> 'ms')::integer, (v_pista ->> 'preu')::numeric FROM track;
    v_n := v_n + 1;
  END LOOP;
  RETURN v_n;
END $$;
```
