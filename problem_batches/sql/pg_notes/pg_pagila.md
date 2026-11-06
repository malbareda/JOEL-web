# Pagila PostgreSQL — verificació amb el corrector real (postgres)

Totes les respostes s'han passat pel checker real (`dmoj/checkers/postgres.py`) contra la base de dades `pagila`. Entre parèntesis, la retroacció que dona el checker.

## Pagila — Consultes avançades (pgadvquery)

### 1. Per a cada categoria, mostra el nom de la categoria (`category.name`), el nombre total de pel·lícules que hi pertanyen, quantes d'aquestes tenen la classificació (`rating`) `R` i quantes duren més de 120 minuts (`length > 120`). Fes servir `count(*) FILTER (WHERE …)`. Columnes, en aquest ordre: nom de la categoria, total, pel·lícules `R`, pel·lícules de més de 120 minuts.

Referència (0.04 s, referència + resposta):
```sql
SELECT c.name, count(*), count(*) FILTER (WHERE f.rating = 'R'), count(*) FILTER (WHERE f.length > 120)
FROM category c JOIN film_category fc ON fc.category_id = c.category_id JOIN film f ON f.film_id = fc.film_id
GROUP BY c.name
```

Alternativa (ACCEPTADA) — sense FILTER, amb sum(CASE …):
```sql
SELECT c.name, count(*), sum(CASE WHEN f.rating = 'R' THEN 1 ELSE 0 END), sum(CASE WHEN f.length > 120 THEN 1 ELSE 0 END)
FROM category c JOIN film_category USING (category_id) JOIN film f USING (film_id) GROUP BY c.category_id, c.name
```

Incorrecta (REBUTJADA: Result sets differ (comparing unordered)) — >= 120 en lloc de > 120:
```sql
SELECT c.name, count(*), count(*) FILTER (WHERE f.rating = 'R'), count(*) FILTER (WHERE f.length >= 120)
FROM category c JOIN film_category fc ON fc.category_id = c.category_id JOIN film f ON f.film_id = fc.film_id
GROUP BY c.name
```

Incorrecta (REBUTJADA: Result sets differ (comparing unordered)) — count(condició) compta també els false (només ignora NULL):
```sql
SELECT c.name, count(*), count(f.rating = 'R'), count(f.length > 120)
FROM category c JOIN film_category fc ON fc.category_id = c.category_id JOIN film f ON f.film_id = fc.film_id
GROUP BY c.name
```

### 2. Per a cada categoria, mostra la pel·lícula més llarga (la de `length` més gran). Si dins d'una categoria n'hi ha diverses empatades amb la durada màxima, queda't amb la primera per ordre alfabètic del títol. Fes servir `DISTINCT ON`. Columnes: nom de la categoria, títol (`title`) i durada (`length`); una fila per categoria.

Referència (0.03 s, referència + resposta):
```sql
SELECT DISTINCT ON (c.name) c.name, f.title, f.length
FROM category c JOIN film_category fc ON fc.category_id = c.category_id JOIN film f ON f.film_id = fc.film_id
ORDER BY c.name, f.length DESC, f.title
```

Alternativa (ACCEPTADA) — amb LATERAL i LIMIT 1:
```sql
SELECT c.name, t.title, t.length FROM category c CROSS JOIN LATERAL (
  SELECT f.title, f.length FROM film f JOIN film_category fc USING (film_id)
  WHERE fc.category_id = c.category_id ORDER BY f.length DESC, f.title LIMIT 1) t
```

Alternativa (ACCEPTADA) — amb row_number():
```sql
SELECT name, title, length FROM (
  SELECT c.name, f.title, f.length, row_number() OVER (PARTITION BY c.name ORDER BY f.length DESC, f.title) AS rn
  FROM category c JOIN film_category USING (category_id) JOIN film f USING (film_id)) t
WHERE rn = 1
```

Incorrecta (REBUTJADA: Result sets differ (comparing unordered)) — desempat per títol descendent:
```sql
SELECT DISTINCT ON (c.name) c.name, f.title, f.length
FROM category c JOIN film_category fc ON fc.category_id = c.category_id JOIN film f ON f.film_id = fc.film_id
ORDER BY c.name, f.length DESC, f.title DESC
```

Incorrecta (REBUTJADA: Wrong number of rows: got more than 16, expected 16) — subconsulta amb max(): surten tots els empatats (Action en té dues):
```sql
SELECT c.name, f.title, f.length
FROM category c JOIN film_category fc ON fc.category_id = c.category_id JOIN film f ON f.film_id = fc.film_id
WHERE f.length = (SELECT max(f2.length) FROM film f2 JOIN film_category fc2 USING (film_id) WHERE fc2.category_id = c.category_id)
```

Incorrecta (REBUTJADA: Result sets differ (comparing unordered)) — oblida el DESC: treu la més curta:
```sql
SELECT DISTINCT ON (c.name) c.name, f.title, f.length
FROM category c JOIN film_category fc ON fc.category_id = c.category_id JOIN film f ON f.film_id = fc.film_id
ORDER BY c.name, f.length
```

### 3. Calcula els ingressos (suma de `payment.amount`) per botiga i per classificació de pel·lícula, amb subtotals. La botiga d'un pagament és la de la còpia llogada (`payment` → `rental` → `inventory.store_id`) i la classificació és el `rating` de la pel·lícula d'aquesta còpia. Fes servir `GROUP BY ROLLUP (…)`: hi ha d'haver una fila per cada parella botiga–classificació, una fila de subtotal per a cada botiga (amb la classificació a `NULL`) i una fila de total general (botiga i classificació a `NULL`). Columnes: `store_id`, `rating`, total.

Referència (0.09 s, referència + resposta):
```sql
SELECT i.store_id, f.rating, sum(p.amount)
FROM payment p JOIN rental r ON r.rental_id = p.rental_id JOIN inventory i ON i.inventory_id = r.inventory_id
JOIN film f ON f.film_id = i.film_id
GROUP BY ROLLUP (i.store_id, f.rating)
```

Alternativa (ACCEPTADA) — amb GROUPING SETS:
```sql
SELECT i.store_id, f.rating, sum(p.amount)
FROM payment p JOIN rental r USING (rental_id) JOIN inventory i USING (inventory_id) JOIN film f USING (film_id)
GROUP BY GROUPING SETS ((i.store_id, f.rating), (i.store_id), ())
```

Alternativa (ACCEPTADA) — amb UNION ALL:
```sql
SELECT i.store_id, f.rating, sum(p.amount) FROM payment p JOIN rental r USING (rental_id) JOIN inventory i USING (inventory_id) JOIN film f USING (film_id) GROUP BY 1, 2
UNION ALL
SELECT i.store_id, NULL, sum(p.amount) FROM payment p JOIN rental r USING (rental_id) JOIN inventory i USING (inventory_id) GROUP BY 1
UNION ALL
SELECT NULL, NULL, sum(amount) FROM payment
```

Incorrecta (REBUTJADA: Wrong number of rows: got more than 13, expected 13) — CUBE: afegeix també els subtotals per classificació:
```sql
SELECT i.store_id, f.rating, sum(p.amount)
FROM payment p JOIN rental r ON r.rental_id = p.rental_id JOIN inventory i ON i.inventory_id = r.inventory_id
JOIN film f ON f.film_id = i.film_id
GROUP BY CUBE (i.store_id, f.rating)
```

Incorrecta (REBUTJADA: Result sets differ (comparing unordered)) — agrupa per l'empleat del pagament (staff_id) en lloc de per la botiga de la còpia:
```sql
SELECT p.staff_id, f.rating, sum(p.amount)
FROM payment p JOIN rental r ON r.rental_id = p.rental_id JOIN inventory i ON i.inventory_id = r.inventory_id
JOIN film f ON f.film_id = i.film_id
GROUP BY ROLLUP (p.staff_id, f.rating)
```

### 4. Volem veure l'activitat diària del juny de 2022, **incloent-hi els dies sense cap lloguer**. Per a cada dia de l'1 al 30 de juny de 2022 (genera'ls amb `generate_series`), mostra: el dia (de tipus `date`), el nombre de lloguers d'aquell dia (segons `rental_date::date`; 0 si no n'hi ha cap), el nombre acumulat de lloguers des de l'1 de juny fins a aquell dia inclòs (`sum(…) OVER (ORDER BY …)`) i la diferència respecte del dia anterior (lloguers del dia menys lloguers del dia anterior, amb `LAG`; `NULL` per a l'1 de juny). Columnes en aquest ordre.

Referència (0.05 s, referència + resposta):
```sql
SELECT d.dia, d.n, sum(d.n) OVER (ORDER BY d.dia), d.n - lag(d.n) OVER (ORDER BY d.dia)
FROM (SELECT g.dia::date AS dia, count(r.rental_id) AS n
      FROM generate_series(DATE '2022-06-01', DATE '2022-06-30', INTERVAL '1 day') AS g(dia)
      LEFT JOIN rental r ON r.rental_date::date = g.dia::date
      GROUP BY g.dia) d
```

Alternativa (ACCEPTADA) — generate_series d'enters i subconsulta correlacionada, marc ROWS explícit:
```sql
WITH dies AS (SELECT generate_series(1, 30) AS n),
     llog AS (SELECT DATE '2022-06-01' + n - 1 AS dia, (SELECT count(*) FROM rental r WHERE r.rental_date >= DATE '2022-06-01' + n - 1 AND r.rental_date < DATE '2022-06-01' + n) AS quants FROM dies)
SELECT dia, quants, sum(quants) OVER (ORDER BY dia ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW), quants - lag(quants) OVER (ORDER BY dia) FROM llog
```

Incorrecta (REBUTJADA: Wrong number of rows: got 8, expected 30) — sense generate_series: no surten els dies sense lloguers:
```sql
SELECT r.rental_date::date, count(*), sum(count(*)) OVER (ORDER BY r.rental_date::date), count(*) - lag(count(*)) OVER (ORDER BY r.rental_date::date)
FROM rental r WHERE r.rental_date >= '2022-06-01' AND r.rental_date < '2022-07-01' GROUP BY 1
```

Incorrecta (REBUTJADA: Result sets differ (comparing unordered)) — count(*) amb LEFT JOIN: els dies sense lloguers compten 1:
```sql
SELECT g.dia::date, count(*), sum(count(*)) OVER (ORDER BY g.dia), count(*) - lag(count(*)) OVER (ORDER BY g.dia)
FROM generate_series(DATE '2022-06-01', DATE '2022-06-30', INTERVAL '1 day') AS g(dia)
LEFT JOIN rental r ON r.rental_date::date = g.dia::date GROUP BY g.dia
```

Incorrecta (REBUTJADA: Result sets differ (comparing unordered)) — el dia surt com a timestamp, no com a date:
```sql
SELECT g.dia, count(r.rental_id), sum(count(r.rental_id)) OVER (ORDER BY g.dia), count(r.rental_id) - lag(count(r.rental_id)) OVER (ORDER BY g.dia)
FROM generate_series(DATE '2022-06-01', DATE '2022-06-30', INTERVAL '1 day') AS g(dia)
LEFT JOIN rental r ON r.rental_date::date = g.dia::date GROUP BY g.dia
```

### 5. Per a cada botiga del client (`customer.store_id`), mostra els clients que ocupen les **dues primeres posicions** per import total pagat (suma de `payment.amount`). Calcula la posició amb `RANK()` dins de cada botiga, de més a menys import: els clients empatats tenen la mateixa posició i surten tots. Columnes: `store_id`, `customer_id`, nom complet (`first_name || ' ' || last_name`), import total i posició.

Referència (0.05 s, referència + resposta):
```sql
SELECT store_id, customer_id, nom, total, posicio FROM (
  SELECT c.store_id, c.customer_id, c.first_name || ' ' || c.last_name AS nom, sum(p.amount) AS total,
         rank() OVER (PARTITION BY c.store_id ORDER BY sum(p.amount) DESC) AS posicio
  FROM customer c JOIN payment p ON p.customer_id = c.customer_id
  GROUP BY c.store_id, c.customer_id) t
WHERE posicio <= 2
```

Alternativa (ACCEPTADA) — posició calculada amb una subconsulta (1 + clients amb més import):
```sql
WITH t AS (SELECT c.store_id, c.customer_id, c.first_name || ' ' || c.last_name AS nom, sum(p.amount) AS total
           FROM customer c JOIN payment p USING (customer_id) GROUP BY 1, 2, 3)
SELECT * FROM (SELECT *, 1 + (SELECT count(*) FROM t t2 WHERE t2.store_id = t.store_id AND t2.total > t.total) AS posicio FROM t) x WHERE posicio <= 2
```

Incorrecta (REBUTJADA: Wrong number of rows: got 4, expected 5) — row_number(): talla l'empat de la segona posició de la botiga 2:
```sql
SELECT store_id, customer_id, nom, total, posicio FROM (
  SELECT c.store_id, c.customer_id, c.first_name || ' ' || c.last_name AS nom, sum(p.amount) AS total,
         row_number() OVER (PARTITION BY c.store_id ORDER BY sum(p.amount) DESC) AS posicio
  FROM customer c JOIN payment p ON p.customer_id = c.customer_id
  GROUP BY c.store_id, c.customer_id) t
WHERE posicio <= 2
```

Incorrecta (REBUTJADA: Wrong number of rows: got 4, expected 5) — LATERAL … LIMIT 2: també talla l'empat:
```sql
SELECT s.store_id, t.* FROM store s CROSS JOIN LATERAL (
  SELECT c.customer_id, c.first_name || ' ' || c.last_name, sum(p.amount) AS total, rank() OVER (ORDER BY sum(p.amount) DESC)
  FROM customer c JOIN payment p USING (customer_id) WHERE c.store_id = s.store_id
  GROUP BY c.customer_id ORDER BY total DESC LIMIT 2) t
```

Incorrecta (REBUTJADA: Wrong number of rows: got 4, expected 5) — fa servir la botiga de la còpia llogada en lloc de la del client:
```sql
SELECT store_id, customer_id, nom, total, posicio FROM (
  SELECT i.store_id, c.customer_id, c.first_name || ' ' || c.last_name AS nom, sum(p.amount) AS total,
         rank() OVER (PARTITION BY i.store_id ORDER BY sum(p.amount) DESC) AS posicio
  FROM customer c JOIN payment p ON p.customer_id = c.customer_id JOIN rental r ON r.rental_id = p.rental_id JOIN inventory i ON i.inventory_id = r.inventory_id
  GROUP BY i.store_id, c.customer_id) t
WHERE posicio <= 2
```

### 6. Al «joc de Kevin Bacon», dos actors estan a distància 1 si han sortit junts en alguna pel·lícula, i a distància 2 si no han sortit mai junts però tenen algun company de repartiment en comú. Amb una consulta recursiva (`WITH RECURSIVE`) que parteixi de l'actriu `PENELOPE GUINESS`, mostra els actors que estan **exactament a distància 2** d'ella (la seva distància mínima és 2). Columnes: `actor_id`, `first_name`, `last_name`.

Referència (0.08 s, referència + resposta):
```sql
WITH RECURSIVE xarxa (actor_id, dist) AS (
  SELECT actor_id, 0 FROM actor WHERE first_name = 'PENELOPE' AND last_name = 'GUINESS'
  UNION ALL
  SELECT fa2.actor_id, x.dist + 1
  FROM xarxa x JOIN film_actor fa1 ON fa1.actor_id = x.actor_id
  JOIN film_actor fa2 ON fa2.film_id = fa1.film_id AND fa2.actor_id <> fa1.actor_id
  WHERE x.dist < 2)
SELECT a.actor_id, a.first_name, a.last_name
FROM (SELECT actor_id, min(dist) AS dist FROM xarxa GROUP BY actor_id) m JOIN actor a ON a.actor_id = m.actor_id
WHERE m.dist = 2
```

Alternativa (ACCEPTADA) — recursiva amb array del camí per evitar cicles:
```sql
WITH RECURSIVE xarxa (actor_id, dist, cami) AS (
  SELECT actor_id, 0, ARRAY[actor_id] FROM actor WHERE first_name = 'PENELOPE' AND last_name = 'GUINESS'
  UNION ALL
  SELECT DISTINCT fa2.actor_id, x.dist + 1, x.cami || fa2.actor_id
  FROM xarxa x JOIN film_actor fa1 ON fa1.actor_id = x.actor_id
  JOIN film_actor fa2 ON fa2.film_id = fa1.film_id
  WHERE x.dist < 2 AND NOT fa2.actor_id = ANY (x.cami))
SELECT actor_id, first_name, last_name FROM actor
WHERE actor_id IN (SELECT actor_id FROM xarxa WHERE dist = 2)
  AND actor_id NOT IN (SELECT actor_id FROM xarxa WHERE dist < 2)
```

Alternativa (ACCEPTADA) — sense recursió (dos nivells de JOIN fixos); el checker no pot exigir WITH RECURSIVE:
```sql
SELECT a.actor_id, a.first_name, a.last_name FROM actor a
WHERE a.actor_id NOT IN (SELECT fa2.actor_id FROM actor p JOIN film_actor fa1 ON fa1.actor_id = p.actor_id JOIN film_actor fa2 ON fa2.film_id = fa1.film_id WHERE p.first_name = 'PENELOPE' AND p.last_name = 'GUINESS')
AND a.actor_id IN (SELECT fb.actor_id FROM actor p JOIN film_actor fa1 ON fa1.actor_id = p.actor_id JOIN film_actor fa2 ON fa2.film_id = fa1.film_id JOIN film_actor fb2 ON fb2.actor_id = fa2.actor_id JOIN film_actor fb ON fb.film_id = fb2.film_id WHERE p.first_name = 'PENELOPE' AND p.last_name = 'GUINESS')
```

Incorrecta (REBUTJADA: Wrong number of rows: got more than 120, expected 120) — no es queda amb la distància mínima: hi surten actors que també són a distància 1 (i repetits):
```sql
WITH RECURSIVE xarxa (actor_id, dist) AS (
  SELECT actor_id, 0 FROM actor WHERE first_name = 'PENELOPE' AND last_name = 'GUINESS'
  UNION
  SELECT fa2.actor_id, x.dist + 1
  FROM xarxa x JOIN film_actor fa1 ON fa1.actor_id = x.actor_id
  JOIN film_actor fa2 ON fa2.film_id = fa1.film_id AND fa2.actor_id <> fa1.actor_id
  WHERE x.dist < 2)
SELECT a.actor_id, a.first_name, a.last_name FROM xarxa x JOIN actor a USING (actor_id) WHERE x.dist = 2
```

Incorrecta (REBUTJADA: Wrong number of rows: got more than 120, expected 120) — DISTINCT però sense excloure els de distància 1:
```sql
WITH RECURSIVE xarxa (actor_id, dist) AS (
  SELECT actor_id, 0 FROM actor WHERE first_name = 'PENELOPE' AND last_name = 'GUINESS'
  UNION
  SELECT fa2.actor_id, x.dist + 1
  FROM xarxa x JOIN film_actor fa1 ON fa1.actor_id = x.actor_id
  JOIN film_actor fa2 ON fa2.film_id = fa1.film_id AND fa2.actor_id <> fa1.actor_id
  WHERE x.dist < 2)
SELECT DISTINCT a.actor_id, a.first_name, a.last_name FROM xarxa x JOIN actor a USING (actor_id) WHERE x.dist = 2 AND a.actor_id <> 1
```

## Pagila — Funcions (pgfunc)

### 1. Crea la funció `total_pagat(p_customer_id integer) RETURNS numeric`, en `LANGUAGE sql`, que retorni l'import total que ha pagat un client (suma de `payment.amount`). Si el client no té cap pagament, no existeix o el paràmetre és `NULL`, ha de retornar `0` (no `NULL`).

Referència (1.15 s, referència + resposta):
```sql
CREATE FUNCTION total_pagat(p_customer_id integer) RETURNS numeric
LANGUAGE sql STABLE AS $$
  SELECT coalesce(sum(amount), 0) FROM payment WHERE customer_id = p_customer_id
$$;
--@@TEST@@ SELECT total_pagat(1)
--@@TEST@@ SELECT total_pagat(526)
--@@TEST@@ SELECT total_pagat(9999)
--@@TEST@@ SELECT total_pagat(NULL)
--@@TEST@@ SELECT customer_id, total_pagat(customer_id) FROM customer WHERE total_pagat(customer_id) > 190
```

Alternativa (ACCEPTADA) — en PL/pgSQL (l'enunciat demana LANGUAGE sql, però el checker no ho pot comprovar):
```sql
CREATE OR REPLACE FUNCTION total_pagat(p_customer_id integer) RETURNS numeric AS $$
DECLARE t numeric;
BEGIN
  SELECT sum(amount) INTO t FROM payment WHERE customer_id = p_customer_id;
  IF t IS NULL THEN t := 0; END IF;
  RETURN t;
END $$ LANGUAGE plpgsql;
```

Incorrecta (REBUTJADA: Test 3 (SELECT total_pagat(9999)): Result sets differ (comparing unordered)) — sense coalesce: retorna NULL per al client 9999:
```sql
CREATE FUNCTION total_pagat(p_customer_id integer) RETURNS numeric
LANGUAGE sql AS $$ SELECT sum(amount) FROM payment WHERE customer_id = p_customer_id $$;
```

Incorrecta (REBUTJADA: Test 1 (SELECT total_pagat(1)): Result sets differ (comparing unordered)) — RETURNS integer: arrodoneix l'import:
```sql
CREATE FUNCTION total_pagat(p_customer_id integer) RETURNS integer
LANGUAGE sql AS $$ SELECT coalesce(sum(amount), 0) FROM payment WHERE customer_id = p_customer_id $$;
```

### 2. Crea la funció `num_copies(p_film_id integer, p_store_id integer DEFAULT NULL) RETURNS integer` que retorni quantes còpies (`inventory`) té una pel·lícula a la botiga indicada. Si no s'indica la botiga (o és `NULL`), ha de comptar les còpies de totes les botigues. Respecta els noms dels paràmetres: les proves també criden la funció amb notació de noms (`num_copies(p_store_id => 2, p_film_id => 3)`).

Referència (0.88 s, referència + resposta):
```sql
CREATE FUNCTION num_copies(p_film_id integer, p_store_id integer DEFAULT NULL) RETURNS integer
LANGUAGE sql STABLE AS $$
  SELECT count(*)::integer FROM inventory
  WHERE film_id = p_film_id AND (p_store_id IS NULL OR store_id = p_store_id)
$$;
--@@TEST@@ SELECT num_copies(1)
--@@TEST@@ SELECT num_copies(1, 1)
--@@TEST@@ SELECT num_copies(2, 1)
--@@TEST@@ SELECT num_copies(3)
--@@TEST@@ SELECT num_copies(14)
--@@TEST@@ SELECT num_copies(p_store_id => 2, p_film_id => 3)
```

Alternativa (ACCEPTADA) — PL/pgSQL amb IF:
```sql
CREATE FUNCTION num_copies(p_film_id integer, p_store_id integer DEFAULT NULL) RETURNS integer AS $$
BEGIN
  IF p_store_id IS NULL THEN
    RETURN (SELECT count(*) FROM inventory WHERE film_id = p_film_id);
  END IF;
  RETURN (SELECT count(*) FROM inventory WHERE film_id = p_film_id AND store_id = p_store_id);
END $$ LANGUAGE plpgsql;
```

Incorrecta (REBUTJADA: Test 1 (SELECT num_copies(1)): Result sets differ (comparing unordered)) — store_id = NULL no és mai cert: num_copies(1) torna 0:
```sql
CREATE FUNCTION num_copies(p_film_id integer, p_store_id integer DEFAULT NULL) RETURNS integer
LANGUAGE sql AS $$ SELECT count(*)::integer FROM inventory WHERE film_id = p_film_id AND store_id = p_store_id $$;
```

Incorrecta (REBUTJADA: Test 1 (SELECT num_copies(1)): yours gives an error (SQLSTATE 42883 undefined_function), the expected one returns rows) — sense DEFAULT: num_copies(1) dona error:
```sql
CREATE FUNCTION num_copies(p_film_id integer, p_store_id integer) RETURNS integer
LANGUAGE sql AS $$ SELECT count(*)::integer FROM inventory WHERE film_id = p_film_id AND (p_store_id IS NULL OR store_id = p_store_id) $$;
```

Incorrecta (REBUTJADA: Test 6 (SELECT num_copies(p_store_id => 2, p_film_id => 3)): yours gives an error (SQLSTATE 42883 undefined_function), the expected one returns rows) — noms de paràmetres diferents: falla la crida amb notació de noms:
```sql
CREATE FUNCTION num_copies(film integer, botiga integer DEFAULT NULL) RETURNS integer
LANGUAGE sql AS $$ SELECT count(*)::integer FROM inventory WHERE film_id = film AND (botiga IS NULL OR store_id = botiga) $$;
```

### 3. Crea la funció `pelis_actor(p_nom text, p_cognom text) RETURNS TABLE (film_id integer, title text, categoria text)` que retorni les pel·lícules en què ha sortit l'actor amb aquest nom i cognom, amb el nom de la categoria de cada pel·lícula. La cerca no ha de distingir majúscules de minúscules (`'penelope'` ha de trobar `PENELOPE`). Si hi ha més d'un actor amb el mateix nom i cognom, ha de retornar les pel·lícules de tots ells. Si no n'hi ha cap, no retorna cap fila.

Referència (0.90 s, referència + resposta):
```sql
CREATE FUNCTION pelis_actor(p_nom text, p_cognom text)
RETURNS TABLE (film_id integer, title text, categoria text)
LANGUAGE sql STABLE AS $$
  SELECT f.film_id, f.title, c.name
  FROM actor a JOIN film_actor fa ON fa.actor_id = a.actor_id JOIN film f ON f.film_id = fa.film_id
  JOIN film_category fc ON fc.film_id = f.film_id JOIN category c ON c.category_id = fc.category_id
  WHERE upper(a.first_name) = upper(p_nom) AND upper(a.last_name) = upper(p_cognom)
$$;
--@@TEST@@ SELECT * FROM pelis_actor('PENELOPE', 'GUINESS')
--@@TEST@@ SELECT * FROM pelis_actor('Penelope', 'guiness')
--@@TEST@@ SELECT count(*), count(DISTINCT film_id) FROM pelis_actor('susan', 'davis')
--@@TEST@@ SELECT * FROM pelis_actor('Joan', 'Puig')
--@@TEST@@ SELECT categoria, count(*) FROM pelis_actor('ed', 'chase') GROUP BY categoria
```

Alternativa (ACCEPTADA) — PL/pgSQL amb RETURN QUERY i ILIKE:
```sql
CREATE FUNCTION pelis_actor(p_nom text, p_cognom text)
RETURNS TABLE (film_id integer, title text, categoria text) AS $$
BEGIN
  RETURN QUERY
  SELECT f.film_id, f.title, c.name
  FROM film f JOIN film_category USING (film_id) JOIN category c USING (category_id)
  WHERE f.film_id IN (SELECT fa.film_id FROM film_actor fa JOIN actor a USING (actor_id)
                      WHERE a.first_name ILIKE p_nom AND a.last_name ILIKE p_cognom);
END $$ LANGUAGE plpgsql;
```

Incorrecta (REBUTJADA: Test 2 (SELECT * FROM pelis_actor('Penelope', 'guiness')): Wrong number of rows: got 0, expected 19) — distingeix majúscules:
```sql
CREATE FUNCTION pelis_actor(p_nom text, p_cognom text)
RETURNS TABLE (film_id integer, title text, categoria text)
LANGUAGE sql AS $$
  SELECT f.film_id, f.title, c.name
  FROM actor a JOIN film_actor fa ON fa.actor_id = a.actor_id JOIN film f ON f.film_id = fa.film_id
  JOIN film_category fc ON fc.film_id = f.film_id JOIN category c ON c.category_id = fc.category_id
  WHERE a.first_name = p_nom AND a.last_name = p_cognom
$$;
```

Incorrecta (REBUTJADA: Test 3 (SELECT count(*), count(DISTINCT film_id) FROM pelis_actor...): Result sets differ (comparing unordered)) — SELECT INTO d'un sol actor_id: amb dues SUSAN DAVIS només en troba un:
```sql
CREATE FUNCTION pelis_actor(p_nom text, p_cognom text)
RETURNS TABLE (film_id integer, title text, categoria text) AS $$
DECLARE v_actor integer;
BEGIN
  SELECT actor_id INTO v_actor FROM actor WHERE upper(first_name) = upper(p_nom) AND upper(last_name) = upper(p_cognom);
  RETURN QUERY
  SELECT f.film_id, f.title, c.name
  FROM film_actor fa JOIN film f ON f.film_id = fa.film_id
  JOIN film_category fc ON fc.film_id = f.film_id JOIN category c ON c.category_id = fc.category_id
  WHERE fa.actor_id = v_actor;
END $$ LANGUAGE plpgsql;
```

### 4. Crea la funció `estadistiques_client(p_customer_id integer, OUT num_lloguers integer, OUT total_pagat numeric, OUT darrer_lloguer date)` que calculi, per a un client: el nombre de lloguers que ha fet (`rental`), l'import total que ha pagat (`payment`, segons `payment.customer_id`) i la data (de tipus `date`) del seu lloguer més recent. Si el client no existeix, ha de retornar `0`, `0` i `NULL`. Compte: a pagila hi ha lloguers amb més d'un pagament, i pagaments de clients diferents per a un mateix lloguer.

Referència (1.15 s, referència + resposta):
```sql
CREATE FUNCTION estadistiques_client(p_customer_id integer,
    OUT num_lloguers integer, OUT total_pagat numeric, OUT darrer_lloguer date)
LANGUAGE plpgsql STABLE AS $$
BEGIN
  SELECT count(*), max(rental_date)::date INTO num_lloguers, darrer_lloguer
  FROM rental WHERE customer_id = p_customer_id;
  SELECT coalesce(sum(amount), 0) INTO total_pagat FROM payment WHERE customer_id = p_customer_id;
END $$;
--@@TEST@@ SELECT * FROM estadistiques_client(1)
--@@TEST@@ SELECT * FROM estadistiques_client(9999)
--@@TEST@@ SELECT (estadistiques_client(401)).total_pagat
--@@TEST@@ SELECT e.num_lloguers, e.darrer_lloguer FROM estadistiques_client(148) e
--@@TEST@@ SELECT c.customer_id, e.* FROM customer c CROSS JOIN LATERAL estadistiques_client(c.customer_id) e WHERE c.last_name LIKE 'S%'
```

Alternativa (ACCEPTADA) — LANGUAGE sql amb tres subconsultes:
```sql
CREATE FUNCTION estadistiques_client(p_customer_id integer,
    OUT num_lloguers integer, OUT total_pagat numeric, OUT darrer_lloguer date)
LANGUAGE sql AS $$
  SELECT (SELECT count(*) FROM rental WHERE customer_id = p_customer_id)::integer,
         (SELECT coalesce(sum(amount), 0) FROM payment WHERE customer_id = p_customer_id),
         (SELECT max(rental_date)::date FROM rental WHERE customer_id = p_customer_id)
$$;
```

Incorrecta (REBUTJADA: Test 3 (SELECT (estadistiques_client(401)).total_pagat): Result sets differ (comparing unordered)) — JOIN rental-payment per rental_id: compta pagaments d'altres clients (lloguer 4591):
```sql
CREATE FUNCTION estadistiques_client(p_customer_id integer,
    OUT num_lloguers integer, OUT total_pagat numeric, OUT darrer_lloguer date)
LANGUAGE sql AS $$
  SELECT count(*)::integer, coalesce(sum(p.amount), 0), max(r.rental_date)::date
  FROM rental r LEFT JOIN payment p ON p.rental_id = r.rental_id
  WHERE r.customer_id = p_customer_id
$$;
```

Incorrecta (REBUTJADA: Test 2 (SELECT * FROM estadistiques_client(9999)): Result sets differ (comparing unordered)) — sense coalesce: total_pagat NULL per al client inexistent:
```sql
CREATE FUNCTION estadistiques_client(p_customer_id integer,
    OUT num_lloguers integer, OUT total_pagat numeric, OUT darrer_lloguer date)
LANGUAGE plpgsql AS $$
BEGIN
  SELECT count(*), max(rental_date)::date INTO num_lloguers, darrer_lloguer FROM rental WHERE customer_id = p_customer_id;
  SELECT sum(amount) INTO total_pagat FROM payment WHERE customer_id = p_customer_id;
END $$;
```

### 5. Crea la funció PL/pgSQL `preu_lloguer(p_film_id integer, p_dies integer) RETURNS numeric` que calculi quant costa llogar una pel·lícula durant `p_dies` dies: el preu de lloguer (`rental_rate`) cobreix els primers `rental_duration` dies, i cada dia de més costa 1.00 addicional. Validacions, en aquest ordre: si `p_dies` és `NULL` o menor que 1, llança una excepció amb `ERRCODE = 'invalid_parameter_value'`; si la pel·lícula no existeix, llança una excepció amb `ERRCODE = 'no_data_found'`.

Referència (0.92 s, referència + resposta):
```sql
CREATE FUNCTION preu_lloguer(p_film_id integer, p_dies integer) RETURNS numeric
LANGUAGE plpgsql STABLE AS $$
DECLARE
  v_preu numeric;
  v_durada integer;
BEGIN
  IF p_dies IS NULL OR p_dies < 1 THEN
    RAISE EXCEPTION 'Nombre de dies no vàlid: %', p_dies USING ERRCODE = 'invalid_parameter_value';
  END IF;
  SELECT rental_rate, rental_duration INTO v_preu, v_durada FROM film WHERE film_id = p_film_id;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'No existeix la pel·lícula %', p_film_id USING ERRCODE = 'no_data_found';
  END IF;
  IF p_dies > v_durada THEN
    v_preu := v_preu + (p_dies - v_durada) * 1.00;
  END IF;
  RETURN v_preu;
END $$;
--@@TEST@@ SELECT preu_lloguer(1, 3)
--@@TEST@@ SELECT preu_lloguer(1, 6)
--@@TEST@@ SELECT preu_lloguer(1, 9)
--@@TEST@@ SELECT preu_lloguer(2, 5)
--@@TEST@@ SELECT preu_lloguer(1, 0)
--@@TEST@@ SELECT preu_lloguer(1, NULL)
--@@TEST@@ SELECT preu_lloguer(9999, 3)
--@@TEST@@ SELECT preu_lloguer(9999, -2)
```

Alternativa (ACCEPTADA) — %ROWTYPE i codis SQLSTATE numèrics:
```sql
CREATE FUNCTION preu_lloguer(p_film_id integer, p_dies integer) RETURNS numeric AS $$
DECLARE f film%ROWTYPE;
BEGIN
  IF coalesce(p_dies, 0) <= 0 THEN
    RAISE EXCEPTION 'dies incorrectes' USING ERRCODE = '22023';
  END IF;
  SELECT * INTO f FROM film WHERE film_id = p_film_id;
  IF f.film_id IS NULL THEN
    RAISE EXCEPTION 'pel·lícula inexistent' USING ERRCODE = 'P0002';
  END IF;
  RETURN f.rental_rate + greatest(p_dies - f.rental_duration, 0);
END $$ LANGUAGE plpgsql;
```

Incorrecta (REBUTJADA: Test 6 (SELECT preu_lloguer(1, NULL)): yours returns rows, the expected one gives an error (SQLSTATE 22023 invalid_parameter_value)) — p_dies < 1 amb p_dies NULL no és cert: no valida el NULL:
```sql
CREATE FUNCTION preu_lloguer(p_film_id integer, p_dies integer) RETURNS numeric AS $$
DECLARE v_preu numeric; v_durada integer;
BEGIN
  IF p_dies < 1 THEN
    RAISE EXCEPTION 'dies' USING ERRCODE = 'invalid_parameter_value';
  END IF;
  SELECT rental_rate, rental_duration INTO v_preu, v_durada FROM film WHERE film_id = p_film_id;
  IF NOT FOUND THEN RAISE EXCEPTION 'film' USING ERRCODE = 'no_data_found'; END IF;
  RETURN v_preu + greatest(p_dies - v_durada, 0);
END $$ LANGUAGE plpgsql;
```

Incorrecta (REBUTJADA: Test 5 (SELECT preu_lloguer(1, 0)): yours gives an error (SQLSTATE P0001 raise_exception), the expected one gives an error (SQLSTATE 22023 invalid_parameter_value)) — RAISE sense ERRCODE (P0001):
```sql
CREATE FUNCTION preu_lloguer(p_film_id integer, p_dies integer) RETURNS numeric AS $$
DECLARE v_preu numeric; v_durada integer;
BEGIN
  IF p_dies IS NULL OR p_dies < 1 THEN
    RAISE EXCEPTION 'dies';
  END IF;
  SELECT rental_rate, rental_duration INTO v_preu, v_durada FROM film WHERE film_id = p_film_id;
  IF NOT FOUND THEN RAISE EXCEPTION 'film'; END IF;
  RETURN v_preu + greatest(p_dies - v_durada, 0);
END $$ LANGUAGE plpgsql;
```

Incorrecta (REBUTJADA: Test 7 (SELECT preu_lloguer(9999, 3)): yours returns rows, the expected one gives an error (SQLSTATE P0002 no_data_found)) — no comprova si la pel·lícula existeix: retorna NULL:
```sql
CREATE FUNCTION preu_lloguer(p_film_id integer, p_dies integer) RETURNS numeric AS $$
DECLARE v_preu numeric; v_durada integer;
BEGIN
  IF p_dies IS NULL OR p_dies < 1 THEN
    RAISE EXCEPTION 'dies' USING ERRCODE = 'invalid_parameter_value';
  END IF;
  SELECT rental_rate, rental_duration INTO v_preu, v_durada FROM film WHERE film_id = p_film_id;
  RETURN v_preu + greatest(p_dies - v_durada, 0);
END $$ LANGUAGE plpgsql;
```

Incorrecta (REBUTJADA: Test 8 (SELECT preu_lloguer(9999, -2)): yours gives an error (SQLSTATE P0002 no_data_found), the expected one gives an error (SQLSTATE 22023 invalid_parameter_value)) — valida en l'ordre contrari: preu_lloguer(9999, -2) dona no_data_found:
```sql
CREATE FUNCTION preu_lloguer(p_film_id integer, p_dies integer) RETURNS numeric AS $$
DECLARE v_preu numeric; v_durada integer;
BEGIN
  SELECT rental_rate, rental_duration INTO v_preu, v_durada FROM film WHERE film_id = p_film_id;
  IF NOT FOUND THEN RAISE EXCEPTION 'film' USING ERRCODE = 'no_data_found'; END IF;
  IF p_dies IS NULL OR p_dies < 1 THEN
    RAISE EXCEPTION 'dies' USING ERRCODE = 'invalid_parameter_value';
  END IF;
  RETURN v_preu + greatest(p_dies - v_durada, 0);
END $$ LANGUAGE plpgsql;
```

### 6. Crea la funció PL/pgSQL `ultimes_pelis(p_customer_id integer, p_quantes integer DEFAULT 3) RETURNS text` que retorni els títols de les `p_quantes` darreres pel·lícules que ha llogat el client, de la més recent a la més antiga (per `rental_date` descendent i, en cas d'empat, per `rental_id` descendent), separats per `', '` (coma i espai). Si una pel·lícula s'ha llogat més d'una vegada, surt cada vegada. Recorre els lloguers amb un bucle `FOR … IN SELECT … LOOP`. Si `p_quantes` és 0 o negatiu, retorna la cadena buida `''` (no `NULL`). Si el client no existeix, llança una excepció amb `ERRCODE = 'no_data_found'`.

Referència (0.85 s, referència + resposta):
```sql
CREATE FUNCTION ultimes_pelis(p_customer_id integer, p_quantes integer DEFAULT 3) RETURNS text
LANGUAGE plpgsql STABLE AS $$
DECLARE
  v_resultat text := '';
  r record;
BEGIN
  PERFORM 1 FROM customer WHERE customer_id = p_customer_id;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'No existeix el client %', p_customer_id USING ERRCODE = 'no_data_found';
  END IF;
  FOR r IN SELECT f.title
           FROM rental re JOIN inventory i ON i.inventory_id = re.inventory_id JOIN film f ON f.film_id = i.film_id
           WHERE re.customer_id = p_customer_id
           ORDER BY re.rental_date DESC, re.rental_id DESC
           LIMIT greatest(p_quantes, 0)
  LOOP
    IF v_resultat <> '' THEN
      v_resultat := v_resultat || ', ';
    END IF;
    v_resultat := v_resultat || r.title;
  END LOOP;
  RETURN v_resultat;
END $$;
--@@TEST@@ SELECT ultimes_pelis(1)
--@@TEST@@ SELECT ultimes_pelis(1, 5)
--@@TEST@@ SELECT ultimes_pelis(216, 22)
--@@TEST@@ SELECT ultimes_pelis(1, 0)
--@@TEST@@ SELECT ultimes_pelis(1, -4)
--@@TEST@@ SELECT ultimes_pelis(9999)
```

Alternativa (ACCEPTADA) — string_agg en lloc del bucle (el checker no pot exigir el FOR):
```sql
CREATE FUNCTION ultimes_pelis(p_customer_id integer, p_quantes integer DEFAULT 3) RETURNS text AS $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM customer WHERE customer_id = p_customer_id) THEN
    RAISE EXCEPTION 'client' USING ERRCODE = 'P0002';
  END IF;
  IF p_quantes <= 0 THEN RETURN ''; END IF;
  RETURN (SELECT string_agg(title, ', ' ORDER BY rental_date DESC, rental_id DESC) FROM (
            SELECT f.title, r.rental_date, r.rental_id FROM rental r JOIN inventory USING (inventory_id) JOIN film f USING (film_id)
            WHERE r.customer_id = p_customer_id ORDER BY r.rental_date DESC, r.rental_id DESC LIMIT p_quantes) t);
END $$ LANGUAGE plpgsql;
```

Incorrecta (REBUTJADA: Test 4 (SELECT ultimes_pelis(1, 0)): Result sets differ (comparing unordered)) — string_agg sense tractar p_quantes <= 0: retorna NULL en lloc de '':
```sql
CREATE FUNCTION ultimes_pelis(p_customer_id integer, p_quantes integer DEFAULT 3) RETURNS text AS $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM customer WHERE customer_id = p_customer_id) THEN
    RAISE EXCEPTION 'client' USING ERRCODE = 'P0002';
  END IF;
  RETURN (SELECT string_agg(title, ', ' ORDER BY rental_date DESC, rental_id DESC) FROM (
            SELECT f.title, r.rental_date, r.rental_id FROM rental r JOIN inventory USING (inventory_id) JOIN film f USING (film_id)
            WHERE r.customer_id = p_customer_id ORDER BY r.rental_date DESC, r.rental_id DESC LIMIT greatest(p_quantes, 0)) t);
END $$ LANGUAGE plpgsql;
```

Incorrecta (REBUTJADA: Test 3 (SELECT ultimes_pelis(216, 22)): Result sets differ (comparing unordered)) — sense desempat per rental_id (el resultat depèn del pla; aquí falla):
```sql
CREATE FUNCTION ultimes_pelis(p_customer_id integer, p_quantes integer DEFAULT 3) RETURNS text AS $$
DECLARE v text := ''; r record;
BEGIN
  IF NOT EXISTS (SELECT 1 FROM customer WHERE customer_id = p_customer_id) THEN
    RAISE EXCEPTION 'client' USING ERRCODE = 'no_data_found';
  END IF;
  FOR r IN SELECT f.title FROM rental re JOIN inventory i USING (inventory_id) JOIN film f USING (film_id)
           WHERE re.customer_id = p_customer_id ORDER BY re.rental_date DESC LIMIT greatest(p_quantes, 0) LOOP
    IF v <> '' THEN v := v || ', '; END IF;
    v := v || r.title;
  END LOOP;
  RETURN v;
END $$ LANGUAGE plpgsql;
```

Incorrecta (REBUTJADA: Test 6 (SELECT ultimes_pelis(9999)): yours returns rows, the expected one gives an error (SQLSTATE P0002 no_data_found)) — no comprova si el client existeix:
```sql
CREATE FUNCTION ultimes_pelis(p_customer_id integer, p_quantes integer DEFAULT 3) RETURNS text AS $$
DECLARE v text := ''; r record;
BEGIN
  FOR r IN SELECT f.title FROM rental re JOIN inventory i USING (inventory_id) JOIN film f USING (film_id)
           WHERE re.customer_id = p_customer_id ORDER BY re.rental_date DESC, re.rental_id DESC LIMIT greatest(p_quantes, 0) LOOP
    IF v <> '' THEN v := v || ', '; END IF;
    v := v || r.title;
  END LOOP;
  RETURN v;
END $$ LANGUAGE plpgsql;
```

## Pagila — Procediments (pgproc)

### 1. Crea el procediment `alta_actor(p_nom text, p_cognom text)` que afegeixi un actor a `actor` amb el nom i el cognom sense espais al principi ni al final (`trim`) i en majúscules (`upper`); l'`actor_id` el posa la base de dades. Si el nom o el cognom són `NULL` o queden buits després de treure'n els espais, no ha d'inserir res i ha de llançar una excepció amb `ERRCODE = 'check_violation'`.

Referència (0.83 s, referència + resposta):
```sql
CREATE PROCEDURE alta_actor(p_nom text, p_cognom text)
LANGUAGE plpgsql AS $$
BEGIN
  IF coalesce(trim(p_nom), '') = '' OR coalesce(trim(p_cognom), '') = '' THEN
    RAISE EXCEPTION 'El nom i el cognom són obligatoris' USING ERRCODE = 'check_violation';
  END IF;
  INSERT INTO actor (first_name, last_name) VALUES (upper(trim(p_nom)), upper(trim(p_cognom)));
END $$;
--@@TEST@@ CALL alta_actor('  Joan ', 'Puig i Font')
--@@TEST@@ CALL alta_actor('Maria', '   ')
--@@TEST@@ CALL alta_actor(NULL, 'Garcia')
--@@TEST@@ CALL alta_actor('anna', 'serra')
--@@TEST@@ SELECT actor_id, first_name, last_name FROM actor WHERE actor_id > 200
```

Alternativa (ACCEPTADA) — btrim/length i SQLSTATE numèric:
```sql
CREATE OR REPLACE PROCEDURE alta_actor(p_nom text, p_cognom text) AS $$
DECLARE n text := upper(btrim(p_nom)); c text := upper(btrim(p_cognom));
BEGIN
  IF n IS NULL OR c IS NULL OR length(n) = 0 OR length(c) = 0 THEN
    RAISE EXCEPTION 'dades incompletes' USING ERRCODE = '23514';
  END IF;
  INSERT INTO actor (first_name, last_name) VALUES (n, c);
END $$ LANGUAGE plpgsql;
```

Incorrecta (REBUTJADA: Test 3 (CALL alta_actor(NULL, 'Garcia')): yours gives an error (SQLSTATE 23502 not_null_violation), the expected one gives an error (SQLSTATE 23514 check_violation)) — trim(NULL) = '' és NULL: no atura el NULL i salta not_null_violation:
```sql
CREATE PROCEDURE alta_actor(p_nom text, p_cognom text) LANGUAGE plpgsql AS $$
BEGIN
  IF trim(p_nom) = '' OR trim(p_cognom) = '' THEN
    RAISE EXCEPTION 'obligatoris' USING ERRCODE = 'check_violation';
  END IF;
  INSERT INTO actor (first_name, last_name) VALUES (upper(trim(p_nom)), upper(trim(p_cognom)));
END $$;
```

Incorrecta (REBUTJADA: Test 5 (SELECT actor_id, first_name, last_name FROM actor WHERE a...): Result sets differ (comparing unordered)) — no fa trim abans de desar:
```sql
CREATE PROCEDURE alta_actor(p_nom text, p_cognom text) LANGUAGE plpgsql AS $$
BEGIN
  IF coalesce(trim(p_nom), '') = '' OR coalesce(trim(p_cognom), '') = '' THEN
    RAISE EXCEPTION 'obligatoris' USING ERRCODE = 'check_violation';
  END IF;
  INSERT INTO actor (first_name, last_name) VALUES (upper(p_nom), upper(p_cognom));
END $$;
```

Incorrecta (REBUTJADA: Test 2 (CALL alta_actor('Maria', ' ')): yours runs, the expected one gives an error (SQLSTATE 23514 check_violation)) — sense validació:
```sql
CREATE PROCEDURE alta_actor(p_nom text, p_cognom text) LANGUAGE sql AS $$
  INSERT INTO actor (first_name, last_name) VALUES (upper(trim(p_nom)), upper(trim(p_cognom)));
$$;
```

### 2. Crea el procediment `apujar_preus(p_categoria text, p_percent numeric, INOUT p_files integer DEFAULT NULL)` que apugi un `p_percent` per cent el preu de lloguer (`rental_rate`) de totes les pel·lícules de la categoria amb aquest nom exacte (`category.name`), arrodonint a 2 decimals, i que retorni a `p_files` el nombre de pel·lícules modificades (amb `GET DIAGNOSTICS`). Validacions, en aquest ordre: si `p_percent` és `NULL`, menor o igual que 0 o més gran que 50, excepció amb `ERRCODE = 'check_violation'`; si la categoria no existeix, excepció amb `ERRCODE = 'no_data_found'`.

Referència (1.05 s, referència + resposta):
```sql
CREATE PROCEDURE apujar_preus(p_categoria text, p_percent numeric, INOUT p_files integer DEFAULT NULL)
LANGUAGE plpgsql AS $$
BEGIN
  IF p_percent IS NULL OR p_percent <= 0 OR p_percent > 50 THEN
    RAISE EXCEPTION 'Percentatge no vàlid: %', p_percent USING ERRCODE = 'check_violation';
  END IF;
  PERFORM 1 FROM category WHERE name = p_categoria;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'No existeix la categoria %', p_categoria USING ERRCODE = 'no_data_found';
  END IF;
  UPDATE film f SET rental_rate = round(f.rental_rate * (1 + p_percent / 100), 2)
  FROM film_category fc JOIN category c ON c.category_id = fc.category_id
  WHERE fc.film_id = f.film_id AND c.name = p_categoria;
  GET DIAGNOSTICS p_files = ROW_COUNT;
END $$;
--@@TEST@@ CALL apujar_preus('Horror', 10)
--@@TEST@@ CALL apujar_preus('Music', 50, NULL)
--@@TEST@@ CALL apujar_preus('Music', 0)
--@@TEST@@ CALL apujar_preus('Music', 50.5)
--@@TEST@@ CALL apujar_preus('Terror', 5)
--@@TEST@@ CALL apujar_preus('Travel', NULL)
--@@TEST@@ SELECT rental_rate, count(*) FROM film GROUP BY rental_rate
```

Alternativa (ACCEPTADA) — sense round (la columna numeric(4,2) ja arrodoneix) i IN (subconsulta):
```sql
CREATE PROCEDURE apujar_preus(p_categoria text, p_percent numeric, INOUT p_files integer DEFAULT NULL) AS $$
DECLARE v_cat integer;
BEGIN
  IF NOT coalesce(p_percent > 0 AND p_percent <= 50, false) THEN
    RAISE EXCEPTION 'percentatge' USING ERRCODE = '23514';
  END IF;
  SELECT category_id INTO v_cat FROM category WHERE name = p_categoria;
  IF v_cat IS NULL THEN
    RAISE EXCEPTION 'categoria' USING ERRCODE = 'P0002';
  END IF;
  UPDATE film SET rental_rate = rental_rate * (100 + p_percent) / 100
  WHERE film_id IN (SELECT film_id FROM film_category WHERE category_id = v_cat);
  GET DIAGNOSTICS p_files = ROW_COUNT;
END $$ LANGUAGE plpgsql;
```

Incorrecta (REBUTJADA: Test 6 (CALL apujar_preus('Travel', NULL)): yours gives an error (SQLSTATE 23502 not_null_violation), the expected one gives an error (SQLSTATE 23514 check_violation)) — no valida NULL i detecta la categoria inexistent per ROW_COUNT = 0:
```sql
CREATE PROCEDURE apujar_preus(p_categoria text, p_percent numeric, INOUT p_files integer DEFAULT NULL) LANGUAGE plpgsql AS $$
BEGIN
  IF p_percent <= 0 OR p_percent > 50 THEN
    RAISE EXCEPTION 'percentatge' USING ERRCODE = 'check_violation';
  END IF;
  UPDATE film f SET rental_rate = round(f.rental_rate * (1 + p_percent / 100), 2)
  FROM film_category fc JOIN category c ON c.category_id = fc.category_id
  WHERE fc.film_id = f.film_id AND c.name = p_categoria;
  GET DIAGNOSTICS p_files = ROW_COUNT;
  IF p_files = 0 THEN
    RAISE EXCEPTION 'categoria' USING ERRCODE = 'no_data_found';
  END IF;
END $$;
```

Incorrecta (REBUTJADA: Test 7 (SELECT rental_rate, count(*) FROM film GROUP BY rental_rate): Result sets differ (comparing unordered)) — suma el percentatge en lloc d'aplicar-lo:
```sql
CREATE PROCEDURE apujar_preus(p_categoria text, p_percent numeric, INOUT p_files integer DEFAULT NULL) LANGUAGE plpgsql AS $$
BEGIN
  IF p_percent IS NULL OR p_percent <= 0 OR p_percent > 50 THEN
    RAISE EXCEPTION 'percentatge' USING ERRCODE = 'check_violation';
  END IF;
  PERFORM 1 FROM category WHERE name = p_categoria;
  IF NOT FOUND THEN RAISE EXCEPTION 'categoria' USING ERRCODE = 'no_data_found'; END IF;
  UPDATE film f SET rental_rate = f.rental_rate + p_percent / 100
  FROM film_category fc JOIN category c ON c.category_id = fc.category_id
  WHERE fc.film_id = f.film_id AND c.name = p_categoria;
  GET DIAGNOSTICS p_files = ROW_COUNT;
END $$;
```

Incorrecta (REBUTJADA: Test 1 (CALL apujar_preus('Horror', 10)): Result sets differ (comparing unordered)) — no omple p_files:
```sql
CREATE PROCEDURE apujar_preus(p_categoria text, p_percent numeric, INOUT p_files integer DEFAULT NULL) LANGUAGE plpgsql AS $$
BEGIN
  IF p_percent IS NULL OR p_percent <= 0 OR p_percent > 50 THEN
    RAISE EXCEPTION 'percentatge' USING ERRCODE = 'check_violation';
  END IF;
  PERFORM 1 FROM category WHERE name = p_categoria;
  IF NOT FOUND THEN RAISE EXCEPTION 'categoria' USING ERRCODE = 'no_data_found'; END IF;
  UPDATE film f SET rental_rate = round(f.rental_rate * (1 + p_percent / 100), 2)
  FROM film_category fc JOIN category c ON c.category_id = fc.category_id
  WHERE fc.film_id = f.film_id AND c.name = p_categoria;
END $$;
```

### 3. Crea el procediment `reposar_estoc(p_film_id integer, p_store_id integer, p_copies integer)` que afegeixi `p_copies` còpies noves de la pel·lícula a la botiga indicada: una fila nova a `inventory` per còpia (l'`inventory_id` el posa la base de dades). Fes-ho amb un bucle. Validacions, en aquest ordre: si `p_copies` és `NULL` o no està entre 1 i 10 (tots dos inclosos), excepció amb `ERRCODE = 'check_violation'`; si la pel·lícula no existeix o la botiga no existeix, excepció amb `ERRCODE = 'no_data_found'`.

Referència (0.99 s, referència + resposta):
```sql
CREATE PROCEDURE reposar_estoc(p_film_id integer, p_store_id integer, p_copies integer)
LANGUAGE plpgsql AS $$
BEGIN
  IF p_copies IS NULL OR p_copies NOT BETWEEN 1 AND 10 THEN
    RAISE EXCEPTION 'Nombre de còpies no vàlid: %', p_copies USING ERRCODE = 'check_violation';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM film WHERE film_id = p_film_id) THEN
    RAISE EXCEPTION 'No existeix la pel·lícula %', p_film_id USING ERRCODE = 'no_data_found';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM store WHERE store_id = p_store_id) THEN
    RAISE EXCEPTION 'No existeix la botiga %', p_store_id USING ERRCODE = 'no_data_found';
  END IF;
  FOR i IN 1 .. p_copies LOOP
    INSERT INTO inventory (film_id, store_id) VALUES (p_film_id, p_store_id);
  END LOOP;
END $$;
--@@TEST@@ CALL reposar_estoc(14, 1, 3)
--@@TEST@@ CALL reposar_estoc(1, 2, 10)
--@@TEST@@ CALL reposar_estoc(1, 2, 0)
--@@TEST@@ CALL reposar_estoc(1, 2, 11)
--@@TEST@@ CALL reposar_estoc(9999, 1, 1)
--@@TEST@@ CALL reposar_estoc(1, 3, 1)
--@@TEST@@ SELECT inventory_id, film_id, store_id FROM inventory WHERE inventory_id > 4581
```

Alternativa (ACCEPTADA) — INSERT … SELECT generate_series en lloc del bucle:
```sql
CREATE PROCEDURE reposar_estoc(p_film_id integer, p_store_id integer, p_copies integer) AS $$
BEGIN
  IF NOT (p_copies >= 1 AND p_copies <= 10) OR p_copies IS NULL THEN
    RAISE EXCEPTION 'copies' USING ERRCODE = 'check_violation';
  END IF;
  PERFORM 1 FROM film WHERE film_id = p_film_id;
  IF NOT FOUND THEN RAISE EXCEPTION 'film' USING ERRCODE = 'no_data_found'; END IF;
  PERFORM 1 FROM store WHERE store_id = p_store_id;
  IF NOT FOUND THEN RAISE EXCEPTION 'store' USING ERRCODE = 'no_data_found'; END IF;
  INSERT INTO inventory (film_id, store_id) SELECT p_film_id, p_store_id FROM generate_series(1, p_copies);
END $$ LANGUAGE plpgsql;
```

Incorrecta (REBUTJADA: Test 5 (CALL reposar_estoc(9999, 1, 1)): yours gives an error (SQLSTATE 23503 foreign_key_violation), the expected one gives an error (SQLSTATE P0002 no_data_found)) — sense comprovar pel·lícula/botiga (salta foreign_key_violation) ni el NULL:
```sql
CREATE PROCEDURE reposar_estoc(p_film_id integer, p_store_id integer, p_copies integer) LANGUAGE plpgsql AS $$
BEGIN
  IF p_copies NOT BETWEEN 1 AND 10 THEN
    RAISE EXCEPTION 'copies' USING ERRCODE = 'check_violation';
  END IF;
  FOR i IN 1 .. p_copies LOOP
    INSERT INTO inventory (film_id, store_id) VALUES (p_film_id, p_store_id);
  END LOOP;
END $$;
```

Incorrecta (REBUTJADA: Test 2 (CALL reposar_estoc(1, 2, 10)): yours gives an error (SQLSTATE 23514 check_violation), the expected one runs) — p_copies >= 10 en lloc de > 10:
```sql
CREATE PROCEDURE reposar_estoc(p_film_id integer, p_store_id integer, p_copies integer) LANGUAGE plpgsql AS $$
BEGIN
  IF p_copies IS NULL OR p_copies < 1 OR p_copies >= 10 THEN
    RAISE EXCEPTION 'copies' USING ERRCODE = 'check_violation';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM film WHERE film_id = p_film_id) OR NOT EXISTS (SELECT 1 FROM store WHERE store_id = p_store_id) THEN
    RAISE EXCEPTION 'no existeix' USING ERRCODE = 'no_data_found';
  END IF;
  FOR i IN 1 .. p_copies LOOP
    INSERT INTO inventory (film_id, store_id) VALUES (p_film_id, p_store_id);
  END LOOP;
END $$;
```

### 4. Crea el procediment `nou_lloguer(p_inventory_id integer, p_customer_id integer, p_staff_id integer, INOUT p_rental_id integer DEFAULT NULL)` que registri a `rental` un lloguer nou de la còpia indicada, amb data de lloguer `now()` i sense data de retorn, i que retorni a `p_rental_id` l'identificador del lloguer creat. Validacions, en aquest ordre: si la còpia no existeix a `inventory`, excepció amb `ERRCODE = 'no_data_found'`; si la còpia està llogada ara mateix (té algun lloguer amb `return_date` a `NULL`), excepció amb `ERRCODE = 'object_in_use'`.

Referència (1.89 s, referència + resposta):
```sql
CREATE PROCEDURE nou_lloguer(p_inventory_id integer, p_customer_id integer, p_staff_id integer,
                             INOUT p_rental_id integer DEFAULT NULL)
LANGUAGE plpgsql AS $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM inventory WHERE inventory_id = p_inventory_id) THEN
    RAISE EXCEPTION 'No existeix la còpia %', p_inventory_id USING ERRCODE = 'no_data_found';
  END IF;
  IF EXISTS (SELECT 1 FROM rental WHERE inventory_id = p_inventory_id AND return_date IS NULL) THEN
    RAISE EXCEPTION 'La còpia % està llogada', p_inventory_id USING ERRCODE = 'object_in_use';
  END IF;
  INSERT INTO rental (rental_date, inventory_id, customer_id, staff_id)
  VALUES (now(), p_inventory_id, p_customer_id, p_staff_id)
  RETURNING rental_id INTO p_rental_id;
END $$;
--@@TEST@@ CALL nou_lloguer(1, 1, 1)
--@@TEST@@ CALL nou_lloguer(6, 1, 1)
--@@TEST@@ CALL nou_lloguer(1, 2, 2)
--@@TEST@@ CALL nou_lloguer(99999, 1, 1)
--@@TEST@@ CALL nou_lloguer(2, 2, 2, NULL)
--@@TEST@@ SELECT rental_id, inventory_id, customer_id, staff_id, return_date FROM rental WHERE rental_id > 16049
```

Alternativa (ACCEPTADA) — inventory_in_stock() de pagila, current_timestamp i lastval():
```sql
CREATE PROCEDURE nou_lloguer(p_inventory_id integer, p_customer_id integer, p_staff_id integer, INOUT p_rental_id integer DEFAULT NULL) AS $$
BEGIN
  PERFORM 1 FROM inventory WHERE inventory_id = p_inventory_id;
  IF NOT FOUND THEN RAISE EXCEPTION 'copia' USING ERRCODE = 'P0002'; END IF;
  IF NOT inventory_in_stock(p_inventory_id) THEN
    RAISE EXCEPTION 'llogada' USING ERRCODE = '55006';
  END IF;
  INSERT INTO rental (rental_date, inventory_id, customer_id, staff_id) VALUES (current_timestamp, p_inventory_id, p_customer_id, p_staff_id);
  p_rental_id := lastval();
END $$ LANGUAGE plpgsql;
```

Incorrecta (REBUTJADA: Test 4 (CALL nou_lloguer(99999, 1, 1)): yours gives an error (SQLSTATE 23503 foreign_key_violation), the expected one gives an error (SQLSTATE P0002 no_data_found)) — no comprova que la còpia existeixi (inventory_in_stock torna true i salta la clau forana):
```sql
CREATE PROCEDURE nou_lloguer(p_inventory_id integer, p_customer_id integer, p_staff_id integer, INOUT p_rental_id integer DEFAULT NULL) LANGUAGE plpgsql AS $$
BEGIN
  IF NOT inventory_in_stock(p_inventory_id) THEN
    RAISE EXCEPTION 'llogada' USING ERRCODE = 'object_in_use';
  END IF;
  INSERT INTO rental (rental_date, inventory_id, customer_id, staff_id) VALUES (now(), p_inventory_id, p_customer_id, p_staff_id)
  RETURNING rental_id INTO p_rental_id;
END $$;
```

Incorrecta (REBUTJADA: The final content of the database does not match what was expected (table: rental)) — clock_timestamp() en lloc de now(): la data no és la de la transacció:
```sql
CREATE PROCEDURE nou_lloguer(p_inventory_id integer, p_customer_id integer, p_staff_id integer, INOUT p_rental_id integer DEFAULT NULL) LANGUAGE plpgsql AS $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM inventory WHERE inventory_id = p_inventory_id) THEN
    RAISE EXCEPTION 'copia' USING ERRCODE = 'no_data_found';
  END IF;
  IF EXISTS (SELECT 1 FROM rental WHERE inventory_id = p_inventory_id AND return_date IS NULL) THEN
    RAISE EXCEPTION 'llogada' USING ERRCODE = 'object_in_use';
  END IF;
  INSERT INTO rental (rental_date, inventory_id, customer_id, staff_id) VALUES (clock_timestamp(), p_inventory_id, p_customer_id, p_staff_id)
  RETURNING rental_id INTO p_rental_id;
END $$;
```

Incorrecta (REBUTJADA: Test 2 (CALL nou_lloguer(6, 1, 1)): yours returns rows, the expected one gives an error (SQLSTATE 55006 object_in_use)) — no comprova si la còpia està llogada:
```sql
CREATE PROCEDURE nou_lloguer(p_inventory_id integer, p_customer_id integer, p_staff_id integer, INOUT p_rental_id integer DEFAULT NULL) LANGUAGE plpgsql AS $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM inventory WHERE inventory_id = p_inventory_id) THEN
    RAISE EXCEPTION 'copia' USING ERRCODE = 'no_data_found';
  END IF;
  INSERT INTO rental (rental_date, inventory_id, customer_id, staff_id) VALUES (now(), p_inventory_id, p_customer_id, p_staff_id)
  RETURNING rental_id INTO p_rental_id;
END $$;
```

Incorrecta (REBUTJADA: Test 1 (CALL nou_lloguer(1, 1, 1)): Result sets differ (comparing unordered)) — currval(pg_get_serial_sequence(...)): a pagila la seqüència no és OWNED BY la columna i retorna NULL:
```sql
CREATE PROCEDURE nou_lloguer(p_inventory_id integer, p_customer_id integer, p_staff_id integer, INOUT p_rental_id integer DEFAULT NULL) AS $$
BEGIN
  PERFORM 1 FROM inventory WHERE inventory_id = p_inventory_id;
  IF NOT FOUND THEN RAISE EXCEPTION 'copia' USING ERRCODE = 'P0002'; END IF;
  IF NOT inventory_in_stock(p_inventory_id) THEN
    RAISE EXCEPTION 'llogada' USING ERRCODE = '55006';
  END IF;
  INSERT INTO rental (rental_date, inventory_id, customer_id, staff_id) VALUES (current_timestamp, p_inventory_id, p_customer_id, p_staff_id);
  p_rental_id := currval(pg_get_serial_sequence('rental', 'rental_id'));
END $$ LANGUAGE plpgsql;
```

### 5. Crea el procediment `retornar_lloguer(p_inventory_id integer, p_data timestamptz, INOUT p_import numeric DEFAULT NULL)` que registri la devolució de la còpia `p_inventory_id` en el moment `p_data`. Primer busca el lloguer obert d'aquesta còpia (el que té `return_date` a `NULL`): si no n'hi ha cap, excepció amb `ERRCODE = 'no_data_found'` (comprova-ho amb `FOUND`); si `p_data` és anterior a la data del lloguer, excepció amb `ERRCODE = 'invalid_parameter_value'`. Després calcula l'import: el `rental_rate` de la pel·lícula més 1.00 per cada dia de retard, on els dies de lloguer són els **dies complets** (de 24 hores) entre `rental_date` i `p_data` (`extract(day FROM p_data - rental_date)`) i els dies de retard són els que passen del `rental_duration` de la pel·lícula. Finalment posa `return_date = p_data` al lloguer, afegeix un pagament a `payment` (amb el client i l'empleat del lloguer, aquest `rental_id`, l'import calculat i `payment_date = p_data`) i retorna l'import a `p_import`. (La taula `payment` està particionada per mesos, de gener a juliol de 2022: les proves fan servir dates d'aquest període.)

Referència (2.67 s, referència + resposta):
```sql
CREATE PROCEDURE retornar_lloguer(p_inventory_id integer, p_data timestamptz, INOUT p_import numeric DEFAULT NULL)
LANGUAGE plpgsql AS $$
DECLARE
  v_rental rental%ROWTYPE;
  v_preu numeric;
  v_durada integer;
  v_dies integer;
BEGIN
  SELECT * INTO v_rental FROM rental WHERE inventory_id = p_inventory_id AND return_date IS NULL;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'La còpia % no està llogada', p_inventory_id USING ERRCODE = 'no_data_found';
  END IF;
  IF p_data < v_rental.rental_date THEN
    RAISE EXCEPTION 'Data de retorn anterior al lloguer' USING ERRCODE = 'invalid_parameter_value';
  END IF;
  SELECT f.rental_rate, f.rental_duration INTO v_preu, v_durada
  FROM inventory i JOIN film f ON f.film_id = i.film_id WHERE i.inventory_id = p_inventory_id;
  v_dies := extract(day FROM p_data - v_rental.rental_date);
  p_import := v_preu + greatest(v_dies - v_durada, 0) * 1.00;
  UPDATE rental SET return_date = p_data WHERE rental_id = v_rental.rental_id;
  INSERT INTO payment (customer_id, staff_id, rental_id, amount, payment_date)
  VALUES (v_rental.customer_id, v_rental.staff_id, v_rental.rental_id, p_import, p_data);
END $$;
--@@TEST@@ CALL retornar_lloguer(9, '2022-02-20 12:00:00+00')
--@@TEST@@ CALL retornar_lloguer(9, '2022-02-25 12:00:00+00')
--@@TEST@@ CALL retornar_lloguer(1, '2022-02-20 12:00:00+00')
--@@TEST@@ CALL retornar_lloguer(81, '2022-02-15 10:00:00+00')
--@@TEST@@ CALL retornar_lloguer(21, '2022-02-10 10:00:00+00')
--@@TEST@@ CALL retornar_lloguer(25, '2022-02-23 15:00:00+00')
--@@TEST@@ SELECT payment_id, customer_id, staff_id, rental_id, amount, payment_date FROM payment WHERE payment_id > 32098
--@@TEST@@ SELECT rental_id, return_date FROM rental WHERE inventory_id IN (9, 21, 25, 81) AND rental_date >= '2022-02-14' AND rental_date < '2022-02-15'
```

Alternativa (ACCEPTADA) — dies complets calculats amb epoch:
```sql
CREATE PROCEDURE retornar_lloguer(p_inventory_id integer, p_data timestamptz, INOUT p_import numeric DEFAULT NULL) AS $$
DECLARE r record;
BEGIN
  SELECT re.rental_id, re.rental_date, re.customer_id, re.staff_id, f.rental_rate, f.rental_duration INTO r
  FROM rental re JOIN inventory i USING (inventory_id) JOIN film f USING (film_id)
  WHERE re.inventory_id = p_inventory_id AND re.return_date IS NULL;
  IF NOT FOUND THEN RAISE EXCEPTION 'no llogada' USING ERRCODE = 'P0002'; END IF;
  IF p_data < r.rental_date THEN RAISE EXCEPTION 'data' USING ERRCODE = '22023'; END IF;
  p_import := r.rental_rate;
  IF p_data - r.rental_date >= make_interval(days => r.rental_duration + 1) THEN
    p_import := p_import + floor(extract(epoch FROM p_data - r.rental_date) / 86400) - r.rental_duration;
  END IF;
  UPDATE rental SET return_date = p_data WHERE rental_id = r.rental_id;
  INSERT INTO payment (customer_id, staff_id, rental_id, amount, payment_date) VALUES (r.customer_id, r.staff_id, r.rental_id, p_import, p_data);
END $$ LANGUAGE plpgsql;
```

Incorrecta (REBUTJADA: Test 1 (CALL retornar_lloguer(9, '2022-02-20 12:00:00+00')): Result sets differ (comparing unordered)) — dies per diferència de dates (p_data::date - rental_date::date): compta un dia de més:
```sql
CREATE PROCEDURE retornar_lloguer(p_inventory_id integer, p_data timestamptz, INOUT p_import numeric DEFAULT NULL) LANGUAGE plpgsql AS $$
DECLARE r record;
BEGIN
  SELECT re.rental_id, re.rental_date, re.customer_id, re.staff_id, f.rental_rate, f.rental_duration INTO r
  FROM rental re JOIN inventory i USING (inventory_id) JOIN film f USING (film_id)
  WHERE re.inventory_id = p_inventory_id AND re.return_date IS NULL;
  IF NOT FOUND THEN RAISE EXCEPTION 'no llogada' USING ERRCODE = 'no_data_found'; END IF;
  IF p_data < r.rental_date THEN RAISE EXCEPTION 'data' USING ERRCODE = 'invalid_parameter_value'; END IF;
  p_import := r.rental_rate + greatest((p_data::date - r.rental_date::date) - r.rental_duration, 0);
  UPDATE rental SET return_date = p_data WHERE rental_id = r.rental_id;
  INSERT INTO payment (customer_id, staff_id, rental_id, amount, payment_date) VALUES (r.customer_id, r.staff_id, r.rental_id, p_import, p_data);
END $$;
```

Incorrecta (REBUTJADA: Test 2 (CALL retornar_lloguer(9, '2022-02-25 12:00:00+00')): yours gives an error (SQLSTATE 23502 not_null_violation), the expected one gives an error (SQLSTATE P0002 no_data_found)) — no comprova FOUND:
```sql
CREATE PROCEDURE retornar_lloguer(p_inventory_id integer, p_data timestamptz, INOUT p_import numeric DEFAULT NULL) LANGUAGE plpgsql AS $$
DECLARE r record;
BEGIN
  SELECT re.rental_id, re.rental_date, re.customer_id, re.staff_id, f.rental_rate, f.rental_duration INTO r
  FROM rental re JOIN inventory i USING (inventory_id) JOIN film f USING (film_id)
  WHERE re.inventory_id = p_inventory_id AND re.return_date IS NULL;
  IF p_data < r.rental_date THEN RAISE EXCEPTION 'data' USING ERRCODE = 'invalid_parameter_value'; END IF;
  p_import := r.rental_rate + greatest(extract(day FROM p_data - r.rental_date) - r.rental_duration, 0);
  UPDATE rental SET return_date = p_data WHERE rental_id = r.rental_id;
  INSERT INTO payment (customer_id, staff_id, rental_id, amount, payment_date) VALUES (r.customer_id, r.staff_id, r.rental_id, p_import, p_data);
END $$;
```

Incorrecta (REBUTJADA: Test 1 (CALL retornar_lloguer(9, '2022-02-20 12:00:00+00')): yours gives an error (SQLSTATE 23514 check_violation), the expected one returns rows) — payment_date = now(): no hi ha cap partició de payment per a la data d'avui (error 23514):
```sql
CREATE PROCEDURE retornar_lloguer(p_inventory_id integer, p_data timestamptz, INOUT p_import numeric DEFAULT NULL) LANGUAGE plpgsql AS $$
DECLARE r record;
BEGIN
  SELECT re.rental_id, re.rental_date, re.customer_id, re.staff_id, f.rental_rate, f.rental_duration INTO r
  FROM rental re JOIN inventory i USING (inventory_id) JOIN film f USING (film_id)
  WHERE re.inventory_id = p_inventory_id AND re.return_date IS NULL;
  IF NOT FOUND THEN RAISE EXCEPTION 'no llogada' USING ERRCODE = 'no_data_found'; END IF;
  IF p_data < r.rental_date THEN RAISE EXCEPTION 'data' USING ERRCODE = 'invalid_parameter_value'; END IF;
  p_import := r.rental_rate + greatest(extract(day FROM p_data - r.rental_date) - r.rental_duration, 0);
  UPDATE rental SET return_date = p_data WHERE rental_id = r.rental_id;
  INSERT INTO payment (customer_id, staff_id, rental_id, amount, payment_date) VALUES (r.customer_id, 1, r.rental_id, p_import, now());
END $$;
```

### 6. Crea el procediment `traspassar_copies(p_film_id integer, p_origen integer, p_desti integer, INOUT p_moguts integer DEFAULT NULL)` que passi a la botiga `p_desti` totes les còpies de la pel·lícula que són a la botiga `p_origen` i que **no estan llogades** ara mateix (cap lloguer seu té `return_date` a `NULL`); les llogades es queden on són. Recorre les còpies amb un bucle `FOR … IN SELECT` i retorna a `p_moguts` quantes n'has mogut (0 si cap). Validacions, en aquest ordre: si `p_origen = p_desti`, excepció amb `ERRCODE = 'invalid_parameter_value'`; si alguna de les dues botigues no existeix, excepció amb `ERRCODE = 'no_data_found'`.

Referència (1.07 s, referència + resposta):
```sql
CREATE PROCEDURE traspassar_copies(p_film_id integer, p_origen integer, p_desti integer,
                                   INOUT p_moguts integer DEFAULT NULL)
LANGUAGE plpgsql AS $$
DECLARE
  r record;
BEGIN
  IF p_origen = p_desti THEN
    RAISE EXCEPTION 'Origen i destí iguals' USING ERRCODE = 'invalid_parameter_value';
  END IF;
  IF (SELECT count(*) FROM store WHERE store_id IN (p_origen, p_desti)) < 2 THEN
    RAISE EXCEPTION 'Botiga inexistent' USING ERRCODE = 'no_data_found';
  END IF;
  p_moguts := 0;
  FOR r IN SELECT i.inventory_id FROM inventory i
           WHERE i.film_id = p_film_id AND i.store_id = p_origen
             AND NOT EXISTS (SELECT 1 FROM rental re WHERE re.inventory_id = i.inventory_id AND re.return_date IS NULL)
  LOOP
    UPDATE inventory SET store_id = p_desti WHERE inventory_id = r.inventory_id;
    p_moguts := p_moguts + 1;
  END LOOP;
END $$;
--@@TEST@@ CALL traspassar_copies(1, 2, 1)
--@@TEST@@ CALL traspassar_copies(2, 2, 1)
--@@TEST@@ CALL traspassar_copies(2, 2, 1)
--@@TEST@@ CALL traspassar_copies(3, 1, 2)
--@@TEST@@ CALL traspassar_copies(1, 1, 1)
--@@TEST@@ CALL traspassar_copies(1, 1, 3)
--@@TEST@@ CALL traspassar_copies(1, 7, 2)
--@@TEST@@ SELECT inventory_id, film_id, store_id FROM inventory WHERE film_id IN (1, 2, 3)
```

Alternativa (ACCEPTADA) — UPDATE amb inventory_in_stock() i GET DIAGNOSTICS en lloc del bucle:
```sql
CREATE PROCEDURE traspassar_copies(p_film_id integer, p_origen integer, p_desti integer, INOUT p_moguts integer DEFAULT NULL) AS $$
BEGIN
  IF p_origen = p_desti THEN RAISE EXCEPTION 'iguals' USING ERRCODE = '22023'; END IF;
  PERFORM 1 FROM store WHERE store_id = p_origen;
  IF NOT FOUND THEN RAISE EXCEPTION 'origen' USING ERRCODE = 'P0002'; END IF;
  PERFORM 1 FROM store WHERE store_id = p_desti;
  IF NOT FOUND THEN RAISE EXCEPTION 'desti' USING ERRCODE = 'P0002'; END IF;
  UPDATE inventory SET store_id = p_desti
  WHERE film_id = p_film_id AND store_id = p_origen AND inventory_in_stock(inventory_id);
  GET DIAGNOSTICS p_moguts = ROW_COUNT;
END $$ LANGUAGE plpgsql;
```

Incorrecta (REBUTJADA: Test 1 (CALL traspassar_copies(1, 2, 1)): Result sets differ (comparing unordered)) — mou també les còpies llogades:
```sql
CREATE PROCEDURE traspassar_copies(p_film_id integer, p_origen integer, p_desti integer, INOUT p_moguts integer DEFAULT NULL) LANGUAGE plpgsql AS $$
BEGIN
  IF p_origen = p_desti THEN RAISE EXCEPTION 'iguals' USING ERRCODE = 'invalid_parameter_value'; END IF;
  IF (SELECT count(*) FROM store WHERE store_id IN (p_origen, p_desti)) < 2 THEN
    RAISE EXCEPTION 'botiga' USING ERRCODE = 'no_data_found';
  END IF;
  UPDATE inventory SET store_id = p_desti WHERE film_id = p_film_id AND store_id = p_origen;
  GET DIAGNOSTICS p_moguts = ROW_COUNT;
END $$;
```

Incorrecta (REBUTJADA: Test 1 (CALL traspassar_copies(1, 2, 1)): Result sets differ (comparing unordered)) — no inicialitza p_moguts (NULL + 1 = NULL):
```sql
CREATE PROCEDURE traspassar_copies(p_film_id integer, p_origen integer, p_desti integer, INOUT p_moguts integer DEFAULT NULL) LANGUAGE plpgsql AS $$
DECLARE r record;
BEGIN
  IF p_origen = p_desti THEN RAISE EXCEPTION 'iguals' USING ERRCODE = 'invalid_parameter_value'; END IF;
  IF (SELECT count(*) FROM store WHERE store_id IN (p_origen, p_desti)) < 2 THEN
    RAISE EXCEPTION 'botiga' USING ERRCODE = 'no_data_found';
  END IF;
  FOR r IN SELECT i.inventory_id FROM inventory i WHERE i.film_id = p_film_id AND i.store_id = p_origen
             AND NOT EXISTS (SELECT 1 FROM rental re WHERE re.inventory_id = i.inventory_id AND re.return_date IS NULL) LOOP
    UPDATE inventory SET store_id = p_desti WHERE inventory_id = r.inventory_id;
    p_moguts := p_moguts + 1;
  END LOOP;
END $$;
```

Incorrecta (REBUTJADA: Test 6 (CALL traspassar_copies(1, 1, 3)): yours gives an error (SQLSTATE 23503 foreign_key_violation), the expected one gives an error (SQLSTATE P0002 no_data_found)) — no comprova que les botigues existeixin:
```sql
CREATE PROCEDURE traspassar_copies(p_film_id integer, p_origen integer, p_desti integer, INOUT p_moguts integer DEFAULT NULL) LANGUAGE plpgsql AS $$
BEGIN
  IF p_origen = p_desti THEN RAISE EXCEPTION 'iguals' USING ERRCODE = 'invalid_parameter_value'; END IF;
  UPDATE inventory SET store_id = p_desti WHERE film_id = p_film_id AND store_id = p_origen AND inventory_in_stock(inventory_id);
  GET DIAGNOSTICS p_moguts = ROW_COUNT;
END $$;
```

## Pagila — Triggers (pgtrigger)

### 1. Crea la funció de trigger `normalitza_actor()` i el trigger `trg_normalitza_actor` sobre `actor` perquè, cada vegada que s'insereixi o s'actualitzi un actor, el nom (`first_name`) i el cognom (`last_name`) es desin sense espais al principi ni al final i en majúscules (`upper(trim(…))`).

Referència (0.86 s, referència + resposta):
```sql
CREATE FUNCTION normalitza_actor() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  NEW.first_name := upper(trim(NEW.first_name));
  NEW.last_name := upper(trim(NEW.last_name));
  RETURN NEW;
END $$;
CREATE TRIGGER trg_normalitza_actor BEFORE INSERT OR UPDATE ON actor
FOR EACH ROW EXECUTE FUNCTION normalitza_actor();
--@@TEST@@ INSERT INTO actor (first_name, last_name) VALUES ('  joan ', 'puig i font'), ('Anna', ' Serra')
--@@TEST@@ UPDATE actor SET first_name = 'penelope  ' WHERE actor_id = 1
--@@TEST@@ UPDATE actor SET last_name = last_name || ' jr' WHERE actor_id IN (2, 3)
--@@TEST@@ SELECT actor_id, first_name, last_name FROM actor WHERE actor_id IN (1, 2, 3) OR actor_id > 200
```

Alternativa (ACCEPTADA) — UPDATE OF first_name, last_name i EXECUTE PROCEDURE:
```sql
CREATE OR REPLACE FUNCTION normalitza_actor() RETURNS trigger AS $$
BEGIN
  NEW.first_name = upper(btrim(NEW.first_name));
  NEW.last_name = upper(btrim(NEW.last_name));
  RETURN NEW;
END $$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS trg_normalitza_actor ON actor;
CREATE TRIGGER trg_normalitza_actor BEFORE INSERT OR UPDATE OF first_name, last_name ON actor
FOR EACH ROW EXECUTE PROCEDURE normalitza_actor();
```

Incorrecta (REBUTJADA: Test 4 (SELECT actor_id, first_name, last_name FROM actor WHERE a...): Result sets differ (comparing unordered)) — només BEFORE INSERT:
```sql
CREATE FUNCTION normalitza_actor() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  NEW.first_name := upper(trim(NEW.first_name));
  NEW.last_name := upper(trim(NEW.last_name));
  RETURN NEW;
END $$;
CREATE TRIGGER trg_normalitza_actor BEFORE INSERT ON actor FOR EACH ROW EXECUTE FUNCTION normalitza_actor();
```

Incorrecta (REBUTJADA: Test 4 (SELECT actor_id, first_name, last_name FROM actor WHERE a...): Result sets differ (comparing unordered)) — AFTER: canviar NEW no té cap efecte:
```sql
CREATE FUNCTION normalitza_actor() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  NEW.first_name := upper(trim(NEW.first_name));
  NEW.last_name := upper(trim(NEW.last_name));
  RETURN NEW;
END $$;
CREATE TRIGGER trg_normalitza_actor AFTER INSERT OR UPDATE ON actor FOR EACH ROW EXECUTE FUNCTION normalitza_actor();
```

Incorrecta (REBUTJADA: Test 1 (INSERT INTO actor (first_name, last_name) VALUES (' joan ...): yours gives an error (SQLSTATE 2F005 function_executed_no_return_statement), the expected one runs) — sense RETURN NEW (error en executar el trigger):
```sql
CREATE FUNCTION normalitza_actor() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  NEW.first_name := upper(trim(NEW.first_name));
  NEW.last_name := upper(trim(NEW.last_name));
END $$;
CREATE TRIGGER trg_normalitza_actor BEFORE INSERT OR UPDATE ON actor FOR EACH ROW EXECUTE FUNCTION normalitza_actor();
```

### 2. Crea la funció de trigger `valida_preu_film()` i el trigger `trg_valida_preu_film` (`BEFORE UPDATE … FOR EACH ROW`) sobre `film` que impedeixi dues situacions llançant una excepció amb `ERRCODE = 'check_violation'`: (1) que, després del canvi, el preu de lloguer (`rental_rate`) sigui més gran que la meitat del cost de reposició (`replacement_cost`) —un preu exactament igual a la meitat és vàlid—; (2) que el preu de lloguer baixi per sota de la meitat del que tenia (`NEW.rental_rate < OLD.rental_rate / 2`). Compte: la regla (1) també s'ha de comprovar quan només canvia el cost de reposició.

Referència (0.97 s, referència + resposta):
```sql
CREATE FUNCTION valida_preu_film() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.rental_rate > NEW.replacement_cost / 2 THEN
    RAISE EXCEPTION 'El preu de lloguer (%) supera la meitat del cost de reposició (%)', NEW.rental_rate, NEW.replacement_cost
      USING ERRCODE = 'check_violation';
  END IF;
  IF NEW.rental_rate < OLD.rental_rate / 2 THEN
    RAISE EXCEPTION 'Rebaixa massa gran: de % a %', OLD.rental_rate, NEW.rental_rate USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_valida_preu_film BEFORE UPDATE ON film
FOR EACH ROW EXECUTE FUNCTION valida_preu_film();
--@@TEST@@ UPDATE film SET rental_rate = 2.99 WHERE film_id = 2
--@@TEST@@ UPDATE film SET rental_rate = 1.49 WHERE film_id = 2
--@@TEST@@ UPDATE film SET rental_rate = 10.49 WHERE film_id = 1
--@@TEST@@ UPDATE film SET rental_rate = 10.50 WHERE film_id = 1
--@@TEST@@ UPDATE film SET replacement_cost = 9.00 WHERE film_id = 3
--@@TEST@@ UPDATE film SET replacement_cost = 9.00 WHERE film_id = 8
--@@TEST@@ UPDATE film SET replacement_cost = 9.98 WHERE film_id = 7
--@@TEST@@ UPDATE film SET rental_rate = rental_rate * 1.5 WHERE rating = 'G' AND film_id < 100
--@@TEST@@ UPDATE film SET rental_rate = 0.99, replacement_cost = 1.98 WHERE film_id = 1
--@@TEST@@ SELECT film_id, rental_rate, replacement_cost FROM film WHERE film_id IN (1, 2, 3, 7, 8)
```

Alternativa (ACCEPTADA) — multiplicant per 2 i UPDATE OF rental_rate, replacement_cost:
```sql
CREATE FUNCTION valida_preu_film() RETURNS trigger AS $$
BEGIN
  IF NEW.rental_rate * 2 > NEW.replacement_cost OR NEW.rental_rate * 2 < OLD.rental_rate THEN
    RAISE EXCEPTION 'preu no vàlid' USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END $$ LANGUAGE plpgsql;
CREATE TRIGGER trg_valida_preu_film BEFORE UPDATE OF rental_rate, replacement_cost ON film
FOR EACH ROW EXECUTE FUNCTION valida_preu_film();
```

Incorrecta (REBUTJADA: Test 6 (UPDATE film SET replacement_cost = 9.00 WHERE film_id = 8): yours runs, the expected one gives an error (SQLSTATE 23514 check_violation)) — UPDATE OF rental_rate: no salta quan només canvia replacement_cost:
```sql
CREATE FUNCTION valida_preu_film() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.rental_rate > NEW.replacement_cost / 2 OR NEW.rental_rate < OLD.rental_rate / 2 THEN
    RAISE EXCEPTION 'preu no vàlid' USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_valida_preu_film BEFORE UPDATE OF rental_rate ON film FOR EACH ROW EXECUTE FUNCTION valida_preu_film();
```

Incorrecta (REBUTJADA: Test 2 (UPDATE film SET rental_rate = 1.49 WHERE film_id = 2): yours runs, the expected one gives an error (SQLSTATE 23514 check_violation)) — RETURN NULL en lloc de RAISE: descarta la fila sense error:
```sql
CREATE FUNCTION valida_preu_film() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.rental_rate > NEW.replacement_cost / 2 OR NEW.rental_rate < OLD.rental_rate / 2 THEN
    RAISE NOTICE 'preu no vàlid';
    RETURN NULL;
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_valida_preu_film BEFORE UPDATE ON film FOR EACH ROW EXECUTE FUNCTION valida_preu_film();
```

Incorrecta (REBUTJADA: Test 7 (UPDATE film SET replacement_cost = 9.98 WHERE film_id = 7): yours gives an error (SQLSTATE 23514 check_violation), the expected one runs) — >= en lloc de >: rebutja el preu exactament igual a la meitat:
```sql
CREATE FUNCTION valida_preu_film() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.rental_rate >= NEW.replacement_cost / 2 OR NEW.rental_rate < OLD.rental_rate / 2 THEN
    RAISE EXCEPTION 'preu no vàlid' USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_valida_preu_film BEFORE UPDATE ON film FOR EACH ROW EXECUTE FUNCTION valida_preu_film();
```

### 3. Crea la taula `log_categories (id serial PRIMARY KEY, operacio text NOT NULL, category_id integer, nom_antic text, nom_nou text, moment timestamptz NOT NULL DEFAULT now())`, la funció de trigger `audita_categoria()` i el trigger `trg_audita_categoria` (`AFTER … FOR EACH ROW`) sobre `category` que registri cada inserció, modificació i esborrament de categories: `operacio` és el valor de `TG_OP` (`'INSERT'`, `'UPDATE'` o `'DELETE'`), `category_id` és l'identificador de la categoria afectada, `nom_antic` és el nom abans del canvi (`NULL` en una inserció) i `nom_nou` el nom després del canvi (`NULL` en un esborrament). Una fila de registre per cada fila afectada, també quan un `UPDATE` deixa el nom igual.

Referència (0.87 s, referència + resposta):
```sql
CREATE TABLE log_categories (
  id serial PRIMARY KEY,
  operacio text NOT NULL,
  category_id integer,
  nom_antic text,
  nom_nou text,
  moment timestamptz NOT NULL DEFAULT now()
);
CREATE FUNCTION audita_categoria() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'INSERT' THEN
    INSERT INTO log_categories (operacio, category_id, nom_antic, nom_nou) VALUES (TG_OP, NEW.category_id, NULL, NEW.name);
  ELSIF TG_OP = 'UPDATE' THEN
    INSERT INTO log_categories (operacio, category_id, nom_antic, nom_nou) VALUES (TG_OP, NEW.category_id, OLD.name, NEW.name);
  ELSE
    INSERT INTO log_categories (operacio, category_id, nom_antic, nom_nou) VALUES (TG_OP, OLD.category_id, OLD.name, NULL);
  END IF;
  RETURN NULL;
END $$;
CREATE TRIGGER trg_audita_categoria AFTER INSERT OR UPDATE OR DELETE ON category
FOR EACH ROW EXECUTE FUNCTION audita_categoria();
--@@TEST@@ INSERT INTO category (name) VALUES ('Western'), ('Anime')
--@@TEST@@ UPDATE category SET name = 'Sci-Fi & Fantasy' WHERE name = 'Sci-Fi'
--@@TEST@@ DELETE FROM category WHERE name = 'Anime'
--@@TEST@@ DELETE FROM category WHERE name = 'Horror'
--@@TEST@@ UPDATE category SET name = name WHERE name LIKE 'W%'
--@@TEST@@ SELECT id, operacio, category_id, nom_antic, nom_nou, moment FROM log_categories ORDER BY id
```

Alternativa (ACCEPTADA) — un sol INSERT amb CASE:
```sql
CREATE TABLE log_categories (id serial PRIMARY KEY, operacio text NOT NULL, category_id integer, nom_antic text, nom_nou text, moment timestamptz NOT NULL DEFAULT now());
CREATE FUNCTION audita_categoria() RETURNS trigger AS $$
BEGIN
  INSERT INTO log_categories (operacio, category_id, nom_antic, nom_nou)
  VALUES (TG_OP,
          CASE WHEN TG_OP = 'DELETE' THEN OLD.category_id ELSE NEW.category_id END,
          CASE WHEN TG_OP <> 'INSERT' THEN OLD.name END,
          CASE WHEN TG_OP <> 'DELETE' THEN NEW.name END);
  IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
  RETURN NEW;
END $$ LANGUAGE plpgsql;
CREATE TRIGGER trg_audita_categoria AFTER INSERT OR UPDATE OR DELETE ON category FOR EACH ROW EXECUTE FUNCTION audita_categoria();
```

Incorrecta (REBUTJADA: Test 3 (DELETE FROM category WHERE name = 'Anime'): it changed 0 rows, expected 1) — BEFORE amb RETURN NEW: en un DELETE NEW és NULL i l'esborrament es descarta:
```sql
CREATE TABLE log_categories (id serial PRIMARY KEY, operacio text NOT NULL, category_id integer, nom_antic text, nom_nou text, moment timestamptz NOT NULL DEFAULT now());
CREATE FUNCTION audita_categoria() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  INSERT INTO log_categories (operacio, category_id, nom_antic, nom_nou) VALUES (TG_OP, NEW.category_id, OLD.name, NEW.name);
  RETURN NEW;
END $$;
CREATE TRIGGER trg_audita_categoria BEFORE INSERT OR UPDATE OR DELETE ON category FOR EACH ROW EXECUTE FUNCTION audita_categoria();
```

Incorrecta (REBUTJADA: Test 6 (SELECT id, operacio, category_id, nom_antic, nom_nou, mom...): Wrong number of rows: got 4, expected 5) — FOR EACH STATEMENT: NEW i OLD són NULL, una sola fila de registre per sentència i sense dades:
```sql
CREATE TABLE log_categories (id serial PRIMARY KEY, operacio text NOT NULL, category_id integer, nom_antic text, nom_nou text, moment timestamptz NOT NULL DEFAULT now());
CREATE FUNCTION audita_categoria() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'INSERT' THEN
    INSERT INTO log_categories (operacio, category_id, nom_antic, nom_nou) VALUES (TG_OP, NEW.category_id, NULL, NEW.name);
  ELSIF TG_OP = 'UPDATE' THEN
    INSERT INTO log_categories (operacio, category_id, nom_antic, nom_nou) VALUES (TG_OP, NEW.category_id, OLD.name, NEW.name);
  ELSE
    INSERT INTO log_categories (operacio, category_id, nom_antic, nom_nou) VALUES (TG_OP, OLD.category_id, OLD.name, NULL);
  END IF;
  RETURN NULL;
END $$;
CREATE TRIGGER trg_audita_categoria AFTER INSERT OR UPDATE OR DELETE ON category FOR EACH STATEMENT EXECUTE FUNCTION audita_categoria();
```

Incorrecta (REBUTJADA: Test 6 (SELECT id, operacio, category_id, nom_antic, nom_nou, mom...): Wrong number of rows: got 7, expected 5) — dos triggers: les insercions es registren dues vegades:
```sql
CREATE TABLE log_categories (id serial PRIMARY KEY, operacio text NOT NULL, category_id integer, nom_antic text, nom_nou text, moment timestamptz NOT NULL DEFAULT now());
CREATE FUNCTION audita_categoria() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'INSERT' THEN
    INSERT INTO log_categories (operacio, category_id, nom_antic, nom_nou) VALUES (TG_OP, NEW.category_id, NULL, NEW.name);
  ELSIF TG_OP = 'UPDATE' THEN
    INSERT INTO log_categories (operacio, category_id, nom_antic, nom_nou) VALUES (TG_OP, NEW.category_id, OLD.name, NEW.name);
  ELSE
    INSERT INTO log_categories (operacio, category_id, nom_antic, nom_nou) VALUES (TG_OP, OLD.category_id, OLD.name, NULL);
  END IF;
  RETURN NULL;
END $$;
CREATE TRIGGER trg_audita_categoria AFTER INSERT OR UPDATE OR DELETE ON category FOR EACH ROW WHEN (pg_trigger_depth() < 5) EXECUTE FUNCTION audita_categoria();
DROP TRIGGER IF EXISTS x ON category;
CREATE TRIGGER trg_audita_categoria2 AFTER INSERT ON category FOR EACH ROW EXECUTE FUNCTION audita_categoria();
```

### 4. Crea la taula `log_preus (film_id integer NOT NULL, preu_antic numeric(4,2), preu_nou numeric(4,2))`, la funció de trigger `registra_preu()` i el trigger `trg_registra_preu` sobre `film` que afegeixi una fila a `log_preus` cada vegada que canviï **de debò** el preu de lloguer d'una pel·lícula. Fes servir `AFTER UPDATE OF rental_rate … FOR EACH ROW WHEN (…)`: si un `UPDATE` deixa el preu igual, o només modifica altres columnes, no s'ha de registrar res.

Referència (1.01 s, referència + resposta):
```sql
CREATE TABLE log_preus (
  film_id integer NOT NULL,
  preu_antic numeric(4,2),
  preu_nou numeric(4,2)
);
CREATE FUNCTION registra_preu() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  INSERT INTO log_preus (film_id, preu_antic, preu_nou) VALUES (NEW.film_id, OLD.rental_rate, NEW.rental_rate);
  RETURN NULL;
END $$;
CREATE TRIGGER trg_registra_preu AFTER UPDATE OF rental_rate ON film
FOR EACH ROW WHEN (OLD.rental_rate IS DISTINCT FROM NEW.rental_rate)
EXECUTE FUNCTION registra_preu();
--@@TEST@@ UPDATE film SET rental_rate = 3.99 WHERE film_id IN (1, 2, 3)
--@@TEST@@ UPDATE film SET rental_rate = 3.99 WHERE film_id IN (1, 4)
--@@TEST@@ UPDATE film SET rental_rate = rental_rate WHERE rating = 'NC-17'
--@@TEST@@ UPDATE film SET length = length + 10 WHERE film_id = 5
--@@TEST@@ UPDATE film SET rental_rate = rental_rate + 1 WHERE film_id BETWEEN 10 AND 12
--@@TEST@@ SELECT film_id, preu_antic, preu_nou FROM log_preus
```

Alternativa (ACCEPTADA) — IF dins de la funció en lloc de WHEN (el checker no pot exigir WHEN):
```sql
CREATE TABLE log_preus (film_id integer NOT NULL, preu_antic numeric(4,2), preu_nou numeric(4,2));
CREATE FUNCTION registra_preu() RETURNS trigger AS $$
BEGIN
  IF NEW.rental_rate <> OLD.rental_rate THEN
    INSERT INTO log_preus VALUES (OLD.film_id, OLD.rental_rate, NEW.rental_rate);
  END IF;
  RETURN NEW;
END $$ LANGUAGE plpgsql;
CREATE TRIGGER trg_registra_preu AFTER UPDATE ON film FOR EACH ROW EXECUTE FUNCTION registra_preu();
```

Incorrecta (REBUTJADA: Test 6 (SELECT film_id, preu_antic, preu_nou FROM log_preus): Wrong number of rows: got 218, expected 7) — sense WHEN: registra també els UPDATE que deixen el preu igual:
```sql
CREATE TABLE log_preus (film_id integer NOT NULL, preu_antic numeric(4,2), preu_nou numeric(4,2));
CREATE FUNCTION registra_preu() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  INSERT INTO log_preus VALUES (NEW.film_id, OLD.rental_rate, NEW.rental_rate);
  RETURN NULL;
END $$;
CREATE TRIGGER trg_registra_preu AFTER UPDATE OF rental_rate ON film FOR EACH ROW EXECUTE FUNCTION registra_preu();
```

Incorrecta (REBUTJADA: Test 6 (SELECT film_id, preu_antic, preu_nou FROM log_preus): Result sets differ (comparing unordered)) — preu antic i nou intercanviats:
```sql
CREATE TABLE log_preus (film_id integer NOT NULL, preu_antic numeric(4,2), preu_nou numeric(4,2));
CREATE FUNCTION registra_preu() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  INSERT INTO log_preus VALUES (NEW.film_id, NEW.rental_rate, OLD.rental_rate);
  RETURN NULL;
END $$;
CREATE TRIGGER trg_registra_preu AFTER UPDATE OF rental_rate ON film FOR EACH ROW WHEN (OLD.rental_rate <> NEW.rental_rate) EXECUTE FUNCTION registra_preu();
```

### 5. Crea la funció de trigger `filtra_pagament()` i el trigger `trg_filtra_pagament` (`BEFORE INSERT … FOR EACH ROW`) sobre `payment` amb aquestes regles: si l'import (`amount`) és negatiu, llança una excepció amb `ERRCODE = 'check_violation'`; si l'import és 0, la fila s'ha de **descartar sense error** (`RETURN NULL`): no es desa, però la resta de files de la mateixa sentència sí; en qualsevol altre cas, la fila es desa tal com ve. (`payment` és una taula particionada: el trigger es crea sobre `payment`.)

Referència (1.62 s, referència + resposta):
```sql
CREATE FUNCTION filtra_pagament() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.amount < 0 THEN
    RAISE EXCEPTION 'Import negatiu: %', NEW.amount USING ERRCODE = 'check_violation';
  END IF;
  IF NEW.amount = 0 THEN
    RETURN NULL;
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_filtra_pagament BEFORE INSERT ON payment
FOR EACH ROW EXECUTE FUNCTION filtra_pagament();
--@@TEST@@ INSERT INTO payment (customer_id, staff_id, rental_id, amount, payment_date) VALUES (1, 1, 76, 0, '2022-05-01 10:00:00+00'), (1, 1, 76, 2.99, '2022-05-01 10:00:00+00'), (2, 1, 320, 0.00, '2022-05-02 10:00:00+00')
--@@TEST@@ INSERT INTO payment (customer_id, staff_id, rental_id, amount, payment_date) VALUES (1, 1, 76, -1.50, '2022-05-01 10:00:00+00')
--@@TEST@@ INSERT INTO payment (customer_id, staff_id, rental_id, amount, payment_date) SELECT customer_id, staff_id, rental_id, amount, payment_date FROM payment WHERE amount = 0
--@@TEST@@ INSERT INTO payment (customer_id, staff_id, rental_id, amount, payment_date) SELECT customer_id, staff_id, rental_id, amount, payment_date + interval '1 hour' FROM payment WHERE customer_id = 1 AND payment_date < '2022-02-01'
--@@TEST@@ SELECT customer_id, staff_id, rental_id, amount, payment_date FROM payment WHERE payment_id > 32098
```

Alternativa (ACCEPTADA) — amb CASE:
```sql
CREATE FUNCTION filtra_pagament() RETURNS trigger AS $$
BEGIN
  CASE
    WHEN NEW.amount < 0 THEN RAISE EXCEPTION 'negatiu' USING ERRCODE = '23514';
    WHEN NEW.amount = 0 THEN RETURN NULL;
    ELSE RETURN NEW;
  END CASE;
END $$ LANGUAGE plpgsql;
CREATE TRIGGER trg_filtra_pagament BEFORE INSERT ON payment FOR EACH ROW EXECUTE FUNCTION filtra_pagament();
```

Incorrecta (REBUTJADA: Test 1 (INSERT INTO payment (customer_id, staff_id, rental_id, am...): it changed 3 rows, expected 1) — AFTER: el RETURN NULL no descarta res:
```sql
CREATE FUNCTION filtra_pagament() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.amount < 0 THEN RAISE EXCEPTION 'negatiu' USING ERRCODE = 'check_violation'; END IF;
  IF NEW.amount = 0 THEN RETURN NULL; END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_filtra_pagament AFTER INSERT ON payment FOR EACH ROW EXECUTE FUNCTION filtra_pagament();
```

Incorrecta (REBUTJADA: Test 1 (INSERT INTO payment (customer_id, staff_id, rental_id, am...): yours gives an error (SQLSTATE 23514 check_violation), the expected one runs) — llança error també amb import 0:
```sql
CREATE FUNCTION filtra_pagament() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.amount <= 0 THEN RAISE EXCEPTION 'import no vàlid' USING ERRCODE = 'check_violation'; END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_filtra_pagament BEFORE INSERT ON payment FOR EACH ROW EXECUTE FUNCTION filtra_pagament();
```

Incorrecta (REBUTJADA: Test 1 (INSERT INTO payment (customer_id, staff_id, rental_id, am...): it changed 3 rows, expected 1) — FOR EACH STATEMENT: NEW és NULL i no es descarta cap fila:
```sql
CREATE FUNCTION filtra_pagament() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.amount < 0 THEN RAISE EXCEPTION 'negatiu' USING ERRCODE = 'check_violation'; END IF;
  IF NEW.amount = 0 THEN RETURN NULL; END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_filtra_pagament BEFORE INSERT ON payment FOR EACH STATEMENT EXECUTE FUNCTION filtra_pagament();
```

### 6. Crea la taula `resum_actualitzacions (files integer NOT NULL, increment numeric(8,2) NOT NULL)`, la funció de trigger `resumeix_actualitzacio()` i el trigger `trg_resumeix_actualitzacio` sobre `film` que, **una sola vegada per cada sentència `UPDATE`** (`FOR EACH STATEMENT`), afegeixi una fila a `resum_actualitzacions` amb el nombre de pel·lícules modificades per la sentència i la suma de les variacions del preu de lloguer (`rental_rate` nou menys antic; 0 si no ha canviat cap preu). Fes servir taules de transició (`REFERENCING OLD TABLE AS … NEW TABLE AS …`). Si la sentència no modifica cap fila, no s'ha d'afegir res.

Referència (1.01 s, referència + resposta):
```sql
CREATE TABLE resum_actualitzacions (
  files integer NOT NULL,
  increment numeric(8,2) NOT NULL
);
CREATE FUNCTION resumeix_actualitzacio() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
  v_files integer;
  v_increment numeric;
BEGIN
  SELECT count(*), coalesce(sum(n.rental_rate - o.rental_rate), 0) INTO v_files, v_increment
  FROM nous n JOIN antics o ON o.film_id = n.film_id;
  IF v_files > 0 THEN
    INSERT INTO resum_actualitzacions (files, increment) VALUES (v_files, v_increment);
  END IF;
  RETURN NULL;
END $$;
CREATE TRIGGER trg_resumeix_actualitzacio AFTER UPDATE ON film
REFERENCING OLD TABLE AS antics NEW TABLE AS nous
FOR EACH STATEMENT EXECUTE FUNCTION resumeix_actualitzacio();
--@@TEST@@ UPDATE film SET rental_rate = rental_rate + 1 WHERE rating = 'G' AND rental_rate < 4
--@@TEST@@ UPDATE film SET rental_rate = 0.99 WHERE film_id IN (2, 3)
--@@TEST@@ UPDATE film SET title = title WHERE film_id = 9999
--@@TEST@@ UPDATE film SET length = length + 1 WHERE film_id <= 10
--@@TEST@@ SELECT files, increment FROM resum_actualitzacions
```

Alternativa (ACCEPTADA) — diferència de sumes sense JOIN:
```sql
CREATE TABLE resum_actualitzacions (files integer NOT NULL, increment numeric(8,2) NOT NULL);
CREATE FUNCTION resumeix_actualitzacio() RETURNS trigger AS $$
BEGIN
  INSERT INTO resum_actualitzacions
  SELECT (SELECT count(*) FROM nous), (SELECT coalesce(sum(rental_rate), 0) FROM nous) - (SELECT coalesce(sum(rental_rate), 0) FROM antics)
  WHERE EXISTS (SELECT 1 FROM nous);
  RETURN NULL;
END $$ LANGUAGE plpgsql;
CREATE TRIGGER trg_resumeix_actualitzacio AFTER UPDATE ON film REFERENCING NEW TABLE AS nous OLD TABLE AS antics
FOR EACH STATEMENT EXECUTE FUNCTION resumeix_actualitzacio();
```

Incorrecta (REBUTJADA: Test 5 (SELECT files, increment FROM resum_actualitzacions): Wrong number of rows: got 135, expected 3) — FOR EACH ROW: una fila per pel·lícula:
```sql
CREATE TABLE resum_actualitzacions (files integer NOT NULL, increment numeric(8,2) NOT NULL);
CREATE FUNCTION resumeix_actualitzacio() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  INSERT INTO resum_actualitzacions VALUES (1, NEW.rental_rate - OLD.rental_rate);
  RETURN NULL;
END $$;
CREATE TRIGGER trg_resumeix_actualitzacio AFTER UPDATE ON film FOR EACH ROW EXECUTE FUNCTION resumeix_actualitzacio();
```

Incorrecta (REBUTJADA: Test 5 (SELECT files, increment FROM resum_actualitzacions): Wrong number of rows: got 4, expected 3) — no comprova que la sentència hagi modificat files: hi afegeix (0, 0):
```sql
CREATE TABLE resum_actualitzacions (files integer NOT NULL, increment numeric(8,2) NOT NULL);
CREATE FUNCTION resumeix_actualitzacio() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  INSERT INTO resum_actualitzacions
  SELECT count(*), coalesce(sum(n.rental_rate - o.rental_rate), 0) FROM nous n JOIN antics o USING (film_id);
  RETURN NULL;
END $$;
CREATE TRIGGER trg_resumeix_actualitzacio AFTER UPDATE ON film REFERENCING OLD TABLE AS antics NEW TABLE AS nous
FOR EACH STATEMENT EXECUTE FUNCTION resumeix_actualitzacio();
```

Incorrecta (REBUTJADA: Test 5 (SELECT files, increment FROM resum_actualitzacions): Wrong number of rows: got 2, expected 3) — compta només les files amb canvi de preu:
```sql
CREATE TABLE resum_actualitzacions (files integer NOT NULL, increment numeric(8,2) NOT NULL);
CREATE FUNCTION resumeix_actualitzacio() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  INSERT INTO resum_actualitzacions
  SELECT count(*), sum(n.rental_rate - o.rental_rate) FROM nous n JOIN antics o USING (film_id) WHERE n.rental_rate <> o.rental_rate HAVING count(*) > 0;
  RETURN NULL;
END $$;
CREATE TRIGGER trg_resumeix_actualitzacio AFTER UPDATE ON film REFERENCING OLD TABLE AS antics NEW TABLE AS nous
FOR EACH STATEMENT EXECUTE FUNCTION resumeix_actualitzacio();
```

## Pagila — Tipus, arrays i JSON (pgobjrel)

### 1. Mostra el títol i la llista d'extres (`special_features`, tal com és, com a array) de les pel·lícules de la categoria `Music` que tenen, com a mínim, els extres `Trailers` i `Commentaries` (en poden tenir d'altres). Fes servir l'operador de contenció d'arrays `@>`. Columnes: `title`, `special_features`.

Referència (0.03 s, referència + resposta):
```sql
SELECT f.title, f.special_features
FROM film f JOIN film_category fc ON fc.film_id = f.film_id JOIN category c ON c.category_id = fc.category_id
WHERE c.name = 'Music' AND f.special_features @> ARRAY['Trailers', 'Commentaries']
```

Alternativa (ACCEPTADA) — amb = ANY i subconsulta:
```sql
SELECT title, special_features FROM film
WHERE 'Trailers' = ANY (special_features) AND 'Commentaries' = ANY (special_features)
  AND film_id IN (SELECT film_id FROM film_category JOIN category USING (category_id) WHERE name = 'Music')
```

Incorrecta (REBUTJADA: Wrong number of rows: got more than 10, expected 10) — && (solapament): n'hi ha prou amb un dels dos extres:
```sql
SELECT f.title, f.special_features
FROM film f JOIN film_category fc ON fc.film_id = f.film_id JOIN category c ON c.category_id = fc.category_id
WHERE c.name = 'Music' AND f.special_features && ARRAY['Trailers', 'Commentaries']
```

Incorrecta (REBUTJADA: Wrong number of rows: got 0, expected 10) — igualtat d'arrays: només troba els que tenen exactament aquests dos:
```sql
SELECT f.title, f.special_features
FROM film f JOIN film_category fc ON fc.film_id = f.film_id JOIN category c ON c.category_id = fc.category_id
WHERE c.name = 'Music' AND f.special_features = ARRAY['Trailers', 'Commentaries']
```

Incorrecta (REBUTJADA: Result sets differ (comparing unordered)) — converteix l'array a text:
```sql
SELECT f.title, array_to_string(f.special_features, ',')
FROM film f JOIN film_category fc ON fc.film_id = f.film_id JOIN category c ON c.category_id = fc.category_id
WHERE c.name = 'Music' AND f.special_features @> ARRAY['Trailers', 'Commentaries']
```

### 2. Per a cada extra diferent que apareix a `special_features`, mostra quantes pel·lícules el tenen i la seva durada mitjana (`length`) arrodonida a 1 decimal. Desplega l'array amb `unnest`. Columnes: extra, nombre de pel·lícules, durada mitjana.

Referència (0.03 s, referència + resposta):
```sql
SELECT e.extra, count(*), round(avg(f.length), 1)
FROM film f CROSS JOIN LATERAL unnest(f.special_features) AS e(extra)
GROUP BY e.extra
```

Alternativa (ACCEPTADA) — unnest a la llista del SELECT:
```sql
SELECT extra, count(*), round(avg(length), 1) FROM (SELECT unnest(special_features) AS extra, length FROM film) t GROUP BY extra
```

Alternativa (ACCEPTADA) — DISTINCT unnest i subconsultes amb ANY:
```sql
SELECT x.extra, (SELECT count(*) FROM film WHERE x.extra = ANY (special_features)), (SELECT round(avg(length), 1) FROM film WHERE x.extra = ANY (special_features))
FROM (SELECT DISTINCT unnest(special_features) AS extra FROM film) x
```

Incorrecta (REBUTJADA: Result sets differ (comparing unordered)) — sense arrodonir:
```sql
SELECT e.extra, count(*), avg(f.length)
FROM film f CROSS JOIN LATERAL unnest(f.special_features) AS e(extra) GROUP BY e.extra
```

Incorrecta (REBUTJADA: Wrong number of rows: got more than 4, expected 4) — agrupa per l'array sencer, no per cada extra:
```sql
SELECT array_to_string(special_features, ', '), count(*), round(avg(length), 1) FROM film GROUP BY special_features
```

### 3. Per a cada botiga, genera un document JSON amb el nombre de còpies (`inventory`) que té de cada categoria. Columnes: `store_id` i un array JSON (`jsonb_agg`) d'objectes `{"categoria": <nom de la categoria>, "copies": <nombre de còpies>}` (fes-los amb `jsonb_build_object`), ordenat alfabèticament pel nom de la categoria. Només hi surten les categories amb alguna còpia a la botiga.

Referència (0.04 s, referència + resposta):
```sql
SELECT s.store_id,
       jsonb_agg(jsonb_build_object('categoria', s.name, 'copies', s.copies) ORDER BY s.name)
FROM (SELECT i.store_id, c.name, count(*) AS copies
      FROM inventory i JOIN film_category fc ON fc.film_id = i.film_id JOIN category c ON c.category_id = fc.category_id
      GROUP BY i.store_id, c.name) s
GROUP BY s.store_id
```

Alternativa (ACCEPTADA) — json_agg / json_build_object (json en lloc de jsonb) i claus en un altre ordre:
```sql
SELECT st.store_id,
  (SELECT json_agg(json_build_object('copies', t.n, 'categoria', t.name) ORDER BY t.name)
   FROM (SELECT c.name, count(*) AS n FROM inventory i JOIN film_category USING (film_id) JOIN category c USING (category_id)
         WHERE i.store_id = st.store_id GROUP BY c.name) t)
FROM store st
```

Incorrecta (REBUTJADA: Result sets differ (comparing unordered)) — ordenat per nombre de còpies:
```sql
SELECT s.store_id, jsonb_agg(jsonb_build_object('categoria', s.name, 'copies', s.copies) ORDER BY s.copies DESC)
FROM (SELECT i.store_id, c.name, count(*) AS copies FROM inventory i JOIN film_category fc ON fc.film_id = i.film_id JOIN category c ON c.category_id = fc.category_id GROUP BY i.store_id, c.name) s
GROUP BY s.store_id
```

Incorrecta (REBUTJADA: Result sets differ (comparing unordered)) — compta pel·lícules diferents, no còpies:
```sql
SELECT s.store_id, jsonb_agg(jsonb_build_object('categoria', s.name, 'copies', s.copies) ORDER BY s.name)
FROM (SELECT i.store_id, c.name, count(DISTINCT i.film_id) AS copies FROM inventory i JOIN film_category fc ON fc.film_id = i.film_id JOIN category c ON c.category_id = fc.category_id GROUP BY i.store_id, c.name) s
GROUP BY s.store_id
```

Incorrecta (REBUTJADA: Result sets differ (comparing unordered)) — jsonb_object_agg: un objecte {categoria: còpies} en lloc d'un array d'objectes:
```sql
SELECT s.store_id, jsonb_object_agg(s.name, s.copies)
FROM (SELECT i.store_id, c.name, count(*) AS copies FROM inventory i JOIN film_category fc ON fc.film_id = i.film_id JOIN category c ON c.category_id = fc.category_id GROUP BY i.store_id, c.name) s
GROUP BY s.store_id
```

### 4. Crea el domini `email_client`, basat en `text`, que no admeti `NULL` i que només accepti els valors que compleixen l'expressió regular `'^[a-z0-9._-]+@[a-z0-9-]+(\.[a-z0-9-]+)+$'` (amb l'operador `~`, que distingeix majúscules de minúscules). Després crea la funció `canvia_email(p_customer_id integer, p_email email_client) RETURNS boolean` que canviï el correu (`customer.email`) del client i retorni `true` si el client existeix i `false` si no existeix.

Referència (0.90 s, referència + resposta):
```sql
CREATE DOMAIN email_client AS text NOT NULL
  CHECK (VALUE ~ '^[a-z0-9._-]+@[a-z0-9-]+(\.[a-z0-9-]+)+$');
CREATE FUNCTION canvia_email(p_customer_id integer, p_email email_client) RETURNS boolean
LANGUAGE plpgsql AS $$
BEGIN
  UPDATE customer SET email = p_email WHERE customer_id = p_customer_id;
  RETURN FOUND;
END $$;
--@@TEST@@ SELECT 'joan.puig@ies-sabadell.cat'::email_client
--@@TEST@@ SELECT 'Joan.Puig@ies-sabadell.cat'::email_client
--@@TEST@@ SELECT 'joan@localhost'::email_client
--@@TEST@@ SELECT 'joan@@exemple.cat'::email_client
--@@TEST@@ SELECT NULL::email_client
--@@TEST@@ SELECT canvia_email(1, 'mary.smith@exemple.cat')
--@@TEST@@ SELECT canvia_email(9999, 'ningu@exemple.cat')
--@@TEST@@ SELECT canvia_email(2, 'patricia johnson@exemple.cat')
--@@TEST@@ SELECT canvia_email(3, NULL)
--@@TEST@@ SELECT customer_id, email FROM customer WHERE customer_id IN (1, 2, 3)
```

Alternativa (ACCEPTADA) — restriccions amb nom i GET DIAGNOSTICS:
```sql
CREATE DOMAIN email_client text CONSTRAINT format_email CHECK (VALUE ~ '^[a-z0-9._-]+@[a-z0-9-]+(\.[a-z0-9-]+)+$') CONSTRAINT obligatori NOT NULL;
CREATE FUNCTION canvia_email(p_customer_id integer, p_email email_client) RETURNS boolean AS $$
DECLARE n integer;
BEGIN
  UPDATE customer SET email = p_email WHERE customer_id = p_customer_id;
  GET DIAGNOSTICS n = ROW_COUNT;
  RETURN n > 0;
END $$ LANGUAGE plpgsql;
```

Incorrecta (REBUTJADA: Test 5 (SELECT NULL::email_client): yours returns rows, the expected one gives an error (SQLSTATE 23502 not_null_violation)) — domini sense NOT NULL:
```sql
CREATE DOMAIN email_client AS text CHECK (VALUE ~ '^[a-z0-9._-]+@[a-z0-9-]+(\.[a-z0-9-]+)+$');
CREATE FUNCTION canvia_email(p_customer_id integer, p_email email_client) RETURNS boolean LANGUAGE plpgsql AS $$
BEGIN
  UPDATE customer SET email = p_email WHERE customer_id = p_customer_id;
  RETURN FOUND;
END $$;
```

Incorrecta (REBUTJADA: Test 2 (SELECT 'Joan.Puig@ies-sabadell.cat'::email_client): yours returns rows, the expected one gives an error (SQLSTATE 23514 check_violation)) — ~* no distingeix majúscules:
```sql
CREATE DOMAIN email_client AS text NOT NULL CHECK (VALUE ~* '^[a-z0-9._-]+@[a-z0-9-]+(\.[a-z0-9-]+)+$');
CREATE FUNCTION canvia_email(p_customer_id integer, p_email email_client) RETURNS boolean LANGUAGE plpgsql AS $$
BEGIN
  UPDATE customer SET email = p_email WHERE customer_id = p_customer_id;
  RETURN FOUND;
END $$;
```

Incorrecta (REBUTJADA: Test 7 (SELECT canvia_email(9999, 'ningu@exemple.cat')): Result sets differ (comparing unordered)) — LANGUAGE sql amb RETURNING: per a un client inexistent retorna NULL, no false:
```sql
CREATE DOMAIN email_client AS text NOT NULL CHECK (VALUE ~ '^[a-z0-9._-]+@[a-z0-9-]+(\.[a-z0-9-]+)+$');
CREATE FUNCTION canvia_email(p_customer_id integer, p_email email_client) RETURNS boolean LANGUAGE sql AS $$
  UPDATE customer SET email = p_email WHERE customer_id = p_customer_id RETURNING true;
$$;
```

### 5. Crea el tipus enumerat `nivell_client` amb els valors `'bronze'`, `'plata'` i `'or'`, en aquest ordre (de menys a més), i la funció `nivell(p_customer_id integer) RETURNS nivell_client` que classifiqui un client segons l'import total que ha pagat: menys de 100 → `bronze`; de 100 (inclòs) a 150 (no inclòs) → `plata`; 150 o més → `or`. Un client sense pagaments és `bronze`; si el client no existeix, la funció retorna `NULL`.

Referència (2.77 s, referència + resposta):
```sql
CREATE TYPE nivell_client AS ENUM ('bronze', 'plata', 'or');
CREATE FUNCTION nivell(p_customer_id integer) RETURNS nivell_client
LANGUAGE plpgsql STABLE AS $$
DECLARE
  v_total numeric;
BEGIN
  IF NOT EXISTS (SELECT 1 FROM customer WHERE customer_id = p_customer_id) THEN
    RETURN NULL;
  END IF;
  SELECT coalesce(sum(amount), 0) INTO v_total FROM payment WHERE customer_id = p_customer_id;
  RETURN CASE WHEN v_total < 100 THEN 'bronze'
              WHEN v_total < 150 THEN 'plata'
              ELSE 'or' END;
END $$;
--@@TEST@@ SELECT nivell(1), nivell(148), nivell(43)
--@@TEST@@ SELECT nivell(9999)
--@@TEST@@ INSERT INTO payment (customer_id, staff_id, rental_id, amount, payment_date) VALUES (43, 1, 1, 0.24, '2022-05-01 10:00:00+00')
--@@TEST@@ SELECT nivell(43)
--@@TEST@@ SELECT nivell(customer_id) AS n, count(*) FROM customer GROUP BY n
--@@TEST@@ SELECT max(nivell(customer_id)) FROM customer
--@@TEST@@ SELECT count(*) FROM customer WHERE nivell(customer_id) >= 'plata'
```

Alternativa (ACCEPTADA) — LANGUAGE sql:
```sql
CREATE TYPE nivell_client AS ENUM ('bronze', 'plata', 'or');
CREATE FUNCTION nivell(p_customer_id integer) RETURNS nivell_client LANGUAGE sql AS $$
  SELECT CASE WHEN t < 100 THEN 'bronze' WHEN t < 150 THEN 'plata' ELSE 'or' END::nivell_client
  FROM (SELECT (SELECT coalesce(sum(amount), 0) FROM payment p WHERE p.customer_id = c.customer_id) AS t
        FROM customer c WHERE c.customer_id = p_customer_id) x
$$;
```

Incorrecta (REBUTJADA: Test 6 (SELECT max(nivell(customer_id)) FROM customer): Result sets differ (comparing unordered)) — retorna text: max() i >= comparen alfabèticament:
```sql
CREATE TYPE nivell_client AS ENUM ('bronze', 'plata', 'or');
CREATE FUNCTION nivell(p_customer_id integer) RETURNS text LANGUAGE sql AS $$
  SELECT CASE WHEN t < 100 THEN 'bronze' WHEN t < 150 THEN 'plata' ELSE 'or' END
  FROM (SELECT (SELECT coalesce(sum(amount), 0) FROM payment p WHERE p.customer_id = c.customer_id) AS t
        FROM customer c WHERE c.customer_id = p_customer_id) x
$$;
```

Incorrecta (REBUTJADA: Test 6 (SELECT max(nivell(customer_id)) FROM customer): Result sets differ (comparing unordered)) — enum declarat en l'ordre contrari:
```sql
CREATE TYPE nivell_client AS ENUM ('or', 'plata', 'bronze');
CREATE FUNCTION nivell(p_customer_id integer) RETURNS nivell_client LANGUAGE sql AS $$
  SELECT CASE WHEN t < 100 THEN 'bronze' WHEN t < 150 THEN 'plata' ELSE 'or' END::nivell_client
  FROM (SELECT (SELECT coalesce(sum(amount), 0) FROM payment p WHERE p.customer_id = c.customer_id) AS t
        FROM customer c WHERE c.customer_id = p_customer_id) x
$$;
```

Incorrecta (REBUTJADA: Test 2 (SELECT nivell(9999)): Result sets differ (comparing unordered)) — client inexistent → bronze, i límits amb <=:
```sql
CREATE TYPE nivell_client AS ENUM ('bronze', 'plata', 'or');
CREATE FUNCTION nivell(p_customer_id integer) RETURNS nivell_client LANGUAGE sql AS $$
  SELECT CASE WHEN coalesce(sum(amount), 0) <= 100 THEN 'bronze' WHEN sum(amount) <= 150 THEN 'plata' ELSE 'or' END::nivell_client
  FROM payment WHERE customer_id = p_customer_id
$$;
```

### 6. Crea el tipus compost `fitxa_peli` amb els camps `titol text, categoria text, actors text[], extres text[]` (en aquest ordre) i la funció `fitxa(p_film_id integer) RETURNS fitxa_peli` que retorni la fitxa d'una pel·lícula: el títol, el nom de la seva categoria, l'array dels actors (cada un com a `first_name || ' ' || last_name`, ordenats alfabèticament per aquest text; un array buit `'{}'`, no `NULL`, si no en té cap) i els extres (`special_features` tal com són). Si la pel·lícula no existeix, excepció amb `ERRCODE = 'no_data_found'`. Crea també la funció `fitxa_json(p_film_id integer) RETURNS jsonb` que retorni la mateixa fitxa com a objecte JSON amb les claus `titol`, `categoria`, `actors` (array JSON) i `extres` (array JSON).

Referència (1.00 s, referència + resposta):
```sql
CREATE TYPE fitxa_peli AS (titol text, categoria text, actors text[], extres text[]);
CREATE FUNCTION fitxa(p_film_id integer) RETURNS fitxa_peli
LANGUAGE plpgsql STABLE AS $$
DECLARE
  v fitxa_peli;
BEGIN
  SELECT f.title,
         (SELECT c.name FROM film_category fc JOIN category c ON c.category_id = fc.category_id WHERE fc.film_id = f.film_id),
         ARRAY(SELECT a.first_name || ' ' || a.last_name FROM film_actor fa JOIN actor a ON a.actor_id = fa.actor_id
               WHERE fa.film_id = f.film_id ORDER BY 1),
         f.special_features
  INTO v
  FROM film f WHERE f.film_id = p_film_id;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'No existeix la pel·lícula %', p_film_id USING ERRCODE = 'no_data_found';
  END IF;
  RETURN v;
END $$;
CREATE FUNCTION fitxa_json(p_film_id integer) RETURNS jsonb
LANGUAGE sql STABLE AS $$
  SELECT to_jsonb(fitxa(p_film_id))
$$;
--@@TEST@@ SELECT * FROM fitxa(1)
--@@TEST@@ SELECT (fitxa(2)).categoria, cardinality((fitxa(2)).actors)
--@@TEST@@ SELECT * FROM fitxa(257)
--@@TEST@@ SELECT * FROM fitxa(9999)
--@@TEST@@ SELECT fitxa_json(3)
--@@TEST@@ SELECT fitxa_json(3) ->> 'categoria', fitxa_json(3) -> 'actors' -> 0, jsonb_array_length(fitxa_json(257) -> 'actors')
--@@TEST@@ SELECT jsonb_path_query(fitxa_json(1), '$.actors[*] ? (@ starts with "C")')
--@@TEST@@ SELECT f.titol FROM film CROSS JOIN LATERAL fitxa(film_id) f WHERE 'PENELOPE GUINESS' = ANY (f.actors) AND f.extres @> '{Trailers}'
--@@TEST@@ SELECT fitxa(4) = ROW('AFFAIR PREJUDICE', 'Horror', (fitxa(4)).actors, '{Commentaries,"Behind the Scenes"}')::fitxa_peli
```

Alternativa (ACCEPTADA) — array_agg amb FILTER i coalesce, i jsonb_build_object:
```sql
CREATE TYPE fitxa_peli AS (titol text, categoria text, actors text[], extres text[]);
CREATE FUNCTION fitxa(p_film_id integer) RETURNS fitxa_peli AS $$
DECLARE r fitxa_peli;
BEGIN
  IF NOT EXISTS (SELECT 1 FROM film WHERE film_id = p_film_id) THEN
    RAISE EXCEPTION 'film' USING ERRCODE = 'P0002';
  END IF;
  SELECT f.title, c.name, coalesce(array_agg(a.first_name || ' ' || a.last_name ORDER BY a.first_name || ' ' || a.last_name) FILTER (WHERE a.actor_id IS NOT NULL), '{}'), f.special_features
  INTO r.titol, r.categoria, r.actors, r.extres
  FROM film f LEFT JOIN film_category fc ON fc.film_id = f.film_id LEFT JOIN category c ON c.category_id = fc.category_id
  LEFT JOIN film_actor fa ON fa.film_id = f.film_id LEFT JOIN actor a ON a.actor_id = fa.actor_id
  WHERE f.film_id = p_film_id GROUP BY f.title, c.name, f.special_features;
  RETURN r;
END $$ LANGUAGE plpgsql;
CREATE FUNCTION fitxa_json(p_film_id integer) RETURNS jsonb AS $$
DECLARE r fitxa_peli := fitxa(p_film_id);
BEGIN
  RETURN jsonb_build_object('titol', r.titol, 'categoria', r.categoria, 'actors', to_jsonb(r.actors), 'extres', to_jsonb(r.extres));
END $$ LANGUAGE plpgsql;
```

Incorrecta (REBUTJADA: Test 3 (SELECT * FROM fitxa(257)): Result sets differ (comparing unordered)) — array_agg amb LEFT JOIN: per a una pel·lícula sense actors dona {NULL}:
```sql
CREATE TYPE fitxa_peli AS (titol text, categoria text, actors text[], extres text[]);
CREATE FUNCTION fitxa(p_film_id integer) RETURNS fitxa_peli LANGUAGE sql AS $$
  SELECT f.title, c.name, array_agg(a.first_name || ' ' || a.last_name ORDER BY a.first_name, a.last_name), f.special_features
  FROM film f JOIN film_category fc ON fc.film_id = f.film_id JOIN category c ON c.category_id = fc.category_id
  LEFT JOIN film_actor fa ON fa.film_id = f.film_id LEFT JOIN actor a ON a.actor_id = fa.actor_id
  WHERE f.film_id = p_film_id GROUP BY f.title, c.name, f.special_features
$$;
CREATE FUNCTION fitxa_json(p_film_id integer) RETURNS jsonb LANGUAGE sql AS $$ SELECT to_jsonb(fitxa(p_film_id)) $$;
```

Incorrecta (REBUTJADA: Test 5 (SELECT fitxa_json(3)): Result sets differ (comparing unordered)) — clau 'title' en lloc de 'titol' al JSON:
```sql
CREATE TYPE fitxa_peli AS (titol text, categoria text, actors text[], extres text[]);
CREATE FUNCTION fitxa(p_film_id integer) RETURNS fitxa_peli LANGUAGE plpgsql AS $$
DECLARE v fitxa_peli;
BEGIN
  SELECT f.title, (SELECT c.name FROM film_category fc JOIN category c USING (category_id) WHERE fc.film_id = f.film_id),
         ARRAY(SELECT a.first_name || ' ' || a.last_name FROM film_actor fa JOIN actor a USING (actor_id) WHERE fa.film_id = f.film_id ORDER BY 1),
         f.special_features INTO v FROM film f WHERE f.film_id = p_film_id;
  IF NOT FOUND THEN RAISE EXCEPTION 'film' USING ERRCODE = 'no_data_found'; END IF;
  RETURN v;
END $$;
CREATE FUNCTION fitxa_json(p_film_id integer) RETURNS jsonb LANGUAGE sql AS $$
  SELECT jsonb_build_object('title', (fitxa(p_film_id)).titol, 'categoria', (fitxa(p_film_id)).categoria, 'actors', (fitxa(p_film_id)).actors, 'extres', (fitxa(p_film_id)).extres)
$$;
```

Incorrecta (REBUTJADA: Test 1 (SELECT * FROM fitxa(1)): Result sets differ (comparing unordered)) — actors ordenats per cognom:
```sql
CREATE TYPE fitxa_peli AS (titol text, categoria text, actors text[], extres text[]);
CREATE FUNCTION fitxa(p_film_id integer) RETURNS fitxa_peli LANGUAGE plpgsql AS $$
DECLARE v fitxa_peli;
BEGIN
  SELECT f.title, (SELECT c.name FROM film_category fc JOIN category c USING (category_id) WHERE fc.film_id = f.film_id),
         ARRAY(SELECT a.first_name || ' ' || a.last_name FROM film_actor fa JOIN actor a USING (actor_id) WHERE fa.film_id = f.film_id ORDER BY a.last_name),
         f.special_features INTO v FROM film f WHERE f.film_id = p_film_id;
  IF NOT FOUND THEN RAISE EXCEPTION 'film' USING ERRCODE = 'no_data_found'; END IF;
  RETURN v;
END $$;
CREATE FUNCTION fitxa_json(p_film_id integer) RETURNS jsonb LANGUAGE sql AS $$ SELECT to_jsonb(fitxa(p_film_id)) $$;
```

