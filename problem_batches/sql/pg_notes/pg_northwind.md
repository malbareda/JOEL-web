# Northwind PostgreSQL — verificació amb el corrector real (postgres)


## Northwind — Consultes avançades (pgadvquery)


### 1. Resum del catàleg per categoria. Per a cada categoria, mostra: `category_name`, el nombre total de productes, quants estan descatalogats (`discontinued = 1`), quants productes **actius** (`discontinued = 0`) cal reposar perquè tenen `units_in_stock <= reorder_level`, i el preu mitjà (`unit_price`) dels productes actius arrodonit a 2 decimals. Fes servir `count(*) FILTER (WHERE ...)` i `avg(...) FILTER (WHERE ...)` en lloc de `CASE`.

Referència:
```sql
SELECT c.category_name, count(*), count(*) FILTER (WHERE p.discontinued = 1), count(*) FILTER (WHERE p.discontinued = 0 AND p.units_in_stock <= p.reorder_level), round(avg(p.unit_price) FILTER (WHERE p.discontinued = 0)::numeric, 2) FROM categories c JOIN products p ON p.category_id = c.category_id GROUP BY c.category_name
```

Alternativa (ACCEPTADA):
```sql
SELECT category_name, count(*) AS productes, sum(CASE WHEN discontinued = 1 THEN 1 ELSE 0 END) AS descatalogats, sum(CASE WHEN discontinued = 0 AND units_in_stock <= reorder_level THEN 1 ELSE 0 END) AS a_reposar, round(avg(CASE WHEN discontinued = 0 THEN unit_price END)::numeric, 2) AS preu_mitja FROM products JOIN categories USING (category_id) GROUP BY category_id, category_name
```

Incorrecta — el preu mitjà inclou els descatalogats (REBUTJADA: Result sets differ (comparing unordered)):
```sql
SELECT c.category_name, count(*), count(*) FILTER (WHERE p.discontinued = 1), count(*) FILTER (WHERE p.discontinued = 0 AND p.units_in_stock <= p.reorder_level), round(avg(p.unit_price)::numeric, 2) FROM categories c JOIN products p ON p.category_id = c.category_id GROUP BY c.category_name
```

Incorrecta — compta també els descatalogats a reposar (REBUTJADA: Result sets differ (comparing unordered)):
```sql
SELECT c.category_name, count(*), count(*) FILTER (WHERE p.discontinued = 1), count(*) FILTER (WHERE p.units_in_stock <= p.reorder_level), round(avg(p.unit_price) FILTER (WHERE p.discontinued = 0)::numeric, 2) FROM categories c JOIN products p ON p.category_id = c.category_id GROUP BY c.category_name
```


### 2. Per a cada client que ha fet alguna comanda, mostra la seva **darrera** comanda: `customer_id`, `company_name`, `order_id` i `order_date`. Si un client té dues comandes el mateix darrer dia, agafa la d'`order_id` més gran. Resol-ho amb `SELECT DISTINCT ON (...)` i l'`ORDER BY` adequat.

Referència:
```sql
SELECT DISTINCT ON (o.customer_id) o.customer_id, c.company_name, o.order_id, o.order_date FROM orders o JOIN customers c ON c.customer_id = o.customer_id ORDER BY o.customer_id, o.order_date DESC, o.order_id DESC
```

Alternativa (ACCEPTADA):
```sql
SELECT customer_id, company_name, order_id, order_date FROM (SELECT o.customer_id, c.company_name, o.order_id, o.order_date, row_number() OVER (PARTITION BY o.customer_id ORDER BY o.order_date DESC, o.order_id DESC) AS rn FROM orders o JOIN customers c USING (customer_id)) t WHERE rn = 1
```

Incorrecta — no desempata per `order_id` (dos clients tenen dues comandes el darrer dia) (REBUTJADA: Result sets differ (comparing unordered)):
```sql
SELECT DISTINCT ON (o.customer_id) o.customer_id, c.company_name, o.order_id, o.order_date FROM orders o JOIN customers c ON c.customer_id = o.customer_id ORDER BY o.customer_id, o.order_date DESC, o.order_id
```

Incorrecta — agafa la primera comanda en lloc de la darrera (REBUTJADA: Result sets differ (comparing unordered)):
```sql
SELECT DISTINCT ON (o.customer_id) o.customer_id, c.company_name, o.order_id, o.order_date FROM orders o JOIN customers c ON c.customer_id = o.customer_id ORDER BY o.customer_id, o.order_date, o.order_id
```


### 3. Per a cada categoria, els **3 productes més venuts** (en unitats, la suma de `order_details.quantity`). Mostra `category_name`, `product_name` i les unitats venudes. Resol-ho amb una subconsulta `JOIN LATERAL (... ORDER BY ... LIMIT 3)` que, per a cada categoria, busqui els seus tres productes (no hi ha empats a la tercera posició).

Referència:
```sql
SELECT c.category_name, t.product_name, t.unitats FROM categories c CROSS JOIN LATERAL (SELECT p.product_name, sum(od.quantity) AS unitats FROM products p JOIN order_details od ON od.product_id = p.product_id WHERE p.category_id = c.category_id GROUP BY p.product_id, p.product_name ORDER BY unitats DESC LIMIT 3) t
```

Alternativa (ACCEPTADA):
```sql
SELECT category_name, product_name, unitats FROM (SELECT c.category_name, p.product_name, sum(od.quantity) AS unitats, rank() OVER (PARTITION BY c.category_id ORDER BY sum(od.quantity) DESC) AS r FROM categories c JOIN products p USING (category_id) JOIN order_details od USING (product_id) GROUP BY c.category_id, c.category_name, p.product_id, p.product_name) t WHERE r <= 3
```

Incorrecta — `LIMIT 3` a tota la consulta en lloc de dins del `LATERAL` (REBUTJADA: Wrong number of rows: got 3, expected 24):
```sql
SELECT c.category_name, p.product_name, sum(od.quantity) AS unitats FROM categories c JOIN products p ON p.category_id = c.category_id JOIN order_details od ON od.product_id = p.product_id GROUP BY c.category_name, p.product_name ORDER BY unitats DESC LIMIT 3
```

Incorrecta — compta línies de comanda (`count(*)`) en lloc d'unitats (REBUTJADA: Result sets differ (comparing unordered)):
```sql
SELECT c.category_name, t.product_name, t.n FROM categories c CROSS JOIN LATERAL (SELECT p.product_name, count(*) AS n FROM products p JOIN order_details od ON od.product_id = p.product_id WHERE p.category_id = c.category_id GROUP BY p.product_name ORDER BY n DESC LIMIT 3) t
```


### 4. Unitats venudes per categoria i any de la comanda (`order_date`), amb subtotals. Mostra `category_name`, l'any (enter) i la suma de `quantity`, i fes servir `GROUP BY ROLLUP (...)` perquè també surtin el total de cada categoria (any a `NULL`) i el total general (categoria i any a `NULL`).

Referència:
```sql
SELECT c.category_name, extract(year FROM o.order_date)::int AS anyo, sum(od.quantity) FROM order_details od JOIN orders o ON o.order_id = od.order_id JOIN products p ON p.product_id = od.product_id JOIN categories c ON c.category_id = p.category_id GROUP BY ROLLUP (c.category_name, extract(year FROM o.order_date)::int)
```

Alternativa — amb `GROUPING SETS` i `date_part` (ACCEPTADA):
```sql
SELECT category_name, date_part('year', order_date)::int, sum(quantity) FROM order_details JOIN orders USING (order_id) JOIN products USING (product_id) JOIN categories USING (category_id) GROUP BY GROUPING SETS ((category_name, date_part('year', order_date)::int), (category_name), ())
```

Alternativa — amb `UNION ALL` (ACCEPTADA):
```sql
SELECT c.category_name, extract(year FROM o.order_date)::int, sum(od.quantity) FROM order_details od JOIN orders o USING (order_id) JOIN products p USING (product_id) JOIN categories c USING (category_id) GROUP BY 1, 2 UNION ALL SELECT c.category_name, NULL, sum(od.quantity) FROM order_details od JOIN products p USING (product_id) JOIN categories c USING (category_id) GROUP BY 1 UNION ALL SELECT NULL, NULL, sum(quantity) FROM order_details
```

Incorrecta — `CUBE` afegeix també els totals per any (REBUTJADA: Wrong number of rows: got more than 33, expected 33):
```sql
SELECT c.category_name, extract(year FROM o.order_date)::int, sum(od.quantity) FROM order_details od JOIN orders o ON o.order_id = od.order_id JOIN products p ON p.product_id = od.product_id JOIN categories c ON c.category_id = p.category_id GROUP BY CUBE (c.category_name, extract(year FROM o.order_date)::int)
```

Incorrecta — `GROUP BY` normal: falten els subtotals (REBUTJADA: Wrong number of rows: got 24, expected 33):
```sql
SELECT c.category_name, extract(year FROM o.order_date)::int, sum(od.quantity) FROM order_details od JOIN orders o ON o.order_id = od.order_id JOIN products p ON p.product_id = od.product_id JOIN categories c ON c.category_id = p.category_id GROUP BY 1, 2
```


### 5. Evolució mensual de les unitats venudes l'any **1997** (comandes amb `order_date` del 1997). Per a cada mes, mostra: el número de mes (enter, 1-12), les unitats venudes (suma de `quantity`), la diferència respecte del mes anterior (`NULL` al gener), les unitats acumulades des del gener fins a aquell mes inclòs, i la mitjana mòbil de 3 mesos (la mitjana d'aquell mes i dels dos anteriors; al gener i al febrer, la dels mesos que hi hagi) arrodonida a 2 decimals. Fes servir `LAG`, `SUM() OVER` i un marc `ROWS BETWEEN 2 PRECEDING AND CURRENT ROW`.

Referència:
```sql
WITH m AS (SELECT extract(month FROM o.order_date)::int AS mes, sum(od.quantity) AS unitats FROM orders o JOIN order_details od ON od.order_id = o.order_id WHERE o.order_date >= DATE '1997-01-01' AND o.order_date < DATE '1998-01-01' GROUP BY 1) SELECT mes, unitats, unitats - lag(unitats) OVER (ORDER BY mes), sum(unitats) OVER (ORDER BY mes), round(avg(unitats) OVER (ORDER BY mes ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 2) FROM m
```

Alternativa (ACCEPTADA):
```sql
SELECT date_part('month', order_date)::int AS mes, sum(quantity) AS u, sum(quantity) - lag(sum(quantity)) OVER w, sum(sum(quantity)) OVER (w ROWS UNBOUNDED PRECEDING), round(avg(sum(quantity)) OVER (w ROWS 2 PRECEDING), 2) FROM orders JOIN order_details USING (order_id) WHERE extract(year FROM order_date) = 1997 GROUP BY 1 WINDOW w AS (ORDER BY date_part('month', order_date)::int)
```

Incorrecta — sense marc: la mitjana és acumulada des del gener (REBUTJADA: Result sets differ (comparing unordered)):
```sql
WITH m AS (SELECT extract(month FROM o.order_date)::int AS mes, sum(od.quantity) AS unitats FROM orders o JOIN order_details od ON od.order_id = o.order_id WHERE extract(year FROM o.order_date) = 1997 GROUP BY 1) SELECT mes, unitats, unitats - lag(unitats) OVER (ORDER BY mes), sum(unitats) OVER (ORDER BY mes), round(avg(unitats) OVER (ORDER BY mes), 2) FROM m
```

Incorrecta — `lag(unitats, 1, 0)`: al gener posa la diferència respecte de 0 en lloc de `NULL` (REBUTJADA: Result sets differ (comparing unordered)):
```sql
WITH m AS (SELECT extract(month FROM o.order_date)::int AS mes, sum(od.quantity) AS unitats FROM orders o JOIN order_details od ON od.order_id = o.order_id WHERE extract(year FROM o.order_date) = 1997 GROUP BY 1) SELECT mes, unitats, unitats - lag(unitats, 1, 0::bigint) OVER (ORDER BY mes), sum(unitats) OVER (ORDER BY mes), round(avg(unitats) OVER (ORDER BY mes ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 2) FROM m
```

Incorrecta — `sum() OVER ()` sense `ORDER BY`: el total de l'any a totes les files (REBUTJADA: Result sets differ (comparing unordered)):
```sql
WITH m AS (SELECT extract(month FROM o.order_date)::int AS mes, sum(od.quantity) AS unitats FROM orders o JOIN order_details od ON od.order_id = o.order_id WHERE extract(year FROM o.order_date) = 1997 GROUP BY 1) SELECT mes, unitats, unitats - lag(unitats) OVER (ORDER BY mes), sum(unitats) OVER (), round(avg(unitats) OVER (ORDER BY mes ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 2) FROM m
```


### 6. Organigrama de vendes. Per a cada empleat, mostra: `employee_id`, el seu nivell a la jerarquia (0 per a qui no té cap, `reports_to` a `NULL`; 1 per als qui en depenen directament...), el camí des del cap de tots fins a ell format pels cognoms (`last_name`) separats per `' > '` (per exemple `Fuller > Buchanan > King`), i el nombre de comandes (`orders`) gestionades per tot el seu equip: les seves més les de tots els empleats que en depenen directament o indirectament. Fes servir `WITH RECURSIVE`.

Referència:
```sql
WITH RECURSIVE arbre AS (SELECT employee_id, 0 AS nivell, last_name::text AS cami FROM employees WHERE reports_to IS NULL UNION ALL SELECT e.employee_id, a.nivell + 1, a.cami || ' > ' || e.last_name FROM employees e JOIN arbre a ON e.reports_to = a.employee_id), equip AS (SELECT employee_id AS cap, employee_id AS membre FROM employees UNION ALL SELECT q.cap, e.employee_id FROM equip q JOIN employees e ON e.reports_to = q.membre) SELECT a.employee_id, a.nivell, a.cami, (SELECT count(*) FROM equip q JOIN orders o ON o.employee_id = q.membre WHERE q.cap = a.employee_id) FROM arbre a
```

Alternativa — el camí guarda els ids, i el recompte busca l'empleat dins del camí de cada membre (ACCEPTADA):
```sql
WITH RECURSIVE arbre AS (SELECT employee_id, 0 AS nivell, last_name::text AS cami, ARRAY[employee_id] AS ids FROM employees WHERE reports_to IS NULL UNION ALL SELECT e.employee_id, a.nivell + 1, a.cami || ' > ' || e.last_name, a.ids || e.employee_id FROM employees e JOIN arbre a ON e.reports_to = a.employee_id) SELECT a.employee_id, a.nivell, a.cami, (SELECT count(*) FROM arbre b JOIN orders o ON o.employee_id = b.employee_id WHERE a.employee_id = ANY (b.ids)) FROM arbre a
```

Incorrecta — compta només les comandes pròpies (REBUTJADA: Result sets differ (comparing unordered)):
```sql
WITH RECURSIVE arbre AS (SELECT employee_id, 0 AS nivell, last_name::text AS cami FROM employees WHERE reports_to IS NULL UNION ALL SELECT e.employee_id, a.nivell + 1, a.cami || ' > ' || e.last_name FROM employees e JOIN arbre a ON e.reports_to = a.employee_id) SELECT a.employee_id, a.nivell, a.cami, (SELECT count(*) FROM orders o WHERE o.employee_id = a.employee_id) FROM arbre a
```

Incorrecta — compta només els subordinats directes (no els indirectes) (REBUTJADA: Result sets differ (comparing unordered)):
```sql
WITH RECURSIVE arbre AS (SELECT employee_id, 0 AS nivell, last_name::text AS cami FROM employees WHERE reports_to IS NULL UNION ALL SELECT e.employee_id, a.nivell + 1, a.cami || ' > ' || e.last_name FROM employees e JOIN arbre a ON e.reports_to = a.employee_id) SELECT a.employee_id, a.nivell, a.cami, (SELECT count(*) FROM orders o JOIN employees e ON e.employee_id = o.employee_id WHERE e.employee_id = a.employee_id OR e.reports_to = a.employee_id) FROM arbre a
```

Incorrecta — camí a l'inrevés (de l'empleat cap amunt) (REBUTJADA: Result sets differ (comparing unordered)):
```sql
WITH RECURSIVE arbre AS (SELECT employee_id, 0 AS nivell, last_name::text AS cami FROM employees WHERE reports_to IS NULL UNION ALL SELECT e.employee_id, a.nivell + 1, e.last_name || ' > ' || a.cami FROM employees e JOIN arbre a ON e.reports_to = a.employee_id), equip AS (SELECT employee_id AS cap, employee_id AS membre FROM employees UNION ALL SELECT q.cap, e.employee_id FROM equip q JOIN employees e ON e.reports_to = q.membre) SELECT a.employee_id, a.nivell, a.cami, (SELECT count(*) FROM equip q JOIN orders o ON o.employee_id = q.membre WHERE q.cap = a.employee_id) FROM arbre a
```


## Northwind — Funcions (pgfunc)


### 1. Crea la funció `import_comanda(p_order_id integer) RETURNS numeric` que retorni l'import d'una comanda: la suma de `unit_price * quantity * (1 - discount)` de les seves línies (`order_details`), calculada amb `numeric` (converteix `unit_price` i `discount` a `numeric` abans d'operar) i arrodonida a 2 decimals al final. Si la comanda no existeix, ha de retornar `NULL`. Pots fer-la amb `LANGUAGE sql`.

Referència:
```sql
CREATE FUNCTION import_comanda(p_order_id integer) RETURNS numeric LANGUAGE sql STABLE AS $$
  SELECT round(sum(od.unit_price::numeric * od.quantity * (1 - od.discount::numeric)), 2)
  FROM order_details od WHERE od.order_id = p_order_id
$$;
--@@TEST@@ SELECT import_comanda(10248)
--@@TEST@@ SELECT import_comanda(10264)
--@@TEST@@ SELECT import_comanda(1)
--@@TEST@@ SELECT order_id, import_comanda(order_id) FROM orders WHERE customer_id IN ('ALFKI', 'FOLKO', 'SAVEA') ORDER BY order_id
```

Alternativa (ACCEPTADA):
```sql
CREATE OR REPLACE FUNCTION import_comanda(p_order_id integer) RETURNS numeric AS $$
DECLARE v numeric;
BEGIN
  SELECT sum(unit_price::numeric * quantity * (1 - discount::numeric)) INTO v
  FROM order_details WHERE order_id = p_order_id;
  RETURN round(v, 2);
END;
$$ LANGUAGE plpgsql;
```

Incorrecta — calcula amb `real`/`double precision`: alguns imports queden 1 cèntim per sota (REBUTJADA: Test 2 (SELECT import_comanda(10264)): Result sets differ (comparing unordered)):
```sql
CREATE FUNCTION import_comanda(p_order_id integer) RETURNS numeric LANGUAGE sql AS $$
  SELECT round(sum(unit_price * quantity * (1 - discount))::numeric, 2) FROM order_details WHERE order_id = p_order_id
$$;
```

Incorrecta — retorna 0 per a una comanda que no existeix (REBUTJADA: Test 3 (SELECT import_comanda(1)): Result sets differ (comparing unordered)):
```sql
CREATE FUNCTION import_comanda(p_order_id integer) RETURNS numeric LANGUAGE sql AS $$
  SELECT coalesce(round(sum(unit_price::numeric * quantity * (1 - discount::numeric)), 2), 0) FROM order_details WHERE order_id = p_order_id
$$;
```

Incorrecta — oblida el descompte (REBUTJADA: Test 2 (SELECT import_comanda(10264)): Result sets differ (comparing unordered)):
```sql
CREATE FUNCTION import_comanda(p_order_id integer) RETURNS numeric LANGUAGE sql AS $$
  SELECT round(sum(unit_price::numeric * quantity), 2) FROM order_details WHERE order_id = p_order_id
$$;
```

Incorrecta — paràmetre `smallint`: la crida amb un `integer` no troba la funció (REBUTJADA: Test 1 (SELECT import_comanda(10248)): yours gives an error (SQLSTATE 42883 undefined_function), the expected one returns rows):
```sql
CREATE FUNCTION import_comanda(p_order_id smallint) RETURNS numeric LANGUAGE sql AS $$
  SELECT round(sum(unit_price::numeric * quantity * (1 - discount::numeric)), 2) FROM order_details WHERE order_id = p_order_id
$$;
```


### 2. Crea la funció PL/pgSQL `estat_estoc(p_product_id integer) RETURNS text` que classifiqui un producte segons aquestes regles, **en aquest ordre de prioritat**: `'DESCATALOGAT'` si `discontinued = 1`; `'ESGOTAT'` si `units_in_stock = 0`; `'REPOSAR'` si `units_in_stock <= reorder_level`; i `'OK'` en qualsevol altre cas. Si el producte no existeix, ha de llançar una excepció amb `ERRCODE = 'no_data_found'`.

Referència:
```sql
CREATE FUNCTION estat_estoc(p_product_id integer) RETURNS text LANGUAGE plpgsql AS $$
DECLARE p products%ROWTYPE;
BEGIN
  SELECT * INTO p FROM products WHERE product_id = p_product_id;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'El producte % no existeix', p_product_id USING ERRCODE = 'no_data_found';
  END IF;
  IF p.discontinued = 1 THEN RETURN 'DESCATALOGAT';
  ELSIF p.units_in_stock = 0 THEN RETURN 'ESGOTAT';
  ELSIF p.units_in_stock <= p.reorder_level THEN RETURN 'REPOSAR';
  END IF;
  RETURN 'OK';
END $$;
--@@TEST@@ SELECT product_id, estat_estoc(product_id) FROM products ORDER BY product_id
--@@TEST@@ UPDATE products SET units_in_stock = reorder_level WHERE product_id = 11
--@@TEST@@ SELECT estat_estoc(11)
--@@TEST@@ SELECT estat_estoc(999)
```

Alternativa — amb `CASE` i `LANGUAGE plpgsql` mínim (ACCEPTADA):
```sql
CREATE OR REPLACE FUNCTION estat_estoc(p_product_id integer) RETURNS text AS $$
DECLARE r text;
BEGIN
  SELECT CASE WHEN discontinued = 1 THEN 'DESCATALOGAT' WHEN units_in_stock = 0 THEN 'ESGOTAT'
              WHEN units_in_stock <= reorder_level THEN 'REPOSAR' ELSE 'OK' END INTO STRICT r
  FROM products WHERE product_id = p_product_id;
  RETURN r;
EXCEPTION WHEN no_data_found THEN RAISE EXCEPTION 'no existeix' USING ERRCODE = 'P0002';
END $$ LANGUAGE plpgsql;
```

Incorrecta — ordre de prioritat equivocat (comprova l'estoc abans que `discontinued`) (REBUTJADA: Test 1 (SELECT product_id, estat_estoc(product_id) FROM products ...): Result sets differ (comparing unordered)):
```sql
CREATE FUNCTION estat_estoc(p_product_id integer) RETURNS text LANGUAGE plpgsql AS $$
DECLARE p products%ROWTYPE;
BEGIN
  SELECT * INTO p FROM products WHERE product_id = p_product_id;
  IF NOT FOUND THEN RAISE EXCEPTION 'no existeix' USING ERRCODE = 'no_data_found'; END IF;
  IF p.units_in_stock = 0 THEN RETURN 'ESGOTAT'; ELSIF p.discontinued = 1 THEN RETURN 'DESCATALOGAT';
  ELSIF p.units_in_stock <= p.reorder_level THEN RETURN 'REPOSAR'; END IF;
  RETURN 'OK';
END $$;
```

Incorrecta — `<` en lloc de `<=` (REBUTJADA: Test 3 (SELECT estat_estoc(11)): Result sets differ (comparing unordered)):
```sql
CREATE FUNCTION estat_estoc(p_product_id integer) RETURNS text LANGUAGE plpgsql AS $$
DECLARE p products%ROWTYPE;
BEGIN
  SELECT * INTO p FROM products WHERE product_id = p_product_id;
  IF NOT FOUND THEN RAISE EXCEPTION 'no existeix' USING ERRCODE = 'no_data_found'; END IF;
  IF p.discontinued = 1 THEN RETURN 'DESCATALOGAT'; ELSIF p.units_in_stock = 0 THEN RETURN 'ESGOTAT';
  ELSIF p.units_in_stock < p.reorder_level THEN RETURN 'REPOSAR'; END IF;
  RETURN 'OK';
END $$;
```

Incorrecta — no valida que el producte existeixi (retorna `'OK'`) (REBUTJADA: Test 4 (SELECT estat_estoc(999)): yours returns rows, the expected one gives an error (SQLSTATE P0002 no_data_found)):
```sql
CREATE FUNCTION estat_estoc(p_product_id integer) RETURNS text LANGUAGE plpgsql AS $$
DECLARE p products%ROWTYPE;
BEGIN
  SELECT * INTO p FROM products WHERE product_id = p_product_id;
  IF p.discontinued = 1 THEN RETURN 'DESCATALOGAT'; ELSIF p.units_in_stock = 0 THEN RETURN 'ESGOTAT';
  ELSIF p.units_in_stock <= p.reorder_level THEN RETURN 'REPOSAR'; END IF;
  RETURN 'OK';
END $$;
```

Incorrecta — `RAISE EXCEPTION` sense `ERRCODE` (dona `P0001` en lloc de `P0002`) (REBUTJADA: Test 4 (SELECT estat_estoc(999)): yours gives an error (SQLSTATE P0001 raise_exception), the expected one gives an error (SQLSTATE P0002 no_data_found)):
```sql
CREATE FUNCTION estat_estoc(p_product_id integer) RETURNS text LANGUAGE plpgsql AS $$
DECLARE p products%ROWTYPE;
BEGIN
  SELECT * INTO p FROM products WHERE product_id = p_product_id;
  IF NOT FOUND THEN RAISE EXCEPTION 'no existeix'; END IF;
  IF p.discontinued = 1 THEN RETURN 'DESCATALOGAT'; ELSIF p.units_in_stock = 0 THEN RETURN 'ESGOTAT';
  ELSIF p.units_in_stock <= p.reorder_level THEN RETURN 'REPOSAR'; END IF;
  RETURN 'OK';
END $$;
```


### 3. Crea la funció `productes_categoria(p_categoria varchar, p_preu_minim numeric DEFAULT 0)` que retorni una taula (`RETURNS TABLE (producte varchar, preu numeric, estoc integer)`) amb el nom, el preu (`unit_price`) i les unitats en estoc dels productes **actius** (`discontinued = 0`) de la categoria anomenada `p_categoria` (`category_name`) amb un preu de com a mínim `p_preu_minim`. Si no hi ha cap categoria amb aquest nom, ha de llançar una excepció amb `ERRCODE = 'no_data_found'`; si `p_preu_minim` és negatiu, amb `ERRCODE = 'invalid_parameter_value'`. (Si dins la funció et surt un error de tipus o de nom de columna ambigu, recorda que `unit_price` és `real` i que els noms de les columnes de `RETURNS TABLE` són variables dins del cos.)

Referència:
```sql
CREATE FUNCTION productes_categoria(p_categoria varchar, p_preu_minim numeric DEFAULT 0)
RETURNS TABLE (producte varchar, preu numeric, estoc integer) LANGUAGE plpgsql AS $$
DECLARE v_cat smallint;
BEGIN
  IF p_preu_minim < 0 THEN
    RAISE EXCEPTION 'Preu mínim negatiu' USING ERRCODE = 'invalid_parameter_value';
  END IF;
  SELECT c.category_id INTO v_cat FROM categories c WHERE c.category_name = p_categoria;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'La categoria % no existeix', p_categoria USING ERRCODE = 'no_data_found';
  END IF;
  RETURN QUERY SELECT p.product_name, p.unit_price::numeric, p.units_in_stock::integer
    FROM products p WHERE p.category_id = v_cat AND p.discontinued = 0 AND p.unit_price >= p_preu_minim;
END $$;
--@@TEST@@ SELECT * FROM productes_categoria('Seafood')
--@@TEST@@ SELECT * FROM productes_categoria('Beverages', 18)
--@@TEST@@ SELECT * FROM productes_categoria('Meat/Poultry', 0)
--@@TEST@@ SELECT count(*) FROM productes_categoria('Confections', 1000)
--@@TEST@@ SELECT * FROM productes_categoria('Pizza')
--@@TEST@@ SELECT * FROM productes_categoria('Seafood', -5)
```

Alternativa — amb `#variable_conflict use_column` i un `FOR ... LOOP` amb `RETURN NEXT` (ACCEPTADA):
```sql
CREATE FUNCTION productes_categoria(p_categoria varchar, p_preu_minim numeric DEFAULT 0)
RETURNS TABLE (producte varchar, preu numeric, estoc integer) AS $$
#variable_conflict use_column
DECLARE r record;
BEGIN
  IF NOT EXISTS (SELECT 1 FROM categories WHERE category_name = p_categoria) THEN
    RAISE EXCEPTION 'no existeix' USING ERRCODE = 'P0002';
  END IF;
  IF p_preu_minim < 0 THEN RAISE EXCEPTION 'negatiu' USING ERRCODE = '22023'; END IF;
  FOR r IN SELECT product_name, unit_price, units_in_stock FROM products JOIN categories USING (category_id)
           WHERE category_name = p_categoria AND discontinued = 0 AND unit_price >= p_preu_minim LOOP
    producte := r.product_name; preu := r.unit_price; estoc := r.units_in_stock;
    RETURN NEXT;
  END LOOP;
END $$ LANGUAGE plpgsql;
```

Incorrecta — no filtra els productes descatalogats (REBUTJADA: Test 2 (SELECT * FROM productes_categoria('Beverages', 18)): Wrong number of rows: got 7, expected 5):
```sql
CREATE FUNCTION productes_categoria(p_categoria varchar, p_preu_minim numeric DEFAULT 0)
RETURNS TABLE (producte varchar, preu numeric, estoc integer) LANGUAGE plpgsql AS $$
BEGIN
  IF p_preu_minim < 0 THEN RAISE EXCEPTION 'negatiu' USING ERRCODE = 'invalid_parameter_value'; END IF;
  IF NOT EXISTS (SELECT 1 FROM categories c WHERE c.category_name = p_categoria) THEN
    RAISE EXCEPTION 'no existeix' USING ERRCODE = 'no_data_found'; END IF;
  RETURN QUERY SELECT p.product_name, p.unit_price::numeric, p.units_in_stock::integer FROM products p
    JOIN categories c ON c.category_id = p.category_id WHERE c.category_name = p_categoria AND p.unit_price >= p_preu_minim;
END $$;
```

Incorrecta — `LANGUAGE sql` sense validacions: una categoria inexistent retorna 0 files en lloc de l'error (REBUTJADA: Test 5 (SELECT * FROM productes_categoria('Pizza')): yours returns rows, the expected one gives an error (SQLSTATE P0002 no_data_found)):
```sql
CREATE FUNCTION productes_categoria(p_categoria varchar, p_preu_minim numeric DEFAULT 0)
RETURNS TABLE (producte varchar, preu numeric, estoc integer) LANGUAGE sql AS $$
  SELECT p.product_name, p.unit_price::numeric, p.units_in_stock::integer FROM products p
  JOIN categories c ON c.category_id = p.category_id
  WHERE c.category_name = p_categoria AND p.discontinued = 0 AND p.unit_price >= p_preu_minim
$$;
```

Incorrecta — preu mínim estricte (`>`): el producte de 18 de `Beverages` no surt (REBUTJADA: Test 2 (SELECT * FROM productes_categoria('Beverages', 18)): Wrong number of rows: got 2, expected 5):
```sql
CREATE FUNCTION productes_categoria(p_categoria varchar, p_preu_minim numeric DEFAULT 0)
RETURNS TABLE (producte varchar, preu numeric, estoc integer) LANGUAGE plpgsql AS $$
BEGIN
  IF p_preu_minim < 0 THEN RAISE EXCEPTION 'negatiu' USING ERRCODE = 'invalid_parameter_value'; END IF;
  IF NOT EXISTS (SELECT 1 FROM categories c WHERE c.category_name = p_categoria) THEN
    RAISE EXCEPTION 'no existeix' USING ERRCODE = 'no_data_found'; END IF;
  RETURN QUERY SELECT p.product_name, p.unit_price::numeric, p.units_in_stock::integer FROM products p
    JOIN categories c ON c.category_id = p.category_id WHERE c.category_name = p_categoria
    AND p.discontinued = 0 AND p.unit_price > p_preu_minim;
END $$;
```


### 4. Crea la funció `resum_client(p_customer_id varchar, OUT num_comandes integer, OUT primera date, OUT darrera date, OUT facturat numeric)` que retorni, per a un client: quantes comandes ha fet, la data (`order_date`) de la primera i de la darrera, i el total facturat (suma de `unit_price * quantity * (1 - discount)` de totes les línies de les seves comandes, calculada amb `numeric` i arrodonida a 2 decimals al final). Un client sense comandes ha de retornar `0`, `NULL`, `NULL`, `0`. Si el client no existeix, excepció amb `ERRCODE = 'no_data_found'`.

Referència:
```sql
CREATE FUNCTION resum_client(p_customer_id varchar, OUT num_comandes integer, OUT primera date,
                             OUT darrera date, OUT facturat numeric) LANGUAGE plpgsql AS $$
BEGIN
  PERFORM 1 FROM customers WHERE customer_id = p_customer_id;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'El client % no existeix', p_customer_id USING ERRCODE = 'no_data_found';
  END IF;
  SELECT count(*), min(order_date), max(order_date) INTO num_comandes, primera, darrera
    FROM orders WHERE customer_id = p_customer_id;
  SELECT coalesce(round(sum(od.unit_price::numeric * od.quantity * (1 - od.discount::numeric)), 2), 0) INTO facturat
    FROM orders o JOIN order_details od ON od.order_id = o.order_id WHERE o.customer_id = p_customer_id;
END $$;
--@@TEST@@ SELECT * FROM resum_client('ALFKI')
--@@TEST@@ SELECT * FROM resum_client('FOLKO')
--@@TEST@@ SELECT * FROM resum_client('CENTC')
--@@TEST@@ SELECT * FROM resum_client('FISSA')
--@@TEST@@ SELECT num_comandes, facturat FROM resum_client('SAVEA')
--@@TEST@@ SELECT * FROM resum_client('XXXXX')
```

Alternativa — `LANGUAGE sql` no pot llançar excepcions: amb PL/pgSQL i un sol `SELECT` amb `LEFT JOIN` (ACCEPTADA):
```sql
CREATE OR REPLACE FUNCTION resum_client(p_customer_id varchar, OUT num_comandes integer, OUT primera date, OUT darrera date, OUT facturat numeric) AS $$
BEGIN
  IF NOT EXISTS (SELECT FROM customers WHERE customer_id = p_customer_id) THEN
    RAISE EXCEPTION USING ERRCODE = 'P0002', MESSAGE = 'client inexistent';
  END IF;
  SELECT count(DISTINCT o.order_id), min(o.order_date), max(o.order_date),
         round(coalesce(sum(d.unit_price::numeric * d.quantity * (1 - d.discount::numeric)), 0), 2)
    INTO num_comandes, primera, darrera, facturat
    FROM orders o LEFT JOIN order_details d ON d.order_id = o.order_id WHERE o.customer_id = p_customer_id;
END $$ LANGUAGE plpgsql;
```

Incorrecta — `count(*)` amb el `JOIN` de les línies: compta línies, no comandes (REBUTJADA: Test 1 (SELECT * FROM resum_client('ALFKI')): Result sets differ (comparing unordered)):
```sql
CREATE FUNCTION resum_client(p_customer_id varchar, OUT num_comandes integer, OUT primera date, OUT darrera date, OUT facturat numeric) LANGUAGE plpgsql AS $$
BEGIN
  IF NOT EXISTS (SELECT FROM customers WHERE customer_id = p_customer_id) THEN
    RAISE EXCEPTION 'no existeix' USING ERRCODE = 'no_data_found'; END IF;
  SELECT count(*), min(o.order_date), max(o.order_date), coalesce(round(sum(d.unit_price::numeric * d.quantity * (1 - d.discount::numeric)), 2), 0)
    INTO num_comandes, primera, darrera, facturat FROM orders o JOIN order_details d ON d.order_id = o.order_id
    WHERE o.customer_id = p_customer_id;
END $$;
```

Incorrecta — un client sense comandes retorna `facturat` a `NULL` (REBUTJADA: Test 4 (SELECT * FROM resum_client('FISSA')): Result sets differ (comparing unordered)):
```sql
CREATE FUNCTION resum_client(p_customer_id varchar, OUT num_comandes integer, OUT primera date, OUT darrera date, OUT facturat numeric) LANGUAGE plpgsql AS $$
BEGIN
  IF NOT EXISTS (SELECT FROM customers WHERE customer_id = p_customer_id) THEN
    RAISE EXCEPTION 'no existeix' USING ERRCODE = 'no_data_found'; END IF;
  SELECT count(*), min(order_date), max(order_date) INTO num_comandes, primera, darrera FROM orders WHERE customer_id = p_customer_id;
  SELECT round(sum(d.unit_price::numeric * d.quantity * (1 - d.discount::numeric)), 2) INTO facturat
    FROM orders o JOIN order_details d ON d.order_id = o.order_id WHERE o.customer_id = p_customer_id;
END $$;
```

Incorrecta — no comprova que el client existeixi (REBUTJADA: Test 6 (SELECT * FROM resum_client('XXXXX')): yours returns rows, the expected one gives an error (SQLSTATE P0002 no_data_found)):
```sql
CREATE FUNCTION resum_client(p_customer_id varchar, OUT num_comandes integer, OUT primera date, OUT darrera date, OUT facturat numeric) LANGUAGE plpgsql AS $$
BEGIN
  SELECT count(*), min(order_date), max(order_date) INTO num_comandes, primera, darrera FROM orders WHERE customer_id = p_customer_id;
  SELECT coalesce(round(sum(d.unit_price::numeric * d.quantity * (1 - d.discount::numeric)), 2), 0) INTO facturat
    FROM orders o JOIN order_details d ON d.order_id = o.order_id WHERE o.customer_id = p_customer_id;
END $$;
```


### 5. Crea la funció `dies_laborables(p_inici date, p_fi date) RETURNS integer` que compti quants dies laborables (de dilluns a divendres) hi ha **després** de `p_inici` i fins a `p_fi` **inclòs** (és a dir, els dies `d` amb `p_inici < d <= p_fi`). Si `p_inici` i `p_fi` són iguals, el resultat és 0. Si algun dels dos paràmetres és `NULL`, ha de retornar `NULL` (així una comanda pendent d'enviar no té valor). Si `p_fi` és anterior a `p_inici`, excepció amb `ERRCODE = 'invalid_parameter_value'`. Fes-ho amb un bucle (`WHILE` o `LOOP`) que recorri els dies, o amb `generate_series`. Servirà per saber quants dies laborables va trigar cada comanda a sortir: `dies_laborables(order_date, shipped_date)`.

Referència:
```sql
CREATE FUNCTION dies_laborables(p_inici date, p_fi date) RETURNS integer LANGUAGE plpgsql AS $$
DECLARE d date; n integer := 0;
BEGIN
  IF p_inici IS NULL OR p_fi IS NULL THEN RETURN NULL; END IF;
  IF p_fi < p_inici THEN
    RAISE EXCEPTION 'La data final és anterior a la inicial' USING ERRCODE = 'invalid_parameter_value';
  END IF;
  d := p_inici + 1;
  WHILE d <= p_fi LOOP
    IF extract(isodow FROM d) < 6 THEN n := n + 1; END IF;
    d := d + 1;
  END LOOP;
  RETURN n;
END $$;
--@@TEST@@ SELECT dies_laborables(DATE '1998-05-01', DATE '1998-05-01')
--@@TEST@@ SELECT dies_laborables(DATE '1998-05-01', DATE '1998-05-04')
--@@TEST@@ SELECT dies_laborables(DATE '1998-05-02', DATE '1998-05-09')
--@@TEST@@ SELECT dies_laborables(DATE '1998-05-01', NULL)
--@@TEST@@ SELECT order_id, dies_laborables(order_date, shipped_date) FROM orders WHERE customer_id IN ('ALFKI', 'BOLID', 'RICSU') ORDER BY order_id
--@@TEST@@ SELECT dies_laborables(DATE '1998-05-04', DATE '1998-05-01')
```

Alternativa — amb `generate_series` i `STRICT` (retorna `NULL` si algun paràmetre és `NULL`) (ACCEPTADA):
```sql
CREATE FUNCTION dies_laborables(p_inici date, p_fi date) RETURNS integer AS $$
BEGIN
  IF p_fi < p_inici THEN RAISE EXCEPTION 'dates' USING ERRCODE = '22023'; END IF;
  RETURN (SELECT count(*) FROM generate_series(p_inici + 1, p_fi, interval '1 day') AS g(d)
          WHERE extract(dow FROM g.d) NOT IN (0, 6));
END $$ LANGUAGE plpgsql STRICT;
```

Incorrecta — compta també el dia inicial (REBUTJADA: Test 1 (SELECT dies_laborables(DATE '1998-05-01', DATE '1998-05-01')): Result sets differ (comparing unordered)):
```sql
CREATE FUNCTION dies_laborables(p_inici date, p_fi date) RETURNS integer LANGUAGE plpgsql AS $$
DECLARE d date := p_inici; n integer := 0;
BEGIN
  IF p_inici IS NULL OR p_fi IS NULL THEN RETURN NULL; END IF;
  IF p_fi < p_inici THEN RAISE EXCEPTION 'dates' USING ERRCODE = 'invalid_parameter_value'; END IF;
  WHILE d <= p_fi LOOP IF extract(isodow FROM d) < 6 THEN n := n + 1; END IF; d := d + 1; END LOOP;
  RETURN n;
END $$;
```

Incorrecta — `extract(dow ...) < 6`: el diumenge (0) compta com a laborable i el dissabte no (REBUTJADA: Test 2 (SELECT dies_laborables(DATE '1998-05-01', DATE '1998-05-04')): Result sets differ (comparing unordered)):
```sql
CREATE FUNCTION dies_laborables(p_inici date, p_fi date) RETURNS integer LANGUAGE plpgsql AS $$
DECLARE d date; n integer := 0;
BEGIN
  IF p_inici IS NULL OR p_fi IS NULL THEN RETURN NULL; END IF;
  IF p_fi < p_inici THEN RAISE EXCEPTION 'dates' USING ERRCODE = 'invalid_parameter_value'; END IF;
  d := p_inici + 1;
  WHILE d <= p_fi LOOP IF extract(dow FROM d) < 6 THEN n := n + 1; END IF; d := d + 1; END LOOP;
  RETURN n;
END $$;
```

Incorrecta — dies naturals (`p_fi - p_inici`) en lloc de laborables (REBUTJADA: Test 2 (SELECT dies_laborables(DATE '1998-05-01', DATE '1998-05-04')): Result sets differ (comparing unordered)):
```sql
CREATE FUNCTION dies_laborables(p_inici date, p_fi date) RETURNS integer LANGUAGE plpgsql AS $$
BEGIN
  IF p_fi < p_inici THEN RAISE EXCEPTION 'dates' USING ERRCODE = 'invalid_parameter_value'; END IF;
  RETURN p_fi - p_inici;
END $$;
```

Incorrecta — sense validació: amb les dates girades retorna 0 (REBUTJADA: Test 6 (SELECT dies_laborables(DATE '1998-05-04', DATE '1998-05-01')): yours returns rows, the expected one gives an error (SQLSTATE 22023 invalid_parameter_value)):
```sql
CREATE FUNCTION dies_laborables(p_inici date, p_fi date) RETURNS integer LANGUAGE plpgsql AS $$
DECLARE d date; n integer := 0;
BEGIN
  IF p_inici IS NULL OR p_fi IS NULL THEN RETURN NULL; END IF;
  d := p_inici + 1;
  WHILE d <= p_fi LOOP IF extract(isodow FROM d) < 6 THEN n := n + 1; END IF; d := d + 1; END LOOP;
  RETURN n;
END $$;
```


### 6. Crea la funció `comissio_empleat(p_employee_id integer, p_any integer, p_percentatge numeric DEFAULT 5) RETURNS numeric` que calculi la comissió anual d'un comercial. Per a **cada mes** de l'any `p_any` (segons `order_date`) en què l'empleat té vendes, les vendes del mes són la suma de `unit_price * quantity * (1 - discount)` de les línies de les seves comandes, calculada amb `numeric`; la comissió del mes és el `p_percentatge` % d'aquestes vendes, més un **1 % extra** si les vendes del mes superen els 10000. Retorna la suma de les comissions de tots els mesos arrodonida a 2 decimals (no arrodoneixis res abans del final), o `0` si aquell any no té vendes. Validacions: si l'empleat no existeix, excepció amb `ERRCODE = 'no_data_found'`; si `p_percentatge` no està entre 0 i 20 (tots dos inclosos), excepció amb `ERRCODE = 'check_violation'`. Fes servir un `FOR ... IN SELECT ... LOOP` que recorri les vendes de cada mes.

Referència:
```sql
CREATE FUNCTION comissio_empleat(p_employee_id integer, p_any integer, p_percentatge numeric DEFAULT 5)
RETURNS numeric LANGUAGE plpgsql AS $$
DECLARE r record; total numeric := 0;
BEGIN
  IF NOT EXISTS (SELECT 1 FROM employees WHERE employee_id = p_employee_id) THEN
    RAISE EXCEPTION 'L''empleat % no existeix', p_employee_id USING ERRCODE = 'no_data_found';
  END IF;
  IF p_percentatge IS NULL OR p_percentatge < 0 OR p_percentatge > 20 THEN
    RAISE EXCEPTION 'Percentatge fora de rang: %', p_percentatge USING ERRCODE = 'check_violation';
  END IF;
  FOR r IN SELECT extract(month FROM o.order_date) AS mes, sum(od.unit_price::numeric * od.quantity * (1 - od.discount::numeric)) AS vendes
           FROM orders o JOIN order_details od ON od.order_id = o.order_id
           WHERE o.employee_id = p_employee_id AND extract(year FROM o.order_date) = p_any GROUP BY 1 LOOP
    total := total + r.vendes * p_percentatge / 100;
    IF r.vendes > 10000 THEN total := total + r.vendes * 0.01; END IF;
  END LOOP;
  RETURN round(total, 2);
END $$;
--@@TEST@@ SELECT comissio_empleat(3, 1997)
--@@TEST@@ SELECT comissio_empleat(4, 1997, 7.5)
--@@TEST@@ SELECT employee_id, comissio_empleat(employee_id, 1996, 3) FROM employees ORDER BY employee_id
--@@TEST@@ SELECT comissio_empleat(5, 1995)
--@@TEST@@ SELECT comissio_empleat(1, 1998, 20)
--@@TEST@@ SELECT comissio_empleat(1, 1998, 25)
--@@TEST@@ SELECT comissio_empleat(42, 1997)
```

Alternativa — sense bucle, amb una subconsulta per mesos i `CASE` (ACCEPTADA):
```sql
CREATE FUNCTION comissio_empleat(p_employee_id integer, p_any integer, p_percentatge numeric DEFAULT 5) RETURNS numeric AS $$
BEGIN
  IF p_percentatge NOT BETWEEN 0 AND 20 THEN RAISE EXCEPTION 'pct' USING ERRCODE = '23514'; END IF;
  PERFORM FROM employees WHERE employee_id = p_employee_id;
  IF NOT FOUND THEN RAISE EXCEPTION 'emp' USING ERRCODE = 'P0002'; END IF;
  RETURN coalesce((SELECT round(sum(v * (p_percentatge + CASE WHEN v > 10000 THEN 1 ELSE 0 END) / 100), 2)
    FROM (SELECT sum(unit_price::numeric * quantity * (1 - discount::numeric)) AS v FROM orders JOIN order_details USING (order_id)
          WHERE employee_id = p_employee_id AND date_part('year', order_date) = p_any
          GROUP BY date_trunc('month', order_date)) m), 0);
END $$ LANGUAGE plpgsql;
```

Incorrecta — aplica l'1 % extra a tot l'any si el total anual supera 10000 (REBUTJADA: Test 1 (SELECT comissio_empleat(3, 1997)): Result sets differ (comparing unordered)):
```sql
CREATE FUNCTION comissio_empleat(p_employee_id integer, p_any integer, p_percentatge numeric DEFAULT 5) RETURNS numeric LANGUAGE plpgsql AS $$
DECLARE v numeric;
BEGIN
  IF NOT EXISTS (SELECT 1 FROM employees WHERE employee_id = p_employee_id) THEN RAISE EXCEPTION 'emp' USING ERRCODE = 'no_data_found'; END IF;
  IF p_percentatge < 0 OR p_percentatge > 20 THEN RAISE EXCEPTION 'pct' USING ERRCODE = 'check_violation'; END IF;
  SELECT coalesce(sum(od.unit_price::numeric * od.quantity * (1 - od.discount::numeric)), 0) INTO v FROM orders o
    JOIN order_details od ON od.order_id = o.order_id WHERE o.employee_id = p_employee_id AND extract(year FROM o.order_date) = p_any;
  IF v > 10000 THEN RETURN round(v * (p_percentatge + 1) / 100, 2); END IF;
  RETURN round(v * p_percentatge / 100, 2);
END $$;
```

Incorrecta — arrodoneix la comissió de cada mes (REBUTJADA: Test 2 (SELECT comissio_empleat(4, 1997, 7.5)): Result sets differ (comparing unordered)):
```sql
CREATE FUNCTION comissio_empleat(p_employee_id integer, p_any integer, p_percentatge numeric DEFAULT 5) RETURNS numeric LANGUAGE plpgsql AS $$
DECLARE r record; total numeric := 0;
BEGIN
  IF NOT EXISTS (SELECT 1 FROM employees WHERE employee_id = p_employee_id) THEN RAISE EXCEPTION 'emp' USING ERRCODE = 'no_data_found'; END IF;
  IF p_percentatge < 0 OR p_percentatge > 20 THEN RAISE EXCEPTION 'pct' USING ERRCODE = 'check_violation'; END IF;
  FOR r IN SELECT sum(od.unit_price::numeric * od.quantity * (1 - od.discount::numeric)) AS v FROM orders o JOIN order_details od ON od.order_id = o.order_id
           WHERE o.employee_id = p_employee_id AND extract(year FROM o.order_date) = p_any GROUP BY extract(month FROM o.order_date) LOOP
    total := total + round(r.v * (p_percentatge + CASE WHEN r.v > 10000 THEN 1 ELSE 0 END) / 100, 2);
  END LOOP;
  RETURN round(total, 2);
END $$;
```

Incorrecta — valida el percentatge amb `RAISE EXCEPTION` sense `ERRCODE` (REBUTJADA: Test 6 (SELECT comissio_empleat(1, 1998, 25)): yours gives an error (SQLSTATE P0001 raise_exception), the expected one gives an error (SQLSTATE 23514 check_violation)):
```sql
CREATE FUNCTION comissio_empleat(p_employee_id integer, p_any integer, p_percentatge numeric DEFAULT 5) RETURNS numeric LANGUAGE plpgsql AS $$
DECLARE r record; total numeric := 0;
BEGIN
  IF NOT EXISTS (SELECT 1 FROM employees WHERE employee_id = p_employee_id) THEN RAISE EXCEPTION 'emp' USING ERRCODE = 'no_data_found'; END IF;
  IF p_percentatge < 0 OR p_percentatge > 20 THEN RAISE EXCEPTION 'pct'; END IF;
  FOR r IN SELECT sum(od.unit_price::numeric * od.quantity * (1 - od.discount::numeric)) AS v FROM orders o JOIN order_details od ON od.order_id = o.order_id
           WHERE o.employee_id = p_employee_id AND extract(year FROM o.order_date) = p_any GROUP BY extract(month FROM o.order_date) LOOP
    total := total + r.v * (p_percentatge + CASE WHEN r.v > 10000 THEN 1 ELSE 0 END) / 100;
  END LOOP;
  RETURN round(total, 2);
END $$;
```

Incorrecta — sense `DEFAULT`: la crida amb dos arguments no troba la funció (REBUTJADA: Test 1 (SELECT comissio_empleat(3, 1997)): yours gives an error (SQLSTATE 42883 undefined_function), the expected one returns rows):
```sql
CREATE FUNCTION comissio_empleat(p_employee_id integer, p_any integer, p_percentatge numeric) RETURNS numeric LANGUAGE plpgsql AS $$
DECLARE r record; total numeric := 0;
BEGIN
  IF NOT EXISTS (SELECT 1 FROM employees WHERE employee_id = p_employee_id) THEN RAISE EXCEPTION 'emp' USING ERRCODE = 'no_data_found'; END IF;
  IF p_percentatge < 0 OR p_percentatge > 20 THEN RAISE EXCEPTION 'pct' USING ERRCODE = 'check_violation'; END IF;
  FOR r IN SELECT sum(od.unit_price::numeric * od.quantity * (1 - od.discount::numeric)) AS v FROM orders o JOIN order_details od ON od.order_id = o.order_id
           WHERE o.employee_id = p_employee_id AND extract(year FROM o.order_date) = p_any GROUP BY extract(month FROM o.order_date) LOOP
    total := total + r.v * (p_percentatge + CASE WHEN r.v > 10000 THEN 1 ELSE 0 END) / 100;
  END LOOP;
  RETURN round(total, 2);
END $$;
```


## Northwind — Procediments (pgproc)


### 1. Crea el procediment `alta_transportista(p_nom varchar, p_telefon varchar)` que doni d'alta un transportista a `shippers` amb `shipper_id` = el màxim actual + 1, `company_name` = `p_nom` **sense espais al principi ni al final** (`trim`) i `phone` = `p_telefon`. Validacions: si `p_nom` és `NULL` o només té espais, excepció amb `ERRCODE = 'check_violation'`; si ja hi ha un transportista amb el mateix nom sense distingir majúscules i minúscules (`'ups'` és el mateix que `'UPS'`), excepció amb `ERRCODE = 'unique_violation'`.

Referència:
```sql
CREATE PROCEDURE alta_transportista(p_nom varchar, p_telefon varchar) LANGUAGE plpgsql AS $$
BEGIN
  IF p_nom IS NULL OR trim(p_nom) = '' THEN
    RAISE EXCEPTION 'Cal indicar el nom' USING ERRCODE = 'check_violation';
  END IF;
  IF EXISTS (SELECT 1 FROM shippers WHERE lower(company_name) = lower(trim(p_nom))) THEN
    RAISE EXCEPTION 'Ja existeix el transportista %', trim(p_nom) USING ERRCODE = 'unique_violation';
  END IF;
  INSERT INTO shippers (shipper_id, company_name, phone)
  SELECT coalesce(max(shipper_id), 0) + 1, trim(p_nom), p_telefon FROM shippers;
END $$;
--@@TEST@@ CALL alta_transportista('  Seur  ', '93 555 12 34')
--@@TEST@@ CALL alta_transportista('ups', NULL)
--@@TEST@@ CALL alta_transportista('   ', '000')
--@@TEST@@ CALL alta_transportista(NULL, '000')
--@@TEST@@ CALL alta_transportista('Correos Express', NULL)
--@@TEST@@ CALL alta_transportista('seur', NULL)
--@@TEST@@ SELECT * FROM shippers ORDER BY shipper_id
```

Alternativa (ACCEPTADA):
```sql
CREATE OR REPLACE PROCEDURE alta_transportista(p_nom varchar, p_telefon varchar) AS $$
DECLARE v_nom varchar := btrim(p_nom); v_id smallint;
BEGIN
  IF coalesce(v_nom, '') = '' THEN RAISE EXCEPTION USING ERRCODE = '23514', MESSAGE = 'nom buit'; END IF;
  PERFORM FROM shippers WHERE company_name ILIKE v_nom;
  IF FOUND THEN RAISE EXCEPTION USING ERRCODE = '23505', MESSAGE = 'duplicat'; END IF;
  SELECT max(shipper_id) + 1 INTO v_id FROM shippers;
  INSERT INTO shippers VALUES (v_id, v_nom, p_telefon);
END $$ LANGUAGE plpgsql;
```

Incorrecta — no fa `trim` del nom (REBUTJADA: Test 6 (CALL alta_transportista('seur', NULL)): yours runs, the expected one gives an error (SQLSTATE 23505 unique_violation)):
```sql
CREATE PROCEDURE alta_transportista(p_nom varchar, p_telefon varchar) LANGUAGE plpgsql AS $$
BEGIN
  IF p_nom IS NULL OR trim(p_nom) = '' THEN RAISE EXCEPTION 'buit' USING ERRCODE = 'check_violation'; END IF;
  IF EXISTS (SELECT 1 FROM shippers WHERE lower(company_name) = lower(trim(p_nom))) THEN RAISE EXCEPTION 'dup' USING ERRCODE = 'unique_violation'; END IF;
  INSERT INTO shippers SELECT max(shipper_id) + 1, p_nom, p_telefon FROM shippers;
END $$;
```

Incorrecta — comprova el duplicat distingint majúscules (`'ups'` s'insereix) (REBUTJADA: Test 2 (CALL alta_transportista('ups', NULL)): yours runs, the expected one gives an error (SQLSTATE 23505 unique_violation)):
```sql
CREATE PROCEDURE alta_transportista(p_nom varchar, p_telefon varchar) LANGUAGE plpgsql AS $$
BEGIN
  IF p_nom IS NULL OR trim(p_nom) = '' THEN RAISE EXCEPTION 'buit' USING ERRCODE = 'check_violation'; END IF;
  IF EXISTS (SELECT 1 FROM shippers WHERE company_name = trim(p_nom)) THEN RAISE EXCEPTION 'dup' USING ERRCODE = 'unique_violation'; END IF;
  INSERT INTO shippers SELECT max(shipper_id) + 1, trim(p_nom), p_telefon FROM shippers;
END $$;
```

Incorrecta — `p_nom = ''` no detecta un nom fet només d'espais ni `NULL` (REBUTJADA: Test 3 (CALL alta_transportista(' ', '000')): yours runs, the expected one gives an error (SQLSTATE 23514 check_violation)):
```sql
CREATE PROCEDURE alta_transportista(p_nom varchar, p_telefon varchar) LANGUAGE plpgsql AS $$
BEGIN
  IF p_nom = '' THEN RAISE EXCEPTION 'buit' USING ERRCODE = 'check_violation'; END IF;
  IF EXISTS (SELECT 1 FROM shippers WHERE lower(company_name) = lower(trim(p_nom))) THEN RAISE EXCEPTION 'dup' USING ERRCODE = 'unique_violation'; END IF;
  INSERT INTO shippers SELECT max(shipper_id) + 1, trim(p_nom), p_telefon FROM shippers;
END $$;
```


### 2. Crea el procediment `actualitzar_preus(p_categoria varchar, p_percentatge numeric)` que apugi (o abaixi, si és negatiu) un `p_percentatge` % el preu (`unit_price`) dels productes **actius** (`discontinued = 0`) de la categoria anomenada `p_categoria`. El preu nou s'ha d'arrodonir a 2 decimals: `round(unit_price::numeric * (1 + p_percentatge / 100), 2)`. Validacions: si `p_percentatge` és `NULL` o no està entre -50 i 100 (tots dos inclosos), excepció amb `ERRCODE = 'check_violation'`; si la categoria no existeix, excepció amb `ERRCODE = 'no_data_found'`.

Referència:
```sql
CREATE PROCEDURE actualitzar_preus(p_categoria varchar, p_percentatge numeric) LANGUAGE plpgsql AS $$
DECLARE v_cat smallint;
BEGIN
  IF p_percentatge IS NULL OR p_percentatge NOT BETWEEN -50 AND 100 THEN
    RAISE EXCEPTION 'Percentatge no vàlid: %', p_percentatge USING ERRCODE = 'check_violation';
  END IF;
  SELECT category_id INTO v_cat FROM categories WHERE category_name = p_categoria;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'La categoria % no existeix', p_categoria USING ERRCODE = 'no_data_found';
  END IF;
  UPDATE products SET unit_price = round(unit_price::numeric * (1 + p_percentatge / 100), 2)
   WHERE category_id = v_cat AND discontinued = 0;
END $$;
--@@TEST@@ CALL actualitzar_preus('Seafood', 10)
--@@TEST@@ CALL actualitzar_preus('Beverages', -7.5)
--@@TEST@@ CALL actualitzar_preus('Pizza', 5)
--@@TEST@@ CALL actualitzar_preus('Produce', 150)
--@@TEST@@ CALL actualitzar_preus('Produce', NULL)
--@@TEST@@ CALL actualitzar_preus('Meat/Poultry', -50)
--@@TEST@@ SELECT product_id, unit_price FROM products WHERE category_id IN (1, 6, 8) ORDER BY product_id
```

Alternativa — amb `UPDATE ... FROM` i `FOUND` per detectar la categoria (no funcionaria si la categoria existís però no tingués productes actius; a Northwind no passa) (ACCEPTADA):
```sql
CREATE PROCEDURE actualitzar_preus(p_categoria varchar, p_percentatge numeric) AS $$
BEGIN
  IF NOT (p_percentatge BETWEEN -50 AND 100) OR p_percentatge IS NULL THEN RAISE EXCEPTION 'pct' USING ERRCODE = '23514'; END IF;
  UPDATE products p SET unit_price = round(p.unit_price::numeric * (1 + p_percentatge / 100), 2) FROM categories c
   WHERE c.category_id = p.category_id AND c.category_name = p_categoria AND p.discontinued = 0;
  IF NOT FOUND THEN RAISE EXCEPTION 'cat' USING ERRCODE = 'P0002'; END IF;
END $$ LANGUAGE plpgsql;
```

Incorrecta — també canvia els productes descatalogats (REBUTJADA: Test 7 (SELECT product_id, unit_price FROM products WHERE categor...): Result sets differ (comparing unordered)):
```sql
CREATE PROCEDURE actualitzar_preus(p_categoria varchar, p_percentatge numeric) LANGUAGE plpgsql AS $$
BEGIN
  IF p_percentatge IS NULL OR p_percentatge NOT BETWEEN -50 AND 100 THEN RAISE EXCEPTION 'pct' USING ERRCODE = 'check_violation'; END IF;
  IF NOT EXISTS (SELECT 1 FROM categories WHERE category_name = p_categoria) THEN RAISE EXCEPTION 'cat' USING ERRCODE = 'no_data_found'; END IF;
  UPDATE products SET unit_price = round(unit_price::numeric * (1 + p_percentatge / 100), 2)
   WHERE category_id = (SELECT category_id FROM categories WHERE category_name = p_categoria);
END $$;
```

Incorrecta — no arrodoneix el preu (REBUTJADA: Test 7 (SELECT product_id, unit_price FROM products WHERE categor...): Result sets differ (comparing unordered)):
```sql
CREATE PROCEDURE actualitzar_preus(p_categoria varchar, p_percentatge numeric) LANGUAGE plpgsql AS $$
BEGIN
  IF p_percentatge IS NULL OR p_percentatge NOT BETWEEN -50 AND 100 THEN RAISE EXCEPTION 'pct' USING ERRCODE = 'check_violation'; END IF;
  IF NOT EXISTS (SELECT 1 FROM categories WHERE category_name = p_categoria) THEN RAISE EXCEPTION 'cat' USING ERRCODE = 'no_data_found'; END IF;
  UPDATE products SET unit_price = unit_price * (1 + p_percentatge / 100)
   WHERE category_id = (SELECT category_id FROM categories WHERE category_name = p_categoria) AND discontinued = 0;
END $$;
```

Incorrecta — no valida el `NULL` (`NOT BETWEEN` amb `NULL` és `NULL`, no cert): no dona error (REBUTJADA: Test 5 (CALL actualitzar_preus('Produce', NULL)): yours runs, the expected one gives an error (SQLSTATE 23514 check_violation)):
```sql
CREATE PROCEDURE actualitzar_preus(p_categoria varchar, p_percentatge numeric) LANGUAGE plpgsql AS $$
BEGIN
  IF p_percentatge NOT BETWEEN -50 AND 100 THEN RAISE EXCEPTION 'pct' USING ERRCODE = 'check_violation'; END IF;
  IF NOT EXISTS (SELECT 1 FROM categories WHERE category_name = p_categoria) THEN RAISE EXCEPTION 'cat' USING ERRCODE = 'no_data_found'; END IF;
  UPDATE products SET unit_price = round(unit_price::numeric * (1 + p_percentatge / 100), 2)
   WHERE category_id = (SELECT category_id FROM categories WHERE category_name = p_categoria) AND discontinued = 0;
END $$;
```


### 3. Crea el procediment `rebre_estoc(p_product_id integer, INOUT p_unitats integer)` que registri l'arribada de `p_unitats` unitats d'un producte: suma `p_unitats` a `units_in_stock` i les resta de `units_on_order` (sense que `units_on_order` quedi per sota de 0). En acabar, el paràmetre `INOUT` `p_unitats` ha de contenir el **nou** `units_in_stock` del producte (és el que retorna el `CALL`). Validacions, en aquest ordre: si `p_unitats` és `NULL` o no és positiu, excepció amb `ERRCODE = 'check_violation'`; si el producte no existeix, `ERRCODE = 'no_data_found'`; si el producte està descatalogat (`discontinued = 1`), excepció sense `ERRCODE` (el codi per defecte, `raise_exception`).

Referència:
```sql
CREATE PROCEDURE rebre_estoc(p_product_id integer, INOUT p_unitats integer) LANGUAGE plpgsql AS $$
DECLARE v_desc integer;
BEGIN
  IF p_unitats IS NULL OR p_unitats <= 0 THEN
    RAISE EXCEPTION 'Les unitats han de ser positives' USING ERRCODE = 'check_violation';
  END IF;
  SELECT discontinued INTO v_desc FROM products WHERE product_id = p_product_id;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'El producte % no existeix', p_product_id USING ERRCODE = 'no_data_found';
  END IF;
  IF v_desc = 1 THEN
    RAISE EXCEPTION 'El producte % està descatalogat', p_product_id;
  END IF;
  UPDATE products SET units_in_stock = units_in_stock + p_unitats,
                      units_on_order = greatest(units_on_order - p_unitats, 0)
   WHERE product_id = p_product_id
   RETURNING units_in_stock INTO p_unitats;
END $$;
--@@TEST@@ CALL rebre_estoc(3, 30)
--@@TEST@@ CALL rebre_estoc(3, 50)
--@@TEST@@ SELECT units_in_stock, units_on_order FROM products WHERE product_id = 3
--@@TEST@@ CALL rebre_estoc(31, 70)
--@@TEST@@ CALL rebre_estoc(1, 10)
--@@TEST@@ CALL rebre_estoc(3, 0)
--@@TEST@@ CALL rebre_estoc(3, NULL)
--@@TEST@@ CALL rebre_estoc(500, 5)
```

Alternativa (ACCEPTADA):
```sql
CREATE PROCEDURE rebre_estoc(p_product_id integer, INOUT p_unitats integer) AS $$
DECLARE p products%ROWTYPE;
BEGIN
  IF coalesce(p_unitats, 0) <= 0 THEN RAISE EXCEPTION 'unitats' USING ERRCODE = '23514'; END IF;
  SELECT * INTO p FROM products WHERE product_id = p_product_id;
  IF p.product_id IS NULL THEN RAISE EXCEPTION 'no existeix' USING ERRCODE = 'P0002'; END IF;
  IF p.discontinued = 1 THEN RAISE EXCEPTION 'descatalogat' USING ERRCODE = 'P0001'; END IF;
  UPDATE products SET units_in_stock = p.units_in_stock + p_unitats,
    units_on_order = CASE WHEN p.units_on_order > p_unitats THEN p.units_on_order - p_unitats ELSE 0 END
   WHERE product_id = p_product_id;
  p_unitats := p.units_in_stock + p_unitats;
END $$ LANGUAGE plpgsql;
```

Incorrecta — `units_on_order` pot quedar negatiu (REBUTJADA: Test 3 (SELECT units_in_stock, units_on_order FROM products WHERE...): Result sets differ (comparing unordered)):
```sql
CREATE PROCEDURE rebre_estoc(p_product_id integer, INOUT p_unitats integer) LANGUAGE plpgsql AS $$
DECLARE v integer;
BEGIN
  IF p_unitats IS NULL OR p_unitats <= 0 THEN RAISE EXCEPTION 'u' USING ERRCODE = 'check_violation'; END IF;
  SELECT discontinued INTO v FROM products WHERE product_id = p_product_id;
  IF NOT FOUND THEN RAISE EXCEPTION 'no' USING ERRCODE = 'no_data_found'; END IF;
  IF v = 1 THEN RAISE EXCEPTION 'desc'; END IF;
  UPDATE products SET units_in_stock = units_in_stock + p_unitats, units_on_order = units_on_order - p_unitats
   WHERE product_id = p_product_id RETURNING units_in_stock INTO p_unitats;
END $$;
```

Incorrecta — no assigna el paràmetre `INOUT` (el `CALL` retorna les unitats rebudes) (REBUTJADA: Test 1 (CALL rebre_estoc(3, 30)): Result sets differ (comparing unordered)):
```sql
CREATE PROCEDURE rebre_estoc(p_product_id integer, INOUT p_unitats integer) LANGUAGE plpgsql AS $$
DECLARE v integer;
BEGIN
  IF p_unitats IS NULL OR p_unitats <= 0 THEN RAISE EXCEPTION 'u' USING ERRCODE = 'check_violation'; END IF;
  SELECT discontinued INTO v FROM products WHERE product_id = p_product_id;
  IF NOT FOUND THEN RAISE EXCEPTION 'no' USING ERRCODE = 'no_data_found'; END IF;
  IF v = 1 THEN RAISE EXCEPTION 'desc'; END IF;
  UPDATE products SET units_in_stock = units_in_stock + p_unitats, units_on_order = greatest(units_on_order - p_unitats, 0)
   WHERE product_id = p_product_id;
END $$;
```

Incorrecta — no comprova si el producte està descatalogat (REBUTJADA: Test 5 (CALL rebre_estoc(1, 10)): yours returns rows, the expected one gives an error (SQLSTATE P0001 raise_exception)):
```sql
CREATE PROCEDURE rebre_estoc(p_product_id integer, INOUT p_unitats integer) LANGUAGE plpgsql AS $$
BEGIN
  IF p_unitats IS NULL OR p_unitats <= 0 THEN RAISE EXCEPTION 'u' USING ERRCODE = 'check_violation'; END IF;
  UPDATE products SET units_in_stock = units_in_stock + p_unitats, units_on_order = greatest(units_on_order - p_unitats, 0)
   WHERE product_id = p_product_id RETURNING units_in_stock INTO p_unitats;
  IF NOT FOUND THEN RAISE EXCEPTION 'no' USING ERRCODE = 'no_data_found'; END IF;
END $$;
```


### 4. Crea el procediment `enviar_pendents(p_transportista varchar, p_data date, INOUT p_enviades integer DEFAULT NULL)` que marqui com a enviades totes les comandes pendents (`shipped_date` a `NULL`) fetes fins a `p_data` inclosa (`order_date <= p_data`): `shipped_date` = `p_data` i `ship_via` = l'identificador del transportista anomenat `p_transportista` (`shippers.company_name`). Al paràmetre `p_enviades` hi ha de deixar quantes comandes ha actualitzat (fes servir `GET DIAGNOSTICS ... = ROW_COUNT`); si no n'hi ha cap, `0`, sense error. Validacions: si `p_data` és `NULL`, excepció amb `ERRCODE = 'null_value_not_allowed'`; si el transportista no existeix, `ERRCODE = 'no_data_found'`.

Referència:
```sql
CREATE PROCEDURE enviar_pendents(p_transportista varchar, p_data date, INOUT p_enviades integer DEFAULT NULL)
LANGUAGE plpgsql AS $$
DECLARE v_ship smallint;
BEGIN
  IF p_data IS NULL THEN
    RAISE EXCEPTION 'Cal indicar la data' USING ERRCODE = 'null_value_not_allowed';
  END IF;
  SELECT shipper_id INTO v_ship FROM shippers WHERE company_name = p_transportista;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'El transportista % no existeix', p_transportista USING ERRCODE = 'no_data_found';
  END IF;
  UPDATE orders SET shipped_date = p_data, ship_via = v_ship
   WHERE shipped_date IS NULL AND order_date <= p_data;
  GET DIAGNOSTICS p_enviades = ROW_COUNT;
END $$;
--@@TEST@@ CALL enviar_pendents('Speedy Express', DATE '1998-04-30', NULL)
--@@TEST@@ CALL enviar_pendents('Speedy Express', DATE '1998-04-30', NULL)
--@@TEST@@ CALL enviar_pendents('UPS', DATE '1998-05-05', NULL)
--@@TEST@@ CALL enviar_pendents('Seur', DATE '1998-05-10', NULL)
--@@TEST@@ CALL enviar_pendents('UPS', NULL, NULL)
--@@TEST@@ SELECT order_id, shipped_date, ship_via FROM orders WHERE order_id >= 11000 ORDER BY order_id
```

Alternativa — amb `FOR ... LOOP` comptant una a una (ACCEPTADA):
```sql
CREATE PROCEDURE enviar_pendents(p_transportista varchar, p_data date, INOUT p_enviades integer DEFAULT NULL) AS $$
DECLARE r record; v smallint;
BEGIN
  IF p_data IS NULL THEN RAISE EXCEPTION 'data' USING ERRCODE = '22004'; END IF;
  v := (SELECT shipper_id FROM shippers WHERE company_name = p_transportista);
  IF v IS NULL THEN RAISE EXCEPTION 'transp' USING ERRCODE = 'P0002'; END IF;
  p_enviades := 0;
  FOR r IN SELECT order_id FROM orders WHERE shipped_date IS NULL AND order_date <= p_data LOOP
    UPDATE orders SET shipped_date = p_data, ship_via = v WHERE order_id = r.order_id;
    p_enviades := p_enviades + 1;
  END LOOP;
END $$ LANGUAGE plpgsql;
```

Incorrecta — `< p_data`: les comandes del mateix dia no s'envien (REBUTJADA: Test 1 (CALL enviar_pendents('Speedy Express', DATE '1998-04-30',...): Result sets differ (comparing unordered)):
```sql
CREATE PROCEDURE enviar_pendents(p_transportista varchar, p_data date, INOUT p_enviades integer DEFAULT NULL) LANGUAGE plpgsql AS $$
DECLARE v smallint;
BEGIN
  IF p_data IS NULL THEN RAISE EXCEPTION 'd' USING ERRCODE = 'null_value_not_allowed'; END IF;
  SELECT shipper_id INTO v FROM shippers WHERE company_name = p_transportista;
  IF NOT FOUND THEN RAISE EXCEPTION 't' USING ERRCODE = 'no_data_found'; END IF;
  UPDATE orders SET shipped_date = p_data, ship_via = v WHERE shipped_date IS NULL AND order_date < p_data;
  GET DIAGNOSTICS p_enviades = ROW_COUNT;
END $$;
```

Incorrecta — no canvia `ship_via` (REBUTJADA: Test 6 (SELECT order_id, shipped_date, ship_via FROM orders WHERE...): Result sets differ (comparing unordered)):
```sql
CREATE PROCEDURE enviar_pendents(p_transportista varchar, p_data date, INOUT p_enviades integer DEFAULT NULL) LANGUAGE plpgsql AS $$
BEGIN
  IF p_data IS NULL THEN RAISE EXCEPTION 'd' USING ERRCODE = 'null_value_not_allowed'; END IF;
  PERFORM 1 FROM shippers WHERE company_name = p_transportista;
  IF NOT FOUND THEN RAISE EXCEPTION 't' USING ERRCODE = 'no_data_found'; END IF;
  UPDATE orders SET shipped_date = p_data WHERE shipped_date IS NULL AND order_date <= p_data;
  GET DIAGNOSTICS p_enviades = ROW_COUNT;
END $$;
```

Incorrecta — fa servir `FOUND` com si fos el nombre de files (dona 1 o 0) (REBUTJADA: Test 1 (CALL enviar_pendents('Speedy Express', DATE '1998-04-30',...): Result sets differ (comparing unordered)):
```sql
CREATE PROCEDURE enviar_pendents(p_transportista varchar, p_data date, INOUT p_enviades integer DEFAULT NULL) LANGUAGE plpgsql AS $$
DECLARE v smallint;
BEGIN
  IF p_data IS NULL THEN RAISE EXCEPTION 'd' USING ERRCODE = 'null_value_not_allowed'; END IF;
  SELECT shipper_id INTO v FROM shippers WHERE company_name = p_transportista;
  IF NOT FOUND THEN RAISE EXCEPTION 't' USING ERRCODE = 'no_data_found'; END IF;
  UPDATE orders SET shipped_date = p_data, ship_via = v WHERE shipped_date IS NULL AND order_date <= p_data;
  p_enviades := FOUND::integer;
END $$;
```


### 5. Quan un comercial deixa l'empresa, un altre n'assumeix la feina. Crea el procediment `traspassar_cartera(p_de integer, p_a integer, INOUT p_comandes integer DEFAULT NULL)` que passi de l'empleat `p_de` a l'empleat `p_a`:
1. les comandes **pendents** d'enviar (`shipped_date` a `NULL`) de `p_de` (`orders.employee_id`); el nombre de comandes traspassades es retorna a `p_comandes`;
2. els territoris de `p_de` a `employee_territories` (si `p_a` ja tenia algun d'aquests territoris, simplement s'esborra la fila de `p_de`);
3. els empleats que depenen directament de `p_de` (`reports_to = p_de`) passen a dependre de `p_a`; però si el mateix `p_a` depenia de `p_de`, `p_a` passa a dependre del cap de `p_de` (el `reports_to` de `p_de`, que pot ser `NULL`).
Validacions, en aquest ordre: si `p_de = p_a`, excepció amb `ERRCODE = 'check_violation'`; si algun dels dos empleats no existeix, `ERRCODE = 'no_data_found'`. Fes servir `FOUND` o `GET DIAGNOSTICS` on calgui.

Referència:
```sql
CREATE PROCEDURE traspassar_cartera(p_de integer, p_a integer, INOUT p_comandes integer DEFAULT NULL)
LANGUAGE plpgsql AS $$
DECLARE v_cap smallint;
BEGIN
  IF p_de = p_a THEN
    RAISE EXCEPTION 'Els dos empleats són el mateix' USING ERRCODE = 'check_violation';
  END IF;
  SELECT reports_to INTO v_cap FROM employees WHERE employee_id = p_de;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'L''empleat % no existeix', p_de USING ERRCODE = 'no_data_found';
  END IF;
  PERFORM 1 FROM employees WHERE employee_id = p_a;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'L''empleat % no existeix', p_a USING ERRCODE = 'no_data_found';
  END IF;
  UPDATE orders SET employee_id = p_a WHERE employee_id = p_de AND shipped_date IS NULL;
  GET DIAGNOSTICS p_comandes = ROW_COUNT;
  DELETE FROM employee_territories et WHERE et.employee_id = p_de
     AND EXISTS (SELECT 1 FROM employee_territories x WHERE x.employee_id = p_a AND x.territory_id = et.territory_id);
  UPDATE employee_territories SET employee_id = p_a WHERE employee_id = p_de;
  UPDATE employees SET reports_to = v_cap WHERE employee_id = p_a AND reports_to = p_de;
  UPDATE employees SET reports_to = p_a WHERE reports_to = p_de;
END $$;
--@@TEST@@ INSERT INTO employee_territories VALUES (3, '20852')
--@@TEST@@ CALL traspassar_cartera(4, 3, NULL)
--@@TEST@@ CALL traspassar_cartera(5, 6, NULL)
--@@TEST@@ CALL traspassar_cartera(2, 8, NULL)
--@@TEST@@ SELECT employee_id, reports_to FROM employees ORDER BY employee_id
--@@TEST@@ SELECT * FROM employee_territories WHERE employee_id IN (3, 4, 5, 6) ORDER BY 1, 2
--@@TEST@@ CALL traspassar_cartera(7, 7, NULL)
--@@TEST@@ CALL traspassar_cartera(7, 99, NULL)
--@@TEST@@ CALL traspassar_cartera(99, 7, NULL)
```

Alternativa — en un altre ordre, i per als territoris `INSERT ... ON CONFLICT DO NOTHING` + `DELETE` (ACCEPTADA):
```sql
CREATE PROCEDURE traspassar_cartera(p_de integer, p_a integer, INOUT p_comandes integer DEFAULT NULL) AS $$
DECLARE e_de employees%ROWTYPE;
BEGIN
  IF p_de = p_a THEN RAISE EXCEPTION 'iguals' USING ERRCODE = '23514'; END IF;
  SELECT * INTO e_de FROM employees WHERE employee_id = p_de;
  IF NOT FOUND OR NOT EXISTS (SELECT FROM employees WHERE employee_id = p_a) THEN
    RAISE EXCEPTION 'no existeix' USING ERRCODE = 'P0002'; END IF;
  UPDATE employees SET reports_to = CASE WHEN employee_id = p_a THEN e_de.reports_to ELSE p_a END WHERE reports_to = p_de;
  INSERT INTO employee_territories SELECT p_a, territory_id FROM employee_territories WHERE employee_id = p_de ON CONFLICT DO NOTHING;
  DELETE FROM employee_territories WHERE employee_id = p_de;
  UPDATE orders SET employee_id = p_a WHERE employee_id = p_de AND shipped_date IS NULL;
  GET DIAGNOSTICS p_comandes = ROW_COUNT;
END $$ LANGUAGE plpgsql;
```

Incorrecta — traspassa totes les comandes, també les ja enviades (REBUTJADA: Test 2 (CALL traspassar_cartera(4, 3, NULL)): Result sets differ (comparing unordered)):
```sql
CREATE PROCEDURE traspassar_cartera(p_de integer, p_a integer, INOUT p_comandes integer DEFAULT NULL) LANGUAGE plpgsql AS $$
DECLARE v_cap smallint;
BEGIN
  IF p_de = p_a THEN RAISE EXCEPTION 'i' USING ERRCODE = 'check_violation'; END IF;
  SELECT reports_to INTO v_cap FROM employees WHERE employee_id = p_de;
  IF NOT FOUND OR NOT EXISTS (SELECT 1 FROM employees WHERE employee_id = p_a) THEN RAISE EXCEPTION 'n' USING ERRCODE = 'no_data_found'; END IF;
  UPDATE orders SET employee_id = p_a WHERE employee_id = p_de;
  GET DIAGNOSTICS p_comandes = ROW_COUNT;
  DELETE FROM employee_territories et WHERE et.employee_id = p_de AND EXISTS (SELECT 1 FROM employee_territories x WHERE x.employee_id = p_a AND x.territory_id = et.territory_id);
  UPDATE employee_territories SET employee_id = p_a WHERE employee_id = p_de;
  UPDATE employees SET reports_to = v_cap WHERE employee_id = p_a AND reports_to = p_de;
  UPDATE employees SET reports_to = p_a WHERE reports_to = p_de;
END $$;
```

Incorrecta — no té en compte el territori repetit: l'`UPDATE` falla per clau primària duplicada (REBUTJADA: Test 2 (CALL traspassar_cartera(4, 3, NULL)): yours gives an error (SQLSTATE 23505 unique_violation), the expected one returns rows):
```sql
CREATE PROCEDURE traspassar_cartera(p_de integer, p_a integer, INOUT p_comandes integer DEFAULT NULL) LANGUAGE plpgsql AS $$
DECLARE v_cap smallint;
BEGIN
  IF p_de = p_a THEN RAISE EXCEPTION 'i' USING ERRCODE = 'check_violation'; END IF;
  SELECT reports_to INTO v_cap FROM employees WHERE employee_id = p_de;
  IF NOT FOUND OR NOT EXISTS (SELECT 1 FROM employees WHERE employee_id = p_a) THEN RAISE EXCEPTION 'n' USING ERRCODE = 'no_data_found'; END IF;
  UPDATE orders SET employee_id = p_a WHERE employee_id = p_de AND shipped_date IS NULL;
  GET DIAGNOSTICS p_comandes = ROW_COUNT;
  UPDATE employee_territories SET employee_id = p_a WHERE employee_id = p_de;
  UPDATE employees SET reports_to = v_cap WHERE employee_id = p_a AND reports_to = p_de;
  UPDATE employees SET reports_to = p_a WHERE reports_to = p_de;
END $$;
```

Incorrecta — ordre equivocat: primer reassigna tots els subordinats i `p_a` acaba depenent de si mateix (REBUTJADA: Test 5 (SELECT employee_id, reports_to FROM employees ORDER BY em...): Result sets differ (comparing unordered)):
```sql
CREATE PROCEDURE traspassar_cartera(p_de integer, p_a integer, INOUT p_comandes integer DEFAULT NULL) LANGUAGE plpgsql AS $$
DECLARE v_cap smallint;
BEGIN
  IF p_de = p_a THEN RAISE EXCEPTION 'i' USING ERRCODE = 'check_violation'; END IF;
  SELECT reports_to INTO v_cap FROM employees WHERE employee_id = p_de;
  IF NOT FOUND OR NOT EXISTS (SELECT 1 FROM employees WHERE employee_id = p_a) THEN RAISE EXCEPTION 'n' USING ERRCODE = 'no_data_found'; END IF;
  UPDATE orders SET employee_id = p_a WHERE employee_id = p_de AND shipped_date IS NULL;
  GET DIAGNOSTICS p_comandes = ROW_COUNT;
  DELETE FROM employee_territories et WHERE et.employee_id = p_de AND EXISTS (SELECT 1 FROM employee_territories x WHERE x.employee_id = p_a AND x.territory_id = et.territory_id);
  UPDATE employee_territories SET employee_id = p_a WHERE employee_id = p_de;
  UPDATE employees SET reports_to = p_a WHERE reports_to = p_de;
  UPDATE employees SET reports_to = v_cap WHERE employee_id = p_a AND reports_to = p_de;
END $$;
```


### 6. Crea el procediment `crear_comanda(p_customer_id varchar, p_employee_id integer, p_productes integer[], p_quantitats integer[], INOUT p_order_id integer DEFAULT NULL)` que doni d'alta una comanda completa i retorni el seu identificador a `p_order_id`:
- a `orders`: `order_id` = màxim + 1, el client i l'empleat donats, `order_date` = `current_date`, `required_date` = `current_date + 14`, `freight` = 0, `shipped_date` i `ship_via` a `NULL`, i `ship_name`, `ship_address`, `ship_city`, `ship_region`, `ship_postal_code` i `ship_country` copiats de `company_name`, `address`, `city`, `region`, `postal_code` i `country` del client;
- a `order_details`, una línia per a cada posició `i` dels arrays: producte `p_productes[i]`, quantitat `p_quantitats[i]`, el `unit_price` actual del producte i `discount` = 0;
- resta cada quantitat de `units_in_stock` del producte.
Validacions: si algun dels arrays és `NULL` o buit, o no tenen la mateixa llargada, `ERRCODE = 'invalid_parameter_value'`; si el client, l'empleat o algun producte no existeix, `ERRCODE = 'no_data_found'`; si algun producte està descatalogat, alguna quantitat no és positiva o no hi ha prou estoc (`units_in_stock < quantitat`), `ERRCODE = 'check_violation'`. Si falla qualsevol validació, no ha de quedar res de la comanda. (No cal tractar productes repetits dins dels arrays.)

Referència:
```sql
CREATE PROCEDURE crear_comanda(p_customer_id varchar, p_employee_id integer, p_productes integer[],
                              p_quantitats integer[], INOUT p_order_id integer DEFAULT NULL)
LANGUAGE plpgsql AS $$
DECLARE c customers%ROWTYPE; p products%ROWTYPE; i integer;
BEGIN
  IF coalesce(cardinality(p_productes), 0) = 0 OR cardinality(p_productes) IS DISTINCT FROM cardinality(p_quantitats) THEN
    RAISE EXCEPTION 'Arrays buits o de llargades diferents' USING ERRCODE = 'invalid_parameter_value';
  END IF;
  SELECT * INTO c FROM customers WHERE customer_id = p_customer_id;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'El client % no existeix', p_customer_id USING ERRCODE = 'no_data_found';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM employees WHERE employee_id = p_employee_id) THEN
    RAISE EXCEPTION 'L''empleat % no existeix', p_employee_id USING ERRCODE = 'no_data_found';
  END IF;
  SELECT coalesce(max(order_id), 0) + 1 INTO p_order_id FROM orders;
  INSERT INTO orders (order_id, customer_id, employee_id, order_date, required_date, shipped_date, ship_via,
                      freight, ship_name, ship_address, ship_city, ship_region, ship_postal_code, ship_country)
  VALUES (p_order_id, c.customer_id, p_employee_id, current_date, current_date + 14, NULL, NULL, 0,
          c.company_name, c.address, c.city, c.region, c.postal_code, c.country);
  FOR i IN 1 .. cardinality(p_productes) LOOP
    SELECT * INTO p FROM products WHERE product_id = p_productes[i];
    IF NOT FOUND THEN
      RAISE EXCEPTION 'El producte % no existeix', p_productes[i] USING ERRCODE = 'no_data_found';
    END IF;
    IF p.discontinued = 1 OR p_quantitats[i] IS NULL OR p_quantitats[i] <= 0 OR p.units_in_stock < p_quantitats[i] THEN
      RAISE EXCEPTION 'No es pot servir % unitats del producte %', p_quantitats[i], p.product_id
        USING ERRCODE = 'check_violation';
    END IF;
    INSERT INTO order_details (order_id, product_id, unit_price, quantity, discount)
    VALUES (p_order_id, p.product_id, p.unit_price, p_quantitats[i], 0);
    UPDATE products SET units_in_stock = units_in_stock - p_quantitats[i] WHERE product_id = p.product_id;
  END LOOP;
END $$;
--@@TEST@@ CALL crear_comanda('ALFKI', 3, ARRAY[11, 72], ARRAY[5, 10], NULL)
--@@TEST@@ SELECT * FROM order_details WHERE order_id > 11077 ORDER BY 1, 2
--@@TEST@@ SELECT * FROM orders WHERE order_id > 11077
--@@TEST@@ CALL crear_comanda('ALFKI', 3, ARRAY[11], ARRAY[1, 2], NULL)
--@@TEST@@ CALL crear_comanda('BOLID', 4, ARRAY[]::integer[], ARRAY[]::integer[], NULL)
--@@TEST@@ CALL crear_comanda('ZZZZZ', 3, ARRAY[11], ARRAY[1], NULL)
--@@TEST@@ CALL crear_comanda('ALFKI', 33, ARRAY[11], ARRAY[1], NULL)
--@@TEST@@ CALL crear_comanda('ALFKI', 3, ARRAY[11, 999], ARRAY[1, 1], NULL)
--@@TEST@@ CALL crear_comanda('ALFKI', 3, ARRAY[11, 1], ARRAY[1, 1], NULL)
--@@TEST@@ CALL crear_comanda('ALFKI', 3, ARRAY[11, 31], ARRAY[1, 1], NULL)
--@@TEST@@ CALL crear_comanda('ALFKI', 3, ARRAY[11, 60], ARRAY[1, 0], NULL)
--@@TEST@@ CALL crear_comanda('BOLID', 4, ARRAY[3, 60], ARRAY[13, 2], NULL)
--@@TEST@@ SELECT product_id, units_in_stock FROM products WHERE product_id IN (3, 11, 31, 60, 72) ORDER BY 1
```

Alternativa — valida tots els productes abans d'inserir res, amb `unnest(...) WITH ORDINALITY` (ACCEPTADA):
```sql
CREATE PROCEDURE crear_comanda(p_customer_id varchar, p_employee_id integer, p_productes integer[],
  p_quantitats integer[], INOUT p_order_id integer DEFAULT NULL) AS $$
DECLARE r record;
BEGIN
  IF p_productes IS NULL OR p_quantitats IS NULL OR array_length(p_productes, 1) IS NULL
     OR array_length(p_productes, 1) <> coalesce(array_length(p_quantitats, 1), 0) THEN
    RAISE EXCEPTION 'arrays' USING ERRCODE = '22023'; END IF;
  PERFORM FROM customers WHERE customer_id = p_customer_id;
  IF NOT FOUND THEN RAISE EXCEPTION 'client' USING ERRCODE = 'P0002'; END IF;
  PERFORM FROM employees WHERE employee_id = p_employee_id;
  IF NOT FOUND THEN RAISE EXCEPTION 'empleat' USING ERRCODE = 'P0002'; END IF;
  FOR r IN SELECT u.prod, u.q, p.product_id, p.discontinued, p.units_in_stock
           FROM unnest(p_productes, p_quantitats) WITH ORDINALITY AS u(prod, q, n)
           LEFT JOIN products p ON p.product_id = u.prod ORDER BY u.n LOOP
    IF r.product_id IS NULL THEN RAISE EXCEPTION 'producte' USING ERRCODE = 'P0002'; END IF;
    IF r.discontinued = 1 OR NOT (r.q > 0) OR r.units_in_stock < r.q THEN RAISE EXCEPTION 'estoc' USING ERRCODE = '23514'; END IF;
  END LOOP;
  p_order_id := (SELECT max(order_id) + 1 FROM orders);
  INSERT INTO orders (order_id, customer_id, employee_id, order_date, required_date, freight, ship_name, ship_address,
                      ship_city, ship_region, ship_postal_code, ship_country)
  SELECT p_order_id, customer_id, p_employee_id, current_date, current_date + 14, 0, company_name, address, city, region,
         postal_code, country FROM customers WHERE customer_id = p_customer_id;
  INSERT INTO order_details SELECT p_order_id, p.product_id, p.unit_price, u.q, 0
    FROM unnest(p_productes, p_quantitats) AS u(prod, q) JOIN products p ON p.product_id = u.prod;
  UPDATE products p SET units_in_stock = p.units_in_stock - u.q FROM unnest(p_productes, p_quantitats) AS u(prod, q)
   WHERE p.product_id = u.prod;
END $$ LANGUAGE plpgsql;
```

Incorrecta — `<=` en comprovar l'estoc: no deixa vendre exactament les unitats que queden (REBUTJADA: Test 12 (CALL crear_comanda('BOLID', 4, ARRAY[3, 60], ARRAY[13, 2]...): yours gives an error (SQLSTATE 23514 check_violation), the expected one returns rows):
```sql
CREATE PROCEDURE crear_comanda(p_customer_id varchar, p_employee_id integer, p_productes integer[],
                              p_quantitats integer[], INOUT p_order_id integer DEFAULT NULL)
LANGUAGE plpgsql AS $$
DECLARE c customers%ROWTYPE; p products%ROWTYPE; i integer;
BEGIN
  IF coalesce(cardinality(p_productes), 0) = 0 OR cardinality(p_productes) IS DISTINCT FROM cardinality(p_quantitats) THEN
    RAISE EXCEPTION 'Arrays buits o de llargades diferents' USING ERRCODE = 'invalid_parameter_value';
  END IF;
  SELECT * INTO c FROM customers WHERE customer_id = p_customer_id;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'El client % no existeix', p_customer_id USING ERRCODE = 'no_data_found';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM employees WHERE employee_id = p_employee_id) THEN
    RAISE EXCEPTION 'L''empleat % no existeix', p_employee_id USING ERRCODE = 'no_data_found';
  END IF;
  SELECT coalesce(max(order_id), 0) + 1 INTO p_order_id FROM orders;
  INSERT INTO orders (order_id, customer_id, employee_id, order_date, required_date, shipped_date, ship_via,
                      freight, ship_name, ship_address, ship_city, ship_region, ship_postal_code, ship_country)
  VALUES (p_order_id, c.customer_id, p_employee_id, current_date, current_date + 14, NULL, NULL, 0,
          c.company_name, c.address, c.city, c.region, c.postal_code, c.country);
  FOR i IN 1 .. cardinality(p_productes) LOOP
    SELECT * INTO p FROM products WHERE product_id = p_productes[i];
    IF NOT FOUND THEN
      RAISE EXCEPTION 'El producte % no existeix', p_productes[i] USING ERRCODE = 'no_data_found';
    END IF;
    IF p.discontinued = 1 OR p_quantitats[i] IS NULL OR p_quantitats[i] <= 0 OR p.units_in_stock <= p_quantitats[i] THEN
      RAISE EXCEPTION 'No es pot servir % unitats del producte %', p_quantitats[i], p.product_id
        USING ERRCODE = 'check_violation';
    END IF;
    INSERT INTO order_details (order_id, product_id, unit_price, quantity, discount)
    VALUES (p_order_id, p.product_id, p.unit_price, p_quantitats[i], 0);
    UPDATE products SET units_in_stock = units_in_stock - p_quantitats[i] WHERE product_id = p.product_id;
  END LOOP;
END $$;
```

Incorrecta — no copia les dades d'enviament del client (REBUTJADA: Test 3 (SELECT * FROM orders WHERE order_id > 11077): Result sets differ (comparing unordered)):
```sql
CREATE PROCEDURE crear_comanda(p_customer_id varchar, p_employee_id integer, p_productes integer[],
                              p_quantitats integer[], INOUT p_order_id integer DEFAULT NULL)
LANGUAGE plpgsql AS $$
DECLARE c customers%ROWTYPE; p products%ROWTYPE; i integer;
BEGIN
  IF coalesce(cardinality(p_productes), 0) = 0 OR cardinality(p_productes) IS DISTINCT FROM cardinality(p_quantitats) THEN
    RAISE EXCEPTION 'Arrays buits o de llargades diferents' USING ERRCODE = 'invalid_parameter_value';
  END IF;
  SELECT * INTO c FROM customers WHERE customer_id = p_customer_id;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'El client % no existeix', p_customer_id USING ERRCODE = 'no_data_found';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM employees WHERE employee_id = p_employee_id) THEN
    RAISE EXCEPTION 'L''empleat % no existeix', p_employee_id USING ERRCODE = 'no_data_found';
  END IF;
  SELECT coalesce(max(order_id), 0) + 1 INTO p_order_id FROM orders;
  INSERT INTO orders (order_id, customer_id, employee_id, order_date, required_date, shipped_date, ship_via,
                      freight, ship_name, ship_address, ship_city, ship_region, ship_postal_code, ship_country)
  VALUES (p_order_id, c.customer_id, p_employee_id, current_date, current_date + 14, NULL, NULL, 0,
          NULL, NULL, NULL, NULL, NULL, NULL);
  FOR i IN 1 .. cardinality(p_productes) LOOP
    SELECT * INTO p FROM products WHERE product_id = p_productes[i];
    IF NOT FOUND THEN
      RAISE EXCEPTION 'El producte % no existeix', p_productes[i] USING ERRCODE = 'no_data_found';
    END IF;
    IF p.discontinued = 1 OR p_quantitats[i] IS NULL OR p_quantitats[i] <= 0 OR p.units_in_stock < p_quantitats[i] THEN
      RAISE EXCEPTION 'No es pot servir % unitats del producte %', p_quantitats[i], p.product_id
        USING ERRCODE = 'check_violation';
    END IF;
    INSERT INTO order_details (order_id, product_id, unit_price, quantity, discount)
    VALUES (p_order_id, p.product_id, p.unit_price, p_quantitats[i], 0);
    UPDATE products SET units_in_stock = units_in_stock - p_quantitats[i] WHERE product_id = p.product_id;
  END LOOP;
END $$;
```

Incorrecta — no valida les llargades dels arrays: amb `ARRAY[11]` i `ARRAY[1, 2]` crea la comanda igualment (REBUTJADA: Test 4 (CALL crear_comanda('ALFKI', 3, ARRAY[11], ARRAY[1, 2], NULL)): yours returns rows, the expected one gives an error (SQLSTATE 22023 invalid_parameter_value)):
```sql
CREATE PROCEDURE crear_comanda(p_customer_id varchar, p_employee_id integer, p_productes integer[],
                              p_quantitats integer[], INOUT p_order_id integer DEFAULT NULL)
LANGUAGE plpgsql AS $$
DECLARE c customers%ROWTYPE; p products%ROWTYPE; i integer;
BEGIN
  IF coalesce(cardinality(p_productes), 0) = 0 THEN
    RAISE EXCEPTION 'Arrays buits o de llargades diferents' USING ERRCODE = 'invalid_parameter_value';
  END IF;
  SELECT * INTO c FROM customers WHERE customer_id = p_customer_id;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'El client % no existeix', p_customer_id USING ERRCODE = 'no_data_found';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM employees WHERE employee_id = p_employee_id) THEN
    RAISE EXCEPTION 'L''empleat % no existeix', p_employee_id USING ERRCODE = 'no_data_found';
  END IF;
  SELECT coalesce(max(order_id), 0) + 1 INTO p_order_id FROM orders;
  INSERT INTO orders (order_id, customer_id, employee_id, order_date, required_date, shipped_date, ship_via,
                      freight, ship_name, ship_address, ship_city, ship_region, ship_postal_code, ship_country)
  VALUES (p_order_id, c.customer_id, p_employee_id, current_date, current_date + 14, NULL, NULL, 0,
          c.company_name, c.address, c.city, c.region, c.postal_code, c.country);
  FOR i IN 1 .. cardinality(p_productes) LOOP
    SELECT * INTO p FROM products WHERE product_id = p_productes[i];
    IF NOT FOUND THEN
      RAISE EXCEPTION 'El producte % no existeix', p_productes[i] USING ERRCODE = 'no_data_found';
    END IF;
    IF p.discontinued = 1 OR p_quantitats[i] IS NULL OR p_quantitats[i] <= 0 OR p.units_in_stock < p_quantitats[i] THEN
      RAISE EXCEPTION 'No es pot servir % unitats del producte %', p_quantitats[i], p.product_id
        USING ERRCODE = 'check_violation';
    END IF;
    INSERT INTO order_details (order_id, product_id, unit_price, quantity, discount)
    VALUES (p_order_id, p.product_id, p.unit_price, p_quantitats[i], 0);
    UPDATE products SET units_in_stock = units_in_stock - p_quantitats[i] WHERE product_id = p.product_id;
  END LOOP;
END $$;
```


## Northwind — Triggers (pgtrigger)


### 1. Crea un trigger `BEFORE INSERT OR UPDATE` a `products` (`FOR EACH ROW`) que: (1) llanci una excepció amb `ERRCODE = 'check_violation'` si el `unit_price` nou és `NULL` o negatiu, o si `units_in_stock` queda negatiu; i (2) quan el producte quedi descatalogat (`discontinued = 1`), posi automàticament `units_on_order` i `reorder_level` a 0.

Referència:
```sql
CREATE FUNCTION f_valida_producte() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.unit_price IS NULL OR NEW.unit_price < 0 THEN
    RAISE EXCEPTION 'Preu no vàlid per al producte %', NEW.product_id USING ERRCODE = 'check_violation';
  END IF;
  IF NEW.units_in_stock < 0 THEN
    RAISE EXCEPTION 'Estoc negatiu per al producte %', NEW.product_id USING ERRCODE = 'check_violation';
  END IF;
  IF NEW.discontinued = 1 THEN
    NEW.units_on_order := 0;
    NEW.reorder_level := 0;
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_valida_producte BEFORE INSERT OR UPDATE ON products
  FOR EACH ROW EXECUTE FUNCTION f_valida_producte();
--@@TEST@@ UPDATE products SET unit_price = -1 WHERE product_id = 1
--@@TEST@@ UPDATE products SET units_in_stock = units_in_stock - 20 WHERE category_id = 4
--@@TEST@@ UPDATE products SET units_in_stock = units_in_stock - 5 WHERE category_id = 4 AND units_in_stock >= 5
--@@TEST@@ UPDATE products SET discontinued = 1 WHERE product_id IN (3, 4)
--@@TEST@@ INSERT INTO products VALUES (78, 'Crema catalana', 1, 3, '12 unitats', 4.5, 10, 5, 3, 1)
--@@TEST@@ INSERT INTO products VALUES (79, 'Mel de romaní', 1, 2, '6 pots', NULL, 10, 0, 0, 0)
--@@TEST@@ SELECT * FROM products WHERE product_id IN (3, 4, 78) ORDER BY product_id
```

Alternativa — amb un `IF` combinat i el trigger escrit primer amb `CREATE OR REPLACE` de la funció (ACCEPTADA):
```sql
CREATE OR REPLACE FUNCTION valida() RETURNS trigger AS $$
BEGIN
  IF coalesce(NEW.unit_price, -1) < 0 OR NEW.units_in_stock < 0 THEN
    RAISE EXCEPTION 'dades no vàlides' USING ERRCODE = '23514';
  END IF;
  IF NEW.discontinued = 1 THEN NEW.units_on_order = 0; NEW.reorder_level = 0; END IF;
  RETURN NEW;
END $$ LANGUAGE plpgsql;
CREATE TRIGGER t BEFORE UPDATE OR INSERT ON products FOR EACH ROW EXECUTE PROCEDURE valida();
```

Incorrecta — trigger `AFTER`: les validacions funcionen, però els canvis a `NEW` no tenen cap efecte (REBUTJADA: Test 7 (SELECT * FROM products WHERE product_id IN (3, 4, 78) ORD...): Result sets differ (comparing unordered)):
```sql
CREATE FUNCTION f_valida_producte() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.unit_price IS NULL OR NEW.unit_price < 0 THEN
    RAISE EXCEPTION 'Preu no vàlid per al producte %', NEW.product_id USING ERRCODE = 'check_violation';
  END IF;
  IF NEW.units_in_stock < 0 THEN
    RAISE EXCEPTION 'Estoc negatiu per al producte %', NEW.product_id USING ERRCODE = 'check_violation';
  END IF;
  IF NEW.discontinued = 1 THEN
    NEW.units_on_order := 0;
    NEW.reorder_level := 0;
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_valida_producte AFTER INSERT OR UPDATE ON products
  FOR EACH ROW EXECUTE FUNCTION f_valida_producte();
```

Incorrecta — només `BEFORE UPDATE`: les insercions no es validen ni es completen (REBUTJADA: Test 6 (INSERT INTO products VALUES (79, 'Mel de romaní', 1, 2, '...): yours runs, the expected one gives an error (SQLSTATE 23514 check_violation)):
```sql
CREATE FUNCTION f_valida_producte() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.unit_price IS NULL OR NEW.unit_price < 0 THEN
    RAISE EXCEPTION 'Preu no vàlid per al producte %', NEW.product_id USING ERRCODE = 'check_violation';
  END IF;
  IF NEW.units_in_stock < 0 THEN
    RAISE EXCEPTION 'Estoc negatiu per al producte %', NEW.product_id USING ERRCODE = 'check_violation';
  END IF;
  IF NEW.discontinued = 1 THEN
    NEW.units_on_order := 0;
    NEW.reorder_level := 0;
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_valida_producte BEFORE UPDATE ON products
  FOR EACH ROW EXECUTE FUNCTION f_valida_producte();
```

Incorrecta — no comprova el preu `NULL` (REBUTJADA: Test 6 (INSERT INTO products VALUES (79, 'Mel de romaní', 1, 2, '...): yours runs, the expected one gives an error (SQLSTATE 23514 check_violation)):
```sql
CREATE FUNCTION f_valida_producte() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.unit_price < 0 THEN
    RAISE EXCEPTION 'Preu no vàlid per al producte %', NEW.product_id USING ERRCODE = 'check_violation';
  END IF;
  IF NEW.units_in_stock < 0 THEN
    RAISE EXCEPTION 'Estoc negatiu per al producte %', NEW.product_id USING ERRCODE = 'check_violation';
  END IF;
  IF NEW.discontinued = 1 THEN
    NEW.units_on_order := 0;
    NEW.reorder_level := 0;
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_valida_producte BEFORE INSERT OR UPDATE ON products
  FOR EACH ROW EXECUTE FUNCTION f_valida_producte();
```


### 2. Crea un trigger `BEFORE INSERT` a `orders` (`FOR EACH ROW`) que completi les comandes noves: si `order_date` és `NULL`, posa-hi `current_date`; si `required_date` és `NULL`, posa-hi `order_date` + 28 dies; si `freight` és `NULL`, posa-hi 0; i cadascun dels camps `ship_name`, `ship_address`, `ship_city`, `ship_region`, `ship_postal_code` i `ship_country` que sigui `NULL` s'omple amb el camp corresponent del client (`company_name`, `address`, `city`, `region`, `postal_code`, `country`). Els camps que ja tinguin valor no es toquen. Quan es modifica una comanda (`UPDATE`) no s'ha de fer res.

Referència:
```sql
CREATE FUNCTION f_completa_comanda() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE c customers%ROWTYPE;
BEGIN
  SELECT * INTO c FROM customers WHERE customer_id = NEW.customer_id;
  NEW.order_date := coalesce(NEW.order_date, current_date);
  NEW.required_date := coalesce(NEW.required_date, NEW.order_date + 28);
  NEW.freight := coalesce(NEW.freight, 0);
  NEW.ship_name := coalesce(NEW.ship_name, c.company_name);
  NEW.ship_address := coalesce(NEW.ship_address, c.address);
  NEW.ship_city := coalesce(NEW.ship_city, c.city);
  NEW.ship_region := coalesce(NEW.ship_region, c.region);
  NEW.ship_postal_code := coalesce(NEW.ship_postal_code, c.postal_code);
  NEW.ship_country := coalesce(NEW.ship_country, c.country);
  RETURN NEW;
END $$;
CREATE TRIGGER trg_completa_comanda BEFORE INSERT ON orders
  FOR EACH ROW EXECUTE FUNCTION f_completa_comanda();
--@@TEST@@ INSERT INTO orders (order_id, customer_id, employee_id, order_date) VALUES (11078, 'OLDWO', 1, DATE '1998-05-07')
--@@TEST@@ INSERT INTO orders (order_id, customer_id, employee_id, ship_name, ship_city) VALUES (11079, 'HUNGO', 2, 'Hungry Owl (magatzem)', 'Dublin')
--@@TEST@@ INSERT INTO orders (order_id, customer_id, employee_id, order_date, required_date, freight, ship_country) VALUES (11080, 'BOLID', 3, DATE '1998-05-07', DATE '1998-05-20', 12.5, 'Portugal')
--@@TEST@@ INSERT INTO orders (order_id, customer_id, employee_id, order_date) VALUES (11081, NULL, 3, DATE '1998-05-08')
--@@TEST@@ UPDATE orders SET freight = NULL, ship_city = NULL WHERE order_id = 10248
--@@TEST@@ SELECT * FROM orders WHERE order_id = 10248 OR order_id > 11077 ORDER BY order_id
```

Alternativa — amb un sol `SELECT ... INTO NEW.camp, ...` i `TG_OP` (ACCEPTADA):
```sql
CREATE FUNCTION completa() RETURNS trigger AS $$
BEGIN
  IF TG_OP <> 'INSERT' THEN RETURN NEW; END IF;
  IF NEW.order_date IS NULL THEN NEW.order_date := current_date; END IF;
  IF NEW.required_date IS NULL THEN NEW.required_date := NEW.order_date + interval '28 days'; END IF;
  IF NEW.freight IS NULL THEN NEW.freight := 0; END IF;
  SELECT coalesce(NEW.ship_name, company_name), coalesce(NEW.ship_address, address), coalesce(NEW.ship_city, city),
         coalesce(NEW.ship_region, region), coalesce(NEW.ship_postal_code, postal_code), coalesce(NEW.ship_country, country)
    INTO NEW.ship_name, NEW.ship_address, NEW.ship_city, NEW.ship_region, NEW.ship_postal_code, NEW.ship_country
    FROM customers WHERE customer_id = NEW.customer_id;
  RETURN NEW;
END $$ LANGUAGE plpgsql;
CREATE TRIGGER t BEFORE INSERT OR UPDATE ON orders FOR EACH ROW EXECUTE FUNCTION completa();
```

Incorrecta — `BEFORE INSERT OR UPDATE`: també omple els camps en modificar una comanda (REBUTJADA: Test 6 (SELECT * FROM orders WHERE order_id = 10248 OR order_id >...): Result sets differ (comparing unordered)):
```sql
CREATE FUNCTION f_completa_comanda() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE c customers%ROWTYPE;
BEGIN
  SELECT * INTO c FROM customers WHERE customer_id = NEW.customer_id;
  NEW.order_date := coalesce(NEW.order_date, current_date);
  NEW.required_date := coalesce(NEW.required_date, NEW.order_date + 28);
  NEW.freight := coalesce(NEW.freight, 0);
  NEW.ship_name := coalesce(NEW.ship_name, c.company_name);
  NEW.ship_address := coalesce(NEW.ship_address, c.address);
  NEW.ship_city := coalesce(NEW.ship_city, c.city);
  NEW.ship_region := coalesce(NEW.ship_region, c.region);
  NEW.ship_postal_code := coalesce(NEW.ship_postal_code, c.postal_code);
  NEW.ship_country := coalesce(NEW.ship_country, c.country);
  RETURN NEW;
END $$;
CREATE TRIGGER trg_completa_comanda BEFORE INSERT OR UPDATE ON orders
  FOR EACH ROW EXECUTE FUNCTION f_completa_comanda();
```

Incorrecta — `required_date` a partir de `current_date` en lloc de la data de la comanda (REBUTJADA: Test 6 (SELECT * FROM orders WHERE order_id = 10248 OR order_id >...): Result sets differ (comparing unordered)):
```sql
CREATE FUNCTION f_completa_comanda() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE c customers%ROWTYPE;
BEGIN
  SELECT * INTO c FROM customers WHERE customer_id = NEW.customer_id;
  NEW.order_date := coalesce(NEW.order_date, current_date);
  NEW.required_date := coalesce(NEW.required_date, current_date + 28);
  NEW.freight := coalesce(NEW.freight, 0);
  NEW.ship_name := coalesce(NEW.ship_name, c.company_name);
  NEW.ship_address := coalesce(NEW.ship_address, c.address);
  NEW.ship_city := coalesce(NEW.ship_city, c.city);
  NEW.ship_region := coalesce(NEW.ship_region, c.region);
  NEW.ship_postal_code := coalesce(NEW.ship_postal_code, c.postal_code);
  NEW.ship_country := coalesce(NEW.ship_country, c.country);
  RETURN NEW;
END $$;
CREATE TRIGGER trg_completa_comanda BEFORE INSERT ON orders
  FOR EACH ROW EXECUTE FUNCTION f_completa_comanda();
```

Incorrecta — copia les dades del client encara que la comanda ja en porti (REBUTJADA: Test 6 (SELECT * FROM orders WHERE order_id = 10248 OR order_id >...): Result sets differ (comparing unordered)):
```sql
CREATE FUNCTION f_completa_comanda() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE c customers%ROWTYPE;
BEGIN
  SELECT * INTO c FROM customers WHERE customer_id = NEW.customer_id;
  NEW.order_date := coalesce(NEW.order_date, current_date);
  NEW.required_date := coalesce(NEW.required_date, NEW.order_date + 28);
  NEW.freight := coalesce(NEW.freight, 0);
  NEW.ship_name := c.company_name;
  NEW.ship_address := coalesce(NEW.ship_address, c.address);
  NEW.ship_city := c.city;
  NEW.ship_region := coalesce(NEW.ship_region, c.region);
  NEW.ship_postal_code := coalesce(NEW.ship_postal_code, c.postal_code);
  NEW.ship_country := c.country;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_completa_comanda BEFORE INSERT ON orders
  FOR EACH ROW EXECUTE FUNCTION f_completa_comanda();
```


### 3. Crea la taula `historial_preus (product_id smallint, preu_antic real, preu_nou real, data date)` i un trigger `AFTER UPDATE OF unit_price` a `products` (`FOR EACH ROW`) que hi afegeixi una fila (producte, preu anterior, preu nou, `current_date`) cada vegada que el preu d'un producte **canviï de veritat**: si l'`UPDATE` deixa el preu igual, no s'ha de registrar res. Fes servir la clàusula `WHEN (...)` del trigger per filtrar-ho.

Referència:
```sql
CREATE TABLE historial_preus (product_id smallint, preu_antic real, preu_nou real, data date);
CREATE FUNCTION f_historial_preus() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  INSERT INTO historial_preus VALUES (NEW.product_id, OLD.unit_price, NEW.unit_price, current_date);
  RETURN NULL;
END $$;
CREATE TRIGGER trg_historial_preus AFTER UPDATE OF unit_price ON products
  FOR EACH ROW WHEN (OLD.unit_price IS DISTINCT FROM NEW.unit_price)
  EXECUTE FUNCTION f_historial_preus();
--@@TEST@@ UPDATE products SET unit_price = unit_price * 1.1 WHERE category_id = 1
--@@TEST@@ UPDATE products SET unit_price = unit_price WHERE category_id = 2
--@@TEST@@ UPDATE products SET units_in_stock = 0, discontinued = 1 WHERE product_id = 3
--@@TEST@@ UPDATE products SET unit_price = 20 WHERE product_id IN (1, 2, 3, 40)
--@@TEST@@ SELECT product_id, preu_antic, preu_nou, data FROM historial_preus ORDER BY product_id, preu_nou
```

Alternativa — comprovació dins de la funció en lloc de `WHEN`, i trigger `AFTER UPDATE` (de qualsevol columna) (ACCEPTADA):
```sql
CREATE TABLE historial_preus (product_id smallint, preu_antic real, preu_nou real, data date);
CREATE FUNCTION hp() RETURNS trigger AS $$
BEGIN
  IF NEW.unit_price IS DISTINCT FROM OLD.unit_price THEN
    INSERT INTO historial_preus (product_id, preu_antic, preu_nou, data) VALUES (OLD.product_id, OLD.unit_price, NEW.unit_price, now()::date);
  END IF;
  RETURN NEW;
END $$ LANGUAGE plpgsql;
CREATE TRIGGER t AFTER UPDATE ON products FOR EACH ROW EXECUTE FUNCTION hp();
```

Incorrecta — sense `WHEN`: registra també els `UPDATE` que no canvien el preu (REBUTJADA: Test 5 (SELECT product_id, preu_antic, preu_nou, data FROM histor...): Wrong number of rows: got 28, expected 16):
```sql
CREATE TABLE historial_preus (product_id smallint, preu_antic real, preu_nou real, data date);
CREATE FUNCTION f_historial_preus() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  INSERT INTO historial_preus VALUES (NEW.product_id, OLD.unit_price, NEW.unit_price, current_date);
  RETURN NULL;
END $$;
CREATE TRIGGER trg_historial_preus AFTER UPDATE OF unit_price ON products
  FOR EACH ROW
  EXECUTE FUNCTION f_historial_preus();
```

Incorrecta — `BEFORE` amb `RETURN NULL`: descarta les modificacions dels preus (REBUTJADA: Test 1 (UPDATE products SET unit_price = unit_price * 1.1 WHERE c...): it changed 0 rows, expected 12):
```sql
CREATE TABLE historial_preus (product_id smallint, preu_antic real, preu_nou real, data date);
CREATE FUNCTION f_historial_preus() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  INSERT INTO historial_preus VALUES (NEW.product_id, OLD.unit_price, NEW.unit_price, current_date);
  RETURN NULL;
END $$;
CREATE TRIGGER trg_historial_preus BEFORE UPDATE OF unit_price ON products
  FOR EACH ROW WHEN (OLD.unit_price IS DISTINCT FROM NEW.unit_price)
  EXECUTE FUNCTION f_historial_preus();
```

Incorrecta — preu antic i nou intercanviats (REBUTJADA: Test 5 (SELECT product_id, preu_antic, preu_nou, data FROM histor...): Result sets differ (comparing unordered)):
```sql
CREATE TABLE historial_preus (product_id smallint, preu_antic real, preu_nou real, data date);
CREATE FUNCTION f_historial_preus() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  INSERT INTO historial_preus VALUES (NEW.product_id, NEW.unit_price, OLD.unit_price, current_date);
  RETURN NULL;
END $$;
CREATE TRIGGER trg_historial_preus AFTER UPDATE OF unit_price ON products
  FOR EACH ROW WHEN (OLD.unit_price IS DISTINCT FROM NEW.unit_price)
  EXECUTE FUNCTION f_historial_preus();
```


### 4. Crea un **únic** trigger `AFTER INSERT OR UPDATE OR DELETE` a `order_details` (`FOR EACH ROW`) que mantingui `products.units_in_stock` al dia: en inserir una línia, resta la quantitat de l'estoc del producte; en esborrar-la, la torna a sumar; en modificar-la, torna la quantitat antiga al producte antic i resta la nova del producte nou (pot ser que canviï el producte, no només la quantitat). Fes servir `TG_OP` per saber quina operació s'ha fet. Si després de restar l'estoc d'un producte queda negatiu, llança una excepció amb `ERRCODE = 'check_violation'` (així es desfà tota la sentència).

Referència:
```sql
CREATE FUNCTION f_estoc_linies() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP IN ('UPDATE', 'DELETE') THEN
    UPDATE products SET units_in_stock = units_in_stock + OLD.quantity WHERE product_id = OLD.product_id;
  END IF;
  IF TG_OP IN ('INSERT', 'UPDATE') THEN
    UPDATE products SET units_in_stock = units_in_stock - NEW.quantity WHERE product_id = NEW.product_id;
    IF (SELECT units_in_stock FROM products WHERE product_id = NEW.product_id) < 0 THEN
      RAISE EXCEPTION 'No hi ha prou estoc del producte %', NEW.product_id USING ERRCODE = 'check_violation';
    END IF;
  END IF;
  RETURN NULL;
END $$;
CREATE TRIGGER trg_estoc_linies AFTER INSERT OR UPDATE OR DELETE ON order_details
  FOR EACH ROW EXECUTE FUNCTION f_estoc_linies();
--@@TEST@@ INSERT INTO order_details VALUES (10248, 1, 18, 5, 0)
--@@TEST@@ UPDATE order_details SET quantity = quantity + 2 WHERE order_id = 10248
--@@TEST@@ DELETE FROM order_details WHERE order_id = 10249
--@@TEST@@ UPDATE order_details SET product_id = 2, quantity = 4 WHERE order_id = 10248 AND product_id = 1
--@@TEST@@ INSERT INTO order_details VALUES (10249, 72, 34.8, 15, 0)
--@@TEST@@ UPDATE order_details SET quantity = 30 WHERE order_id = 10248 AND product_id = 72
--@@TEST@@ SELECT product_id, units_in_stock FROM products WHERE product_id IN (1, 2, 11, 14, 42, 51, 72) ORDER BY product_id
```

Alternativa — amb `CASE TG_OP` i les comprovacions abans de restar (ACCEPTADA):
```sql
CREATE FUNCTION estoc() RETURNS trigger AS $$
DECLARE e integer;
BEGIN
  CASE TG_OP
    WHEN 'INSERT' THEN
      UPDATE products SET units_in_stock = units_in_stock - NEW.quantity WHERE product_id = NEW.product_id RETURNING units_in_stock INTO e;
      IF e < 0 THEN RAISE EXCEPTION 'estoc' USING ERRCODE = '23514'; END IF;
    WHEN 'DELETE' THEN
      UPDATE products SET units_in_stock = units_in_stock + OLD.quantity WHERE product_id = OLD.product_id;
    ELSE
      UPDATE products SET units_in_stock = units_in_stock + OLD.quantity WHERE product_id = OLD.product_id;
      UPDATE products SET units_in_stock = units_in_stock - NEW.quantity WHERE product_id = NEW.product_id RETURNING units_in_stock INTO e;
      IF e < 0 THEN RAISE EXCEPTION 'estoc' USING ERRCODE = '23514'; END IF;
  END CASE;
  RETURN NULL;
END $$ LANGUAGE plpgsql;
CREATE TRIGGER t AFTER INSERT OR UPDATE OR DELETE ON order_details FOR EACH ROW EXECUTE FUNCTION estoc();
```

Incorrecta — en un `UPDATE` només aplica la diferència de quantitats al producte nou (no té en compte el canvi de producte) (REBUTJADA: Test 7 (SELECT product_id, units_in_stock FROM products WHERE pro...): Result sets differ (comparing unordered)):
```sql
CREATE FUNCTION estoc() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'INSERT' THEN UPDATE products SET units_in_stock = units_in_stock - NEW.quantity WHERE product_id = NEW.product_id;
  ELSIF TG_OP = 'DELETE' THEN UPDATE products SET units_in_stock = units_in_stock + OLD.quantity WHERE product_id = OLD.product_id;
  ELSE UPDATE products SET units_in_stock = units_in_stock - (NEW.quantity - OLD.quantity) WHERE product_id = NEW.product_id;
  END IF;
  IF TG_OP <> 'DELETE' AND (SELECT units_in_stock FROM products WHERE product_id = NEW.product_id) < 0 THEN
    RAISE EXCEPTION 'estoc' USING ERRCODE = 'check_violation'; END IF;
  RETURN NULL;
END $$;
CREATE TRIGGER t AFTER INSERT OR UPDATE OR DELETE ON order_details FOR EACH ROW EXECUTE FUNCTION estoc();
```

Incorrecta — no controla l'estoc negatiu (REBUTJADA: Test 5 (INSERT INTO order_details VALUES (10249, 72, 34.8, 15, 0)): yours runs, the expected one gives an error (SQLSTATE 23514 check_violation)):
```sql
CREATE FUNCTION f_estoc_linies() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP IN ('UPDATE', 'DELETE') THEN
    UPDATE products SET units_in_stock = units_in_stock + OLD.quantity WHERE product_id = OLD.product_id;
  END IF;
  IF TG_OP IN ('INSERT', 'UPDATE') THEN
    UPDATE products SET units_in_stock = units_in_stock - NEW.quantity WHERE product_id = NEW.product_id;
  END IF;
  RETURN NULL;
END $$;
CREATE TRIGGER trg_estoc_linies AFTER INSERT OR UPDATE OR DELETE ON order_details
  FOR EACH ROW EXECUTE FUNCTION f_estoc_linies();
```

Incorrecta — trigger només `AFTER INSERT OR UPDATE`: esborrar una línia no retorna l'estoc (REBUTJADA: Test 7 (SELECT product_id, units_in_stock FROM products WHERE pro...): Result sets differ (comparing unordered)):
```sql
CREATE FUNCTION f_estoc_linies() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP IN ('UPDATE', 'DELETE') THEN
    UPDATE products SET units_in_stock = units_in_stock + OLD.quantity WHERE product_id = OLD.product_id;
  END IF;
  IF TG_OP IN ('INSERT', 'UPDATE') THEN
    UPDATE products SET units_in_stock = units_in_stock - NEW.quantity WHERE product_id = NEW.product_id;
    IF (SELECT units_in_stock FROM products WHERE product_id = NEW.product_id) < 0 THEN
      RAISE EXCEPTION 'No hi ha prou estoc del producte %', NEW.product_id USING ERRCODE = 'check_violation';
    END IF;
  END IF;
  RETURN NULL;
END $$;
CREATE TRIGGER trg_estoc_linies AFTER INSERT OR UPDATE ON order_details
  FOR EACH ROW EXECUTE FUNCTION f_estoc_linies();
```


### 5. Les comandes que ja s'han enviat no es poden esborrar. Crea un trigger `BEFORE DELETE` a `orders` (`FOR EACH ROW`) que: si la comanda ja té `shipped_date`, **descarti en silenci** l'esborrat d'aquella fila (sense error: la comanda es queda i la resta de files de la mateixa sentència s'esborren igualment); i si encara no s'ha enviat, abans d'esborrar-la, esborri les seves línies (`order_details`) perquè la clau forana no ho impedeixi.

Referència:
```sql
CREATE FUNCTION f_esborra_comanda() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.shipped_date IS NOT NULL THEN
    RETURN NULL;
  END IF;
  DELETE FROM order_details WHERE order_id = OLD.order_id;
  RETURN OLD;
END $$;
CREATE TRIGGER trg_esborra_comanda BEFORE DELETE ON orders
  FOR EACH ROW EXECUTE FUNCTION f_esborra_comanda();
--@@TEST@@ DELETE FROM orders WHERE order_id IN (10248, 11077)
--@@TEST@@ DELETE FROM orders WHERE customer_id = 'LILAS'
--@@TEST@@ DELETE FROM orders WHERE order_id = 10250
--@@TEST@@ SELECT count(*) FROM orders
--@@TEST@@ SELECT count(*) FROM order_details
```

Alternativa — amb `WHEN` al trigger i una funció que només esborra les línies (les enviades s'esborren a part amb un segon trigger que retorna `NULL`) (ACCEPTADA):
```sql
CREATE FUNCTION no_res() RETURNS trigger AS $$ BEGIN RETURN NULL; END $$ LANGUAGE plpgsql;
CREATE FUNCTION linies() RETURNS trigger AS $$ BEGIN DELETE FROM order_details d WHERE d.order_id = OLD.order_id; RETURN OLD; END $$ LANGUAGE plpgsql;
CREATE TRIGGER a_enviades BEFORE DELETE ON orders FOR EACH ROW WHEN (OLD.shipped_date IS NOT NULL) EXECUTE FUNCTION no_res();
CREATE TRIGGER b_pendents BEFORE DELETE ON orders FOR EACH ROW WHEN (OLD.shipped_date IS NULL) EXECUTE FUNCTION linies();
```

Incorrecta — `RETURN NEW` en un `BEFORE DELETE`: `NEW` és `NULL` i no s'esborra cap comanda (REBUTJADA: Test 1 (DELETE FROM orders WHERE order_id IN (10248, 11077)): it changed 0 rows, expected 1):
```sql
CREATE FUNCTION f_esborra_comanda() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.shipped_date IS NOT NULL THEN
    RETURN NULL;
  END IF;
  DELETE FROM order_details WHERE order_id = OLD.order_id;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_esborra_comanda BEFORE DELETE ON orders
  FOR EACH ROW EXECUTE FUNCTION f_esborra_comanda();
```

Incorrecta — `RAISE EXCEPTION` en lloc de descartar la fila: falla tota la sentència (REBUTJADA: Test 1 (DELETE FROM orders WHERE order_id IN (10248, 11077)): yours gives an error (SQLSTATE P0001 raise_exception), the expected one runs):
```sql
CREATE FUNCTION f_esborra_comanda() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.shipped_date IS NOT NULL THEN
    RAISE EXCEPTION 'Comanda ja enviada';
  END IF;
  DELETE FROM order_details WHERE order_id = OLD.order_id;
  RETURN OLD;
END $$;
CREATE TRIGGER trg_esborra_comanda BEFORE DELETE ON orders
  FOR EACH ROW EXECUTE FUNCTION f_esborra_comanda();
```

Incorrecta — no esborra les línies: la clau forana fa fallar l'esborrat (REBUTJADA: Test 1 (DELETE FROM orders WHERE order_id IN (10248, 11077)): yours gives an error (SQLSTATE 23503 foreign_key_violation), the expected one runs):
```sql
CREATE FUNCTION f_esborra_comanda() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.shipped_date IS NOT NULL THEN
    RETURN NULL;
  END IF;
  RETURN OLD;
END $$;
CREATE TRIGGER trg_esborra_comanda BEFORE DELETE ON orders
  FOR EACH ROW EXECUTE FUNCTION f_esborra_comanda();
```


### 6. Crea la taula `log_valor_estoc (productes integer, valor_abans numeric, valor_despres numeric)` i un trigger `AFTER UPDATE` a `products` **a nivell de sentència** (`FOR EACH STATEMENT`) amb taules de transició (`REFERENCING OLD TABLE AS ... NEW TABLE AS ...`) que, per a cada sentència `UPDATE`, calculi el valor de l'estoc de les files modificades abans i després (suma de `unit_price::numeric * units_in_stock`, arrodonida a 2 decimals; 0 si la sentència no ha modificat cap fila) i: si el valor de després és més d'un 50 % superior al d'abans (`despres > abans * 1.5`), llanci una excepció amb `ERRCODE = 'check_violation'` (i així es desfà tota la sentència); si no, afegeixi a `log_valor_estoc` **una sola fila** amb el nombre de files modificades i els dos valors.

Referència:
```sql
CREATE TABLE log_valor_estoc (productes integer, valor_abans numeric, valor_despres numeric);
CREATE FUNCTION f_valor_estoc() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE n integer; v_abans numeric; v_despres numeric;
BEGIN
  SELECT count(*), coalesce(round(sum(unit_price::numeric * units_in_stock), 2), 0) INTO n, v_abans FROM antics;
  SELECT coalesce(round(sum(unit_price::numeric * units_in_stock), 2), 0) INTO v_despres FROM nous;
  IF v_despres > v_abans * 1.5 THEN
    RAISE EXCEPTION 'El valor de l''estoc creix massa (% -> %)', v_abans, v_despres USING ERRCODE = 'check_violation';
  END IF;
  INSERT INTO log_valor_estoc VALUES (n, v_abans, v_despres);
  RETURN NULL;
END $$;
CREATE TRIGGER trg_valor_estoc AFTER UPDATE ON products
  REFERENCING OLD TABLE AS antics NEW TABLE AS nous
  FOR EACH STATEMENT EXECUTE FUNCTION f_valor_estoc();
--@@TEST@@ UPDATE products SET unit_price = unit_price * 1.1 WHERE category_id = 1
--@@TEST@@ UPDATE products SET units_in_stock = units_in_stock + 5 WHERE product_id IN (1, 2)
--@@TEST@@ UPDATE products SET unit_price = 0 WHERE product_id = -1
--@@TEST@@ UPDATE products SET unit_price = unit_price * 2 WHERE category_id = 2
--@@TEST@@ UPDATE products SET units_in_stock = units_in_stock * 1.4 WHERE category_id = 3
--@@TEST@@ SELECT productes, valor_abans, valor_despres FROM log_valor_estoc
--@@TEST@@ SELECT sum(units_in_stock) FROM products
```

Alternativa — amb un sol `INSERT ... SELECT` i la comprovació després (l'excepció desfà també la fila del registre) (ACCEPTADA):
```sql
CREATE TABLE log_valor_estoc (productes integer, valor_abans numeric, valor_despres numeric);
CREATE FUNCTION valor() RETURNS trigger AS $$
DECLARE l log_valor_estoc;
BEGIN
  INSERT INTO log_valor_estoc
  SELECT (SELECT count(*) FROM nou), (SELECT round(coalesce(sum(unit_price::numeric * units_in_stock), 0), 2) FROM vell),
         (SELECT round(coalesce(sum(unit_price::numeric * units_in_stock), 0), 2) FROM nou)
  RETURNING * INTO l;
  IF l.valor_despres > l.valor_abans * 1.5 THEN RAISE EXCEPTION 'massa' USING ERRCODE = '23514'; END IF;
  RETURN NULL;
END $$ LANGUAGE plpgsql;
CREATE TRIGGER t AFTER UPDATE ON products REFERENCING NEW TABLE AS nou OLD TABLE AS vell FOR EACH STATEMENT EXECUTE FUNCTION valor();
```

Incorrecta — `FOR EACH ROW` (amb `NEW`/`OLD`): una fila de registre per producte en lloc d'una per sentència (REBUTJADA: Test 6 (SELECT productes, valor_abans, valor_despres FROM log_val...): Wrong number of rows: got 27, expected 4):
```sql
CREATE TABLE log_valor_estoc (productes integer, valor_abans numeric, valor_despres numeric);
CREATE FUNCTION valor() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.unit_price::numeric * NEW.units_in_stock > OLD.unit_price::numeric * OLD.units_in_stock * 1.5 THEN
    RAISE EXCEPTION 'massa' USING ERRCODE = 'check_violation'; END IF;
  INSERT INTO log_valor_estoc VALUES (1, round(OLD.unit_price::numeric * OLD.units_in_stock, 2), round(NEW.unit_price::numeric * NEW.units_in_stock, 2));
  RETURN NULL;
END $$;
CREATE TRIGGER t AFTER UPDATE ON products FOR EACH ROW EXECUTE FUNCTION valor();
```

Incorrecta — sense `coalesce`: amb 0 files modificades registra `NULL` (REBUTJADA: Test 6 (SELECT productes, valor_abans, valor_despres FROM log_val...): Result sets differ (comparing unordered)):
```sql
CREATE TABLE log_valor_estoc (productes integer, valor_abans numeric, valor_despres numeric);
CREATE FUNCTION f_valor_estoc() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE n integer; v_abans numeric; v_despres numeric;
BEGIN
  SELECT count(*), round(sum(unit_price::numeric * units_in_stock), 2) INTO n, v_abans FROM antics;
  SELECT round(sum(unit_price::numeric * units_in_stock), 2) INTO v_despres FROM nous;
  IF v_despres > v_abans * 1.5 THEN
    RAISE EXCEPTION 'El valor de l''estoc creix massa (% -> %)', v_abans, v_despres USING ERRCODE = 'check_violation';
  END IF;
  INSERT INTO log_valor_estoc VALUES (n, v_abans, v_despres);
  RETURN NULL;
END $$;
CREATE TRIGGER trg_valor_estoc AFTER UPDATE ON products
  REFERENCING OLD TABLE AS antics NEW TABLE AS nous
  FOR EACH STATEMENT EXECUTE FUNCTION f_valor_estoc();
```

Incorrecta — no fa la comprovació del 50 % (REBUTJADA: Test 4 (UPDATE products SET unit_price = unit_price * 2 WHERE cat...): yours runs, the expected one gives an error (SQLSTATE 23514 check_violation)):
```sql
CREATE TABLE log_valor_estoc (productes integer, valor_abans numeric, valor_despres numeric);
CREATE FUNCTION f_valor_estoc() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE n integer; v_abans numeric; v_despres numeric;
BEGIN
  SELECT count(*), coalesce(round(sum(unit_price::numeric * units_in_stock), 2), 0) INTO n, v_abans FROM antics;
  SELECT coalesce(round(sum(unit_price::numeric * units_in_stock), 2), 0) INTO v_despres FROM nous;
  INSERT INTO log_valor_estoc VALUES (n, v_abans, v_despres);
  RETURN NULL;
END $$;
CREATE TRIGGER trg_valor_estoc AFTER UPDATE ON products
  REFERENCING OLD TABLE AS antics NEW TABLE AS nous
  FOR EACH STATEMENT EXECUTE FUNCTION f_valor_estoc();
```


## Northwind — Arrays, JSON i tipus (pgobjrel)


### 1. Per a cada categoria, mostra `category_name`, un array amb els noms (`product_name`) dels seus productes **actius** (`discontinued = 0`) ordenats alfabèticament, i un array amb els països (`suppliers.country`) dels proveïdors d'aquests productes actius, sense repetits i ordenats alfabèticament. Fes servir `array_agg(... ORDER BY ...)`.

Referència:
```sql
SELECT c.category_name, array_agg(p.product_name ORDER BY p.product_name), array_agg(DISTINCT s.country ORDER BY s.country) FROM categories c JOIN products p ON p.category_id = c.category_id JOIN suppliers s ON s.supplier_id = p.supplier_id WHERE p.discontinued = 0 GROUP BY c.category_name
```

Alternativa — amb subconsultes `ARRAY(SELECT ...)` (ACCEPTADA):
```sql
SELECT category_name, ARRAY(SELECT product_name FROM products p WHERE p.category_id = c.category_id AND discontinued = 0 ORDER BY 1), ARRAY(SELECT DISTINCT s.country FROM products p JOIN suppliers s USING (supplier_id) WHERE p.category_id = c.category_id AND p.discontinued = 0 ORDER BY 1) FROM categories c
```

Incorrecta — sense `ORDER BY` dins de l'`array_agg`: l'ordre dels elements no és l'alfabètic (REBUTJADA: Result sets differ (comparing unordered)):
```sql
SELECT c.category_name, array_agg(p.product_name), array_agg(DISTINCT s.country) FROM categories c JOIN products p ON p.category_id = c.category_id JOIN suppliers s ON s.supplier_id = p.supplier_id WHERE p.discontinued = 0 GROUP BY c.category_name
```

Incorrecta — països repetits (sense `DISTINCT`) (REBUTJADA: Result sets differ (comparing unordered)):
```sql
SELECT c.category_name, array_agg(p.product_name ORDER BY p.product_name), array_agg(s.country ORDER BY s.country) FROM categories c JOIN products p ON p.category_id = c.category_id JOIN suppliers s ON s.supplier_id = p.supplier_id WHERE p.discontinued = 0 GROUP BY c.category_name
```

Incorrecta — no filtra els descatalogats (REBUTJADA: Result sets differ (comparing unordered)):
```sql
SELECT c.category_name, array_agg(p.product_name ORDER BY p.product_name), array_agg(DISTINCT s.country ORDER BY s.country) FROM categories c JOIN products p ON p.category_id = c.category_id JOIN suppliers s ON s.supplier_id = p.supplier_id GROUP BY c.category_name
```


### 2. La botiga web envia la llista de la compra d'un client com un array de noms de producte: `ARRAY['Tofu', 'Chai', 'Pizza margarita', 'Ikura', 'Chai']`. Escriu una consulta que, a partir d'aquest array escrit literalment a la consulta, retorni una fila per a **cada posició** de l'array: la posició (començant per 1), el nom tal com és a l'array i el `units_in_stock` del producte amb aquest nom (`NULL` si no existeix cap producte amb aquest nom). Fes servir `unnest(...) WITH ORDINALITY`.

Referència:
```sql
SELECT u.pos, u.nom, p.units_in_stock FROM unnest(ARRAY['Tofu', 'Chai', 'Pizza margarita', 'Ikura', 'Chai']) WITH ORDINALITY AS u(nom, pos) LEFT JOIN products p ON p.product_name = u.nom
```

Alternativa — amb `generate_subscripts` i una subconsulta escalar (ACCEPTADA):
```sql
SELECT i, a[i], (SELECT units_in_stock FROM products WHERE product_name = a[i]) FROM (SELECT ARRAY['Tofu', 'Chai', 'Pizza margarita', 'Ikura', 'Chai'] AS a) t, generate_subscripts(a, 1) AS i
```

Incorrecta — `JOIN` en lloc de `LEFT JOIN`: el producte inexistent desapareix (REBUTJADA: Wrong number of rows: got 4, expected 5):
```sql
SELECT u.pos, u.nom, p.units_in_stock FROM unnest(ARRAY['Tofu', 'Chai', 'Pizza margarita', 'Ikura', 'Chai']) WITH ORDINALITY AS u(nom, pos) JOIN products p ON p.product_name = u.nom
```

Incorrecta — `= ANY (...)` sobre la taula: perd les repeticions i el que no existeix, i la posició no és la de l'array (REBUTJADA: Wrong number of rows: got 3, expected 5):
```sql
SELECT row_number() OVER (), product_name, units_in_stock FROM products WHERE product_name = ANY (ARRAY['Tofu', 'Chai', 'Pizza margarita', 'Ikura', 'Chai'])
```

Incorrecta — alias de l'ordinalitat girats: `u(pos, nom)` posa el nom a la columna de posició (REBUTJADA: Result sets differ (comparing unordered)):
```sql
SELECT u.nom, u.pos, p.units_in_stock FROM unnest(ARRAY['Tofu', 'Chai', 'Pizza margarita', 'Ikura', 'Chai']) WITH ORDINALITY AS u(nom, pos) LEFT JOIN products p ON p.product_name = u.nom
```


### 3. Busca les comandes de l'any **1998** (`order_date`) que contenen productes de la categoria `Dairy Products` **i també** de la categoria `Seafood`, i que **no** contenen cap producte descatalogat. Mostra `order_id`, `customer_id` i un array amb els noms de les categories diferents de la comanda ordenats alfabèticament. Agrupa per comanda i fes servir operadors d'arrays al `HAVING`: `@>` (conté) i `&&` (tenen algun element en comú).

Referència:
```sql
SELECT o.order_id, o.customer_id, array_agg(DISTINCT c.category_name ORDER BY c.category_name) FROM orders o JOIN order_details d ON d.order_id = o.order_id JOIN products p ON p.product_id = d.product_id JOIN categories c ON c.category_id = p.category_id WHERE o.order_date >= DATE '1998-01-01' AND o.order_date < DATE '1999-01-01' GROUP BY o.order_id, o.customer_id HAVING array_agg(c.category_name) @> ARRAY['Dairy Products', 'Seafood']::varchar[] AND NOT array_agg(p.product_id) && (SELECT array_agg(product_id) FROM products WHERE discontinued = 1)
```

Alternativa — amb `bool_or` i `<@` (ACCEPTADA):
```sql
SELECT order_id, customer_id, array_agg(DISTINCT category_name ORDER BY category_name) FROM orders JOIN order_details USING (order_id) JOIN products USING (product_id) JOIN categories USING (category_id) WHERE extract(year FROM order_date) = 1998 GROUP BY 1, 2 HAVING '{Dairy Products,Seafood}'::text[] <@ array_agg(category_name::text) AND NOT bool_or(discontinued = 1)
```

Incorrecta — `&&` en lloc de `@>`: agafa les comandes que tenen alguna de les dues categories (REBUTJADA: Wrong number of rows: got more than 24, expected 24):
```sql
SELECT o.order_id, o.customer_id, array_agg(DISTINCT c.category_name ORDER BY c.category_name) FROM orders o JOIN order_details d ON d.order_id = o.order_id JOIN products p ON p.product_id = d.product_id JOIN categories c ON c.category_id = p.category_id WHERE o.order_date >= DATE '1998-01-01' GROUP BY o.order_id, o.customer_id HAVING array_agg(c.category_name) && ARRAY['Dairy Products', 'Seafood']::varchar[] AND NOT array_agg(p.product_id) && (SELECT array_agg(product_id) FROM products WHERE discontinued = 1)
```

Incorrecta — no exclou les comandes amb productes descatalogats (REBUTJADA: Wrong number of rows: got more than 24, expected 24):
```sql
SELECT o.order_id, o.customer_id, array_agg(DISTINCT c.category_name ORDER BY c.category_name) FROM orders o JOIN order_details d ON d.order_id = o.order_id JOIN products p ON p.product_id = d.product_id JOIN categories c ON c.category_id = p.category_id WHERE o.order_date >= DATE '1998-01-01' GROUP BY o.order_id, o.customer_id HAVING array_agg(c.category_name) @> ARRAY['Dairy Products', 'Seafood']::varchar[]
```

Incorrecta — filtra els descatalogats al `WHERE`: la comanda queda, només sense aquelles línies (REBUTJADA: Wrong number of rows: got more than 24, expected 24):
```sql
SELECT o.order_id, o.customer_id, array_agg(DISTINCT c.category_name ORDER BY c.category_name) FROM orders o JOIN order_details d ON d.order_id = o.order_id JOIN products p ON p.product_id = d.product_id JOIN categories c ON c.category_id = p.category_id WHERE o.order_date >= DATE '1998-01-01' AND p.discontinued = 0 GROUP BY o.order_id, o.customer_id HAVING array_agg(c.category_name) @> ARRAY['Dairy Products', 'Seafood']::varchar[]
```


### 4. La botiga web vol les comandes del client `ANATR` en JSON. Per a cada comanda d'aquest client, mostra `order_id` i un document `jsonb` amb aquesta forma:
`{"data": order_date, "empleat": last_name de l'empleat, "linies": [{"producte": product_name, "quantitat": quantity, "preu": unit_price de la línia}, ...]}`
on l'array `linies` té un objecte per cada línia de la comanda, **ordenades pel nom del producte**. Fes servir `jsonb_build_object` i `jsonb_agg(... ORDER BY ...)`. (L'ordre de les claus dins d'un objecte `jsonb` no importa.)

Referència:
```sql
SELECT o.order_id, jsonb_build_object('data', o.order_date, 'empleat', e.last_name, 'linies', jsonb_agg(jsonb_build_object('producte', p.product_name, 'quantitat', d.quantity, 'preu', d.unit_price) ORDER BY p.product_name)) FROM orders o JOIN employees e ON e.employee_id = o.employee_id JOIN order_details d ON d.order_id = o.order_id JOIN products p ON p.product_id = d.product_id WHERE o.customer_id = 'ANATR' GROUP BY o.order_id, o.order_date, e.last_name
```

Alternativa — amb una subconsulta correlacionada per a les línies i `to_jsonb` d'una fila (ACCEPTADA):
```sql
SELECT o.order_id, jsonb_build_object('empleat', (SELECT last_name FROM employees WHERE employee_id = o.employee_id), 'data', o.order_date, 'linies', (SELECT jsonb_agg(to_jsonb(x) ORDER BY x.producte) FROM (SELECT p.product_name AS producte, d.quantity AS quantitat, d.unit_price AS preu FROM order_details d JOIN products p USING (product_id) WHERE d.order_id = o.order_id) x)) FROM orders o WHERE o.customer_id = 'ANATR'
```

Incorrecta — `linies` sense `ORDER BY`: l'ordre de l'array no és el demanat (REBUTJADA: Result sets differ (comparing unordered)):
```sql
SELECT o.order_id, jsonb_build_object('data', o.order_date, 'empleat', e.last_name, 'linies', jsonb_agg(jsonb_build_object('producte', p.product_name, 'quantitat', d.quantity, 'preu', d.unit_price))) FROM orders o JOIN employees e ON e.employee_id = o.employee_id JOIN order_details d ON d.order_id = o.order_id JOIN products p ON p.product_id = d.product_id WHERE o.customer_id = 'ANATR' GROUP BY o.order_id, o.order_date, e.last_name
```

Incorrecta — `json_agg` d'un text: les línies queden com a cadenes en lloc d'objectes (REBUTJADA: Result sets differ (comparing unordered)):
```sql
SELECT o.order_id, jsonb_build_object('data', o.order_date, 'empleat', e.last_name, 'linies', jsonb_agg(jsonb_build_object('producte', p.product_name, 'quantitat', d.quantity, 'preu', d.unit_price)::text ORDER BY p.product_name)) FROM orders o JOIN employees e ON e.employee_id = o.employee_id JOIN order_details d ON d.order_id = o.order_id JOIN products p ON p.product_id = d.product_id WHERE o.customer_id = 'ANATR' GROUP BY o.order_id, o.order_date, e.last_name
```

Incorrecta — preu actual del producte (`products.unit_price`) en lloc del de la línia (REBUTJADA: Result sets differ (comparing unordered)):
```sql
SELECT o.order_id, jsonb_build_object('data', o.order_date, 'empleat', e.last_name, 'linies', jsonb_agg(jsonb_build_object('producte', p.product_name, 'quantitat', d.quantity, 'preu', p.unit_price) ORDER BY p.product_name)) FROM orders o JOIN employees e ON e.employee_id = o.employee_id JOIN order_details d ON d.order_id = o.order_id JOIN products p ON p.product_id = d.product_id WHERE o.customer_id = 'ANATR' GROUP BY o.order_id, o.order_date, e.last_name
```


### 5. Defineix aquests tipus i la funció que els fa servir:
- el tipus enumerat `estat_comanda` amb els valors `'pendent'`, `'enviada'` i `'endarrerida'`, **en aquest ordre**;
- el domini `percentatge`, basat en `numeric`, que només admeti valors entre 0 i 100 (tots dos inclosos; `NULL` sí que s'admet);
- el tipus compost `resum_comanda` amb els camps `order_id integer`, `client varchar`, `import numeric`, `descompte_mitja percentatge` i `estat estat_comanda`, en aquest ordre;
- la funció `resum(p_order_id integer) RETURNS resum_comanda`, que retorni per a una comanda: el seu identificador, el `customer_id`, l'import (suma de `unit_price * quantity * (1 - discount)` en `numeric`, arrodonida a 2 decimals), la mitjana dels descomptes de les línies en percentatge (`avg(discount::numeric) * 100`, arrodonida a 2 decimals) i l'estat: `'pendent'` si no té `shipped_date`, `'endarrerida'` si `shipped_date > required_date` i `'enviada'` en els altres casos. Si la comanda no existeix, excepció amb `ERRCODE = 'no_data_found'`.

Referència:
```sql
CREATE TYPE estat_comanda AS ENUM ('pendent', 'enviada', 'endarrerida');
CREATE DOMAIN percentatge AS numeric CHECK (VALUE BETWEEN 0 AND 100);
CREATE TYPE resum_comanda AS (order_id integer, client varchar, import numeric, descompte_mitja percentatge,
                              estat estat_comanda);
CREATE FUNCTION resum(p_order_id integer) RETURNS resum_comanda LANGUAGE plpgsql AS $$
DECLARE o orders%ROWTYPE; r resum_comanda;
BEGIN
  SELECT * INTO o FROM orders WHERE order_id = p_order_id;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'La comanda % no existeix', p_order_id USING ERRCODE = 'no_data_found';
  END IF;
  r.order_id := o.order_id;
  r.client := o.customer_id;
  SELECT round(sum(unit_price::numeric * quantity * (1 - discount::numeric)), 2),
         round(avg(discount::numeric) * 100, 2)
    INTO r.import, r.descompte_mitja FROM order_details WHERE order_id = p_order_id;
  r.estat := CASE WHEN o.shipped_date IS NULL THEN 'pendent'
                  WHEN o.shipped_date > o.required_date THEN 'endarrerida'
                  ELSE 'enviada' END;
  RETURN r;
END $$;
--@@TEST@@ SELECT (resum(10248)).*
--@@TEST@@ SELECT r.* FROM orders o CROSS JOIN LATERAL resum(o.order_id) r WHERE o.customer_id IN ('LILAS', 'QUICK', 'ALFKI')
--@@TEST@@ SELECT resum(10250) = ROW(10250, 'HANAR', 1552.60, 10, 'enviada')::resum_comanda
--@@TEST@@ SELECT enum_range(NULL::estat_comanda)::text
--@@TEST@@ SELECT (resum(order_id)).estat AS estat, count(*) FROM orders GROUP BY 1
--@@TEST@@ SELECT count(*) FROM orders WHERE (resum(order_id)).estat > 'pendent'
--@@TEST@@ SELECT 12.5::percentatge, NULL::percentatge
--@@TEST@@ SELECT 150::percentatge
--@@TEST@@ SELECT resum(1)
```

Alternativa — funció `LANGUAGE sql` que construeix la fila amb `ROW(...)`, i la validació en una funció PL/pgSQL que la crida (ACCEPTADA):
```sql
CREATE TYPE estat_comanda AS ENUM ('pendent', 'enviada', 'endarrerida');
CREATE DOMAIN percentatge numeric CONSTRAINT rang CHECK (VALUE >= 0 AND VALUE <= 100);
CREATE TYPE resum_comanda AS (order_id integer, client varchar, import numeric, descompte_mitja percentatge, estat estat_comanda);
CREATE FUNCTION resum_sql(p integer) RETURNS resum_comanda LANGUAGE sql AS $$
  SELECT ROW(o.order_id, o.customer_id,
    (SELECT round(sum(unit_price::numeric * quantity * (1 - discount::numeric)), 2) FROM order_details WHERE order_id = p),
    (SELECT round(avg(discount::numeric) * 100, 2) FROM order_details WHERE order_id = p),
    CASE WHEN o.shipped_date IS NULL THEN 'pendent' WHEN o.shipped_date > o.required_date THEN 'endarrerida' ELSE 'enviada' END)::resum_comanda
  FROM orders o WHERE o.order_id = p
$$;
CREATE FUNCTION resum(p_order_id integer) RETURNS resum_comanda LANGUAGE plpgsql AS $$
BEGIN
  IF NOT EXISTS (SELECT FROM orders WHERE order_id = p_order_id) THEN RAISE EXCEPTION 'no' USING ERRCODE = 'P0002'; END IF;
  RETURN resum_sql(p_order_id);
END $$;
```

Incorrecta — l'`ENUM` en un altre ordre (alfabètic): canvia `enum_range` i les comparacions `>` (REBUTJADA: Test 4 (SELECT enum_range(NULL::estat_comanda)::text): Result sets differ (comparing unordered)):
```sql
CREATE TYPE estat_comanda AS ENUM ('endarrerida', 'enviada', 'pendent');
CREATE DOMAIN percentatge AS numeric CHECK (VALUE BETWEEN 0 AND 100);
CREATE TYPE resum_comanda AS (order_id integer, client varchar, import numeric, descompte_mitja percentatge,
                              estat estat_comanda);
CREATE FUNCTION resum(p_order_id integer) RETURNS resum_comanda LANGUAGE plpgsql AS $$
DECLARE o orders%ROWTYPE; r resum_comanda;
BEGIN
  SELECT * INTO o FROM orders WHERE order_id = p_order_id;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'La comanda % no existeix', p_order_id USING ERRCODE = 'no_data_found';
  END IF;
  r.order_id := o.order_id;
  r.client := o.customer_id;
  SELECT round(sum(unit_price::numeric * quantity * (1 - discount::numeric)), 2),
         round(avg(discount::numeric) * 100, 2)
    INTO r.import, r.descompte_mitja FROM order_details WHERE order_id = p_order_id;
  r.estat := CASE WHEN o.shipped_date IS NULL THEN 'pendent'
                  WHEN o.shipped_date > o.required_date THEN 'endarrerida'
                  ELSE 'enviada' END;
  RETURN r;
END $$;
```

Incorrecta — domini sense la restricció `CHECK` (REBUTJADA: Test 8 (SELECT 150::percentatge): yours returns rows, the expected one gives an error (SQLSTATE 23514 check_violation)):
```sql
CREATE TYPE estat_comanda AS ENUM ('pendent', 'enviada', 'endarrerida');
CREATE DOMAIN percentatge AS numeric;
CREATE TYPE resum_comanda AS (order_id integer, client varchar, import numeric, descompte_mitja percentatge,
                              estat estat_comanda);
CREATE FUNCTION resum(p_order_id integer) RETURNS resum_comanda LANGUAGE plpgsql AS $$
DECLARE o orders%ROWTYPE; r resum_comanda;
BEGIN
  SELECT * INTO o FROM orders WHERE order_id = p_order_id;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'La comanda % no existeix', p_order_id USING ERRCODE = 'no_data_found';
  END IF;
  r.order_id := o.order_id;
  r.client := o.customer_id;
  SELECT round(sum(unit_price::numeric * quantity * (1 - discount::numeric)), 2),
         round(avg(discount::numeric) * 100, 2)
    INTO r.import, r.descompte_mitja FROM order_details WHERE order_id = p_order_id;
  r.estat := CASE WHEN o.shipped_date IS NULL THEN 'pendent'
                  WHEN o.shipped_date > o.required_date THEN 'endarrerida'
                  ELSE 'enviada' END;
  RETURN r;
END $$;
```

Incorrecta — `>=` en lloc de `>`: les comandes enviades el mateix dia límit surten com a endarrerides (REBUTJADA: Test 2 (SELECT r.* FROM orders o CROSS JOIN LATERAL resum(o.order...): Result sets differ (comparing unordered)):
```sql
CREATE TYPE estat_comanda AS ENUM ('pendent', 'enviada', 'endarrerida');
CREATE DOMAIN percentatge AS numeric CHECK (VALUE BETWEEN 0 AND 100);
CREATE TYPE resum_comanda AS (order_id integer, client varchar, import numeric, descompte_mitja percentatge,
                              estat estat_comanda);
CREATE FUNCTION resum(p_order_id integer) RETURNS resum_comanda LANGUAGE plpgsql AS $$
DECLARE o orders%ROWTYPE; r resum_comanda;
BEGIN
  SELECT * INTO o FROM orders WHERE order_id = p_order_id;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'La comanda % no existeix', p_order_id USING ERRCODE = 'no_data_found';
  END IF;
  r.order_id := o.order_id;
  r.client := o.customer_id;
  SELECT round(sum(unit_price::numeric * quantity * (1 - discount::numeric)), 2),
         round(avg(discount::numeric) * 100, 2)
    INTO r.import, r.descompte_mitja FROM order_details WHERE order_id = p_order_id;
  r.estat := CASE WHEN o.shipped_date IS NULL THEN 'pendent'
                  WHEN o.shipped_date >= o.required_date THEN 'endarrerida'
                  ELSE 'enviada' END;
  RETURN r;
END $$;
```

Incorrecta — el descompte mitjà com a fracció (0,05) en lloc de percentatge (5) (REBUTJADA: Test 2 (SELECT r.* FROM orders o CROSS JOIN LATERAL resum(o.order...): Result sets differ (comparing unordered)):
```sql
CREATE TYPE estat_comanda AS ENUM ('pendent', 'enviada', 'endarrerida');
CREATE DOMAIN percentatge AS numeric CHECK (VALUE BETWEEN 0 AND 100);
CREATE TYPE resum_comanda AS (order_id integer, client varchar, import numeric, descompte_mitja percentatge,
                              estat estat_comanda);
CREATE FUNCTION resum(p_order_id integer) RETURNS resum_comanda LANGUAGE plpgsql AS $$
DECLARE o orders%ROWTYPE; r resum_comanda;
BEGIN
  SELECT * INTO o FROM orders WHERE order_id = p_order_id;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'La comanda % no existeix', p_order_id USING ERRCODE = 'no_data_found';
  END IF;
  r.order_id := o.order_id;
  r.client := o.customer_id;
  SELECT round(sum(unit_price::numeric * quantity * (1 - discount::numeric)), 2),
         round(avg(discount::numeric), 2)
    INTO r.import, r.descompte_mitja FROM order_details WHERE order_id = p_order_id;
  r.estat := CASE WHEN o.shipped_date IS NULL THEN 'pendent'
                  WHEN o.shipped_date > o.required_date THEN 'endarrerida'
                  ELSE 'enviada' END;
  RETURN r;
END $$;
```


### 6. La botiga web envia les comandes noves com a documents JSON com aquest:
`{"client": "ALFKI", "empleat": 3, "data": "1998-05-07", "linies": [{"producte": 11, "quantitat": 5}, {"producte": 72, "quantitat": 10, "descompte": 0.05}]}`
Crea la funció `importar_comanda(p_doc jsonb) RETURNS integer` que l'insereixi i retorni el nou `order_id`:
- a `orders`: `order_id` = màxim + 1, `customer_id` = `client`, `employee_id` = `empleat`, `order_date` = `data` (o `current_date` si el document no porta `data`), `required_date` = `order_date` + 14 dies, `freight` = 0 i la resta de columnes a `NULL`;
- a `order_details`, una línia per cada element de `linies` (fes servir `jsonb_array_elements`): `product_id` = `producte`, `quantity` = `quantitat`, `unit_price` = el preu actual del producte a `products` i `discount` = `descompte` (0 si no hi és).
Validacions: si el document no té `client`, o `linies` no és un array (`jsonb_typeof`) o és buit, excepció amb `ERRCODE = 'invalid_parameter_value'`; si alguna línia no té `quantitat` o no és positiva, `ERRCODE = 'check_violation'` (ho pots comprovar amb `jsonb_path_exists`); si algun producte no existeix, `ERRCODE = 'no_data_found'`. Si el client no existeix, ja ho impedeix la clau forana.

Referència:
```sql
CREATE FUNCTION importar_comanda(p_doc jsonb) RETURNS integer LANGUAGE plpgsql AS $$
DECLARE v_id integer; l jsonb; v_preu real;
BEGIN
  IF p_doc->>'client' IS NULL OR jsonb_typeof(p_doc->'linies') IS DISTINCT FROM 'array'
     OR jsonb_array_length(p_doc->'linies') = 0 THEN
    RAISE EXCEPTION 'Document de comanda incomplet' USING ERRCODE = 'invalid_parameter_value';
  END IF;
  IF jsonb_path_exists(p_doc, '$.linies[*] ? (!exists(@.quantitat) || @.quantitat <= 0)') THEN
    RAISE EXCEPTION 'Hi ha línies sense quantitat o amb quantitat no positiva' USING ERRCODE = 'check_violation';
  END IF;
  SELECT coalesce(max(order_id), 0) + 1 INTO v_id FROM orders;
  INSERT INTO orders (order_id, customer_id, employee_id, order_date, required_date, freight)
  VALUES (v_id, p_doc->>'client', (p_doc->>'empleat')::integer, coalesce((p_doc->>'data')::date, current_date),
          coalesce((p_doc->>'data')::date, current_date) + 14, 0);
  FOR l IN SELECT * FROM jsonb_array_elements(p_doc->'linies') LOOP
    SELECT unit_price INTO v_preu FROM products WHERE product_id = (l->>'producte')::integer;
    IF NOT FOUND THEN
      RAISE EXCEPTION 'El producte % no existeix', l->>'producte' USING ERRCODE = 'no_data_found';
    END IF;
    INSERT INTO order_details (order_id, product_id, unit_price, quantity, discount)
    VALUES (v_id, (l->>'producte')::integer, v_preu, (l->>'quantitat')::integer, coalesce((l->>'descompte')::real, 0));
  END LOOP;
  RETURN v_id;
END $$;
--@@TEST@@ SELECT importar_comanda('{"client": "ALFKI", "empleat": 3, "data": "1998-05-07", "linies": [{"producte": 11, "quantitat": 5}, {"producte": 72, "quantitat": 10, "descompte": 0.05}]}')
--@@TEST@@ SELECT importar_comanda('{"client": "BOLID", "empleat": 4, "linies": [{"producte": 3, "quantitat": 2, "descompte": 0}]}')
--@@TEST@@ SELECT * FROM orders WHERE order_id > 11077 ORDER BY order_id
--@@TEST@@ SELECT * FROM order_details WHERE order_id > 11077 ORDER BY 1, 2
--@@TEST@@ SELECT importar_comanda('{"empleat": 3, "linies": [{"producte": 11, "quantitat": 5}]}')
--@@TEST@@ SELECT importar_comanda('{"client": "ALFKI", "empleat": 3, "linies": []}')
--@@TEST@@ SELECT importar_comanda('{"client": "ALFKI", "empleat": 3, "linies": {"producte": 11, "quantitat": 5}}')
--@@TEST@@ SELECT importar_comanda('{"client": "ALFKI", "empleat": 3, "linies": [{"producte": 11, "quantitat": 5}, {"producte": 12, "quantitat": 0}]}')
--@@TEST@@ SELECT importar_comanda('{"client": "ALFKI", "empleat": 3, "linies": [{"producte": 11, "quantitat": 5}, {"producte": 12}]}')
--@@TEST@@ SELECT importar_comanda('{"client": "ALFKI", "empleat": 3, "linies": [{"producte": 11, "quantitat": 5}, {"producte": 500, "quantitat": 1}]}')
--@@TEST@@ SELECT importar_comanda('{"client": "ZZZZZ", "empleat": 3, "linies": [{"producte": 11, "quantitat": 5}]}')
```

Alternativa — validant amb `->`/`->>` i inserint totes les línies amb un `INSERT ... SELECT` sobre `jsonb_to_recordset` (ACCEPTADA):
```sql
CREATE FUNCTION importar_comanda(p_doc jsonb) RETURNS integer AS $$
DECLARE n integer; d date := coalesce((p_doc->>'data')::date, current_date);
BEGIN
  IF NOT (p_doc ? 'client') OR p_doc->'client' = 'null' OR jsonb_typeof(p_doc->'linies') <> 'array' OR p_doc->'linies' = '[]' OR p_doc->'linies' IS NULL THEN
    RAISE EXCEPTION 'doc' USING ERRCODE = '22023'; END IF;
  IF EXISTS (SELECT FROM jsonb_to_recordset(p_doc->'linies') AS x(quantitat integer) WHERE x.quantitat IS NULL OR x.quantitat <= 0) THEN
    RAISE EXCEPTION 'quantitat' USING ERRCODE = '23514'; END IF;
  IF EXISTS (SELECT FROM jsonb_to_recordset(p_doc->'linies') AS x(producte integer) LEFT JOIN products p ON p.product_id = x.producte WHERE p.product_id IS NULL) THEN
    RAISE EXCEPTION 'producte' USING ERRCODE = 'P0002'; END IF;
  n := (SELECT max(order_id) + 1 FROM orders);
  INSERT INTO orders (order_id, customer_id, employee_id, order_date, required_date, freight)
  VALUES (n, p_doc->>'client', (p_doc->>'empleat')::int, d, d + 14, 0);
  INSERT INTO order_details SELECT n, x.producte, p.unit_price, x.quantitat, coalesce(x.descompte, 0)
    FROM jsonb_to_recordset(p_doc->'linies') AS x(producte integer, quantitat integer, descompte real)
    JOIN products p ON p.product_id = x.producte;
  RETURN n;
END $$ LANGUAGE plpgsql;
```

Incorrecta — `p_doc->'client'` (jsonb) en lloc de `->>` (text): el `customer_id` queda amb cometes i la clau forana falla (REBUTJADA: Test 1 (SELECT importar_comanda('{"client": "ALFKI", "empleat": 3...): yours gives an error (SQLSTATE 22001 string_data_right_truncation), the expected one returns rows):
```sql
CREATE FUNCTION importar_comanda(p_doc jsonb) RETURNS integer LANGUAGE plpgsql AS $$
DECLARE v_id integer; l jsonb; v_preu real;
BEGIN
  IF p_doc->>'client' IS NULL OR jsonb_typeof(p_doc->'linies') IS DISTINCT FROM 'array'
     OR jsonb_array_length(p_doc->'linies') = 0 THEN
    RAISE EXCEPTION 'Document de comanda incomplet' USING ERRCODE = 'invalid_parameter_value';
  END IF;
  IF jsonb_path_exists(p_doc, '$.linies[*] ? (!exists(@.quantitat) || @.quantitat <= 0)') THEN
    RAISE EXCEPTION 'Hi ha línies sense quantitat o amb quantitat no positiva' USING ERRCODE = 'check_violation';
  END IF;
  SELECT coalesce(max(order_id), 0) + 1 INTO v_id FROM orders;
  INSERT INTO orders (order_id, customer_id, employee_id, order_date, required_date, freight)
  VALUES (v_id, (p_doc->'client')::text, (p_doc->>'empleat')::integer, coalesce((p_doc->>'data')::date, current_date),
          coalesce((p_doc->>'data')::date, current_date) + 14, 0);
  FOR l IN SELECT * FROM jsonb_array_elements(p_doc->'linies') LOOP
    SELECT unit_price INTO v_preu FROM products WHERE product_id = (l->>'producte')::integer;
    IF NOT FOUND THEN
      RAISE EXCEPTION 'El producte % no existeix', l->>'producte' USING ERRCODE = 'no_data_found';
    END IF;
    INSERT INTO order_details (order_id, product_id, unit_price, quantity, discount)
    VALUES (v_id, (l->>'producte')::integer, v_preu, (l->>'quantitat')::integer, coalesce((l->>'descompte')::real, 0));
  END LOOP;
  RETURN v_id;
END $$;
```

Incorrecta — no valida les quantitats (REBUTJADA: Test 8 (SELECT importar_comanda('{"client": "ALFKI", "empleat": 3...): yours returns rows, the expected one gives an error (SQLSTATE 23514 check_violation)):
```sql
CREATE FUNCTION importar_comanda(p_doc jsonb) RETURNS integer LANGUAGE plpgsql AS $$
DECLARE v_id integer; l jsonb; v_preu real;
BEGIN
  IF p_doc->>'client' IS NULL OR jsonb_typeof(p_doc->'linies') IS DISTINCT FROM 'array'
     OR jsonb_array_length(p_doc->'linies') = 0 THEN
    RAISE EXCEPTION 'Document de comanda incomplet' USING ERRCODE = 'invalid_parameter_value';
  END IF;
  SELECT coalesce(max(order_id), 0) + 1 INTO v_id FROM orders;
  INSERT INTO orders (order_id, customer_id, employee_id, order_date, required_date, freight)
  VALUES (v_id, p_doc->>'client', (p_doc->>'empleat')::integer, coalesce((p_doc->>'data')::date, current_date),
          coalesce((p_doc->>'data')::date, current_date) + 14, 0);
  FOR l IN SELECT * FROM jsonb_array_elements(p_doc->'linies') LOOP
    SELECT unit_price INTO v_preu FROM products WHERE product_id = (l->>'producte')::integer;
    IF NOT FOUND THEN
      RAISE EXCEPTION 'El producte % no existeix', l->>'producte' USING ERRCODE = 'no_data_found';
    END IF;
    INSERT INTO order_details (order_id, product_id, unit_price, quantity, discount)
    VALUES (v_id, (l->>'producte')::integer, v_preu, (l->>'quantitat')::integer, coalesce((l->>'descompte')::real, 0));
  END LOOP;
  RETURN v_id;
END $$;
```

Incorrecta — sense `coalesce` per a la data: si el document no porta `data`, la comanda queda sense dates (REBUTJADA: Test 3 (SELECT * FROM orders WHERE order_id > 11077 ORDER BY orde...): Result sets differ (comparing unordered)):
```sql
CREATE FUNCTION importar_comanda(p_doc jsonb) RETURNS integer LANGUAGE plpgsql AS $$
DECLARE v_id integer; l jsonb; v_preu real;
BEGIN
  IF p_doc->>'client' IS NULL OR jsonb_typeof(p_doc->'linies') IS DISTINCT FROM 'array'
     OR jsonb_array_length(p_doc->'linies') = 0 THEN
    RAISE EXCEPTION 'Document de comanda incomplet' USING ERRCODE = 'invalid_parameter_value';
  END IF;
  IF jsonb_path_exists(p_doc, '$.linies[*] ? (!exists(@.quantitat) || @.quantitat <= 0)') THEN
    RAISE EXCEPTION 'Hi ha línies sense quantitat o amb quantitat no positiva' USING ERRCODE = 'check_violation';
  END IF;
  SELECT coalesce(max(order_id), 0) + 1 INTO v_id FROM orders;
  INSERT INTO orders (order_id, customer_id, employee_id, order_date, required_date, freight)
  VALUES (v_id, p_doc->>'client', (p_doc->>'empleat')::integer, (p_doc->>'data')::date,
          (p_doc->>'data')::date + 14, 0);
  FOR l IN SELECT * FROM jsonb_array_elements(p_doc->'linies') LOOP
    SELECT unit_price INTO v_preu FROM products WHERE product_id = (l->>'producte')::integer;
    IF NOT FOUND THEN
      RAISE EXCEPTION 'El producte % no existeix', l->>'producte' USING ERRCODE = 'no_data_found';
    END IF;
    INSERT INTO order_details (order_id, product_id, unit_price, quantity, discount)
    VALUES (v_id, (l->>'producte')::integer, v_preu, (l->>'quantitat')::integer, coalesce((l->>'descompte')::real, 0));
  END LOOP;
  RETURN v_id;
END $$;
```

Incorrecta — ignora el descompte (REBUTJADA: Test 4 (SELECT * FROM order_details WHERE order_id > 11077 ORDER ...): Result sets differ (comparing unordered)):
```sql
CREATE FUNCTION importar_comanda(p_doc jsonb) RETURNS integer LANGUAGE plpgsql AS $$
DECLARE v_id integer; l jsonb; v_preu real;
BEGIN
  IF p_doc->>'client' IS NULL OR jsonb_typeof(p_doc->'linies') IS DISTINCT FROM 'array'
     OR jsonb_array_length(p_doc->'linies') = 0 THEN
    RAISE EXCEPTION 'Document de comanda incomplet' USING ERRCODE = 'invalid_parameter_value';
  END IF;
  IF jsonb_path_exists(p_doc, '$.linies[*] ? (!exists(@.quantitat) || @.quantitat <= 0)') THEN
    RAISE EXCEPTION 'Hi ha línies sense quantitat o amb quantitat no positiva' USING ERRCODE = 'check_violation';
  END IF;
  SELECT coalesce(max(order_id), 0) + 1 INTO v_id FROM orders;
  INSERT INTO orders (order_id, customer_id, employee_id, order_date, required_date, freight)
  VALUES (v_id, p_doc->>'client', (p_doc->>'empleat')::integer, coalesce((p_doc->>'data')::date, current_date),
          coalesce((p_doc->>'data')::date, current_date) + 14, 0);
  FOR l IN SELECT * FROM jsonb_array_elements(p_doc->'linies') LOOP
    SELECT unit_price INTO v_preu FROM products WHERE product_id = (l->>'producte')::integer;
    IF NOT FOUND THEN
      RAISE EXCEPTION 'El producte % no existeix', l->>'producte' USING ERRCODE = 'no_data_found';
    END IF;
    INSERT INTO order_details (order_id, product_id, unit_price, quantity, discount)
    VALUES (v_id, (l->>'producte')::integer, v_preu, (l->>'quantitat')::integer, 0);
  END LOOP;
  RETURN v_id;
END $$;
```

