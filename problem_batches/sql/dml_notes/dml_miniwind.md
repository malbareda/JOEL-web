# dml_miniwind — verificació amb el corrector real (dmoj.checkers.mysqlwrite)

## Miniwind — INSERT avançat

### Q1 OK
- Referència vs ella mateixa: True
- Alternativa correcta → acceptada=True 
  `INSERT INTO order_details (order_id, product_id, quantity, unit_price, status_id) SELECT 80, p.id, 12, p.list_price, s.id FROM products p JOIN order_details_status s ON s.status_name = 'On Order' WHERE p.product_name = 'Northwind Traders Chai'`
- Incorrecta plausible → acceptada=False (The database's final content does not match what was expected after running your statement.)
  `INSERT INTO order_details (order_id, product_id, quantity, unit_price, status_id) SELECT 80, p.id, 12, p.standard_cost, 4 FROM products p WHERE p.product_name = 'Northwind Traders Chai'`

### Q2 OK
- Referència vs ella mateixa: True
- Alternativa correcta → acceptada=True 
  `INSERT INTO orders (employee_id, customer_id, order_date, ship_city, status_id) VALUES ((SELECT id FROM employees WHERE first_name='Thelma' AND last_name='Jirusek'), (SELECT id FROM customers WHERE company='Hudson-Lesch'), '2006-07-01', (SELECT city FROM customers WHERE company='Hudson-Lesch'), (SELECT id FROM orders_status WHERE status_name='New'))`
- Incorrecta plausible → acceptada=False (The database's final content does not match what was expected after running your statement.)
  `INSERT INTO orders (employee_id, customer_id, order_date, ship_city, status_id) SELECT e.id, c.id, '2006-07-01', e.city, 0 FROM employees e, customers c WHERE e.last_name='Jirusek' AND c.company='Hudson-Lesch'`

### Q3 OK
- Referència vs ella mateixa: True
- Alternativa correcta → acceptada=True 
  `INSERT INTO order_details (order_id, product_id, quantity, unit_price, status_id) VALUES (80, 41, 5, 9.65, 4), (80, 98, 5, 1.89, 4), (80, 99, 5, 1.95, 4)`
- Incorrecta plausible → acceptada=False (The database's final content does not match what was expected after running your statement.)
  `INSERT INTO order_details (order_id, product_id, quantity, unit_price, status_id) VALUES (80, 41, 5, 9.65, 4), (80, 98, 5, 1.89, 4)`

### Q4 OK
- Referència vs ella mateixa: True
- Alternativa correcta → acceptada=True 
  `INSERT INTO orders_status (id, status_name) VALUES (2, 'Enviada'), (4, 'Cancel·lada'), (5, 'Retornada') ON DUPLICATE KEY UPDATE id = id`
- Incorrecta plausible → acceptada=False (The database's final content does not match what was expected after running your statement.)
  `REPLACE INTO orders_status (id, status_name) VALUES (4, 'Cancel·lada'), (5, 'Retornada'), (6, 'Enviada')`

### Q5 OK
- Referència vs ella mateixa: True
- Alternativa correcta → acceptada=True 
  `INSERT INTO products (id, product_code, product_name, list_price, category) VALUES (99, 'NWTSO-99', 'Northwind Traders Chicken Soup', 2.25, 'Soups') ON DUPLICATE KEY UPDATE supplier_ids = NULL, standard_cost = 0, list_price = 2.25, reorder_level = NULL, target_level = NULL, quantity_per_unit = NULL, minimum_reorder_quantity = NULL`
- Incorrecta plausible → acceptada=False (The database's final content does not match what was expected after running your statement.)
  `INSERT INTO products (id, product_code, product_name, list_price, category) VALUES (99, 'NWTSO-99', 'Northwind Traders Chicken Soup', 2.25, 'Soups') ON DUPLICATE KEY UPDATE list_price = 2.25`

### Q6 OK
- Referència vs ella mateixa: True
- Alternativa correcta → acceptada=True 
  `INSERT INTO products (id, product_code, product_name, list_price, category) VALUES (1, 'NWTB-1', 'Northwind Traders Chai', 19.5, 'Beverages'), (3, 'NWTCO-3', 'Northwind Traders Syrup', 10.75, 'Condiments'), (100, 'NWTB-100', 'Northwind Traders Kombucha', 6.5, 'Beverages') ON DUPLICATE KEY UPDATE list_price = CASE id WHEN 1 THEN 19.5 WHEN 3 THEN 10.75 ELSE list_price END`
- Incorrecta plausible → acceptada=False (The database's final content does not match what was expected after running your statement.)
  `INSERT IGNORE INTO products (id, product_code, product_name, list_price, category) VALUES (1, 'NWTB-1', 'Northwind Traders Chai', 19.5, 'Beverages'), (3, 'NWTCO-3', 'Northwind Traders Syrup', 10.75, 'Condiments'), (100, 'NWTB-100', 'Northwind Traders Kombucha', 6.5, 'Beverages')`

### Q7 OK
- Referència vs ella mateixa: True
- Alternativa correcta → acceptada=True 
  `INSERT INTO orders (customer_id, employee_id, order_date, status_id, ship_name, ship_address, ship_city, ship_state_province, ship_zip_postal_code, ship_country_region) SELECT c.id, 5, '2006-07-03', 0, CONCAT_WS(' ', c.first_name, c.last_name), c.address, c.city, c.state_province, c.zip_postal_code, c.country_region FROM customers c WHERE c.state_province = 'IN' ORDER BY c.id`
- Incorrecta plausible → acceptada=False (The database's final content does not match what was expected after running your statement.)
  `INSERT INTO orders (customer_id, employee_id, order_date, status_id, ship_name, ship_address, ship_city, ship_state_province, ship_zip_postal_code, ship_country_region) SELECT c.id, 5, '2006-07-03', 0, CONCAT(c.last_name, ' ', c.first_name), c.address, c.city, c.state_province, c.zip_postal_code, c.country_region FROM customers c WHERE c.state_province = 'IN'`

### Q8 OK
- Referència vs ella mateixa: True
- Alternativa correcta → acceptada=True 
  `INSERT INTO order_details (order_id, product_id, quantity, unit_price, discount, status_id) SELECT 61, product_id, quantity, (SELECT ROUND(list_price * 0.95, 2) FROM products WHERE products.id = order_details.product_id), 0, (SELECT id FROM order_details_status WHERE status_name = 'On Order') FROM order_details WHERE order_id = 58`
- Incorrecta plausible → acceptada=False (The database's final content does not match what was expected after running your statement.)
  `INSERT INTO order_details (order_id, product_id, quantity, unit_price, discount, status_id) SELECT 61, product_id, quantity, unit_price, 0.05, 4 FROM order_details WHERE order_id = 58`

### Q9 OK
- Referència vs ella mateixa: True
- Alternativa correcta → acceptada=True 
  `INSERT INTO order_details (order_id, product_id, quantity, unit_price, status_id) SELECT 81, od.product_id, SUM(od.quantity), MAX(p.standard_cost), 4 FROM order_details od JOIN products p ON p.id = od.product_id WHERE p.category = 'Beverages' AND od.order_id IN (SELECT id FROM orders WHERE status_id = (SELECT id FROM orders_status WHERE status_name = 'Closed')) GROUP BY od.product_id`
- Incorrecta plausible → acceptada=False (The database's final content does not match what was expected after running your statement.)
  `INSERT INTO order_details (order_id, product_id, quantity, unit_price, status_id) SELECT 81, od.product_id, SUM(od.quantity), MAX(p.standard_cost), 4 FROM order_details od JOIN products p ON p.id = od.product_id WHERE p.category = 'Beverages' GROUP BY od.product_id`

### Q10 OK
- Referència vs ella mateixa: True
- Alternativa correcta → acceptada=True 
  `INSERT INTO invoices (order_id, invoice_date, due_date, tax, shipping, amount_due) SELECT t.id, '2006-07-01', '2006-07-31', 0, t.shipping_fee, ROUND(t.total, 2) + t.shipping_fee FROM (SELECT o.id, o.shipping_fee, SUM(od.quantity * od.unit_price * (1 - od.discount)) AS total FROM orders o JOIN order_details od ON od.order_id = o.id WHERE o.status_id = (SELECT id FROM orders_status WHERE status_name = 'New') AND o.id NOT IN (SELECT order_id FROM invoices) GROUP BY o.id, o.shipping_fee) t WHERE t.total > 0`
- Incorrecta plausible → acceptada=False (The database's final content does not match what was expected after running your statement.)
  `INSERT INTO invoices (order_id, invoice_date, due_date, tax, shipping, amount_due) SELECT o.id, '2006-07-01', '2006-07-31', 0, o.shipping_fee, ROUND(SUM(od.quantity * od.unit_price * (1 - od.discount)), 2) + o.shipping_fee FROM orders o JOIN order_details od ON od.order_id = o.id WHERE o.status_id = 0 AND o.id NOT IN (SELECT order_id FROM invoices) GROUP BY o.id, o.shipping_fee`

## Miniwind — UPDATE amb JOIN i subconsultes

### Q1 OK
- Referència vs ella mateixa: True
- Alternativa correcta → acceptada=True 
  `UPDATE orders SET shipped_date = order_date + INTERVAL 7 DAY, status_id = 2 WHERE shipped_date IS NULL AND YEAR(order_date) = 2006 AND MONTH(order_date) = 3`
- Incorrecta plausible → acceptada=False (The database's final content does not match what was expected after running your statement.)
  `UPDATE orders SET shipped_date = order_date + INTERVAL 7 DAY, status_id = 2 WHERE shipped_date IS NULL AND order_date BETWEEN '2006-03-01' AND '2006-04-30'`

### Q2 OK
- Referència vs ella mateixa: True
- Alternativa correcta → acceptada=True 
  `UPDATE products SET product_name = CONCAT(REPLACE(product_name, 'Northwind Traders ', ''), ' (beguda)') WHERE category = 'Beverages'`
- Incorrecta plausible → acceptada=False (The database's final content does not match what was expected after running your statement.)
  `UPDATE products SET product_name = CONCAT(SUBSTRING(product_name, 18), ' (beguda)') WHERE category = 'Beverages'`

### Q3 OK
- Referència vs ella mateixa: True
- Alternativa correcta → acceptada=True 
  `UPDATE products SET list_price = ROUND(list_price + list_price * 7 / 100, 2) WHERE category LIKE 'Canned Fruit%'`
- Incorrecta plausible → acceptada=False (The database's final content does not match what was expected after running your statement.)
  `UPDATE products SET list_price = TRUNCATE(list_price * 1.07, 2) WHERE category = 'Canned Fruit & Vegetables'`

### Q4 OK
- Referència vs ella mateixa: True
- Alternativa correcta → acceptada=True 
  `UPDATE products SET minimum_reorder_quantity = IF(list_price >= 5, 10, IF(list_price >= 2, 20, 50)) WHERE minimum_reorder_quantity IS NULL`
- Incorrecta plausible → acceptada=False (The database's final content does not match what was expected after running your statement.)
  `UPDATE products SET minimum_reorder_quantity = CASE WHEN list_price <= 2 THEN 50 WHEN list_price <= 5 THEN 20 ELSE 10 END WHERE minimum_reorder_quantity IS NULL`

### Q5 OK
- Referència vs ella mateixa: True
- Alternativa correcta → acceptada=True 
  `UPDATE order_details SET discount = 0.1 WHERE product_id IN (SELECT id FROM products WHERE category = 'Beverages') AND order_id IN (SELECT o.id FROM orders o JOIN employees e ON e.id = o.employee_id WHERE e.last_name = 'Jurek')`
- Incorrecta plausible → acceptada=False (The database's final content does not match what was expected after running your statement.)
  `UPDATE order_details od JOIN products p ON p.id = od.product_id SET od.discount = 0.1 WHERE p.category = 'Beverages'`

### Q6 OK
- Referència vs ella mateixa: True
- Alternativa correcta → acceptada=True 
  `UPDATE invoices i JOIN orders o ON o.id = i.order_id SET o.payment_type = 'Efectiu', i.tax = ROUND(o.shipping_fee / 10, 2), i.due_date = CAST(i.invoice_date AS DATE) + INTERVAL 15 DAY WHERE o.payment_type = 'Cash'`
- Incorrecta plausible → acceptada=False (The database's final content does not match what was expected after running your statement.)
  `UPDATE invoices i JOIN orders o ON o.id = i.order_id SET o.payment_type = 'Efectiu', i.tax = ROUND(o.shipping_fee / 10, 2), i.due_date = i.invoice_date + INTERVAL 15 DAY WHERE o.payment_type = 'Cash'`

### Q7 OK
- Referència vs ella mateixa: True
- Alternativa correcta → acceptada=True 
  `UPDATE invoices i JOIN orders o ON o.id = i.order_id JOIN (SELECT order_id, SUM(quantity * unit_price * (1 - discount)) AS total FROM order_details GROUP BY order_id) t ON t.order_id = i.order_id SET i.amount_due = ROUND(t.total + o.shipping_fee, 2) WHERE DATE_FORMAT(i.invoice_date, '%Y-%m') = '2006-03'`
- Incorrecta plausible → acceptada=False (The database's final content does not match what was expected after running your statement.)
  `UPDATE invoices i SET i.amount_due = ROUND((SELECT SUM(od.quantity * od.unit_price) FROM order_details od WHERE od.order_id = i.order_id), 2) WHERE i.invoice_date >= '2006-03-01' AND i.invoice_date < '2006-04-01'`

### Q8 OK
- Referència vs ella mateixa: True
- Alternativa correcta → acceptada=True 
  `UPDATE orders o JOIN (SELECT o2.id FROM orders o2 JOIN orders_status s ON s.id = o2.status_id WHERE s.status_name = 'Closed' ORDER BY o2.shipping_fee DESC, o2.id LIMIT 3) t ON t.id = o.id SET o.shipping_fee = o.shipping_fee - 50`
- Incorrecta plausible → acceptada=False (The database's final content does not match what was expected after running your statement.)
  `UPDATE orders SET shipping_fee = shipping_fee - 50 WHERE status_id = 3 ORDER BY shipping_fee DESC, id DESC LIMIT 3`

### Q9 OK
- Referència vs ella mateixa: True
- Alternativa correcta → acceptada=True 
  `UPDATE products SET list_price = ROUND(list_price * 1.05, 2) WHERE id IN (SELECT product_id FROM (SELECT product_id FROM order_details GROUP BY product_id ORDER BY SUM(quantity) DESC, product_id LIMIT 3) AS top3)`
- Incorrecta plausible → acceptada=False (The database's final content does not match what was expected after running your statement.)
  `UPDATE products p JOIN (SELECT product_id, COUNT(*) AS n FROM order_details GROUP BY product_id ORDER BY n DESC, product_id LIMIT 3) t ON t.product_id = p.id SET p.list_price = ROUND(p.list_price * 1.05, 2)`

### Q10 OK
- Referència vs ella mateixa: True
- Alternativa correcta → acceptada=True 
  `UPDATE products p SET p.list_price = ROUND(p.list_price * 0.9, 2) WHERE p.list_price > 2 * (SELECT AVG(p2.list_price) FROM products p2 WHERE p2.category = p.category)`
- Incorrecta plausible → acceptada=False (The database's final content does not match what was expected after running your statement.)
  `UPDATE products p SET p.list_price = ROUND(p.list_price * 0.9, 2) WHERE p.list_price > 2 * (SELECT AVG(p2.list_price) FROM products p2)`

## Miniwind — DELETE

### Q1 OK
- Referència vs ella mateixa: True
- Alternativa correcta → acceptada=True 
  `DELETE FROM customers WHERE RIGHT(company, 8) = 'and Sons'`
- Incorrecta plausible → acceptada=False (The database's final content does not match what was expected after running your statement.)
  `DELETE FROM customers WHERE company LIKE '%Sons%' AND id = 23`

### Q2 OK
- Referència vs ella mateixa: True
- Alternativa correcta → acceptada=True 
  `DELETE FROM invoices WHERE DATE(invoice_date) = '2006-03-24' AND HOUR(invoice_date) = 10 AND MINUTE(invoice_date) >= 55`
- Incorrecta plausible → acceptada=False (The database's final content does not match what was expected after running your statement.)
  `DELETE FROM invoices WHERE DATE(invoice_date) = '2006-03-24' AND HOUR(invoice_date) = 10 AND MINUTE(invoice_date) > 55`

### Q3 OK
- Referència vs ella mateixa: True
- Alternativa correcta → acceptada=True 
  `DELETE FROM order_details WHERE (order_id = 41 OR order_id = 43 OR order_id = 44) AND quantity >= 20 AND quantity <= 30`
- Incorrecta plausible → acceptada=False (The database's final content does not match what was expected after running your statement.)
  `DELETE FROM order_details WHERE order_id IN (41, 43, 44) AND quantity > 20 AND quantity < 30`

### Q4 OK
- Referència vs ella mateixa: True
- Alternativa correcta → acceptada=True 
  `DELETE FROM products WHERE category = 'Canned Fruit & Vegetables' AND NOT EXISTS (SELECT 1 FROM order_details od WHERE od.product_id = products.id)`
- Incorrecta plausible → acceptada=False (SQL error: Cannot delete or update a parent row: a foreign key constraint fails (`w_miniwind`.`order_details`, CONSTRAINT `fk_order_details_products1` FOREIGN KEY (`product_id`) REFERENCES `products` (`id`) ON DELETE NO ACTION ON UPDATE NO ACTION))
  `DELETE FROM products WHERE category = 'Canned Fruit & Vegetables' AND id NOT IN (SELECT product_id FROM order_details WHERE order_id < 70)`

### Q5 OK
- Referència vs ella mateixa: True
- Alternativa correcta → acceptada=True 
  `DELETE c FROM customers c LEFT JOIN orders o ON o.customer_id = c.id WHERE o.id IS NULL AND c.state_province IN ('CA', 'NY')`
- Incorrecta plausible → acceptada=False (The database's final content does not match what was expected after running your statement.)
  `DELETE FROM customers WHERE state_province = 'CA' AND NOT EXISTS (SELECT 1 FROM orders o WHERE o.customer_id = customers.id)`

### Q6 OK
- Referència vs ella mateixa: True
- Alternativa correcta → acceptada=True 
  `DELETE FROM order_details WHERE status_id = (SELECT id FROM order_details_status WHERE status_name = 'Allocated') AND order_id IN (SELECT o.id FROM orders o JOIN customers c ON c.id = o.customer_id WHERE c.company = 'Lueilwitz, Homenick and Quigley')`
- Incorrecta plausible → acceptada=False (The database's final content does not match what was expected after running your statement.)
  `DELETE od FROM order_details od JOIN orders o ON o.id = od.order_id JOIN customers c ON c.id = o.customer_id WHERE c.company = 'Lueilwitz, Homenick and Quigley'`

### Q7 OK
- Referència vs ella mateixa: True
- Alternativa correcta → acceptada=True 
  `DELETE FROM order_details WHERE id IN (SELECT id FROM (SELECT od.id FROM order_details od JOIN order_details_status s ON s.id = od.status_id WHERE s.status_name = 'Allocated' ORDER BY od.quantity * od.unit_price, od.id LIMIT 2) t)`
- Incorrecta plausible → acceptada=False (The database's final content does not match what was expected after running your statement.)
  `DELETE FROM order_details WHERE status_id = 1 ORDER BY quantity, id LIMIT 2`

### Q8 OK
- Referència vs ella mateixa: True
- Alternativa correcta → acceptada=True 
  `DELETE o FROM orders o LEFT JOIN order_details od ON od.order_id = o.id LEFT JOIN invoices i ON i.order_id = o.id WHERE o.status_id = 0 AND od.id IS NULL AND i.id IS NULL`
- Incorrecta plausible → acceptada=False (The database's final content does not match what was expected after running your statement.)
  `DELETE o FROM orders o LEFT JOIN order_details od ON od.order_id = o.id WHERE o.status_id = 0 AND od.id IS NULL AND o.shipped_date IS NOT NULL`

### Q9 OK
- Referència vs ella mateixa: True
- Alternativa correcta → acceptada=True 
  `DELETE FROM products WHERE category IN ('Soups', 'Cereal') AND id NOT IN (SELECT product_id FROM order_details WHERE product_id IS NOT NULL)`
- Incorrecta plausible → acceptada=False (The database's final content does not match what was expected after running your statement.)
  `DELETE p FROM products p LEFT JOIN order_details od ON od.product_id = p.id WHERE od.id IS NULL AND p.category = 'Soups'`

### Q10 OK
- Referència vs ella mateixa: True
- Alternativa correcta → acceptada=True 
  `DELETE FROM order_details WHERE order_id IN (SELECT o.id FROM orders o JOIN orders_status s ON s.id = o.status_id WHERE s.status_name = 'Closed') AND (order_id, quantity * unit_price) IN (SELECT * FROM (SELECT order_id, MIN(quantity * unit_price) FROM order_details GROUP BY order_id HAVING COUNT(*) > 1) t)`
- Incorrecta plausible → acceptada=False (The database's final content does not match what was expected after running your statement.)
  `DELETE od FROM order_details od JOIN (SELECT order_id, MIN(quantity * unit_price) AS minim FROM order_details GROUP BY order_id HAVING COUNT(*) > 1) t ON t.order_id = od.order_id WHERE od.quantity * od.unit_price = t.minim`

