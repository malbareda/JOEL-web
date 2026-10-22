# miniwind — enunciats a revisar

## Miniwind QT — Join 04
- Usa `DISTINCTROW` (específic de MySQL). Enunciat generat: Mostra, sense repeticions, el nom i el cognom de l'empleat i el nom i el cognom del client que s'han relacionat alguna vegada a través d'una comanda (distingint clarament les columnes de l'empleat de les del client). Ordena pel cognom i el nom de l'empleat.

## Miniwind QT — Test 6
- Usa la funció `DATEDIFF` de MySQL. Enunciat generat: Mostra, sense repeticions, el codi de l'empleat (`employee_id`) responsable de les comandes que s'han trigat més de 2 dies a enviar (diferència entre `shipped_date` i `order_date`). Ordena de major a menor codi d'empleat.

## Miniwind QT — Funcions 01
- Usa les funcions `CEIL` i `FLOOR` de MySQL. Enunciat generat: Mostra l'identificador (`id`), el nom (`product_name`), el preu de venda (`list_price`) arrodonit a l'alça i el preu de cost (`standard_cost`) arrodonit a la baixa dels productes de la categoria 'Soups'.
- Usa les funcions `ROUND` i `ABS` de MySQL. Enunciat generat: Mostra l'identificador (`id`), el nom (`product_name`), el preu de venda (`list_price`), el preu de cost (`standard_cost`) i la diferència entre tots dos preus arrodonida a dos decimals, dels productes amb més de 2 de diferència entre el preu de venda i el de cost. Ordena per identificador de producte.
- Usa la funció `CONCAT` de MySQL. Enunciat generat: Mostra en una única columna el cognom i el nom dels empleats separats per una coma i un espai (per exemple, «Polet, Seila»). Ordena pel cognom.
- Usa les funcions `CONCAT` i `LEFT` de MySQL. Enunciat generat: Mostra en una única columna les dues primeres lletres del nom i les dues primeres lletres del cognom de cada client, ordenades alfabèticament.
- Usa les funcions `UPPER`, `LOWER` i `REPLACE` de MySQL. Enunciat generat: Mostra el cognom (`last_name`) en majúscules, el nom (`first_name`) en minúscules i el correu (`email_address`) de cada client substituint la terminació '.edu' per '.cat'. Ordena pel cognom i el nom.
- Usa la funció `LENGTH` de MySQL. Enunciat generat: Mostra el nom (`first_name`) i el cognom (`last_name`) dels clients el nom dels quals té una longitud superior a 5, o bé la combinació de nom i cognom té una longitud superior a 11, sempre que, a més, el cognom tingui una longitud superior a 5. Ordena pel nom i el cognom.
- Usa la funció `SUBSTR` de MySQL (depèn de posicions fixes del nom). Enunciat generat: Mostra el nom dels productes sense el prefix comú 'Northwind Traders ' (les 18 primeres posicions del nom). Ordena el resultat alfabèticament.
- Usa la funció `IFNULL` de MySQL. Enunciat generat: Mostra l'identificador (`id`), la data (`order_date`) i la data d'enviament (`shipped_date`) de les comandes; si una comanda encara no s'ha enviat, mostra 'PENDENT' com a data d'enviament. Ordena per identificador de comanda.
- Usa la funció condicional `IF` de MySQL. Enunciat generat: Mostra l'identificador (`id`), el codi (`product_code`), el preu de cost (`standard_cost`) i el preu de venda (`list_price`) dels productes, i una columna addicional amb el valor 'MARGE ALT' si la diferència entre el preu de venda i el de cost supera 3, o 'MARGE NORMAL' en cas contrari.
- Usa l'expressió `CASE` (consulta complexa amb diversos trams). Enunciat generat: Mostra l'identificador (`id`), el codi (`product_code`), el preu de cost (`standard_cost`) i el preu de venda (`list_price`) dels productes, i una columna addicional amb el marge: 'MARGE MOLT ALT' si la diferència entre el preu de venda i el de cost supera 5, 'MARGE ALT' si està entre 3 (exclòs) i 5, 'MARGE NORMAL' si està entre 2 (exclòs) i 3, i 'MARGE BAIX' en cas contrari. Ordena per identificador.

## Miniwind QT — Funcions 02
- `LEFT JOIN` amb `COUNT` per incloure productes sense comandes. Enunciat generat: Mostra, per cada producte, l'identificador (`id`), el codi (`product_code`), el nom (`product_name`) i quantes vegades s'ha demanat en alguna comanda (línies de `order_details`), incloent-hi amb un 0 els productes que no s'han demanat mai. Ordena per identificador.
- Usa les funcions `DATE` i `YEAR` de MySQL. Enunciat generat: Mostra els 2 dies de l'any 2006 en què s'han venut més unitats de producte en total. De cada dia, mostra la data (sense hora) i la suma de quantitats (`quantity`). Ordena de més a menys unitats venudes.
- Usa les funcions `MONTH` i `YEAR` de MySQL; consulta amb diversos `JOIN` i agregació. Enunciat generat: Mostra el nom (`first_name`), el cognom (`last_name`) del client, el nom del producte (`product_name`) i l'import total a pagar de cada producte (suma de `quantity * unit_price`), dels clients que han fet alguna comanda durant l'abril de 2006. Ordena pel cognom i, en empat, pel nom del producte.
- Usa les funcions `MONTH` i `YEAR` de MySQL. Enunciat generat: Mostra, per cada mes de l'any 2006 en què s'hagin emès factures, el número de mes i l'import total de les despeses d'enviament (`shipping_fee`) facturades aquell mes.
- Consulta complexa: agrupació per categoria amb `HAVING COUNT(...) >= 2`. Enunciat generat: Mostra el nom (`first_name`) i el cognom (`last_name`) dels clients que han fet comandes de dos o més productes de la mateixa categoria (`category`).

## Miniwind QT — Join 05
- Usa la funció `MONTH` de MySQL. Enunciat generat: Mostra l'identificador de la factura (com a `invoice_id`), el nom (`first_name`) i el cognom (`last_name`) del client i l'import a pagar (`amount_due`) de les factures (`invoices`) emeses durant el mes de març (taules `orders`, `invoices` i `customers`).
- Usa la funció `DATE` de MySQL. Enunciat generat: Mostra el nom (`first_name`) i el cognom (`last_name`) de l'empleat, l'identificador de la comanda (com a `order_id`) i la data de la comanda sense hora (com a `order_date`) de les comandes que ha gestionat cada empleat (taules `employees` i `orders`).
- Usa la funció `DATE` de MySQL. Enunciat generat: Mostra l'identificador de la comanda (com a `order_id`), el nom de l'estat (`status_name`) i la data de la comanda sense hora (com a `order_date`) de totes les comandes (taules `orders` i `orders_status`).

## Miniwind QT — Join 03
- Usa `NVL` (sinònim d'`IFNULL`, específic de MySQL/Oracle). Enunciat generat: Mostra l'identificador (`id`) i el nom (`product_name`) de tots els productes i la quantitat demanada (`quantity`); dels que s'han demanat també ha de sortir l'identificador de la comanda (`order_id`), i dels que no, aquest identificador ha de sortir com a 0. Ordena per identificador de producte i, en empat, per identificador de comanda.

## Miniwind QT — Barrejades 01
- Usa les funcions `YEAR` i `MONTH` de MySQL. Enunciat generat: Mostra totes les dades de les factures (`invoices`) emeses el març o l'abril de 2006 que incloguin algun producte amb 'beer' en el nom. Ordena per identificador de factura.
- Usa la funció `GROUP_CONCAT` de MySQL. Enunciat generat: Mostra, per cada client, el seu identificador (`id`), el nom (`first_name`), el cognom (`last_name`) i els identificadors de totes les seves comandes agrupats en una sola línia per client.
- Consulta complexa amb `HAVING COUNT(DISTINCT ...)`. Enunciat generat: Mostra el nom (`first_name`) i el cognom (`last_name`) dels empleats que han venut més de 5 productes diferents.

## Miniwind QT — Barrejades 02
- Consulta complexa amb subconsulta correlacionada per trobar el màxim. Enunciat generat: Mostra el nom (`first_name`) i el cognom (`last_name`) dels clients que han fet el màxim nombre de comandes.
- Usa la funció `IFNULL` de MySQL. Enunciat generat: Mostra, per cada empleat, el seu identificador (`id`) i els diners que ha generat en vendes (suma de `quantity * unit_price`); si no ha venut res, ha de sortir 0.
- Consulta complexa: `AVG` sobre una subconsulta (taula derivada) amb `IFNULL`. Enunciat generat: Mostra la mitjana dels diners venuts pels empleats (mitjana, sobre el conjunt d'empleats, de la suma de `quantity * unit_price` de cadascun, comptant 0 els que no han venut res).
- Consulta molt complexa: subconsulta imbricada amb `IFNULL` per comparar amb la mitjana. Enunciat generat: Mostra el nom (`first_name`), el cognom (`last_name`) i l'import venut dels empleats que han venut (en diners) més que la mitjana de tots els empleats. Ordena alfabèticament pel cognom i el nom.
- Usa `UNION`. Enunciat generat: Mostra el nom (`first_name`) i el cognom (`last_name`) de tots els empleats i de tots els clients en una sola llista, ordenada pel cognom i el nom.
- Consulta complexa amb subconsulta per trobar el màxim nombre de línies. Enunciat generat: Mostra l'identificador (`order_id`) de les comandes que tenen el màxim nombre de línies de detall.

## Miniwind QT — Subconsultes 01
- Consulta complexa: subconsulta amb `GROUP BY ... ORDER BY COUNT(*) LIMIT 1`. Enunciat generat: Mostra totes les dades dels clients de l'estat (`state_province`) que té més clients.
- Consulta complexa: agregació per comanda i selecció del màxim import. Enunciat generat: Mostra l'import més alt pagat en una sola comanda d'entre les comandes pagades amb targeta de crèdit (`payment_type` igual a 'Credit Card'), calculant l'import com la suma de `quantity * unit_price` de cada comanda.
- Consulta complexa: subconsulta amb `GROUP BY ... LIMIT 1` per al mínim. Enunciat generat: Mostra l'identificador (`id`), el nom (`first_name`) i el cognom (`last_name`) dels clients que, d'entre els que han fet comandes, n'han fet menys.
- Consulta complexa: subconsulta amb `GROUP BY ... LIMIT 1` per al màxim. Enunciat generat: Mostra l'identificador (`id`), el nom (`first_name`) i el cognom (`last_name`) dels clients que han fet més comandes.
- Consulta complexa: subconsulta amb `GROUP BY ... LIMIT 1` filtrant per ciutat. Enunciat generat: Mostra l'identificador (`id`), el nom (`first_name`) i el cognom (`last_name`) dels clients de la ciutat de 'Fresno' que han fet menys comandes.
- Consulta complexa: subconsulta `IN` amb `LIMIT 2`. Enunciat generat: Mostra el nom (`product_name`) dels dos productes més demanats en comandes. Ordena'ls alfabèticament pel nom.
- Usa `< ALL (subconsulta)`. Enunciat generat: Mostra el nom (`product_name`) dels productes el preu de venda (`list_price`) dels quals és inferior al preu de cost (`standard_cost`) de tots els productes de la categoria 'Pasta'. Ordena per identificador.

## Miniwind QT — Funcions 01 (actualitzat 25/26)
- Usa les funcions `CEIL` i `FLOOR` de MySQL. Enunciat generat: Mostra l'identificador (`id`), el nom (`product_name`), el preu de venda (`list_price`) arrodonit a l'alça i el preu de cost (`standard_cost`) arrodonit a la baixa dels productes de la categoria 'Soups'.
- Usa les funcions `ROUND` i `ABS` de MySQL. Enunciat generat: Mostra l'identificador (`id`), el nom (`product_name`), el preu de venda (`list_price`), el preu de cost (`standard_cost`) i la diferència entre tots dos preus arrodonida a dos decimals, dels productes amb més de 2 de diferència. Ordena per identificador de producte.
- Usa la funció `CONCAT` de MySQL. Enunciat generat: Mostra en una única columna el cognom i el nom dels empleats separats per una coma i un espai (per exemple, «Polet, Seila»). Ordena pel cognom.
- Usa les funcions `CONCAT` i `LEFT` de MySQL. Enunciat generat: Mostra en una única columna les dues primeres lletres del nom i les dues primeres lletres del cognom de cada client, ordenades alfabèticament.
- Usa les funcions `UCASE`, `LCASE` i `REPLACE` de MySQL. Enunciat generat: Mostra el cognom (`last_name`) en majúscules, el nom (`first_name`) en minúscules i el correu (`email_address`) de cada client substituint la terminació '.edu' per '.cat'. Ordena pel cognom i el nom.
- Usa la funció `LENGTH` de MySQL. Enunciat generat: Mostra el nom (`first_name`) i el cognom (`last_name`) dels clients el nom dels quals té una longitud superior a 5, o bé la combinació de nom i cognom té una longitud superior a 11, sempre que, a més, el cognom tingui una longitud superior a 5. Ordena pel nom i el cognom.
- Usa la funció `IFNULL` de MySQL. Enunciat generat: Mostra l'identificador (`id`), la data (`order_date`) i la data d'enviament (`shipped_date`) de les comandes; si una comanda encara no s'ha enviat, mostra 'PENDENT' com a data d'enviament. Ordena per identificador de comanda.
- Usa la funció `ROUND` de MySQL. Enunciat generat: Mostra el nom del producte (`product_name`) i el preu de venda (`list_price`) amb un descompte del 10% aplicat, arrodonit a dos decimals.
- Usa la funció `SUBSTR` de MySQL (depèn de posicions fixes del nom). Enunciat generat: Mostra el nom dels productes sense el prefix comú 'Northwind Traders ' (les 18 primeres posicions del nom). Ordena el resultat alfabèticament.
- Usa la funció `YEAR` de MySQL. Enunciat generat: Mostra els anys en què s'ha fet alguna comanda.
- Usa la funció `MONTH` de MySQL. Enunciat generat: Mostra els mesos en què s'han fet comandes durant l'any 2006.

## Miniwind QT — Funcions 0 (actualitzat 26/27)
- Usa les funcions `CEIL` i `FLOOR` de MySQL. Enunciat generat: Mostra l'identificador (`id`), el nom (`product_name`), el preu de venda (`list_price`) arrodonit a l'alça i el preu de cost (`standard_cost`) arrodonit a la baixa dels productes de la categoria 'Soups'.
- Usa la funció `ROUND` de MySQL. Enunciat generat: Mostra l'identificador (`id`), el nom (`product_name`), el preu de venda (`list_price`), el preu de cost (`standard_cost`) i la diferència entre tots dos preus arrodonida a dos decimals, dels productes en què la diferència entre el preu de venda i el de cost és superior a 2. Ordena per identificador de producte.
- Usa la funció `CONCAT` de MySQL. Enunciat generat: Mostra en una única columna el cognom i el nom dels empleats separats per una coma i un espai (per exemple, «Polet, Seila»). Ordena pel cognom.
- Usa les funcions `CONCAT` i `LEFT` de MySQL. Enunciat generat: Mostra en una única columna les dues primeres lletres del nom i les dues primeres lletres del cognom de cada client, ordenades alfabèticament.
- Usa les funcions `UCASE`, `LCASE` i `REPLACE` de MySQL. Enunciat generat: Mostra el cognom (`last_name`) en majúscules, el nom (`first_name`) en minúscules i el correu (`email_address`) de cada client substituint la terminació '.edu' per '.cat'. Ordena pel cognom i el nom.
- Usa la funció `IFNULL` de MySQL. Enunciat generat: Mostra l'identificador (`id`), la data (`order_date`) i la data d'enviament (`shipped_date`) de les comandes; si una comanda encara no s'ha enviat, mostra 'PENDENT' com a data d'enviament. Ordena per identificador de comanda.
- Usa la funció `ROUND` de MySQL. Enunciat generat: Mostra el nom del producte (`product_name`) i el preu de venda (`list_price`) amb un descompte del 10% aplicat, arrodonit a dos decimals.
- Usa la funció `YEAR` de MySQL. Enunciat generat: Mostra els anys en què s'ha fet alguna comanda.
- Usa la funció `MONTH` de MySQL. Enunciat generat: Mostra els mesos en què s'han fet comandes durant l'any 2006.
