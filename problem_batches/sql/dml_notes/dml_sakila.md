# Notes de verificació — dml_sakila.json

Corrector real: `dmoj.checkers.mysqlwrite.check(alternativa, referència, database="sakila")`. Columnes: alternativa acceptada (ha de ser True), incorrecta rebutjada (ha de ser False), referència contra si mateixa amb 2 s de pausa (ha de ser igual), taules canviades.


## Sakila — INSERT avançat

### Q1
- Referència: `INSERT INTO category (name) VALUES ('Anime'), ('Western')`
- Alternativa: `INSERT INTO category (name) SELECT 'Anime' UNION ALL SELECT 'Western'` → acceptada: **True**
- Incorrecta: `INSERT INTO category (name) VALUES ('Anime')` → acceptada: **False** (The database's final content does not match what was expected after running your statement.)
- Referència vs referència amb 2 s de pausa: idèntic = **True**; taules canviades: category

### Q2
- Referència: `INSERT INTO city (city, country_id) SELECT 'Sabadell', country_id FROM country WHERE country = 'Spain'`
- Alternativa: `INSERT INTO city (city, country_id) VALUES ('Sabadell', (SELECT country_id FROM country WHERE country = 'Spain'))` → acceptada: **True**
- Incorrecta: `INSERT INTO city (city, country_id) SELECT 'Sabadell', country_id FROM country WHERE country = 'Portugal'` → acceptada: **False** (The database's final content does not match what was expected after running your statement.)
- Referència vs referència amb 2 s de pausa: idèntic = **True**; taules canviades: city

### Q3
- Referència: `INSERT INTO film_actor (actor_id, film_id) SELECT a.actor_id, f.film_id FROM actor a, film f WHERE a.first_name = 'NICK' AND a.last_name = 'WAHLBERG' AND f.title = 'ZORRO ARK'`
- Alternativa: `INSERT INTO film_actor (actor_id, film_id) VALUES ((SELECT actor_id FROM actor WHERE first_name = 'NICK' AND last_name = 'WAHLBERG'), (SELECT film_id FROM film WHERE title = 'ZORRO ARK'))` → acceptada: **True**
- Incorrecta: `INSERT INTO film_actor (actor_id, film_id) SELECT a.actor_id, f.film_id FROM actor a, film f WHERE a.last_name = 'WAHLBERG' AND f.title = 'ZORRO ARK'` → acceptada: **False** (The database's final content does not match what was expected after running your statement.)
- Referència vs referència amb 2 s de pausa: idèntic = **True**; taules canviades: film_actor

### Q4
- Referència: `INSERT INTO customer (store_id, first_name, last_name, email, address_id, active, create_date) SELECT store_id, first_name, last_name, email, address_id, 1, '2006-02-15 00:00:00' FROM staff`
- Alternativa: `INSERT INTO customer (first_name, last_name, store_id, address_id, email, create_date) SELECT s.first_name, s.last_name, s.store_id, s.address_id, s.email, '2006-02-15' FROM staff s` → acceptada: **True**
- Incorrecta: `INSERT INTO customer (store_id, first_name, last_name, email, address_id, active, create_date) SELECT 1, first_name, last_name, email, address_id, 1, '2006-02-15 00:00:00' FROM staff` → acceptada: **False** (The database's final content does not match what was expected after running your statement.)
- Referència vs referència amb 2 s de pausa: idèntic = **True**; taules canviades: customer

### Q5
- Referència: `INSERT IGNORE INTO film_category (film_id, category_id) SELECT f.film_id, c.category_id FROM film f, category c WHERE f.title LIKE '%DRAGON%' AND c.name = 'Action'`
- Alternativa: `INSERT INTO film_category (film_id, category_id) SELECT f.film_id, (SELECT category_id FROM category WHERE name = 'Action') FROM film f WHERE f.title LIKE '%DRAGON%' AND f.film_id NOT IN (SELECT film_id FROM film_category WHERE category_id = (SELECT category_id FROM category WHERE name = 'Action'))` → acceptada: **True**
- Incorrecta: `INSERT IGNORE INTO film_category (film_id, category_id) SELECT f.film_id, c.category_id FROM film f, category c WHERE f.title LIKE 'DRAGON%' AND c.name = 'Action'` → acceptada: **False** (The database's final content does not match what was expected after running your statement.)
- Referència vs referència amb 2 s de pausa: idèntic = **True**; taules canviades: film_category

### Q6
- Referència: `REPLACE INTO language (language_id, name) VALUES (2, 'Italiano'), (7, 'Català')`
- Alternativa: `INSERT INTO language (language_id, name) VALUES (2, 'Italiano'), (7, 'Català') ON DUPLICATE KEY UPDATE name = VALUES(name)` → acceptada: **True**
- Incorrecta: `INSERT IGNORE INTO language (language_id, name) VALUES (2, 'Italiano'), (7, 'Català')` → acceptada: **False** (The database's final content does not match what was expected after running your statement.)
- Referència vs referència amb 2 s de pausa: idèntic = **True**; taules canviades: language

### Q7
- Referència: `INSERT INTO film (film_id, title, language_id, rental_rate) VALUES (1, 'ACADEMY DINOSAUR', 1, 1.99), (1001, 'SABADELL NIGHTS', 1, 2.99) ON DUPLICATE KEY UPDATE rental_rate = VALUES(rental_rate)`
- Alternativa: `INSERT INTO film (film_id, title, language_id, rental_rate) VALUES (1001, 'SABADELL NIGHTS', 1, 2.99), (1, 'ACADEMY DINOSAUR', 1, 1.99) ON DUPLICATE KEY UPDATE rental_rate = IF(film_id = 1, 1.99, 2.99)` → acceptada: **True**
- Incorrecta: `INSERT INTO film (film_id, title, language_id, rental_rate) VALUES (1, 'ACADEMY DINOSAUR', 1, 1.99), (1001, 'SABADELL NIGHTS', 1, 2.99) ON DUPLICATE KEY UPDATE title = VALUES(title)` → acceptada: **False** (The database's final content does not match what was expected after running your statement.)
- Referència vs referència amb 2 s de pausa: idèntic = **True**; taules canviades: film, film_text

### Q8
- Referència: `INSERT INTO inventory (film_id, store_id) SELECT fc.film_id, 2 FROM film_category fc JOIN category c ON c.category_id = fc.category_id WHERE c.name = 'Animation' AND NOT EXISTS (SELECT 1 FROM inventory i WHERE i.film_id = fc.film_id AND i.store_id = 2)`
- Alternativa: `INSERT INTO inventory (store_id, film_id) SELECT 2, f.film_id FROM film f JOIN film_category fc USING (film_id) JOIN category c USING (category_id) WHERE c.name = 'Animation' AND f.film_id NOT IN (SELECT film_id FROM inventory WHERE store_id = 2)` → acceptada: **True**
- Incorrecta: `INSERT INTO inventory (film_id, store_id) SELECT fc.film_id, 2 FROM film_category fc JOIN category c ON c.category_id = fc.category_id WHERE c.name = 'Animation' AND NOT EXISTS (SELECT 1 FROM inventory i WHERE i.film_id = fc.film_id)` → acceptada: **False** (The database's final content does not match what was expected after running your statement.)
- Referència vs referència amb 2 s de pausa: idèntic = **True**; taules canviades: inventory

### Q9
- Referència: `INSERT INTO payment (customer_id, staff_id, rental_id, amount, payment_date) SELECT r.customer_id, r.staff_id, r.rental_id, f.replacement_cost, '2006-02-15 00:00:00' FROM rental r JOIN inventory i ON i.inventory_id = r.inventory_id JOIN film f ON f.film_id = i.film_id WHERE r.return_date IS NULL`
- Alternativa: `INSERT INTO payment (payment_date, amount, rental_id, staff_id, customer_id) SELECT '2006-02-15 00:00:00', (SELECT f.replacement_cost FROM inventory i JOIN film f USING (film_id) WHERE i.inventory_id = r.inventory_id), r.rental_id, r.staff_id, r.customer_id FROM rental r WHERE r.return_date IS NULL` → acceptada: **True**
- Incorrecta: `INSERT INTO payment (customer_id, staff_id, rental_id, amount, payment_date) SELECT r.customer_id, r.staff_id, r.rental_id, f.rental_rate, '2006-02-15 00:00:00' FROM rental r JOIN inventory i ON i.inventory_id = r.inventory_id JOIN film f ON f.film_id = i.film_id WHERE r.return_date IS NULL` → acceptada: **False** (The database's final content does not match what was expected after running your statement.)
- Referència vs referència amb 2 s de pausa: idèntic = **True**; taules canviades: payment

### Q10
- Referència: `INSERT INTO inventory (film_id, store_id) SELECT i.film_id, 1 FROM rental r JOIN inventory i ON i.inventory_id = r.inventory_id GROUP BY i.film_id ORDER BY COUNT(*) DESC, i.film_id LIMIT 10`
- Alternativa: `INSERT INTO inventory (store_id, film_id) SELECT 1, t.film_id FROM (SELECT i.film_id, COUNT(r.rental_id) AS n FROM inventory i JOIN rental r USING (inventory_id) GROUP BY i.film_id) t ORDER BY t.n DESC, t.film_id ASC LIMIT 10` → acceptada: **True**
- Incorrecta: `INSERT INTO inventory (film_id, store_id) SELECT i.film_id, 1 FROM rental r JOIN inventory i ON i.inventory_id = r.inventory_id GROUP BY i.film_id ORDER BY COUNT(*) DESC, i.film_id DESC LIMIT 10` → acceptada: **False** (The database's final content does not match what was expected after running your statement.)
- Referència vs referència amb 2 s de pausa: idèntic = **True**; taules canviades: inventory


## Sakila — UPDATE amb JOIN i subconsultes

### Q1
- Referència: `UPDATE customer SET email = REPLACE(email, '@sakilacustomer.org', '@videoclub.cat') WHERE store_id = 1`
- Alternativa: `UPDATE customer SET email = CONCAT(SUBSTRING_INDEX(email, '@', 1), '@videoclub.cat') WHERE store_id = 1` → acceptada: **True**
- Incorrecta: `UPDATE customer SET email = REPLACE(email, '@sakilacustomer.org', '@videoclub.cat')` → acceptada: **False** (The database's final content does not match what was expected after running your statement.)
- Referència vs referència amb 2 s de pausa: idèntic = **True**; taules canviades: customer

### Q2
- Referència: `UPDATE film SET rental_rate = CASE WHEN length < 60 THEN 0.99 WHEN length < 120 THEN 2.99 ELSE 4.99 END WHERE rating = 'PG-13'`
- Alternativa: `UPDATE film SET rental_rate = IF(length >= 120, 4.99, IF(length >= 60, 2.99, 0.99)) WHERE rating = 'PG-13'` → acceptada: **True**
- Incorrecta: `UPDATE film SET rental_rate = CASE WHEN length <= 60 THEN 0.99 WHEN length <= 120 THEN 2.99 ELSE 4.99 END WHERE rating = 'PG-13'` → acceptada: **False** (The database's final content does not match what was expected after running your statement.)
- Referència vs referència amb 2 s de pausa: idèntic = **True**; taules canviades: film

### Q3
- Referència: `UPDATE film f JOIN film_category fc ON fc.film_id = f.film_id JOIN category c ON c.category_id = fc.category_id SET f.rental_rate = f.rental_rate + 1.00 WHERE c.name = 'New'`
- Alternativa: `UPDATE film SET rental_rate = rental_rate + 1 WHERE film_id IN (SELECT film_id FROM film_category WHERE category_id = (SELECT category_id FROM category WHERE name = 'New'))` → acceptada: **True**
- Incorrecta: `UPDATE film f JOIN film_category fc ON fc.film_id = f.film_id JOIN category c ON c.category_id = fc.category_id SET f.rental_rate = 4.99 WHERE c.name = 'New'` → acceptada: **False** (The database's final content does not match what was expected after running your statement.)
- Referència vs referència amb 2 s de pausa: idèntic = **True**; taules canviades: film

### Q4
- Referència: `UPDATE film SET replacement_cost = replacement_cost + 5.00 ORDER BY length DESC, film_id LIMIT 5`
- Alternativa: `UPDATE film SET replacement_cost = replacement_cost + 5 WHERE film_id IN (SELECT film_id FROM (SELECT film_id FROM film ORDER BY length DESC, film_id ASC LIMIT 5) t)` → acceptada: **True**
- Incorrecta: `UPDATE film SET replacement_cost = replacement_cost + 5.00 ORDER BY length DESC LIMIT 5` → acceptada: **False** (The database's final content does not match what was expected after running your statement.)
- Referència vs referència amb 2 s de pausa: idèntic = **True**; taules canviades: film

### Q5
- Referència: `UPDATE rental r JOIN inventory i ON i.inventory_id = r.inventory_id JOIN film f ON f.film_id = i.film_id SET r.return_date = DATE_ADD(r.rental_date, INTERVAL f.rental_duration DAY) WHERE r.return_date IS NULL`
- Alternativa: `UPDATE rental r SET r.return_date = r.rental_date + INTERVAL (SELECT f.rental_duration FROM inventory i JOIN film f USING (film_id) WHERE i.inventory_id = r.inventory_id) DAY WHERE r.return_date IS NULL` → acceptada: **True**
- Incorrecta: `UPDATE rental r JOIN inventory i ON i.inventory_id = r.inventory_id JOIN film f ON f.film_id = i.film_id SET r.return_date = DATE(DATE_ADD(r.rental_date, INTERVAL f.rental_duration DAY)) WHERE r.return_date IS NULL` → acceptada: **False** (The database's final content does not match what was expected after running your statement.)
- Referència vs referència amb 2 s de pausa: idèntic = **True**; taules canviades: rental

### Q6
- Referència: `UPDATE customer c SET active = 0 WHERE (SELECT MAX(r.rental_date) FROM rental r WHERE r.customer_id = c.customer_id) < '2005-08-20'`
- Alternativa: `UPDATE customer SET active = 0 WHERE customer_id NOT IN (SELECT customer_id FROM rental WHERE rental_date >= '2005-08-20')` → acceptada: **True**
- Incorrecta: `UPDATE customer c SET active = 0 WHERE (SELECT MIN(r.rental_date) FROM rental r WHERE r.customer_id = c.customer_id) < '2005-08-20'` → acceptada: **False** (The database's final content does not match what was expected after running your statement.)
- Referència vs referència amb 2 s de pausa: idèntic = **True**; taules canviades: customer

### Q7
- Referència: `UPDATE film f JOIN film_category fc ON fc.film_id = f.film_id JOIN category c ON c.category_id = fc.category_id SET f.rental_duration = (SELECT ROUND(AVG(DATEDIFF(r.return_date, r.rental_date))) FROM rental r JOIN inventory i ON i.inventory_id = r.inventory_id WHERE i.film_id = f.film_id AND r.return_date IS NOT NULL) WHERE c.name = 'Travel' AND EXISTS (SELECT 1 FROM rental r JOIN inventory i ON i.inventory_id = r.inventory_id WHERE i.film_id = f.film_id AND r.return_date IS NOT NULL)`
- Alternativa: `UPDATE film f JOIN (SELECT i.film_id, ROUND(AVG(DATEDIFF(r.return_date, r.rental_date))) AS d FROM rental r JOIN inventory i USING (inventory_id) WHERE r.return_date IS NOT NULL GROUP BY i.film_id) t ON t.film_id = f.film_id SET f.rental_duration = t.d WHERE f.film_id IN (SELECT film_id FROM film_category JOIN category USING (category_id) WHERE category.name = 'Travel')` → acceptada: **True**
- Incorrecta: `UPDATE film f JOIN film_category fc ON fc.film_id = f.film_id JOIN category c ON c.category_id = fc.category_id SET f.rental_duration = (SELECT FLOOR(AVG(DATEDIFF(r.return_date, r.rental_date))) FROM rental r JOIN inventory i ON i.inventory_id = r.inventory_id WHERE i.film_id = f.film_id AND r.return_date IS NOT NULL) WHERE c.name = 'Travel' AND EXISTS (SELECT 1 FROM rental r JOIN inventory i ON i.inventory_id = r.inventory_id WHERE i.film_id = f.film_id AND r.return_date IS NOT NULL)` → acceptada: **False** (The database's final content does not match what was expected after running your statement.)
- Referència vs referència amb 2 s de pausa: idèntic = **True**; taules canviades: film

### Q8
- Referència: `UPDATE film SET rental_rate = rental_rate + 0.50 WHERE rating = 'G' AND length > (SELECT m FROM (SELECT AVG(length) AS m FROM film) t)`
- Alternativa: `UPDATE film f JOIN (SELECT AVG(length) AS m FROM film) t ON f.length > t.m SET f.rental_rate = f.rental_rate + 0.5 WHERE f.rating = 'G'` → acceptada: **True**
- Incorrecta: `UPDATE film SET rental_rate = rental_rate + 0.50 WHERE rating = 'G' AND length > (SELECT m FROM (SELECT AVG(length) AS m FROM film WHERE rating = 'G') t)` → acceptada: **False** (The database's final content does not match what was expected after running your statement.)
- Referència vs referència amb 2 s de pausa: idèntic = **True**; taules canviades: film

### Q9
- Referència: `UPDATE film f JOIN film_category fc ON fc.film_id = f.film_id JOIN category c ON c.category_id = fc.category_id JOIN (SELECT i.film_id, COUNT(*) AS n FROM rental r JOIN inventory i ON i.inventory_id = r.inventory_id GROUP BY i.film_id) t ON t.film_id = f.film_id SET f.rental_rate = CASE WHEN t.n >= 25 THEN 4.99 WHEN t.n >= 15 THEN 2.99 ELSE 0.99 END WHERE c.name = 'Comedy'`
- Alternativa: `UPDATE film f SET f.rental_rate = (SELECT CASE WHEN COUNT(*) >= 25 THEN 4.99 WHEN COUNT(*) >= 15 THEN 2.99 ELSE 0.99 END FROM rental r JOIN inventory i USING (inventory_id) WHERE i.film_id = f.film_id) WHERE f.film_id IN (SELECT film_id FROM film_category JOIN category USING (category_id) WHERE name = 'Comedy') AND f.film_id IN (SELECT film_id FROM inventory JOIN rental USING (inventory_id))` → acceptada: **True**
- Incorrecta: `UPDATE film f JOIN film_category fc ON fc.film_id = f.film_id JOIN category c ON c.category_id = fc.category_id JOIN (SELECT i.film_id, COUNT(DISTINCT i.inventory_id) AS n FROM rental r JOIN inventory i ON i.inventory_id = r.inventory_id GROUP BY i.film_id) t ON t.film_id = f.film_id SET f.rental_rate = CASE WHEN t.n >= 25 THEN 4.99 WHEN t.n >= 15 THEN 2.99 ELSE 0.99 END WHERE c.name = 'Comedy'` → acceptada: **False** (The database's final content does not match what was expected after running your statement.)
- Referència vs referència amb 2 s de pausa: idèntic = **True**; taules canviades: film

### Q10
- Referència: `UPDATE payment p JOIN rental r ON r.rental_id = p.rental_id JOIN inventory i ON i.inventory_id = r.inventory_id JOIN film f ON f.film_id = i.film_id SET p.amount = p.amount + 0.50 * (DATEDIFF(r.return_date, r.rental_date) - f.rental_duration) WHERE r.rental_date < '2005-05-28' AND DATEDIFF(r.return_date, r.rental_date) > f.rental_duration`
- Alternativa: `UPDATE payment p SET p.amount = p.amount + (SELECT 0.5 * (DATEDIFF(r.return_date, r.rental_date) - f.rental_duration) FROM rental r JOIN inventory i USING (inventory_id) JOIN film f USING (film_id) WHERE r.rental_id = p.rental_id) WHERE p.rental_id IN (SELECT r.rental_id FROM rental r JOIN inventory i USING (inventory_id) JOIN film f USING (film_id) WHERE r.rental_date < '2005-05-28' AND DATEDIFF(r.return_date, r.rental_date) > f.rental_duration)` → acceptada: **True**
- Incorrecta: `UPDATE payment p JOIN rental r ON r.rental_id = p.rental_id JOIN inventory i ON i.inventory_id = r.inventory_id JOIN film f ON f.film_id = i.film_id SET p.amount = p.amount + 0.50 * DATEDIFF(r.return_date, r.rental_date) WHERE r.rental_date < '2005-05-28' AND DATEDIFF(r.return_date, r.rental_date) > f.rental_duration` → acceptada: **False** (The database's final content does not match what was expected after running your statement.)
- Referència vs referència amb 2 s de pausa: idèntic = **True**; taules canviades: payment


## Sakila — DELETE

### Q1
- Referència: `DELETE FROM payment WHERE payment_date >= '2006-02-01' AND amount < 1`
- Alternativa: `DELETE FROM payment WHERE amount < 1.00 AND payment_date BETWEEN '2006-02-01 00:00:00' AND '2006-12-31 23:59:59'` → acceptada: **True**
- Incorrecta: `DELETE FROM payment WHERE amount < 1` → acceptada: **False** (The database's final content does not match what was expected after running your statement.)
- Referència vs referència amb 2 s de pausa: idèntic = **True**; taules canviades: payment

### Q2
- Referència: `DELETE FROM film_actor WHERE film_id IN (SELECT film_id FROM film WHERE title LIKE '%DINOSAUR%')`
- Alternativa: `DELETE fa FROM film_actor fa JOIN film f ON f.film_id = fa.film_id WHERE LOCATE('DINOSAUR', f.title) > 0` → acceptada: **True**
- Incorrecta: `DELETE FROM film_actor WHERE film_id IN (SELECT film_id FROM film WHERE title LIKE 'DINOSAUR%')` → acceptada: **False** (The database's final content does not match what was expected after running your statement.)
- Referència vs referència amb 2 s de pausa: idèntic = **True**; taules canviades: film_actor

### Q3
- Referència: `DELETE FROM inventory WHERE inventory_id NOT IN (SELECT inventory_id FROM rental)`
- Alternativa: `DELETE FROM inventory WHERE NOT EXISTS (SELECT 1 FROM rental r WHERE r.inventory_id = inventory.inventory_id)` → acceptada: **True**
- Incorrecta: `DELETE FROM inventory WHERE inventory_id NOT IN (SELECT inventory_id FROM rental WHERE rental_date >= '2005-08-01')` → acceptada: **False** (SQL error: Cannot delete or update a parent row: a foreign key constraint fails (`w_sakila`.`rental`, CONSTRAINT `fk_rental_inventory` FOREIGN KEY (`inventory_id`) REFERENCES `inventory` (`inventory_id`) ON UPDATE CASCADE))
- Referència vs referència amb 2 s de pausa: idèntic = **True**; taules canviades: inventory

### Q4
- Referència: `DELETE FROM city WHERE NOT EXISTS (SELECT 1 FROM address a WHERE a.city_id = city.city_id)`
- Alternativa: `DELETE c FROM city c LEFT JOIN address a ON a.city_id = c.city_id WHERE a.address_id IS NULL` → acceptada: **True**
- Incorrecta: `DELETE FROM city WHERE city_id NOT IN (SELECT city_id FROM address) AND country_id = 1` → acceptada: **False** (The database's final content does not match what was expected after running your statement.)
- Referència vs referència amb 2 s de pausa: idèntic = **True**; taules canviades: city

### Q5
- Referència: `DELETE FROM language WHERE NOT EXISTS (SELECT 1 FROM film f WHERE f.language_id = language.language_id OR f.original_language_id = language.language_id)`
- Alternativa: `DELETE FROM language WHERE language_id NOT IN (SELECT language_id FROM film) AND language_id NOT IN (SELECT original_language_id FROM film WHERE original_language_id IS NOT NULL)` → acceptada: **True**
- Incorrecta: `DELETE FROM language WHERE language_id <> 1 AND language_id < 6` → acceptada: **False** (The database's final content does not match what was expected after running your statement.)
- Referència vs referència amb 2 s de pausa: idèntic = **True**; taules canviades: language

### Q6
- Referència: `DELETE FROM payment WHERE customer_id = (SELECT customer_id FROM customer WHERE first_name = 'MARY' AND last_name = 'SMITH') ORDER BY amount, payment_id LIMIT 5`
- Alternativa: `DELETE FROM payment WHERE payment_id IN (SELECT payment_id FROM (SELECT p.payment_id FROM payment p JOIN customer c USING (customer_id) WHERE c.first_name = 'MARY' AND c.last_name = 'SMITH' ORDER BY p.amount ASC, p.payment_id ASC LIMIT 5) t)` → acceptada: **True**
- Incorrecta: `DELETE FROM payment WHERE customer_id = (SELECT customer_id FROM customer WHERE first_name = 'MARY' AND last_name = 'SMITH') ORDER BY amount, payment_id DESC LIMIT 5` → acceptada: **False** (The database's final content does not match what was expected after running your statement.)
- Referència vs referència amb 2 s de pausa: idèntic = **True**; taules canviades: payment

### Q7
- Referència: `DELETE fa FROM film_actor fa JOIN film f ON f.film_id = fa.film_id JOIN film_category fc ON fc.film_id = f.film_id JOIN category c ON c.category_id = fc.category_id WHERE c.name = 'Horror' AND f.length < 60`
- Alternativa: `DELETE FROM film_actor WHERE film_id IN (SELECT f.film_id FROM film f JOIN film_category USING (film_id) JOIN category c USING (category_id) WHERE c.name = 'Horror' AND f.length < 60)` → acceptada: **True**
- Incorrecta: `DELETE fa FROM film_actor fa JOIN film f ON f.film_id = fa.film_id JOIN film_category fc ON fc.film_id = f.film_id JOIN category c ON c.category_id = fc.category_id WHERE f.length < 60` → acceptada: **False** (The database's final content does not match what was expected after running your statement.)
- Referència vs referència amb 2 s de pausa: idèntic = **True**; taules canviades: film_actor

### Q8
- Referència: `DELETE FROM rental WHERE rental_date >= '2006-02-01' AND return_date IS NULL`
- Alternativa: `DELETE FROM rental WHERE YEAR(rental_date) = 2006 AND MONTH(rental_date) = 2 AND return_date IS NULL` → acceptada: **True**
- Incorrecta: `DELETE r, p FROM rental r JOIN payment p ON p.rental_id = r.rental_id WHERE r.rental_date >= '2006-02-01' AND r.return_date IS NULL` → acceptada: **False** (The database's final content does not match what was expected after running your statement.)
- Referència vs referència amb 2 s de pausa: idèntic = **True**; taules canviades: payment, rental

### Q9
- Referència: `DELETE r, p FROM rental r JOIN inventory i ON i.inventory_id = r.inventory_id JOIN film f ON f.film_id = i.film_id LEFT JOIN payment p ON p.rental_id = r.rental_id WHERE f.title = 'ACADEMY DINOSAUR'`
- Alternativa: `DELETE p, r FROM film f JOIN inventory i USING (film_id) JOIN rental r USING (inventory_id) JOIN payment p USING (rental_id) WHERE f.title = 'ACADEMY DINOSAUR'` → acceptada: **True**
- Incorrecta: `DELETE r FROM rental r JOIN inventory i ON i.inventory_id = r.inventory_id JOIN film f ON f.film_id = i.film_id WHERE f.title = 'ACADEMY DINOSAUR'` → acceptada: **False** (The database's final content does not match what was expected after running your statement.)
- Referència vs referència amb 2 s de pausa: idèntic = **True**; taules canviades: payment, rental

### Q10
- Referència: `DELETE p FROM payment p JOIN (SELECT customer_id, AVG(amount) AS m FROM payment GROUP BY customer_id) t ON t.customer_id = p.customer_id WHERE p.customer_id BETWEEN 1 AND 3 AND p.amount < t.m`
- Alternativa: `DELETE FROM payment WHERE payment_id IN (SELECT payment_id FROM (SELECT p.payment_id FROM payment p WHERE p.customer_id BETWEEN 1 AND 3 AND p.amount < (SELECT AVG(q.amount) FROM payment q WHERE q.customer_id = p.customer_id)) x)` → acceptada: **True**
- Incorrecta: `DELETE FROM payment WHERE customer_id IN (1, 2, 3) AND amount < (SELECT m FROM (SELECT customer_id, AVG(amount) AS m FROM payment GROUP BY customer_id) t WHERE t.customer_id = payment.customer_id)` → acceptada: **False** (The database's final content does not match what was expected after running your statement.)
- Referència vs referència amb 2 s de pausa: idèntic = **True**; taules canviades: payment

## Observacions
- Timestamps: abans del canvi del corrector, un mateix UPDATE/INSERT executat amb 2 s de diferència donava `last_update` diferent (comprovat: WA). Ara `mysqlwrite` fa `SET timestamp = 1767225600` (2026-01-01 00:00:00 UTC) i la referència contra si mateixa amb 2 s de pausa surt idèntica a les 30 preguntes. Les dates que formen part del contingut (`create_date`, `payment_date`) es donen explícites a l'enunciat.
- `film_text` no té AUTO_INCREMENT: el trigger `ins_film` hi copia el `film_id` real, que no es normalitza a `<new>`. Per això INSERT Q7 dona el `film_id` 1001 explícit (sense, la comparació no seria determinista: comprovat).
- MariaDB 10.5 NO dona l'error 1093 (accepta subconsultes sobre la taula que es modifica). UPDATE Q8 i DELETE Q10 ho expliquen com a qüestió de portabilitat a MySQL; les dues formes són acceptades.
- DELETE Q10: una taula derivada dins d'una subconsulta correlacionada del WHERE la recalcula MariaDB durant l'esborrat i elimina 49 files en lloc de 42; s'usa com a resposta incorrecta plausible i s'explica a l'"explain".
- DELETE: el SET NULL de `payment.rental_id` no activa ON UPDATE CURRENT_TIMESTAMP de `payment` (comprovat determinista fins i tot abans del rellotge fix).
- Script de generació i verificació: sakila_gen.py (el JSON i aquestes notes es regeneren amb ell).
