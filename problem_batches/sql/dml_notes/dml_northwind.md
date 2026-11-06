# dml_northwind: verificació

Per a cada pregunta: referència, alternativa correcta (ha de passar), incorrecta plausible (ha de fallar), files afectades per la referència. Comprovat amb `dmoj.checkers.mysqlwrite.check(..., database="northwind")`.


## Northwind — INSERT avançat (sqlinsert)

### 1. Al magatzem s'han fet malbé 3 unitats de 'Northwind Traders Scones' i 2 unitats de 'Northwind Traders Mozzarella'. Regis…

- Files afectades (referència): 2
- Referència:
```sql
INSERT INTO `inventory_transactions` (`transaction_type`, `transaction_created_date`, `transaction_modified_date`, `product_id`, `quantity`, `comments`) VALUES ((SELECT `id` FROM `inventory_transaction_types` WHERE `type_name` = 'Waste'), '2006-06-30 18:00:00', '2006-06-30 18:00:00', (SELECT `id` FROM `products` WHERE `product_name` = 'Northwind Traders Scones'), 3, 'Producte caducat'), ((SELECT `id` FROM `inventory_transaction_types` WHERE `type_name` = 'Waste'), '2006-06-30 18:00:00', '2006-06-30 18:00:00', (SELECT `id` FROM `products` WHERE `product_name` = 'Northwind Traders Mozzarella'), 2, 'Producte caducat')
```
- Alternativa: **acceptada** 
```sql
INSERT INTO inventory_transactions (transaction_type, transaction_created_date, transaction_modified_date, product_id, quantity, comments) SELECT t.id, '2006-06-30 18:00:00', '2006-06-30 18:00:00', p.id, CASE p.product_name WHEN 'Northwind Traders Scones' THEN 3 ELSE 2 END, 'Producte caducat' FROM products p JOIN inventory_transaction_types t ON t.type_name = 'Waste' WHERE p.product_name IN ('Northwind Traders Scones', 'Northwind Traders Mozzarella')
```
- Incorrecta plausible: **rebutjada** The database's final content does not match what was expected after running your statement.
```sql
INSERT INTO inventory_transactions (transaction_type, transaction_created_date, transaction_modified_date, product_id, quantity, comments) VALUES (4, '2006-06-30 18:00:00', '2006-06-30 18:00:00', 21, 3, 'Producte caducat'), (4, '2006-06-30 18:00:00', '2006-06-30 18:00:00', 72, 3, 'Producte caducat')
```

### 2. Dona el privilegi 'Purchase Approvals' (taula `privileges`, columna `privilege_name`) a tots els empleats el càrrec dels…

- Files afectades (referència): 2
- Referència:
```sql
INSERT IGNORE INTO `employee_privileges` (`employee_id`, `privilege_id`) SELECT e.`id`, p.`id` FROM `employees` e JOIN `privileges` p ON p.`privilege_name` = 'Purchase Approvals' WHERE e.`job_title` LIKE '%Sales%' AND e.`job_title` <> 'Sales Representative'
```
- Alternativa: **acceptada** 
```sql
INSERT INTO employee_privileges (employee_id, privilege_id) SELECT id, (SELECT id FROM privileges WHERE privilege_name = 'Purchase Approvals') FROM employees e WHERE job_title LIKE '%Sales%' AND job_title <> 'Sales Representative' AND NOT EXISTS (SELECT 1 FROM employee_privileges ep WHERE ep.employee_id = e.id AND ep.privilege_id = (SELECT id FROM privileges WHERE privilege_name = 'Purchase Approvals'))
```
- Incorrecta plausible: **rebutjada** The database's final content does not match what was expected after running your statement.
```sql
INSERT IGNORE INTO employee_privileges (employee_id, privilege_id) SELECT id, 2 FROM employees WHERE job_title LIKE '%Sales%'
```

### 3. Tradueix al català dos missatges de la taula `strings` i n'afegeix un de nou, tot en una sola sentència: el missatge 6 h…

- Files afectades (referència): 5
- Referència:
```sql
REPLACE INTO `strings` (`string_id`, `string_data`) VALUES (6, 'Inventari insuficient.'), (7, 'Inventari insuficient. Vols crear una comanda de compra?'), (115, 'Mes tancat correctament.')
```
- Alternativa: **acceptada** 
```sql
INSERT INTO strings (string_id, string_data) VALUES (6, 'Inventari insuficient.'), (7, 'Inventari insuficient. Vols crear una comanda de compra?'), (115, 'Mes tancat correctament.') ON DUPLICATE KEY UPDATE string_data = VALUES(string_data)
```
- Incorrecta plausible: **rebutjada** The database's final content does not match what was expected after running your statement.
```sql
INSERT IGNORE INTO strings (string_id, string_data) VALUES (6, 'Inventari insuficient.'), (7, 'Inventari insuficient. Vols crear una comanda de compra?'), (115, 'Mes tancat correctament.')
```

### 4. Ha arribat la tarifa nova de begudes. Per a cada fila de la llista següent, si el producte ja existeix (mateix `id`) **n…

- Files afectades (referència): 5
- Referència:
```sql
INSERT INTO `products` (`id`, `product_code`, `product_name`, `list_price`, `category`) VALUES (1, 'NWTB-1', 'Northwind Traders Chai', 19.50, 'Beverages'), (34, 'NWTB-34', 'Northwind Traders Beer', 15.00, 'Beverages'), (100, 'NWTB-100', 'Northwind Traders Lemonade', 3.25, 'Beverages') ON DUPLICATE KEY UPDATE `list_price` = VALUES(`list_price`)
```
- Alternativa: **acceptada** 
```sql
INSERT INTO products (id, product_code, product_name, list_price, category) VALUES (1, 'NWTB-1', 'Northwind Traders Chai', 19.5, 'Beverages'), (34, 'NWTB-34', 'Northwind Traders Beer', 15, 'Beverages'), (100, 'NWTB-100', 'Northwind Traders Lemonade', 3.25, 'Beverages') ON DUPLICATE KEY UPDATE list_price = IF(id = 1, 19.50, 15.00)
```
- Incorrecta plausible: **rebutjada** The database's final content does not match what was expected after running your statement.
```sql
INSERT INTO products (id, product_code, product_name, list_price, category) VALUES (1, 'NWTB-1', 'Northwind Traders Chai', 19.50, 'Beverages'), (34, 'NWTB-34', 'Northwind Traders Beer', 15.00, 'Beverages'), (100, 'NWTB-100', 'Northwind Traders Lemonade', 3.25, 'Beverages') ON DUPLICATE KEY UPDATE list_price = VALUES(list_price), product_code = VALUES(product_code), discontinued = 0, standard_cost = 0
```

### 5. Han arribat totes les comandes de compra que tenen l'estat 'Submitted' (taula `purchase_order_status`, columna `status`)…

- Files afectades (referència): 4
- Referència:
```sql
INSERT INTO `inventory_transactions` (`transaction_type`, `transaction_created_date`, `transaction_modified_date`, `product_id`, `quantity`, `purchase_order_id`, `comments`) SELECT t.`id`, '2006-05-02 09:00:00', '2006-05-02 09:00:00', d.`product_id`, d.`quantity`, d.`purchase_order_id`, CONCAT('Rebut de la comanda de compra #', d.`purchase_order_id`) FROM `purchase_order_details` d JOIN `purchase_orders` po ON po.`id` = d.`purchase_order_id` JOIN `purchase_order_status` s ON s.`id` = po.`status_id` JOIN `inventory_transaction_types` t ON t.`type_name` = 'Purchased' WHERE s.`status` = 'Submitted'
```
- Alternativa: **acceptada** 
```sql
INSERT INTO inventory_transactions (transaction_type, transaction_created_date, transaction_modified_date, product_id, quantity, purchase_order_id, comments) SELECT (SELECT id FROM inventory_transaction_types WHERE type_name = 'Purchased'), '2006-05-02 09:00:00', '2006-05-02 09:00:00', product_id, quantity, purchase_order_id, CONCAT('Rebut de la comanda de compra #', purchase_order_id) FROM purchase_order_details WHERE purchase_order_id IN (SELECT id FROM purchase_orders WHERE status_id = (SELECT id FROM purchase_order_status WHERE status = 'Submitted'))
```
- Incorrecta plausible: **rebutjada** The database's final content does not match what was expected after running your statement.
```sql
INSERT INTO inventory_transactions (transaction_type, transaction_created_date, transaction_modified_date, product_id, quantity, purchase_order_id, comments) SELECT 1, '2006-05-02 09:00:00', '2006-05-02 09:00:00', product_id, quantity, purchase_order_id, CONCAT('Rebut de la comanda de compra #', purchase_order_id) FROM purchase_order_details WHERE date_received IS NULL
```

### 6. Crea una comanda de compra (`purchase_orders`) per a cada proveïdor de `suppliers` que encara no en té cap, amb: `suppli…

- Files afectades (referència): 2
- Referència:
```sql
INSERT INTO `purchase_orders` (`supplier_id`, `created_by`, `creation_date`, `status_id`, `notes`) SELECT s.`id`, (SELECT `id` FROM `employees` WHERE `first_name` = 'Grover' AND `last_name` = 'Coppin'), '2006-07-01 00:00:00', (SELECT `id` FROM `purchase_order_status` WHERE `status` = 'New'), CONCAT('Primera comanda a ', s.`company`) FROM `suppliers` s WHERE NOT EXISTS (SELECT 1 FROM `purchase_orders` po WHERE po.`supplier_id` = s.`id`)
```
- Alternativa: **acceptada** 
```sql
INSERT INTO purchase_orders (supplier_id, created_by, creation_date, status_id, notes) SELECT s.id, e.id, '2006-07-01 00:00:00', st.id, CONCAT('Primera comanda a ', s.company) FROM suppliers s LEFT JOIN purchase_orders po ON po.supplier_id = s.id JOIN employees e ON e.first_name = 'Grover' AND e.last_name = 'Coppin' JOIN purchase_order_status st ON st.status = 'New' WHERE po.id IS NULL
```
- Incorrecta plausible: **rebutjada** The database's final content does not match what was expected after running your statement.
```sql
INSERT INTO purchase_orders (supplier_id, created_by, creation_date, status_id, notes) SELECT s.id, 5, '2006-07-01 00:00:00', 0, CONCAT('Primera comanda a ', s.company) FROM suppliers s WHERE s.id NOT IN (SELECT supplier_id FROM purchase_orders WHERE status_id = 0)
```

### 7. Reserva l'estoc de les línies de comanda que estan en estat 'Allocated' (taula `order_details_status`, columna `status_n…

- Files afectades (referència): 5
- Referència:
```sql
INSERT INTO `inventory_transactions` (`transaction_type`, `transaction_created_date`, `transaction_modified_date`, `product_id`, `quantity`, `comments`) SELECT (SELECT `id` FROM `inventory_transaction_types` WHERE `type_name` = 'On Hold'), '2006-06-30 23:59:00', '2006-06-30 23:59:00', od.`product_id`, SUM(od.`quantity`), CONCAT('Reserva de ', COUNT(*), ' línies') FROM `order_details` od JOIN `order_details_status` s ON s.`id` = od.`status_id` WHERE s.`status_name` = 'Allocated' GROUP BY od.`product_id`
```
- Alternativa: **acceptada** 
```sql
INSERT INTO inventory_transactions (transaction_type, transaction_created_date, transaction_modified_date, product_id, quantity, comments) SELECT t.id, '2006-06-30 23:59:00', '2006-06-30 23:59:00', od.product_id, SUM(od.quantity), CONCAT('Reserva de ', COUNT(od.id), ' línies') FROM order_details od JOIN inventory_transaction_types t ON t.type_name = 'On Hold' WHERE od.status_id = (SELECT id FROM order_details_status WHERE status_name = 'Allocated') GROUP BY od.product_id, t.id
```
- Incorrecta plausible: **rebutjada** The database's final content does not match what was expected after running your statement.
```sql
INSERT INTO inventory_transactions (transaction_type, transaction_created_date, transaction_modified_date, product_id, quantity, comments) SELECT 3, '2006-06-30 23:59:00', '2006-06-30 23:59:00', product_id, quantity, 'Reserva de 1 línies' FROM order_details WHERE status_id = 1
```

### 8. Factura les comandes en estat 'New' (taula `orders_status`) que tenen alguna línia a `order_details` però encara no tene…

- Files afectades (referència): 5
- Referència:
```sql
INSERT INTO `invoices` (`order_id`, `invoice_date`, `due_date`, `tax`, `shipping`, `amount_due`) SELECT o.`id`, '2006-06-30 00:00:00', DATE_ADD('2006-06-30 00:00:00', INTERVAL 30 DAY), 0, o.`shipping_fee`, ROUND(SUM(od.`quantity` * od.`unit_price` * (1 - od.`discount`)) + o.`shipping_fee`, 2) FROM `orders` o JOIN `orders_status` s ON s.`id` = o.`status_id` JOIN `order_details` od ON od.`order_id` = o.`id` LEFT JOIN `invoices` i ON i.`order_id` = o.`id` WHERE s.`status_name` = 'New' AND i.`id` IS NULL GROUP BY o.`id`, o.`shipping_fee`
```
- Alternativa: **acceptada** 
```sql
INSERT INTO invoices (order_id, invoice_date, due_date, tax, shipping, amount_due) SELECT o.id, '2006-06-30', '2006-07-30', 0, o.shipping_fee, ROUND((SELECT SUM(quantity * unit_price * (1 - discount)) FROM order_details WHERE order_id = o.id) + o.shipping_fee, 2) FROM orders o WHERE o.status_id = (SELECT id FROM orders_status WHERE status_name = 'New') AND EXISTS (SELECT 1 FROM order_details WHERE order_id = o.id) AND NOT EXISTS (SELECT 1 FROM invoices WHERE order_id = o.id)
```
- Incorrecta plausible: **rebutjada** The database's final content does not match what was expected after running your statement.
```sql
INSERT INTO invoices (order_id, invoice_date, due_date, tax, shipping, amount_due) SELECT o.id, '2006-06-30', '2006-07-30', 0, o.shipping_fee, ROUND(SUM(od.quantity * od.unit_price * (1 - od.discount)) + o.shipping_fee, 2) FROM orders o JOIN order_details od ON od.order_id = o.id WHERE o.status_id = 0 GROUP BY o.id, o.shipping_fee
```

### 9. Prepara la reposició dels productes de la categoria 'Dried Fruit & Nuts' que tenen poc estoc. L'estoc d'un producte és l…

- Files afectades (referència): 4
- Referència:
```sql
INSERT INTO `purchase_order_details` (`purchase_order_id`, `product_id`, `quantity`, `unit_cost`) SELECT 146, p.`id`, p.`target_level` - SUM(IF(tt.`type_name` = 'Purchased', t.`quantity`, -t.`quantity`)), p.`standard_cost` FROM `products` p JOIN `inventory_transactions` t ON t.`product_id` = p.`id` JOIN `inventory_transaction_types` tt ON tt.`id` = t.`transaction_type` WHERE p.`category` = 'Dried Fruit & Nuts' GROUP BY p.`id`, p.`target_level`, p.`standard_cost`, p.`reorder_level` HAVING SUM(IF(tt.`type_name` = 'Purchased', t.`quantity`, -t.`quantity`)) < p.`reorder_level`
```
- Alternativa: **acceptada** 
```sql
INSERT INTO purchase_order_details (purchase_order_id, product_id, quantity, unit_cost) SELECT 146, x.id, x.target_level - x.estoc, x.standard_cost FROM (SELECT p.id, p.target_level, p.reorder_level, p.standard_cost, SUM(CASE WHEN t.transaction_type = (SELECT id FROM inventory_transaction_types WHERE type_name = 'Purchased') THEN t.quantity ELSE -t.quantity END) AS estoc FROM products p JOIN inventory_transactions t ON t.product_id = p.id WHERE p.category = 'Dried Fruit & Nuts' GROUP BY p.id, p.target_level, p.reorder_level, p.standard_cost) x WHERE x.estoc < x.reorder_level
```
- Incorrecta plausible: **rebutjada** The database's final content does not match what was expected after running your statement.
```sql
INSERT INTO purchase_order_details (purchase_order_id, product_id, quantity, unit_cost) SELECT 146, p.id, p.target_level - SUM(t.quantity), p.standard_cost FROM products p JOIN inventory_transactions t ON t.product_id = p.id WHERE p.category = 'Dried Fruit & Nuts' GROUP BY p.id, p.target_level, p.standard_cost, p.reorder_level HAVING SUM(t.quantity) < p.reorder_level
```

### 10. La comanda 64 és nova i encara no té cap línia. El client vol "el mateix de sempre": afegeix a `order_details` una línia…

- Files afectades (referència): 5
- Referència:
```sql
INSERT INTO `order_details` (`order_id`, `product_id`, `quantity`, `unit_price`, `discount`, `status_id`) SELECT 64, od.`product_id`, ROUND(AVG(od.`quantity`)), p.`list_price`, 0, (SELECT `id` FROM `order_details_status` WHERE `status_name` = 'None') FROM `order_details` od JOIN `orders` o ON o.`id` = od.`order_id` JOIN `products` p ON p.`id` = od.`product_id` WHERE o.`customer_id` = (SELECT `customer_id` FROM `orders` WHERE `id` = 64) AND o.`id` <> 64 GROUP BY od.`product_id`, p.`list_price`
```
- Alternativa: **acceptada** 
```sql
INSERT INTO order_details (order_id, product_id, quantity, unit_price, discount, status_id) SELECT 64, p.id, (SELECT ROUND(AVG(d.quantity)) FROM order_details d JOIN orders o2 ON o2.id = d.order_id WHERE d.product_id = p.id AND o2.customer_id = c.customer_id AND o2.id <> 64), p.list_price, 0, s.id FROM products p JOIN (SELECT customer_id FROM orders WHERE id = 64) c JOIN order_details_status s ON s.status_name = 'None' WHERE p.id IN (SELECT d.product_id FROM order_details d JOIN orders o2 ON o2.id = d.order_id WHERE o2.customer_id = c.customer_id AND o2.id <> 64)
```
- Incorrecta plausible: **rebutjada** The database's final content does not match what was expected after running your statement.
```sql
INSERT INTO order_details (order_id, product_id, quantity, unit_price, discount, status_id) SELECT 64, od.product_id, SUM(od.quantity), p.list_price, 0, 0 FROM order_details od JOIN orders o ON o.id = od.order_id JOIN products p ON p.id = od.product_id WHERE o.customer_id = (SELECT customer_id FROM orders WHERE id = 64) GROUP BY od.product_id, p.list_price
```


## Northwind — UPDATE amb JOIN i subconsultes (sqlupdate)

### 1. Descataloga (`discontinued` = 1) els 4 productes de la categoria 'Canned Fruit & Vegetables' amb el `list_price` més bai…

- Files afectades (referència): 4
- Referència:
```sql
UPDATE `products` SET `discontinued` = 1 WHERE `category` = 'Canned Fruit & Vegetables' ORDER BY `list_price`, `id` LIMIT 4
```
- Alternativa: **acceptada** 
```sql
UPDATE products SET discontinued = 1 WHERE id IN (SELECT id FROM (SELECT id FROM products WHERE category = 'Canned Fruit & Vegetables' ORDER BY list_price ASC, id ASC LIMIT 4) AS barats)
```
- Incorrecta plausible: **rebutjada** The database's final content does not match what was expected after running your statement.
```sql
UPDATE products SET discontinued = 1 WHERE category = 'Canned Fruit & Vegetables' ORDER BY list_price, id DESC LIMIT 4
```

### 2. Alguns productes tenen un `product_code` que no acaba amb el seu propi `id` (per exemple, el producte 20 té el codi 'NWT…

- Files afectades (referència): 2
- Referència:
```sql
UPDATE `products` SET `product_code` = CONCAT(SUBSTRING_INDEX(`product_code`, '-', 1), '-', `id`) WHERE `product_code` NOT LIKE CONCAT('%-', `id`)
```
- Alternativa: **acceptada** 
```sql
UPDATE products SET product_code = CONCAT(LEFT(product_code, LOCATE('-', product_code)), id) WHERE SUBSTRING_INDEX(product_code, '-', -1) <> CAST(id AS CHAR)
```
- Incorrecta plausible: **rebutjada** The database's final content does not match what was expected after running your statement.
```sql
UPDATE products SET product_code = CONCAT(SUBSTRING_INDEX(product_code, '-', -1), '-', id) WHERE product_code NOT LIKE CONCAT('%-', id)
```

### 3. Volem un marge mínim del 30% sobre el cost. Per als productes amb un `list_price` inferior a `standard_cost * 1.3`, posa…

- Files afectades (referència): 3
- Referència:
```sql
UPDATE `products` SET `list_price` = ROUND(`standard_cost` * 1.3, 2) WHERE `list_price` < `standard_cost` * 1.3
```
- Alternativa: **acceptada** 
```sql
UPDATE products SET list_price = ROUND(standard_cost + standard_cost * 30 / 100, 2) WHERE list_price / standard_cost < 1.3
```
- Incorrecta plausible: **rebutjada** The database's final content does not match what was expected after running your statement.
```sql
UPDATE products SET list_price = ROUND(list_price * 1.3, 2) WHERE list_price < standard_cost * 1.3
```

### 4. Aplica descomptes per volum a les línies (`order_details`) de les comandes que estan en estat 'New' (taula `orders_statu…

- Files afectades (referència): 6
- Referència:
```sql
UPDATE `order_details` SET `discount` = CASE WHEN `quantity` >= 100 THEN 0.15 WHEN `quantity` >= 50 THEN 0.1 WHEN `quantity` >= 25 THEN 0.05 ELSE 0 END WHERE `order_id` IN (SELECT o.`id` FROM `orders` o JOIN `orders_status` s ON s.`id` = o.`status_id` WHERE s.`status_name` = 'New')
```
- Alternativa: **acceptada** 
```sql
UPDATE order_details od JOIN orders o ON o.id = od.order_id JOIN orders_status s ON s.id = o.status_id SET od.discount = CASE WHEN od.quantity < 25 THEN 0 WHEN od.quantity < 50 THEN 0.05 WHEN od.quantity < 100 THEN 0.1 ELSE 0.15 END WHERE s.status_name = 'New'
```
- Incorrecta plausible: **rebutjada** The database's final content does not match what was expected after running your statement.
```sql
UPDATE order_details SET discount = CASE WHEN quantity >= 25 THEN 0.05 WHEN quantity >= 50 THEN 0.1 WHEN quantity >= 100 THEN 0.15 ELSE 0 END WHERE order_id IN (SELECT id FROM orders WHERE status_id = 0)
```

### 5. Per a les comandes que es van enviar més de 2 dies després de la data de comanda (diferència en dies entre `shipped_date…

- Files afectades (referència): 3
- Referència:
```sql
UPDATE `orders` SET `notes` = CONCAT('Enviada amb ', DATEDIFF(`shipped_date`, `order_date`), ' dies de retard') WHERE DATEDIFF(`shipped_date`, `order_date`) > 2
```
- Alternativa: **acceptada** 
```sql
UPDATE orders SET notes = CONCAT('Enviada amb ', TO_DAYS(shipped_date) - TO_DAYS(order_date), ' dies de retard') WHERE shipped_date > DATE_ADD(order_date, INTERVAL 2 DAY) AND DATEDIFF(shipped_date, order_date) > 2
```
- Incorrecta plausible: **rebutjada** The database's final content does not match what was expected after running your statement.
```sql
UPDATE orders SET notes = CONCAT('Enviada amb ', DATEDIFF(shipped_date, order_date), ' dies de retard') WHERE DATEDIFF(shipped_date, order_date) >= 2
```

### 6. Reorganització comercial: les comandes en estat 'New' dels clients de l'estat d'Indiana (`customers.state_province` = 'I…

- Files afectades (referència): 4
- Referència:
```sql
UPDATE `orders` o JOIN `customers` c ON c.`id` = o.`customer_id` JOIN `orders_status` s ON s.`id` = o.`status_id` SET o.`employee_id` = (SELECT `id` FROM `employees` WHERE `first_name` = 'Grover' AND `last_name` = 'Coppin'), o.`shipper_id` = (SELECT `id` FROM `shippers` WHERE `company` = 'Shipping Company A') WHERE c.`state_province` = 'IN' AND s.`status_name` = 'New'
```
- Alternativa: **acceptada** 
```sql
UPDATE orders o JOIN customers c ON c.id = o.customer_id JOIN employees e ON e.first_name = 'Grover' AND e.last_name = 'Coppin' JOIN shippers sh ON sh.company = 'Shipping Company A' SET o.employee_id = e.id, o.shipper_id = sh.id WHERE c.state_province = 'IN' AND o.status_id = (SELECT id FROM orders_status WHERE status_name = 'New')
```
- Incorrecta plausible: **rebutjada** The database's final content does not match what was expected after running your statement.
```sql
UPDATE orders o JOIN customers c ON c.id = o.customer_id SET o.employee_id = 5, o.shipper_id = 1 WHERE c.state_province = 'IN'
```

### 7. Actualitza el `standard_cost` de cada producte que s'ha comprat alguna vegada al `unit_cost` de la seva línia de compra …

- Files afectades (referència): 23
- Referència:
```sql
UPDATE `products` p SET p.`standard_cost` = (SELECT d.`unit_cost` FROM `purchase_order_details` d WHERE d.`product_id` = p.`id` ORDER BY d.`id` DESC LIMIT 1) WHERE EXISTS (SELECT 1 FROM `purchase_order_details` d WHERE d.`product_id` = p.`id`)
```
- Alternativa: **acceptada** 
```sql
UPDATE products p JOIN purchase_order_details d ON d.product_id = p.id AND d.id = (SELECT MAX(d2.id) FROM purchase_order_details d2 WHERE d2.product_id = p.id) SET p.standard_cost = d.unit_cost
```
- Incorrecta plausible: **rebutjada** The database's final content does not match what was expected after running your statement.
```sql
UPDATE products p SET p.standard_cost = (SELECT AVG(d.unit_cost) FROM purchase_order_details d WHERE d.product_id = p.id) WHERE EXISTS (SELECT 1 FROM purchase_order_details d WHERE d.product_id = p.id)
```

### 8. Hi ha productes amb un preu desproporcionat respecte a la seva categoria. Per a cada producte amb un `list_price` més gr…

- Files afectades (referència): 5
- Referència:
```sql
UPDATE `products` p JOIN (SELECT `category`, AVG(`list_price`) AS mitjana FROM `products` GROUP BY `category`) m ON m.`category` = p.`category` SET p.`list_price` = ROUND(2 * m.mitjana, 2) WHERE p.`list_price` > 2 * m.mitjana
```
- Alternativa: **acceptada** 
```sql
UPDATE products SET list_price = ROUND(2 * (SELECT AVG(p2.list_price) FROM products p2 WHERE p2.category = products.category), 2) WHERE list_price > 2 * (SELECT AVG(p2.list_price) FROM products p2 WHERE p2.category = products.category)
```
- Incorrecta plausible: **rebutjada** The database's final content does not match what was expected after running your statement.
```sql
UPDATE products p JOIN (SELECT category, AVG(list_price) AS mitjana FROM products GROUP BY category) m ON m.category = p.category SET p.list_price = 2 * m.mitjana WHERE p.list_price > m.mitjana
```

### 9. Recalcula les factures emeses al març del 2006 (`invoice_date` dins de març de 2006): `shipping` = el `shipping_fee` de …

- Files afectades (referència): 11
- Referència:
```sql
UPDATE `invoices` i JOIN `orders` o ON o.`id` = i.`order_id` JOIN (SELECT `order_id`, SUM(`quantity` * `unit_price` * (1 - `discount`)) AS subtotal FROM `order_details` GROUP BY `order_id`) t ON t.`order_id` = i.`order_id` SET i.`shipping` = o.`shipping_fee`, i.`amount_due` = ROUND(t.subtotal + o.`shipping_fee`, 2) WHERE i.`invoice_date` >= '2006-03-01' AND i.`invoice_date` < '2006-04-01'
```
- Alternativa: **acceptada** 
```sql
UPDATE invoices SET shipping = (SELECT shipping_fee FROM orders WHERE id = invoices.order_id), amount_due = ROUND((SELECT SUM(quantity * unit_price * (1 - discount)) FROM order_details WHERE order_id = invoices.order_id) + (SELECT shipping_fee FROM orders WHERE id = invoices.order_id), 2) WHERE YEAR(invoice_date) = 2006 AND MONTH(invoice_date) = 3
```
- Incorrecta plausible: **rebutjada** The database's final content does not match what was expected after running your statement.
```sql
UPDATE invoices i JOIN orders o ON o.id = i.order_id JOIN (SELECT order_id, SUM(quantity * unit_price * (1 - discount)) AS subtotal FROM order_details GROUP BY order_id) t ON t.order_id = i.order_id SET i.shipping = o.shipping_fee, i.amount_due = ROUND(t.subtotal + o.shipping_fee, 2) WHERE i.invoice_date BETWEEN '2006-03-01' AND '2006-03-22'
```

### 10. Hi ha comandes que encara consten com a 'New' però que ja tenen factura. Amb **una sola** sentència que modifiqui dues t…

- Files afectades (referència): 6
- Referència:
```sql
UPDATE `orders` o JOIN `invoices` i ON i.`order_id` = o.`id` SET o.`status_id` = (SELECT `id` FROM `orders_status` WHERE `status_name` = 'Invoiced'), i.`due_date` = DATE_ADD(i.`invoice_date`, INTERVAL 30 DAY) WHERE o.`status_id` = (SELECT `id` FROM `orders_status` WHERE `status_name` = 'New')
```
- Alternativa: **acceptada** 
```sql
UPDATE invoices i JOIN orders o ON o.id = i.order_id JOIN orders_status s_old ON s_old.id = o.status_id AND s_old.status_name = 'New' JOIN orders_status s_new ON s_new.status_name = 'Invoiced' SET i.due_date = i.invoice_date + INTERVAL 30 DAY, o.status_id = s_new.id
```
- Incorrecta plausible: **rebutjada** The database's final content does not match what was expected after running your statement.
```sql
UPDATE orders o JOIN invoices i ON i.order_id = o.id SET o.status_id = 1, i.due_date = DATE_ADD(i.invoice_date, INTERVAL 30 DAY)
```


## Northwind — DELETE (sqldelete)

### 1. Esborra les transaccions d'inventari del tipus 'On Hold' (taula `inventory_transaction_types`, busca'l pel nom) creades …

- Files afectades (referència): 8
- Referència:
```sql
DELETE FROM `inventory_transactions` WHERE `transaction_type` = (SELECT `id` FROM `inventory_transaction_types` WHERE `type_name` = 'On Hold') AND `transaction_created_date` >= '2006-03-01' AND `transaction_created_date` < '2006-04-01'
```
- Alternativa: **acceptada** 
```sql
DELETE t FROM inventory_transactions t JOIN inventory_transaction_types tt ON tt.id = t.transaction_type WHERE tt.type_name = 'On Hold' AND DATE_FORMAT(t.transaction_created_date, '%Y-%m') = '2006-03'
```
- Incorrecta plausible: **rebutjada** The database's final content does not match what was expected after running your statement.
```sql
DELETE FROM inventory_transactions WHERE transaction_type = 3 AND transaction_created_date BETWEEN '2006-03-01' AND '2006-03-29'
```

### 2. A la taula `strings`, esborra els missatges amb `string_id` 100 o més gran que contenen el caràcter `|` (és el lloc on l…

- Files afectades (referència): 3
- Referència:
```sql
DELETE FROM `strings` WHERE `string_id` >= 100 AND `string_data` LIKE '%|%'
```
- Alternativa: **acceptada** 
```sql
DELETE FROM strings WHERE LOCATE('|', string_data) > 0 AND string_id > 99
```
- Incorrecta plausible: **rebutjada** The database's final content does not match what was expected after running your statement.
```sql
DELETE FROM strings WHERE string_data LIKE '%|%'
```

### 3. Esborra de `customers` els clients que no tenen cap comanda a `orders`. Fes-ho amb `NOT IN`.…

- Files afectades (referència): 14
- Referència:
```sql
DELETE FROM `customers` WHERE `id` NOT IN (SELECT `customer_id` FROM `orders` WHERE `customer_id` IS NOT NULL)
```
- Alternativa: **acceptada** 
```sql
DELETE FROM customers WHERE NOT EXISTS (SELECT 1 FROM orders o WHERE o.customer_id = customers.id)
```
- Incorrecta plausible: **rebutjada** SQL error: Cannot delete or update a parent row: a foreign key constraint fails (`w_northwind`.`orders`, CONSTRAINT `fk_orders_customers` FOREIGN KEY (`customer_id`) REFERENCES `customers` (`id`) ON DELETE NO ACTION ON UPDATE NO ACTION)
```sql
DELETE FROM customers WHERE id NOT IN (SELECT customer_id FROM orders WHERE status_id = 3)
```

### 4. Esborra les 5 línies de comanda de compra (`purchase_order_details`) **encara no rebudes** (`date_received` nul) amb la …

- Files afectades (referència): 5
- Referència:
```sql
DELETE FROM `purchase_order_details` WHERE `date_received` IS NULL ORDER BY `quantity` DESC, `id` LIMIT 5
```
- Alternativa: **acceptada** 
```sql
DELETE FROM purchase_order_details WHERE id IN (SELECT id FROM (SELECT id FROM purchase_order_details WHERE date_received IS NULL ORDER BY quantity DESC, id ASC LIMIT 5) AS x)
```
- Incorrecta plausible: **rebutjada** The database's final content does not match what was expected after running your statement.
```sql
DELETE FROM purchase_order_details WHERE date_received IS NULL ORDER BY quantity DESC LIMIT 4
```

### 5. El client 'Towne, Mante and Kuphal' (columna `company`) ha anul·lat tot el que tenia pendent. Esborra les línies (`order…

- Files afectades (referència): 3
- Referència:
```sql
DELETE od FROM `order_details` od JOIN `orders` o ON o.`id` = od.`order_id` JOIN `customers` c ON c.`id` = o.`customer_id` JOIN `orders_status` s ON s.`id` = o.`status_id` WHERE c.`company` = 'Towne, Mante and Kuphal' AND s.`status_name` = 'New'
```
- Alternativa: **acceptada** 
```sql
DELETE FROM order_details WHERE order_id IN (SELECT o.id FROM orders o JOIN customers c ON c.id = o.customer_id WHERE c.company = 'Towne, Mante and Kuphal' AND o.status_id = (SELECT id FROM orders_status WHERE status_name = 'New'))
```
- Incorrecta plausible: **rebutjada** SQL error: Cannot delete or update a parent row: a foreign key constraint fails (`w_northwind`.`order_details`, CONSTRAINT `fk_order_details_orders1` FOREIGN KEY (`order_id`) REFERENCES `orders` (`id`) ON DELETE NO ACTION ON UPDATE NO ACTION)
```sql
DELETE od, o FROM order_details od JOIN orders o ON o.id = od.order_id JOIN customers c ON c.id = o.customer_id WHERE c.company = 'Towne, Mante and Kuphal' AND o.status_id = 0
```

### 6. Esborra les comandes (`orders`) que no tenen cap línia a `order_details` ni cap factura a `invoices`. Usa `NOT EXISTS`.…

- Files afectades (referència): 8
- Referència:
```sql
DELETE FROM `orders` WHERE NOT EXISTS (SELECT 1 FROM `order_details` od WHERE od.`order_id` = `orders`.`id`) AND NOT EXISTS (SELECT 1 FROM `invoices` i WHERE i.`order_id` = `orders`.`id`)
```
- Alternativa: **acceptada** 
```sql
DELETE o FROM orders o LEFT JOIN order_details od ON od.order_id = o.id LEFT JOIN invoices i ON i.order_id = o.id WHERE od.id IS NULL AND i.id IS NULL
```
- Incorrecta plausible: **rebutjada** The database's final content does not match what was expected after running your statement.
```sql
DELETE FROM orders WHERE NOT EXISTS (SELECT 1 FROM order_details od WHERE od.order_id = orders.id) AND shipped_date IS NULL
```

### 7. Neteja el catàleg: esborra els productes de la categoria 'Canned Fruit & Vegetables' que **no** apareixen en cap línia d…

- Files afectades (referència): 7
- Referència:
```sql
DELETE FROM `products` WHERE `category` = 'Canned Fruit & Vegetables' AND NOT EXISTS (SELECT 1 FROM `order_details` d WHERE d.`product_id` = `products`.`id`) AND NOT EXISTS (SELECT 1 FROM `purchase_order_details` pd WHERE pd.`product_id` = `products`.`id`) AND NOT EXISTS (SELECT 1 FROM `inventory_transactions` t WHERE t.`product_id` = `products`.`id`)
```
- Alternativa: **acceptada** 
```sql
DELETE FROM products WHERE category = 'Canned Fruit & Vegetables' AND id NOT IN (SELECT product_id FROM order_details WHERE product_id IS NOT NULL UNION SELECT product_id FROM purchase_order_details WHERE product_id IS NOT NULL UNION SELECT product_id FROM inventory_transactions)
```
- Incorrecta plausible: **rebutjada** The database's final content does not match what was expected after running your statement.
```sql
DELETE FROM products WHERE category = 'Canned Fruit & Vegetables' AND NOT EXISTS (SELECT 1 FROM order_details d WHERE d.product_id = products.id) AND discontinued = 0 AND list_price < 2
```

### 8. Allibera les reserves que ja no calen: esborra les transaccions d'inventari del tipus 'On Hold' dels productes que **no*…

- Files afectades (referència): 3
- Referència:
```sql
DELETE FROM `inventory_transactions` WHERE `transaction_type` = (SELECT `id` FROM `inventory_transaction_types` WHERE `type_name` = 'On Hold') AND `product_id` NOT IN (SELECT od.`product_id` FROM `order_details` od JOIN `order_details_status` s ON s.`id` = od.`status_id` WHERE s.`status_name` = 'Allocated' AND od.`product_id` IS NOT NULL)
```
- Alternativa: **acceptada** 
```sql
DELETE t FROM inventory_transactions t JOIN inventory_transaction_types tt ON tt.id = t.transaction_type WHERE tt.type_name = 'On Hold' AND NOT EXISTS (SELECT 1 FROM order_details od JOIN order_details_status s ON s.id = od.status_id WHERE od.product_id = t.product_id AND s.status_name = 'Allocated')
```
- Incorrecta plausible: **rebutjada** The database's final content does not match what was expected after running your statement.
```sql
DELETE FROM inventory_transactions WHERE transaction_type = 3 AND product_id NOT IN (SELECT product_id FROM order_details WHERE product_id IS NOT NULL)
```

### 9. A `purchase_order_details` hi ha línies duplicades: la mateixa comanda de compra (`purchase_order_id`) amb el mateix pro…

- Files afectades (referència): 4
- Referència:
```sql
DELETE d2 FROM `purchase_order_details` d1 JOIN `purchase_order_details` d2 ON d2.`purchase_order_id` = d1.`purchase_order_id` AND d2.`product_id` = d1.`product_id` AND d2.`id` > d1.`id`
```
- Alternativa: **acceptada** 
```sql
DELETE FROM purchase_order_details WHERE id NOT IN (SELECT min_id FROM (SELECT MIN(id) AS min_id FROM purchase_order_details GROUP BY purchase_order_id, product_id) AS x)
```
- Incorrecta plausible: **rebutjada** The database's final content does not match what was expected after running your statement.
```sql
DELETE d2 FROM purchase_order_details d1 JOIN purchase_order_details d2 ON d2.purchase_order_id = d1.purchase_order_id AND d2.product_id = d1.product_id AND d2.id <> d1.id
```

### 10. Esborra les transaccions d'inventari del tipus 'Sold' la quantitat de les quals és **inferior** a la quantitat mitjana d…

- Files afectades (referència): 20
- Referència:
```sql
DELETE t FROM `inventory_transactions` t JOIN `inventory_transaction_types` tt ON tt.`id` = t.`transaction_type` JOIN (SELECT x.`product_id`, AVG(x.`quantity`) AS mitjana FROM `inventory_transactions` x JOIN `inventory_transaction_types` xt ON xt.`id` = x.`transaction_type` WHERE xt.`type_name` = 'Sold' GROUP BY x.`product_id`) m ON m.`product_id` = t.`product_id` WHERE tt.`type_name` = 'Sold' AND t.`quantity` < m.mitjana
```
- Alternativa: **acceptada** 
```sql
DELETE FROM inventory_transactions WHERE transaction_type = (SELECT id FROM inventory_transaction_types WHERE type_name = 'Sold') AND quantity < (SELECT AVG(x.quantity) FROM inventory_transactions x WHERE x.product_id = inventory_transactions.product_id AND x.transaction_type = inventory_transactions.transaction_type)
```
- Incorrecta plausible: **rebutjada** The database's final content does not match what was expected after running your statement.
```sql
DELETE t FROM inventory_transactions t JOIN (SELECT product_id, AVG(quantity) AS mitjana FROM inventory_transactions GROUP BY product_id) m ON m.product_id = t.product_id WHERE t.transaction_type = 2 AND t.quantity < m.mitjana
```
