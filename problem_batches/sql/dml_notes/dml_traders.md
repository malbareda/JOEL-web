# dml_traders — verificació amb el corrector real (dmoj.checkers.mysqlwrite)

Per a cada pregunta: alternativa (escrita diferent, ha de PASSAR) i incorrecta plausible (ha de FALLAR).

## Traders — INSERT avançat (sqlinsert)

### Q1 OK

- Referència: `INSERT INTO Products (Name) VALUES ('Quantum Saffron'), ('Ion Pepper'), ('Nebula Honey')`
- Alternativa: `INSERT INTO Products (Name) SELECT 'Quantum Saffron' UNION ALL SELECT 'Ion Pepper' UNION ALL SELECT 'Nebula Honey'` -> passed=True 
- Incorrecta: `INSERT INTO Products (Name) VALUES ('Quantum Saffron'), ('Ion Pepper')` -> passed=False The database's final content does not match what was expected after running your statement.

### Q2 OK

- Referència: `INSERT INTO Stays (StartDate, TraderId, EndDate, PlanetId) SELECT '2390-01-10', t.Id, '2390-06-30', p.Id FROM Traders t JOIN Planets p ON p.Name = 'Pasnillon' WHERE t.Nickname = 'Mime'`
- Alternativa: `INSERT INTO Stays (StartDate, TraderId, EndDate, PlanetId) VALUES ('2390-01-10', (SELECT Id FROM Traders WHERE Nickname = 'Mime'), '2390-06-30', (SELECT Id FROM Planets WHERE Name = 'Pasnillon'))` -> passed=True 
- Incorrecta: `INSERT INTO Stays (StartDate, TraderId, EndDate, PlanetId) VALUES ('2390-01-10', (SELECT Id FROM Traders WHERE Nickname = 'Mime'), '2390-06-30', (SELECT Id FROM Planets WHERE Name = 'Proria 3M7A'))` -> passed=False The database's final content does not match what was expected after running your statement.

### Q3 OK

- Referència: `INSERT INTO Stays (StartDate, TraderId, EndDate, PlanetId) SELECT '2400-01-01', t.Id, '2400-01-15', p.Id FROM Traders t CROSS JOIN Planets p WHERE t.DeceaseDate IS NULL AND p.Name = 'Cretestea'`
- Alternativa: `INSERT INTO Stays (StartDate, TraderId, EndDate, PlanetId) SELECT '2400-01-01', Id, '2400-01-15', (SELECT Id FROM Planets WHERE Name = 'Cretestea') FROM Traders WHERE DeceaseDate IS NULL` -> passed=True 
- Incorrecta: `INSERT INTO Stays (StartDate, TraderId, EndDate, PlanetId) SELECT '2400-01-01', Id, '2400-01-15', (SELECT Id FROM Planets WHERE Name = 'Cretestea') FROM Traders` -> passed=False The database's final content does not match what was expected after running your statement.

### Q4 OK

- Referència: `INSERT IGNORE INTO Ships (Name, Type, Capacity) VALUES ('Phoenix', 'Fighter', 8), ('Star Wanderer', 'Cargo ship', 220), ('Comet Tail', 'Spaceship', 12)`
- Alternativa: `INSERT INTO Ships (Name, Type, Capacity) VALUES ('Phoenix', 'Fighter', 8), ('Star Wanderer', 'Cargo ship', 220), ('Comet Tail', 'Spaceship', 12) ON DUPLICATE KEY UPDATE Name = Name` -> passed=True 
- Incorrecta: `INSERT INTO Ships (Name, Type, Capacity) VALUES ('Phoenix', 'Fighter', 8), ('Star Wanderer', 'Cargo ship', 220), ('Comet Tail', 'Spaceship', 12) ON DUPLICATE KEY UPDATE Capacity = VALUES(Capacity)` -> passed=False The database's final content does not match what was expected after running your statement.

### Q5 OK

- Referència: `INSERT INTO PriceChanges (Date, ProductId, PlanetId, NewPrice) VALUES ('2200-03-29', 17, 1, 2250.00), ('2200-03-29', 13, 1, 980.50) ON DUPLICATE KEY UPDATE NewPrice = VALUES(NewPrice)`
- Alternativa: `INSERT INTO PriceChanges (Date, ProductId, PlanetId, NewPrice) SELECT '2200-03-29', 13, 1, 980.50 UNION ALL SELECT '2200-03-29', 17, 1, 2250.00 ON DUPLICATE KEY UPDATE NewPrice = VALUES(NewPrice)` -> passed=True 
- Incorrecta: `REPLACE INTO PriceChanges (Date, ProductId, PlanetId, NewPrice) VALUES ('2200-03-29', 17, 1, 2250.00), ('2200-03-29', 13, 1, 980.50)` -> passed=False The database's final content does not match what was expected after running your statement.

### Q6 OK

- Referència: `REPLACE INTO Ships (Id, Name, Type, Capacity) VALUES (31, 'CS Firebrand II', 'Cargo ship', 140), (128, 'Iron Pelican', 'Cargo ship', 180)`
- Alternativa: `INSERT INTO Ships (Id, Name, Type, Capacity) VALUES (31, 'CS Firebrand II', 'Cargo ship', 140), (128, 'Iron Pelican', 'Cargo ship', 180) ON DUPLICATE KEY UPDATE Name = VALUES(Name), Type = VALUES(Type), Capacity = VALUES(Capacity)` -> passed=True 
- Incorrecta: `REPLACE INTO Ships (Name, Type, Capacity) VALUES ('CS Firebrand II', 'Cargo ship', 140), ('Iron Pelican', 'Cargo ship', 180)` -> passed=False The database's final content does not match what was expected after running your statement.

### Q7 OK

- Referència: `INSERT INTO Trades (StayId, DateTime, Type, Total) SELECT s.Id, TIMESTAMP(s.EndDate, '12:00:00'), 'Sell', ROUND(SUM(t.Total) * 1.15, 2) FROM Stays s JOIN Traders tr ON tr.Id = s.TraderId JOIN Trades t ON t.StayId = s.Id WHERE tr.Nickname = 'Cyclone' AND t.Type = 'Buy' GROUP BY s.Id, s.EndDate`
- Alternativa: `INSERT INTO Trades (StayId, DateTime, Type, Total) SELECT s.Id, CONCAT(s.EndDate, ' 12:00:00'), 'Sell', ROUND(1.15 * (SELECT SUM(b.Total) FROM Trades b WHERE b.StayId = s.Id AND b.Type = 'Buy'), 2) FROM Stays s WHERE s.TraderId = (SELECT Id FROM Traders WHERE Nickname = 'Cyclone') AND EXISTS (SELECT 1 FROM Trades b WHERE b.StayId = s.Id AND b.Type = 'Buy')` -> passed=True 
- Incorrecta: `INSERT INTO Trades (StayId, DateTime, Type, Total) SELECT s.Id, TIMESTAMP(s.EndDate, '12:00:00'), 'Sell', ROUND(SUM(t.Total) * 1.15, 2) FROM Stays s JOIN Traders tr ON tr.Id = s.TraderId JOIN Trades t ON t.StayId = s.Id WHERE tr.Nickname = 'Cyclone' GROUP BY s.Id, s.EndDate` -> passed=False The database's final content does not match what was expected after running your statement.

### Q8 OK

- Referència: `INSERT INTO ShipOwners (ShipId, TraderId, AcquisitionDate, AcquisitionPrice) SELECT s.Id, t.Id, '2390-05-01', s.Capacity * 1500 FROM Ships s JOIN Traders t ON t.Nickname = 'Panther' WHERE s.Type = 'Fighter' AND NOT EXISTS (SELECT 1 FROM ShipOwners o WHERE o.ShipId = s.Id)`
- Alternativa: `INSERT INTO ShipOwners (ShipId, TraderId, AcquisitionDate, AcquisitionPrice) SELECT s.Id, (SELECT Id FROM Traders WHERE Nickname = 'Panther'), '2390-05-01', 1500 * s.Capacity FROM Ships s LEFT JOIN ShipOwners o ON o.ShipId = s.Id WHERE o.Id IS NULL AND s.Type = 'Fighter'` -> passed=True 
- Incorrecta: `INSERT INTO ShipOwners (ShipId, TraderId, AcquisitionDate, AcquisitionPrice) SELECT s.Id, (SELECT Id FROM Traders WHERE Nickname = 'Panther'), '2390-05-01', 1500 * s.Capacity FROM Ships s WHERE s.Type = 'Fighter'` -> passed=False The database's final content does not match what was expected after running your statement.

### Q9 OK

- Referència: `INSERT INTO PriceChanges (Date, ProductId, PlanetId, NewPrice) SELECT '2501-01-01', pc.ProductId, (SELECT Id FROM Planets WHERE Name = 'Cretestea'), ROUND(AVG(pc.NewPrice), 2) FROM PriceChanges pc JOIN Planets p ON p.Id = pc.PlanetId JOIN SolarSystems ss ON ss.Id = p.SystemId WHERE ss.Name = 'Cailt' GROUP BY pc.ProductId HAVING COUNT(*) >= 400`
- Alternativa: `INSERT INTO PriceChanges (Date, ProductId, PlanetId, NewPrice) SELECT '2501-01-01', x.ProductId, cr.Id, x.m FROM (SELECT ProductId, ROUND(AVG(NewPrice), 2) AS m, COUNT(*) AS n FROM PriceChanges WHERE PlanetId IN (SELECT Id FROM Planets WHERE SystemId = (SELECT Id FROM SolarSystems WHERE Name = 'Cailt')) GROUP BY ProductId) x JOIN Planets cr ON cr.Name = 'Cretestea' WHERE x.n >= 400` -> passed=True 
- Incorrecta: `INSERT INTO PriceChanges (Date, ProductId, PlanetId, NewPrice) SELECT '2501-01-01', pc.ProductId, 1, ROUND(AVG(pc.NewPrice), 2) FROM PriceChanges pc GROUP BY pc.ProductId HAVING COUNT(*) >= 400` -> passed=False The database's final content does not match what was expected after running your statement.

### Q10 OK

- Referència: `INSERT INTO TradeLines (ProductId, TradeId, UnitPrice, Quantity) SELECT p.Id, t.Id, 40000.00, 25 FROM Trades t JOIN Stays s ON s.Id = t.StayId JOIN Traders tr ON tr.Id = s.TraderId JOIN Products p ON p.Name = 'Worm Celery' WHERE tr.Nickname = 'Nix' AND t.Type = 'Buy' ON DUPLICATE KEY UPDATE Quantity = TradeLines.Quantity + 25`
- Alternativa: `INSERT INTO TradeLines (ProductId, TradeId, UnitPrice, Quantity) SELECT (SELECT Id FROM Products WHERE Name = 'Worm Celery'), Id, 40000.00, 25 FROM Trades WHERE Type = 'Buy' AND StayId IN (SELECT Id FROM Stays WHERE TraderId = (SELECT Id FROM Traders WHERE Nickname = 'Nix')) ON DUPLICATE KEY UPDATE Quantity = Quantity + VALUES(Quantity)` -> passed=True 
- Incorrecta: `INSERT INTO TradeLines (ProductId, TradeId, UnitPrice, Quantity) SELECT (SELECT Id FROM Products WHERE Name = 'Worm Celery'), Id, 40000.00, 25 FROM Trades WHERE Type = 'Buy' AND StayId IN (SELECT Id FROM Stays WHERE TraderId = (SELECT Id FROM Traders WHERE Nickname = 'Nix')) ON DUPLICATE KEY UPDATE Quantity = 25` -> passed=False The database's final content does not match what was expected after running your statement.

## Traders — UPDATE amb JOIN i subconsultes (sqlupdate)

### Q1 OK

- Referència: `UPDATE ShipOwners SET LostBenefit = ROUND(AcquisitionPrice * 0.40, 2) WHERE LostCause = 'Destroyed' AND AcquisitionCause = 'Bought'`
- Alternativa: `UPDATE ShipOwners SET LostBenefit = ROUND(AcquisitionPrice * 2 / 5, 2) WHERE AcquisitionCause = 'Bought' AND LostCause = 'Destroyed'` -> passed=True 
- Incorrecta: `UPDATE ShipOwners SET LostBenefit = ROUND(AcquisitionPrice * 0.04, 2) WHERE LostCause = 'Destroyed' AND AcquisitionCause = 'Bought'` -> passed=False The database's final content does not match what was expected after running your statement.

### Q2 OK

- Referència: `UPDATE Stays SET EndDate = DATE_ADD(EndDate, INTERVAL 30 DAY) WHERE StartDate >= '2350-01-01' AND PlanetId IN (SELECT p.Id FROM Planets p JOIN SolarSystems ss ON ss.Id = p.SystemId WHERE ss.Name IN ('Ichua', 'Exax'))`
- Alternativa: `UPDATE Stays s JOIN Planets p ON p.Id = s.PlanetId JOIN SolarSystems ss ON ss.Id = p.SystemId SET s.EndDate = s.EndDate + INTERVAL 30 DAY WHERE (ss.Name = 'Ichua' OR ss.Name = 'Exax') AND s.StartDate >= '2350-01-01'` -> passed=True 
- Incorrecta: `UPDATE Stays s JOIN Planets p ON p.Id = s.PlanetId JOIN SolarSystems ss ON ss.Id = p.SystemId SET s.EndDate = s.EndDate + INTERVAL 1 MONTH WHERE ss.Name IN ('Ichua', 'Exax') AND s.StartDate >= '2350-01-01'` -> passed=False The database's final content does not match what was expected after running your statement.

### Q3 OK

- Referència: `UPDATE PriceChanges pc JOIN Planets p ON p.Id = pc.PlanetId JOIN SolarSystems ss ON ss.Id = p.SystemId SET pc.NewPrice = ROUND(pc.NewPrice * 0.85, 2) WHERE ss.Name = 'Vrauddact' AND pc.Date >= '2490-01-01'`
- Alternativa: `UPDATE PriceChanges SET NewPrice = ROUND(NewPrice - NewPrice * 0.15, 2) WHERE Date >= '2490-01-01' AND PlanetId IN (SELECT Id FROM Planets WHERE SystemId = (SELECT Id FROM SolarSystems WHERE Name = 'Vrauddact'))` -> passed=True 
- Incorrecta: `UPDATE PriceChanges pc JOIN Planets p ON p.Id = pc.PlanetId JOIN SolarSystems ss ON ss.Id = p.SystemId SET pc.NewPrice = ROUND(pc.NewPrice * 0.15, 2) WHERE ss.Name = 'Vrauddact' AND pc.Date >= '2490-01-01'` -> passed=False The database's final content does not match what was expected after running your statement.

### Q4 OK

- Referència: `UPDATE Ships SET Type = CASE WHEN Capacity < 150 THEN 'Light cargo ship' WHEN Capacity >= 300 THEN 'Heavy cargo ship' ELSE Type END WHERE Type = 'Cargo ship'`
- Alternativa: `UPDATE Ships SET Type = IF(Capacity < 150, 'Light cargo ship', IF(Capacity >= 300, 'Heavy cargo ship', 'Cargo ship')) WHERE Type = 'Cargo ship'` -> passed=True 
- Incorrecta: `UPDATE Ships SET Type = CASE WHEN Capacity < 150 THEN 'Light cargo ship' WHEN Capacity > 300 THEN 'Heavy cargo ship' ELSE Type END WHERE Type = 'Cargo ship'` -> passed=False The database's final content does not match what was expected after running your statement.

### Q5 OK

- Referència: `UPDATE Ships SET Capacity = Capacity + 50 WHERE Type = 'Cargo ship' ORDER BY Capacity, Id LIMIT 5`
- Alternativa: `UPDATE Ships SET Capacity = Capacity + 50 WHERE Id IN (SELECT Id FROM (SELECT Id FROM Ships WHERE Type = 'Cargo ship' ORDER BY Capacity, Id LIMIT 5) AS x)` -> passed=True 
- Incorrecta: `UPDATE Ships SET Capacity = Capacity + 50 WHERE Type = 'Cargo ship' ORDER BY Capacity DESC, Id LIMIT 5` -> passed=False The database's final content does not match what was expected after running your statement.

### Q6 OK

- Referència: `UPDATE Trades t SET t.Total = (SELECT ROUND(SUM(l.UnitPrice * l.Quantity), 2) FROM TradeLines l WHERE l.TradeId = t.Id) WHERE t.StayId IN (SELECT s.Id FROM Stays s JOIN Traders tr ON tr.Id = s.TraderId WHERE tr.Nickname = 'Pug')`
- Alternativa: `UPDATE Trades t JOIN Stays s ON s.Id = t.StayId JOIN Traders tr ON tr.Id = s.TraderId JOIN (SELECT TradeId, SUM(UnitPrice * Quantity) AS suma FROM TradeLines GROUP BY TradeId) x ON x.TradeId = t.Id SET t.Total = ROUND(x.suma, 2) WHERE tr.Nickname = 'Pug'` -> passed=True 
- Incorrecta: `UPDATE Trades t SET t.Total = (SELECT ROUND(SUM(l.UnitPrice), 2) FROM TradeLines l WHERE l.TradeId = t.Id) WHERE t.StayId IN (SELECT s.Id FROM Stays s JOIN Traders tr ON tr.Id = s.TraderId WHERE tr.Nickname = 'Pug')` -> passed=False The database's final content does not match what was expected after running your statement.

### Q7 OK

- Referència: `UPDATE PriceChanges pc JOIN Planets p ON p.Id = pc.PlanetId SET pc.NewPrice = ROUND(pc.NewPrice * CASE WHEN p.AverageDistance < 1 THEN 1.02 WHEN p.AverageDistance < 10 THEN 1.05 ELSE 1.10 END, 2) WHERE pc.Date BETWEEN '2499-01-01' AND '2499-12-31'`
- Alternativa: `UPDATE PriceChanges SET NewPrice = ROUND(NewPrice * (SELECT CASE WHEN AverageDistance >= 10 THEN 1.10 WHEN AverageDistance >= 1 THEN 1.05 ELSE 1.02 END FROM Planets WHERE Planets.Id = PriceChanges.PlanetId), 2) WHERE YEAR(Date) = 2499` -> passed=True 
- Incorrecta: `UPDATE PriceChanges pc JOIN Planets p ON p.Id = pc.PlanetId SET pc.NewPrice = ROUND(pc.NewPrice * CASE WHEN p.AverageDistance < 1 THEN 1.02 WHEN p.AverageDistance < 10 THEN 1.05 ELSE 1.01 END, 2) WHERE pc.Date BETWEEN '2499-01-01' AND '2499-12-31'` -> passed=False The database's final content does not match what was expected after running your statement.

### Q8 OK

- Referència: `UPDATE Ships SET Capacity = (SELECT ROUND(x.m) FROM (SELECT AVG(Capacity) AS m FROM Ships WHERE Type = 'Fighter') AS x) WHERE Type = 'Fighter' AND Capacity < (SELECT x.m FROM (SELECT AVG(Capacity) AS m FROM Ships WHERE Type = 'Fighter') AS x)`
- Alternativa: `UPDATE Ships s JOIN (SELECT AVG(Capacity) AS m FROM Ships WHERE Type = 'Fighter') AS x SET s.Capacity = ROUND(x.m) WHERE s.Type = 'Fighter' AND s.Capacity < x.m` -> passed=True 
- Incorrecta: `UPDATE Ships s JOIN (SELECT AVG(Capacity) AS m FROM Ships) AS x SET s.Capacity = ROUND(x.m) WHERE s.Type = 'Fighter' AND s.Capacity < x.m` -> passed=False The database's final content does not match what was expected after running your statement.

### Q9 OK

- Referència: `UPDATE Traders t JOIN ShipOwners o ON o.TraderId = t.Id SET t.DeceaseDate = '2384-06-01', o.LostDate = '2384-06-01', o.LostCause = 'Owner deceased', o.LostBenefit = 0 WHERE t.Nickname = 'Cyclone' AND o.LostDate > '2384-06-01'`
- Alternativa: `UPDATE ShipOwners o, Traders t SET o.LostBenefit = 0.00, o.LostCause = 'Owner deceased', o.LostDate = '2384-06-01', t.DeceaseDate = '2384-06-01' WHERE o.TraderId = t.Id AND t.Nickname = 'Cyclone' AND o.LostDate > '2384-06-01'` -> passed=True 
- Incorrecta: `UPDATE Traders t JOIN ShipOwners o ON o.TraderId = t.Id SET t.DeceaseDate = '2384-06-01', o.LostDate = '2384-06-01', o.LostCause = 'Owner deceased' WHERE t.Nickname = 'Cyclone' AND o.LostDate > '2384-06-01'` -> passed=False The database's final content does not match what was expected after running your statement.

### Q10 OK

- Referència: `UPDATE TradeLines l JOIN Trades t ON t.Id = l.TradeId JOIN Stays s ON s.Id = t.StayId JOIN Traders tr ON tr.Id = s.TraderId SET l.UnitPrice = (SELECT pc.NewPrice FROM PriceChanges pc WHERE pc.ProductId = l.ProductId AND pc.PlanetId = s.PlanetId AND pc.Date <= DATE(t.DateTime) ORDER BY pc.Date DESC, pc.Id DESC LIMIT 1) WHERE tr.Nickname = 'Nix' AND t.Type = 'Buy'`
- Alternativa: `UPDATE TradeLines l JOIN Trades t ON t.Id = l.TradeId JOIN Stays s ON s.Id = t.StayId SET l.UnitPrice = (SELECT pc.NewPrice FROM PriceChanges pc WHERE pc.ProductId = l.ProductId AND pc.PlanetId = s.PlanetId AND pc.Date = (SELECT MAX(pc2.Date) FROM PriceChanges pc2 WHERE pc2.ProductId = l.ProductId AND pc2.PlanetId = s.PlanetId AND pc2.Date <= DATE(t.DateTime))) WHERE t.Type = 'Buy' AND s.TraderId = (SELECT Id FROM Traders WHERE Nickname = 'Nix')` -> passed=True 
- Incorrecta: `UPDATE TradeLines l JOIN Trades t ON t.Id = l.TradeId JOIN Stays s ON s.Id = t.StayId JOIN Traders tr ON tr.Id = s.TraderId SET l.UnitPrice = (SELECT pc.NewPrice FROM PriceChanges pc WHERE pc.ProductId = l.ProductId AND pc.PlanetId = s.PlanetId AND pc.Date <= DATE(t.DateTime) ORDER BY pc.Date ASC, pc.Id LIMIT 1) WHERE tr.Nickname = 'Nix' AND t.Type = 'Buy'` -> passed=False The database's final content does not match what was expected after running your statement.

## Traders — DELETE (sqldelete)

### Q1 OK

- Referència: `DELETE FROM PriceChanges WHERE Date < '2201-01-01'`
- Alternativa: `DELETE FROM PriceChanges WHERE YEAR(Date) = 2200` -> passed=True 
- Incorrecta: `DELETE FROM PriceChanges WHERE Date < '2200-12-01'` -> passed=False The database's final content does not match what was expected after running your statement.

### Q2 OK

- Referència: `DELETE FROM PriceChanges WHERE Date < '2220-01-01' AND ProductId IN (SELECT Id FROM Products WHERE Name LIKE '%Leaf')`
- Alternativa: `DELETE pc FROM PriceChanges pc JOIN Products p ON p.Id = pc.ProductId WHERE RIGHT(p.Name, 4) = 'Leaf' AND pc.Date < '2220-01-01'` -> passed=True 
- Incorrecta: `DELETE FROM PriceChanges WHERE Date <= '2220-12-31' AND ProductId IN (SELECT Id FROM Products WHERE Name LIKE '%Leaf')` -> passed=False The database's final content does not match what was expected after running your statement.

### Q3 OK

- Referència: `DELETE FROM Ships WHERE Type = 'Fighter' AND NOT EXISTS (SELECT 1 FROM ShipOwners o WHERE o.ShipId = Ships.Id)`
- Alternativa: `DELETE FROM Ships WHERE Type = 'Fighter' AND Id NOT IN (SELECT ShipId FROM ShipOwners)` -> passed=True 
- Incorrecta: `DELETE FROM Ships WHERE Type = 'Fighter' AND Capacity < 5` -> passed=False SQL error: Cannot delete or update a parent row: a foreign key constraint fails (`w_traders`.`ShipOwners`, CONSTRAINT `ShipOwners_ibfk_1` FOREIGN KEY (`ShipId`) REFERENCES `Ships` (`Id`))

### Q4 OK

- Referència: `DELETE FROM Products WHERE NOT EXISTS (SELECT 1 FROM TradeLines l WHERE l.ProductId = Products.Id) AND NOT EXISTS (SELECT 1 FROM PriceChanges pc WHERE pc.ProductId = Products.Id)`
- Alternativa: `DELETE FROM Products WHERE Id NOT IN (SELECT ProductId FROM TradeLines UNION SELECT ProductId FROM PriceChanges)` -> passed=True 
- Incorrecta: `DELETE FROM Products WHERE Id NOT IN (SELECT ProductId FROM TradeLines)` -> passed=False SQL error: Cannot delete or update a parent row: a foreign key constraint fails (`w_traders`.`PriceChanges`, CONSTRAINT `PriceChanges_ibfk_1` FOREIGN KEY (`ProductId`) REFERENCES `Products` (`Id`))

### Q5 OK

- Referència: `DELETE pc FROM PriceChanges pc JOIN Planets p ON p.Id = pc.PlanetId JOIN SolarSystems ss ON ss.Id = p.SystemId WHERE ss.Name = 'Exax' AND pc.Date < '2210-01-01'`
- Alternativa: `DELETE FROM pc USING PriceChanges AS pc, Planets AS p, SolarSystems AS ss WHERE p.Id = pc.PlanetId AND ss.Id = p.SystemId AND ss.Name = 'Exax' AND pc.Date < '2210-01-01'` -> passed=True 
- Incorrecta: `DELETE pc FROM PriceChanges pc JOIN Planets p ON p.Id = pc.PlanetId JOIN SolarSystems ss ON ss.Id = p.SystemId WHERE ss.Name = 'Exax' AND pc.Date < '2220-01-01'` -> passed=False The database's final content does not match what was expected after running your statement.

### Q6 OK

- Referència: `DELETE FROM TradeLines ORDER BY UnitPrice * Quantity, Id LIMIT 3`
- Alternativa: `DELETE FROM TradeLines WHERE Id IN (SELECT Id FROM (SELECT Id FROM TradeLines ORDER BY UnitPrice * Quantity, Id LIMIT 3) AS x)` -> passed=True 
- Incorrecta: `DELETE FROM TradeLines ORDER BY UnitPrice, Id LIMIT 3` -> passed=False The database's final content does not match what was expected after running your statement.

### Q7 OK

- Referència: `DELETE s FROM Stays s LEFT JOIN Trades t ON t.StayId = s.Id WHERE t.Id IS NULL`
- Alternativa: `DELETE FROM Stays WHERE NOT EXISTS (SELECT 1 FROM Trades WHERE Trades.StayId = Stays.Id)` -> passed=True 
- Incorrecta: `DELETE s FROM Stays s LEFT JOIN Trades t ON t.StayId = s.Id JOIN Traders tr ON tr.Id = s.TraderId WHERE t.Id IS NULL AND tr.DeceaseDate IS NOT NULL` -> passed=False The database's final content does not match what was expected after running your statement.

### Q8 OK

- Referència: `DELETE l FROM TradeLines l JOIN Trades t ON t.Id = l.TradeId JOIN Stays s ON s.Id = t.StayId JOIN Traders tr ON tr.Id = s.TraderId JOIN Planets p ON p.Id = s.PlanetId JOIN SolarSystems ss ON ss.Id = p.SystemId WHERE tr.Nickname = 'Quote' AND ss.Name = 'Zaif' AND t.Type = 'Sell'`
- Alternativa: `DELETE FROM TradeLines WHERE TradeId IN (SELECT t.Id FROM Trades t JOIN Stays s ON s.Id = t.StayId WHERE t.Type = 'Sell' AND s.TraderId = (SELECT Id FROM Traders WHERE Nickname = 'Quote') AND s.PlanetId IN (SELECT Id FROM Planets WHERE SystemId = (SELECT Id FROM SolarSystems WHERE Name = 'Zaif')))` -> passed=True 
- Incorrecta: `DELETE l FROM TradeLines l JOIN Trades t ON t.Id = l.TradeId JOIN Stays s ON s.Id = t.StayId JOIN Traders tr ON tr.Id = s.TraderId JOIN Planets p ON p.Id = s.PlanetId JOIN SolarSystems ss ON ss.Id = p.SystemId WHERE tr.Nickname = 'Quote' AND ss.Name = 'Zaif'` -> passed=False The database's final content does not match what was expected after running your statement.

### Q9 OK

- Referència: `DELETE o FROM ShipOwners o JOIN Ships s ON s.Id = o.ShipId WHERE s.Type = 'Cargo ship' AND o.AcquisitionPrice > (SELECT x.m FROM (SELECT AVG(AcquisitionPrice) AS m FROM ShipOwners WHERE AcquisitionCause = 'Bought') AS x)`
- Alternativa: `DELETE FROM ShipOwners WHERE ShipId IN (SELECT Id FROM Ships WHERE Type = 'Cargo ship') AND AcquisitionPrice > (SELECT AVG(AcquisitionPrice) FROM ShipOwners WHERE AcquisitionCause = 'Bought')` -> passed=True 
- Incorrecta: `DELETE o FROM ShipOwners o JOIN Ships s ON s.Id = o.ShipId WHERE s.Type = 'Cargo ship' AND o.AcquisitionPrice > (SELECT x.m FROM (SELECT AVG(AcquisitionPrice) AS m FROM ShipOwners) AS x)` -> passed=False The database's final content does not match what was expected after running your statement.

### Q10 OK

- Referència: `DELETE o FROM ShipOwners o JOIN ShipOwners o2 ON o2.ShipId = o.ShipId AND o2.AcquisitionDate > o.AcquisitionDate`
- Alternativa: `DELETE FROM ShipOwners WHERE AcquisitionDate < (SELECT m FROM (SELECT ShipId, MAX(AcquisitionDate) AS m FROM ShipOwners GROUP BY ShipId) AS x WHERE x.ShipId = ShipOwners.ShipId)` -> passed=True 
- Incorrecta: `DELETE o FROM ShipOwners o JOIN ShipOwners o2 ON o2.ShipId = o.ShipId AND o2.AcquisitionDate < o.AcquisitionDate` -> passed=False The database's final content does not match what was expected after running your statement.

## Paranys comprovats

- D9 forma directa (error 1093 esperat): `DELETE o FROM ShipOwners o JOIN Ships s ON s.Id = o.ShipId WHERE s.Type = 'Cargo ship' AND o.AcquisitionPrice > (SELECT AVG(AcquisitionPrice) FROM ShipOwners WHERE AcquisitionCause = 'Bought')` -> passed=False SQL error: Table 'o' is specified twice, both as a target for 'DELETE' and as a separate source for data
- U8 forma directa (MariaDB l'accepta): `UPDATE Ships SET Capacity = (SELECT ROUND(AVG(Capacity)) FROM Ships WHERE Type = 'Fighter') WHERE Type = 'Fighter' AND Capacity < (SELECT AVG(Capacity) FROM Ships WHERE Type = 'Fighter')` -> passed=True 

## Dry-run

`manage.py create_db_problems --dry-run dml_traders.json` -> "dml_traders.json: 3 problems, 30 questions, 0 errors / dry run OK, nothing created".
