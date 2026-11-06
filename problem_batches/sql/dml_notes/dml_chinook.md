# Chinook DML — verificació amb el corrector real (mysqlwrite)


## Chinook — INSERT avançat (sqlinsert)


### 1. Insereix dos gèneres nous a la taula `Genre`: `K-Pop` i `Flamenco`, en una sola sentència. No cal indicar el `GenreId` (és `AUTO_INCREMENT`).

Referència:
```sql
INSERT INTO `Genre` (`Name`) VALUES ('K-Pop'), ('Flamenco')
```

Alternativa (ACCEPTADA):
```sql
INSERT INTO Genre VALUES (NULL, 'Flamenco'), (NULL, 'K-Pop')
```

Alternativa (ACCEPTADA):
```sql
INSERT INTO Genre (GenreId, Name) VALUES (26, 'K-Pop'), (27, 'Flamenco')
```

Incorrecta (REBUTJADA: The database's final content does not match what was expected after running your statement.):
```sql
INSERT INTO Genre (Name) VALUES ('K-Pop')
```


### 2. Afegeix a `Album` un àlbum nou titulat `Live at Wembley 2026` de l'artista `Queen`. No escriguis l'`ArtistId` a mà: busca'l a `Artist` pel nom amb una subconsulta.

Referència:
```sql
INSERT INTO `Album` (`Title`, `ArtistId`) VALUES ('Live at Wembley 2026', (SELECT `ArtistId` FROM `Artist` WHERE `Name` = 'Queen'))
```

Alternativa (ACCEPTADA):
```sql
INSERT INTO Album (Title, ArtistId) SELECT 'Live at Wembley 2026', ArtistId FROM Artist WHERE Name = 'Queen'
```

Incorrecta (REBUTJADA: The database's final content does not match what was expected after running your statement.):
```sql
INSERT INTO Album (Title, ArtistId) VALUES ('Live at Wembley 2026', (SELECT ArtistId FROM Artist WHERE Name = 'Metallica'))
```


### 3. Afegeix a `Track` la pista `Smells Like Teen Spirit (Demo)` a l'àlbum titulat `Nevermind`, amb tipus de fitxer (`MediaType`) `MPEG audio file`, gènere `Rock`, compositor (`Composer`) `Kurt Cobain`, 301000 mil·lisegons, 9800000 bytes i preu 0.99. Busca l'`AlbumId`, el `MediaTypeId` i el `GenreId` pel nom amb subconsultes.

Referència:
```sql
INSERT INTO `Track` (`Name`, `AlbumId`, `MediaTypeId`, `GenreId`, `Composer`, `Milliseconds`, `Bytes`, `UnitPrice`) VALUES ('Smells Like Teen Spirit (Demo)', (SELECT `AlbumId` FROM `Album` WHERE `Title` = 'Nevermind'), (SELECT `MediaTypeId` FROM `MediaType` WHERE `Name` = 'MPEG audio file'), (SELECT `GenreId` FROM `Genre` WHERE `Name` = 'Rock'), 'Kurt Cobain', 301000, 9800000, 0.99)
```

Alternativa (ACCEPTADA):
```sql
INSERT INTO Track (Name, AlbumId, MediaTypeId, GenreId, Composer, Milliseconds, Bytes, UnitPrice) SELECT 'Smells Like Teen Spirit (Demo)', a.AlbumId, m.MediaTypeId, g.GenreId, 'Kurt Cobain', 301000, 9800000, 0.99 FROM Album a CROSS JOIN MediaType m CROSS JOIN Genre g WHERE a.Title = 'Nevermind' AND m.Name = 'MPEG audio file' AND g.Name = 'Rock'
```

Incorrecta (REBUTJADA: The database's final content does not match what was expected after running your statement.):
```sql
INSERT INTO Track (Name, AlbumId, MediaTypeId, GenreId, Composer, Milliseconds, Bytes, UnitPrice) VALUES ('Smells Like Teen Spirit (Demo)', (SELECT AlbumId FROM Album WHERE Title = 'Nevermind'), (SELECT MediaTypeId FROM MediaType WHERE Name = 'AAC audio file'), (SELECT GenreId FROM Genre WHERE Name = 'Rock'), 'Kurt Cobain', 301000, 9800000, 0.99)
```


### 4. Afegeix a la llista de reproducció `Grunge` totes les pistes de l'artista `Nirvana`. Algunes ja hi són i la clau primària de `PlaylistTrack` (`PlaylistId`, `TrackId`) no admet duplicats: les que ja hi són s'han de deixar com estan, sense que la sentència falli (per exemple, amb `INSERT IGNORE`).

Referència:
```sql
INSERT IGNORE INTO `PlaylistTrack` (`PlaylistId`, `TrackId`) SELECT p.`PlaylistId`, t.`TrackId` FROM `Playlist` p JOIN `Track` t JOIN `Album` al ON al.`AlbumId` = t.`AlbumId` JOIN `Artist` ar ON ar.`ArtistId` = al.`ArtistId` WHERE p.`Name` = 'Grunge' AND ar.`Name` = 'Nirvana'
```

Alternativa (ACCEPTADA):
```sql
INSERT INTO PlaylistTrack (PlaylistId, TrackId) SELECT (SELECT PlaylistId FROM Playlist WHERE Name = 'Grunge'), t.TrackId FROM Track t WHERE t.AlbumId IN (SELECT AlbumId FROM Album WHERE ArtistId = (SELECT ArtistId FROM Artist WHERE Name = 'Nirvana')) AND t.TrackId NOT IN (SELECT pt.TrackId FROM PlaylistTrack pt JOIN Playlist p ON p.PlaylistId = pt.PlaylistId WHERE p.Name = 'Grunge')
```

Incorrecta (REBUTJADA: The database's final content does not match what was expected after running your statement.):
```sql
INSERT IGNORE INTO PlaylistTrack (PlaylistId, TrackId) SELECT 16, TrackId FROM Track WHERE AlbumId = (SELECT AlbumId FROM Album WHERE Title = 'Nevermind')
```

Incorrecta (REBUTJADA: SQL error: Duplicate entry '16-2003' for key 'PRIMARY'):
```sql
INSERT INTO PlaylistTrack (PlaylistId, TrackId) SELECT 16, t.TrackId FROM Track t JOIN Album a ON a.AlbumId = t.AlbumId WHERE a.ArtistId = 110
```


### 5. Per a cada gènere del qual s'hagin venut més de 75 unitats (suma de `InvoiceLine`.`Quantity` de les seves pistes), crea una llista de reproducció nova a `Playlist` amb el nom `Top ` seguit del nom del gènere (per exemple, `Top Rock`).

Referència:
```sql
INSERT INTO `Playlist` (`Name`) SELECT CONCAT('Top ', g.`Name`) FROM `Genre` g JOIN `Track` t ON t.`GenreId` = g.`GenreId` JOIN `InvoiceLine` l ON l.`TrackId` = t.`TrackId` GROUP BY g.`GenreId`, g.`Name` HAVING SUM(l.`Quantity`) > 75
```

Alternativa (ACCEPTADA):
```sql
INSERT INTO Playlist (Name) SELECT CONCAT('Top ', Name) FROM Genre WHERE (SELECT SUM(l.Quantity) FROM InvoiceLine l JOIN Track t ON t.TrackId = l.TrackId WHERE t.GenreId = Genre.GenreId) > 75
```

Incorrecta (REBUTJADA: The database's final content does not match what was expected after running your statement.):
```sql
INSERT INTO Playlist (Name) SELECT CONCAT('Top ', g.Name) FROM Genre g JOIN Track t ON t.GenreId = g.GenreId GROUP BY g.GenreId, g.Name HAVING COUNT(*) > 75
```


### 6. Afegeix a la llista `On-The-Go 1` les 10 pistes del gènere `Metal` que més unitats s'han venut (suma de `InvoiceLine`.`Quantity`). Si hi ha empat, tria primer les de `TrackId` més petit. Busca el `PlaylistId` pel nom.

Referència:
```sql
INSERT INTO `PlaylistTrack` (`PlaylistId`, `TrackId`) SELECT (SELECT `PlaylistId` FROM `Playlist` WHERE `Name` = 'On-The-Go 1'), t.`TrackId` FROM `Track` t JOIN `Genre` g ON g.`GenreId` = t.`GenreId` JOIN `InvoiceLine` l ON l.`TrackId` = t.`TrackId` WHERE g.`Name` = 'Metal' GROUP BY t.`TrackId` ORDER BY SUM(l.`Quantity`) DESC, t.`TrackId` LIMIT 10
```

Alternativa (ACCEPTADA):
```sql
INSERT INTO PlaylistTrack (PlaylistId, TrackId) SELECT p.PlaylistId, top.TrackId FROM Playlist p JOIN (SELECT l.TrackId, SUM(l.Quantity) AS venudes FROM InvoiceLine l WHERE l.TrackId IN (SELECT TrackId FROM Track WHERE GenreId = (SELECT GenreId FROM Genre WHERE Name = 'Metal')) GROUP BY l.TrackId ORDER BY venudes DESC, l.TrackId ASC LIMIT 10) AS top WHERE p.Name = 'On-The-Go 1'
```

Incorrecta (REBUTJADA: The database's final content does not match what was expected after running your statement.):
```sql
INSERT INTO PlaylistTrack (PlaylistId, TrackId) SELECT 18, t.TrackId FROM Track t JOIN InvoiceLine l ON l.TrackId = t.TrackId WHERE t.GenreId = 3 GROUP BY t.TrackId ORDER BY SUM(l.Quantity) DESC, t.TrackId DESC LIMIT 10
```


### 7. Per a cada client de `Portugal`, crea una factura nova (`Invoice`) amb data `2014-01-15`, total 0 i les dades de facturació (`BillingAddress`, `BillingCity`, `BillingState`, `BillingCountry`, `BillingPostalCode`) copiades de l'adreça del client (`Address`, `City`, `State`, `Country`, `PostalCode`).

Referència:
```sql
INSERT INTO `Invoice` (`CustomerId`, `InvoiceDate`, `BillingAddress`, `BillingCity`, `BillingState`, `BillingCountry`, `BillingPostalCode`, `Total`) SELECT `CustomerId`, '2014-01-15', `Address`, `City`, `State`, `Country`, `PostalCode`, 0 FROM `Customer` WHERE `Country` = 'Portugal'
```

Alternativa (ACCEPTADA):
```sql
INSERT INTO Invoice (Total, InvoiceDate, CustomerId, BillingCountry, BillingCity, BillingAddress, BillingPostalCode, BillingState) SELECT 0.00, '2014-01-15 00:00:00', c.CustomerId, c.Country, c.City, c.Address, c.PostalCode, c.State FROM Customer c WHERE c.Country LIKE 'Portugal'
```

Incorrecta (REBUTJADA: The database's final content does not match what was expected after running your statement.):
```sql
INSERT INTO Invoice (CustomerId, InvoiceDate, BillingAddress, BillingCity, BillingCountry, BillingPostalCode, Total) SELECT CustomerId, '2014-01-15', Address, City, Country, PostalCode, 0 FROM Customer WHERE Country = 'Portugal' AND State IS NOT NULL
```


### 8. Arriba una llista de gèneres amb el seu identificador: (5, `Rock & Roll`), (24, `Classical Music`) i (26, `Lo-fi`). Si el `GenreId` ja existeix, només se n'ha de canviar el nom; si no existeix, s'ha de crear el gènere. Fes-ho amb `INSERT ... ON DUPLICATE KEY UPDATE` (un `REPLACE` fallaria, perquè esborraria gèneres que tenen pistes).

Referència:
```sql
INSERT INTO `Genre` (`GenreId`, `Name`) VALUES (5, 'Rock & Roll'), (24, 'Classical Music'), (26, 'Lo-fi') ON DUPLICATE KEY UPDATE `Name` = VALUES(`Name`)
```

Alternativa (ACCEPTADA):
```sql
INSERT INTO Genre VALUES (26, 'Lo-fi'), (24, 'Classical Music'), (5, 'Rock & Roll') ON DUPLICATE KEY UPDATE Name = VALUES(Name)
```

Incorrecta (REBUTJADA: SQL error: Cannot delete or update a parent row: a foreign key constraint fails (`w_Chinook`.`Track`, CONSTRAINT `FK_TrackGenreId` FOREIGN KEY (`GenreId`) REFERENCES `Genre` (`GenreId`) ON DELETE NO ACTION ON UPDATE NO ACTION)):
```sql
REPLACE INTO Genre (GenreId, Name) VALUES (5, 'Rock & Roll'), (24, 'Classical Music'), (26, 'Lo-fi')
```

Incorrecta (REBUTJADA: The database's final content does not match what was expected after running your statement.):
```sql
INSERT IGNORE INTO Genre (GenreId, Name) VALUES (5, 'Rock & Roll'), (24, 'Classical Music'), (26, 'Lo-fi')
```


### 9. Les llistes de reproducció que no tenen cap pista s'han de marcar afegint ` (buida)` al final del nom (per exemple, `Movies (buida)`). Fes-ho amb una sola sentència d'inserció que reescrigui aquestes files de `Playlist` a partir d'un `SELECT`: `REPLACE ... SELECT` o `INSERT ... SELECT ... ON DUPLICATE KEY UPDATE`. Aquí `REPLACE` funciona perquè aquestes llistes no tenen cap fila filla a `PlaylistTrack`.

Referència:
```sql
REPLACE INTO `Playlist` (`PlaylistId`, `Name`) SELECT p.`PlaylistId`, CONCAT(p.`Name`, ' (buida)') FROM `Playlist` p WHERE NOT EXISTS (SELECT 1 FROM `PlaylistTrack` pt WHERE pt.`PlaylistId` = p.`PlaylistId`)
```

Alternativa (ACCEPTADA):
```sql
INSERT INTO Playlist (PlaylistId, Name) SELECT p.PlaylistId, CONCAT(p.Name, ' (buida)') FROM Playlist p LEFT JOIN PlaylistTrack pt ON pt.PlaylistId = p.PlaylistId WHERE pt.TrackId IS NULL ON DUPLICATE KEY UPDATE Name = VALUES(Name)
```

Incorrecta (REBUTJADA: The database's final content does not match what was expected after running your statement.):
```sql
REPLACE INTO Playlist (PlaylistId, Name) SELECT PlaylistId, CONCAT(Name, ' (buida)') FROM Playlist WHERE PlaylistId IN (2, 4)
```

Incorrecta (REBUTJADA: SQL error: Cannot delete or update a parent row: a foreign key constraint fails (`w_Chinook`.`PlaylistTrack`, CONSTRAINT `FK_PlaylistTrackPlaylistId` FOREIGN KEY (`PlaylistId`) REFERENCES `Playlist` (`PlaylistId`) ON DELETE NO ACTION ON UPDATE NO ACTION)):
```sql
REPLACE INTO Playlist (PlaylistId, Name) SELECT PlaylistId, CONCAT(Name, ' (buida)') FROM Playlist WHERE Name IN ('Movies', 'Audiobooks', 'TV Shows')
```


### 10. El client de la factura amb `InvoiceId` 392 vol completar l'àlbum `For Those About To Rock We Salute You`. Afegeix a `InvoiceLine` una línia per a cada pista d'aquest àlbum que aquest client no hagi comprat mai abans (en cap de les seves factures): `InvoiceId` 392, preu (`UnitPrice`) igual al preu actual de la pista a `Track` i quantitat 1. (El `Total` de la factura no s'ha de tocar.)

Referència:
```sql
INSERT INTO `InvoiceLine` (`InvoiceId`, `TrackId`, `UnitPrice`, `Quantity`) SELECT 392, t.`TrackId`, t.`UnitPrice`, 1 FROM `Track` t JOIN `Album` a ON a.`AlbumId` = t.`AlbumId` WHERE a.`Title` = 'For Those About To Rock We Salute You' AND NOT EXISTS (SELECT 1 FROM `InvoiceLine` l JOIN `Invoice` i ON i.`InvoiceId` = l.`InvoiceId` WHERE l.`TrackId` = t.`TrackId` AND i.`CustomerId` = (SELECT `CustomerId` FROM `Invoice` WHERE `InvoiceId` = 392))
```

Alternativa (ACCEPTADA):
```sql
INSERT INTO InvoiceLine (InvoiceId, TrackId, UnitPrice, Quantity) SELECT 392, TrackId, UnitPrice, 1 FROM Track WHERE AlbumId = (SELECT AlbumId FROM Album WHERE Title = 'For Those About To Rock We Salute You') AND TrackId NOT IN (SELECT l.TrackId FROM InvoiceLine l JOIN Invoice i ON i.InvoiceId = l.InvoiceId JOIN Invoice f ON f.CustomerId = i.CustomerId WHERE f.InvoiceId = 392)
```

Incorrecta (REBUTJADA: The database's final content does not match what was expected after running your statement.):
```sql
INSERT INTO InvoiceLine (InvoiceId, TrackId, UnitPrice, Quantity) SELECT 392, TrackId, UnitPrice, 1 FROM Track WHERE AlbumId = 1 AND TrackId NOT IN (SELECT TrackId FROM InvoiceLine WHERE InvoiceId = 392)
```

Incorrecta (REBUTJADA: The database's final content does not match what was expected after running your statement.):
```sql
INSERT INTO InvoiceLine (InvoiceId, TrackId, UnitPrice, Quantity) SELECT 392, TrackId, UnitPrice, 1 FROM Track WHERE AlbumId = 1 AND TrackId NOT IN (SELECT TrackId FROM InvoiceLine)
```


## Chinook — UPDATE amb JOIN i subconsultes (sqlupdate)


### 1. Als telèfons (`Phone`) dels clients del Brasil (`Country` = `Brazil`) treu els parèntesis: `+55 (12) 3923-5555` ha de quedar `+55 12 3923-5555`.

Referència:
```sql
UPDATE `Customer` SET `Phone` = REPLACE(REPLACE(`Phone`, '(', ''), ')', '') WHERE `Country` = 'Brazil'
```

Alternativa (ACCEPTADA):
```sql
UPDATE Customer SET Phone = REPLACE(REPLACE(Phone, ')', ''), '(', '') WHERE Country IN ('Brazil') AND Phone LIKE '%(%'
```

Incorrecta (REBUTJADA: The database's final content does not match what was expected after running your statement.):
```sql
UPDATE Customer SET Phone = REPLACE(Phone, '(', '') WHERE Country = 'Brazil'
```


### 2. Els empleats del departament d'informàtica (els que tenen un `Title` que comença per `IT`) estrenen adreça: el seu `Email` ha de ser el nom i el cognom en minúscules separats per un punt, seguits de `@chinook.cat` (per exemple, `robert.king@chinook.cat`).

Referència:
```sql
UPDATE `Employee` SET `Email` = CONCAT(LOWER(`FirstName`), '.', LOWER(`LastName`), '@chinook.cat') WHERE `Title` LIKE 'IT%'
```

Alternativa (ACCEPTADA):
```sql
UPDATE Employee SET Email = LOWER(CONCAT_WS('.', FirstName, CONCAT(LastName, '@CHINOOK.CAT'))) WHERE LEFT(Title, 2) = 'IT'
```

Incorrecta (REBUTJADA: The database's final content does not match what was expected after running your statement.):
```sql
UPDATE Employee SET Email = CONCAT(LOWER(FirstName), '.', LOWER(LastName), '@chinook.cat') WHERE Title = 'IT Staff'
```


### 3. Rebaixa un 20% el preu (`UnitPrice`) de totes les pistes de tipus `Protected MPEG-4 video file` (taula `MediaType`), arrodonint a 2 decimals amb `ROUND`. Busca el `MediaTypeId` pel nom.

Referència:
```sql
UPDATE `Track` SET `UnitPrice` = ROUND(`UnitPrice` * 0.8, 2) WHERE `MediaTypeId` = (SELECT `MediaTypeId` FROM `MediaType` WHERE `Name` = 'Protected MPEG-4 video file')
```

Alternativa (ACCEPTADA):
```sql
UPDATE Track t JOIN MediaType m ON m.MediaTypeId = t.MediaTypeId SET t.UnitPrice = ROUND(t.UnitPrice - t.UnitPrice * 0.20, 2) WHERE m.Name = 'Protected MPEG-4 video file'
```

Incorrecta (REBUTJADA: The database's final content does not match what was expected after running your statement.):
```sql
UPDATE Track SET UnitPrice = ROUND(UnitPrice * 0.8, 2) WHERE UnitPrice = 1.99
```


### 4. Puja 0.20 el preu (`UnitPrice`) de totes les pistes de l'artista `Led Zeppelin`. Fes un `UPDATE` multitaula amb `JOIN` entre `Track`, `Album` i `Artist`.

Referència:
```sql
UPDATE `Track` t JOIN `Album` al ON al.`AlbumId` = t.`AlbumId` JOIN `Artist` ar ON ar.`ArtistId` = al.`ArtistId` SET t.`UnitPrice` = t.`UnitPrice` + 0.20 WHERE ar.`Name` = 'Led Zeppelin'
```

Alternativa (ACCEPTADA):
```sql
UPDATE Track SET UnitPrice = UnitPrice + 0.2 WHERE AlbumId IN (SELECT a.AlbumId FROM Album a, Artist r WHERE a.ArtistId = r.ArtistId AND r.Name = 'Led Zeppelin')
```

Incorrecta (REBUTJADA: The database's final content does not match what was expected after running your statement.):
```sql
UPDATE Track t JOIN Album al ON al.AlbumId = t.AlbumId SET t.UnitPrice = t.UnitPrice + 0.20 WHERE al.Title LIKE 'Led Zeppelin%'
```


### 5. Les pistes del gènere `Classical` passen a tenir preu per trams de durada (`Milliseconds`): menys de 180000 ms (3 minuts), 0.79; de 180000 a menys de 360000 ms, 0.99; 360000 ms (6 minuts) o més, 1.49. Fes-ho amb un sol `UPDATE` i `CASE`.

Referència:
```sql
UPDATE `Track` SET `UnitPrice` = CASE WHEN `Milliseconds` < 180000 THEN 0.79 WHEN `Milliseconds` < 360000 THEN 0.99 ELSE 1.49 END WHERE `GenreId` = (SELECT `GenreId` FROM `Genre` WHERE `Name` = 'Classical')
```

Alternativa (ACCEPTADA):
```sql
UPDATE Track t JOIN Genre g ON g.GenreId = t.GenreId SET t.UnitPrice = CASE WHEN t.Milliseconds >= 360000 THEN 1.49 WHEN t.Milliseconds >= 180000 THEN 0.99 ELSE 0.79 END WHERE g.Name = 'Classical'
```

Incorrecta (REBUTJADA: The database's final content does not match what was expected after running your statement.):
```sql
UPDATE Track SET UnitPrice = CASE WHEN Milliseconds < 180000 THEN 0.79 WHEN Milliseconds < 360000 THEN 0.99 ELSE 1.49 END WHERE GenreId = 24 AND Milliseconds >= 360000 OR Milliseconds < 180000
```


### 6. Les 5 pistes més llargues (`Milliseconds`) del gènere `Rock` passen a costar 1.49. Si hi ha empat de durada, tria primer les de `TrackId` més petit. Fes servir `UPDATE ... ORDER BY ... LIMIT`.

Referència:
```sql
UPDATE `Track` SET `UnitPrice` = 1.49 WHERE `GenreId` = (SELECT `GenreId` FROM `Genre` WHERE `Name` = 'Rock') ORDER BY `Milliseconds` DESC, `TrackId` LIMIT 5
```

Alternativa (ACCEPTADA):
```sql
UPDATE Track t JOIN (SELECT TrackId FROM Track WHERE GenreId = 1 ORDER BY Milliseconds DESC, TrackId ASC LIMIT 5) AS llargues ON llargues.TrackId = t.TrackId SET t.UnitPrice = 1.49
```

Incorrecta (REBUTJADA: The database's final content does not match what was expected after running your statement.):
```sql
UPDATE Track SET UnitPrice = 1.49 WHERE GenreId = 1 ORDER BY Milliseconds ASC, TrackId LIMIT 5
```


### 7. Normalitza el país `USA` a `United States`, tant a la columna `Country` dels clients com a la `BillingCountry` de totes les factures d'aquests clients, amb un sol `UPDATE` multitaula.

Referència:
```sql
UPDATE `Customer` c JOIN `Invoice` i ON i.`CustomerId` = c.`CustomerId` SET c.`Country` = 'United States', i.`BillingCountry` = 'United States' WHERE c.`Country` = 'USA'
```

Alternativa (ACCEPTADA):
```sql
UPDATE Invoice i, Customer c SET i.BillingCountry = 'United States', c.Country = 'United States' WHERE i.CustomerId = c.CustomerId AND i.BillingCountry = 'USA'
```

Incorrecta (REBUTJADA: The database's final content does not match what was expected after running your statement.):
```sql
UPDATE Customer c JOIN Invoice i ON i.CustomerId = c.CustomerId SET c.Country = 'United States' WHERE c.Country = 'USA'
```


### 8. Les pistes de l'àlbum `Ten` que duren més que la durada mitjana de les pistes del mateix àlbum passen a costar 1.29. Parany: en MySQL, `WHERE Milliseconds > (SELECT AVG(Milliseconds) FROM Track WHERE ...)` dona l'error 1093 (no es pot llegir de la mateixa taula que s'actualitza); la solució portable és calcular la mitjana dins d'una taula derivada (`SELECT ... FROM (SELECT AVG(...) ...) AS m`), que es materialitza abans de modificar res.

Referència:
```sql
UPDATE `Track` SET `UnitPrice` = 1.29 WHERE `AlbumId` = (SELECT `AlbumId` FROM `Album` WHERE `Title` = 'Ten') AND `Milliseconds` > (SELECT m.mitjana FROM (SELECT AVG(t2.`Milliseconds`) AS mitjana FROM `Track` t2 JOIN `Album` a2 ON a2.`AlbumId` = t2.`AlbumId` WHERE a2.`Title` = 'Ten') AS m)
```

Alternativa (ACCEPTADA):
```sql
UPDATE Track t JOIN Album a ON a.AlbumId = t.AlbumId JOIN (SELECT AlbumId, AVG(Milliseconds) AS mitjana FROM Track GROUP BY AlbumId) AS m ON m.AlbumId = t.AlbumId SET t.UnitPrice = 1.29 WHERE a.Title = 'Ten' AND t.Milliseconds > m.mitjana
```

Alternativa (ACCEPTADA):
```sql
UPDATE Track SET UnitPrice = 1.29 WHERE AlbumId = 181 AND Milliseconds > (SELECT AVG(Milliseconds) FROM Track WHERE AlbumId = 181)
```

Incorrecta (REBUTJADA: The database's final content does not match what was expected after running your statement.):
```sql
UPDATE Track SET UnitPrice = 1.29 WHERE AlbumId = 181 AND Milliseconds > (SELECT AVG(Milliseconds) FROM (SELECT Milliseconds FROM Track) AS m)
```


### 9. Els clients sense empresa (`Company` nul) que han gastat en total més de 45 (suma de `Invoice`.`Total` de totes les seves factures) passen a tenir com a representant (`SupportRepId`) l'empleada `Jane Peacock`. Busca el seu `EmployeeId` pel nom i calcula la despesa amb una taula derivada amb `GROUP BY`.

Referència:
```sql
UPDATE `Customer` c JOIN (SELECT `CustomerId`, SUM(`Total`) AS gastat FROM `Invoice` GROUP BY `CustomerId`) AS d ON d.`CustomerId` = c.`CustomerId` SET c.`SupportRepId` = (SELECT `EmployeeId` FROM `Employee` WHERE `FirstName` = 'Jane' AND `LastName` = 'Peacock') WHERE c.`Company` IS NULL AND d.gastat > 45
```

Alternativa (ACCEPTADA):
```sql
UPDATE Customer c SET c.SupportRepId = (SELECT e.EmployeeId FROM Employee e WHERE CONCAT(e.FirstName, ' ', e.LastName) = 'Jane Peacock') WHERE c.Company IS NULL AND (SELECT SUM(i.Total) FROM Invoice i WHERE i.CustomerId = c.CustomerId) > 45
```

Incorrecta (REBUTJADA: The database's final content does not match what was expected after running your statement.):
```sql
UPDATE Customer c JOIN (SELECT CustomerId, SUM(Total) AS gastat FROM Invoice GROUP BY CustomerId) AS d ON d.CustomerId = c.CustomerId SET c.SupportRepId = 3 WHERE c.Company IS NULL AND d.gastat > 43
```


### 10. Recalcula el `Total` de totes les factures dels clients de França (`Customer`.`Country` = `France`) a partir de les seves línies (`UnitPrice` × `Quantity`), aplicant un 10% de descompte a les línies de pistes de tipus `Protected MPEG-4 video file`. Arrodoneix només el total final a 2 decimals (no cada línia).

Referència:
```sql
UPDATE `Invoice` i JOIN `Customer` c ON c.`CustomerId` = i.`CustomerId` SET i.`Total` = (SELECT ROUND(SUM(CASE WHEN m.`Name` = 'Protected MPEG-4 video file' THEN l.`UnitPrice` * l.`Quantity` * 0.9 ELSE l.`UnitPrice` * l.`Quantity` END), 2) FROM `InvoiceLine` l JOIN `Track` t ON t.`TrackId` = l.`TrackId` JOIN `MediaType` m ON m.`MediaTypeId` = t.`MediaTypeId` WHERE l.`InvoiceId` = i.`InvoiceId`) WHERE c.`Country` = 'France'
```

Alternativa (ACCEPTADA):
```sql
UPDATE Invoice SET Total = ROUND((SELECT SUM(l.UnitPrice * l.Quantity) FROM InvoiceLine l WHERE l.InvoiceId = Invoice.InvoiceId) - 0.1 * (SELECT COALESCE(SUM(l.UnitPrice * l.Quantity), 0) FROM InvoiceLine l JOIN Track t ON t.TrackId = l.TrackId WHERE l.InvoiceId = Invoice.InvoiceId AND t.MediaTypeId = 3), 2) WHERE CustomerId IN (SELECT CustomerId FROM Customer WHERE Country = 'France')
```

Incorrecta (REBUTJADA: The database's final content does not match what was expected after running your statement.):
```sql
UPDATE Invoice i JOIN Customer c ON c.CustomerId = i.CustomerId SET i.Total = ROUND(i.Total * 0.9, 2) WHERE c.Country = 'France' AND i.InvoiceId IN (SELECT l.InvoiceId FROM InvoiceLine l JOIN Track t ON t.TrackId = l.TrackId WHERE t.MediaTypeId = 3)
```


## Chinook — DELETE (sqldelete)


### 1. De la llista de reproducció `Classical 101 - Deep Cuts`, treu les pistes amb `TrackId` entre 3490 i 3495 (tots dos inclosos). Busca el `PlaylistId` pel nom.

Referència:
```sql
DELETE FROM `PlaylistTrack` WHERE `PlaylistId` = (SELECT `PlaylistId` FROM `Playlist` WHERE `Name` = 'Classical 101 - Deep Cuts') AND `TrackId` BETWEEN 3490 AND 3495
```

Alternativa (ACCEPTADA):
```sql
DELETE FROM PlaylistTrack WHERE PlaylistId = 13 AND TrackId >= 3490 AND TrackId <= 3495
```

Incorrecta (REBUTJADA: The database's final content does not match what was expected after running your statement.):
```sql
DELETE FROM PlaylistTrack WHERE PlaylistId = 13 AND TrackId > 3490 AND TrackId < 3495
```

Incorrecta (REBUTJADA: The database's final content does not match what was expected after running your statement.):
```sql
DELETE FROM PlaylistTrack WHERE TrackId BETWEEN 3490 AND 3495
```


### 2. Esborra de `Artist` tots els artistes que són col·laboracions de Santana, és a dir, els que tenen un nom que comença per `Santana Feat.` (cap d'ells té àlbums). L'artista `Santana` sol no s'ha d'esborrar.

Referència:
```sql
DELETE FROM `Artist` WHERE `Name` LIKE 'Santana Feat.%'
```

Alternativa (ACCEPTADA):
```sql
DELETE FROM Artist WHERE LEFT(Name, 13) = 'Santana Feat.'
```

Incorrecta (REBUTJADA: The database's final content does not match what was expected after running your statement.):
```sql
DELETE FROM Artist WHERE Name LIKE 'Santana Feat%' AND ArtistId < 65
```

Incorrecta (REBUTJADA: SQL error: Cannot delete or update a parent row: a foreign key constraint fails (`w_Chinook`.`Album`, CONSTRAINT `FK_AlbumArtistId` FOREIGN KEY (`ArtistId`) REFERENCES `Artist` (`ArtistId`) ON DELETE NO ACTION ON UPDATE NO ACTION)):
```sql
DELETE FROM Artist WHERE Name LIKE 'Santana%'
```


### 3. Esborra els artistes que tenen el caràcter `&` al nom i que no tenen cap àlbum. Els que sí que en tenen s'han de quedar (amb les claus foranes NO ACTION, intentar esborrar-los faria fallar tota la sentència).

Referència:
```sql
DELETE FROM `Artist` WHERE `Name` LIKE '%&%' AND NOT EXISTS (SELECT 1 FROM `Album` al WHERE al.`ArtistId` = `Artist`.`ArtistId`)
```

Alternativa (ACCEPTADA):
```sql
DELETE FROM Artist WHERE INSTR(Name, '&') > 0 AND ArtistId NOT IN (SELECT ArtistId FROM Album)
```

Incorrecta (REBUTJADA: SQL error: Cannot delete or update a parent row: a foreign key constraint fails (`w_Chinook`.`Album`, CONSTRAINT `FK_AlbumArtistId` FOREIGN KEY (`ArtistId`) REFERENCES `Artist` (`ArtistId`) ON DELETE NO ACTION ON UPDATE NO ACTION)):
```sql
DELETE FROM Artist WHERE Name LIKE '%&%' AND ArtistId NOT IN (SELECT ArtistId FROM Album WHERE Title LIKE '%&%')
```

Incorrecta (REBUTJADA: The database's final content does not match what was expected after running your statement.):
```sql
DELETE FROM Artist WHERE Name LIKE '% & %' AND ArtistId NOT IN (SELECT ArtistId FROM Album)
```


### 4. Esborra les 3 línies més cares (`UnitPrice`) de la factura amb `InvoiceId` 89. Si hi ha empat de preu, esborra primer les de `InvoiceLineId` més petit. Fes servir `DELETE ... ORDER BY ... LIMIT`.

Referència:
```sql
DELETE FROM `InvoiceLine` WHERE `InvoiceId` = 89 ORDER BY `UnitPrice` DESC, `InvoiceLineId` LIMIT 3
```

Alternativa (ACCEPTADA):
```sql
DELETE FROM InvoiceLine WHERE InvoiceLineId IN (SELECT id FROM (SELECT InvoiceLineId AS id FROM InvoiceLine WHERE InvoiceId = 89 ORDER BY UnitPrice DESC, InvoiceLineId ASC LIMIT 3) AS x)
```

Incorrecta (REBUTJADA: The database's final content does not match what was expected after running your statement.):
```sql
DELETE FROM InvoiceLine WHERE InvoiceId = 89 ORDER BY UnitPrice DESC, InvoiceLineId DESC LIMIT 3
```


### 5. De la llista de reproducció amb `PlaylistId` 5 (`90’s Music`), treu totes les pistes dels gèneres `World`, `Opera` i `Rock And Roll`. Fes un `DELETE` multitaula amb `JOIN` entre `PlaylistTrack`, `Track` i `Genre`.

Referència:
```sql
DELETE pt FROM `PlaylistTrack` pt JOIN `Track` t ON t.`TrackId` = pt.`TrackId` JOIN `Genre` g ON g.`GenreId` = t.`GenreId` WHERE pt.`PlaylistId` = 5 AND g.`Name` IN ('World', 'Opera', 'Rock And Roll')
```

Alternativa (ACCEPTADA):
```sql
DELETE FROM PlaylistTrack WHERE PlaylistId = 5 AND TrackId IN (SELECT t.TrackId FROM Track t WHERE t.GenreId IN (SELECT GenreId FROM Genre WHERE Name = 'World' OR Name = 'Opera' OR Name = 'Rock And Roll'))
```

Incorrecta (REBUTJADA: The database's final content does not match what was expected after running your statement.):
```sql
DELETE pt FROM PlaylistTrack pt JOIN Track t ON t.TrackId = pt.TrackId JOIN Genre g ON g.GenreId = t.GenreId WHERE pt.PlaylistId = 5 AND g.Name IN ('World', 'Opera', 'Rock')
```


### 6. De la llista `Grunge`, treu les pistes que no s'han venut mai (que no apareixen en cap línia de factura, `InvoiceLine`).

Referència:
```sql
DELETE FROM `PlaylistTrack` WHERE `PlaylistId` = (SELECT `PlaylistId` FROM `Playlist` WHERE `Name` = 'Grunge') AND NOT EXISTS (SELECT 1 FROM `InvoiceLine` l WHERE l.`TrackId` = `PlaylistTrack`.`TrackId`)
```

Alternativa (ACCEPTADA):
```sql
DELETE pt FROM PlaylistTrack pt JOIN Playlist p ON p.PlaylistId = pt.PlaylistId LEFT JOIN InvoiceLine l ON l.TrackId = pt.TrackId WHERE p.Name = 'Grunge' AND l.InvoiceLineId IS NULL
```

Incorrecta (REBUTJADA: The database's final content does not match what was expected after running your statement.):
```sql
DELETE FROM PlaylistTrack WHERE PlaylistId = 16 AND TrackId NOT IN (SELECT TrackId FROM InvoiceLine WHERE InvoiceId < 200)
```


### 7. Esborra les línies de factura (`InvoiceLine`) de pistes de tipus `Protected MPEG-4 video file` que pertanyen a factures de l'any 2013 (`InvoiceDate`). Fes un `DELETE` multitaula amb `JOIN`.

Referència:
```sql
DELETE l FROM `InvoiceLine` l JOIN `Invoice` i ON i.`InvoiceId` = l.`InvoiceId` JOIN `Track` t ON t.`TrackId` = l.`TrackId` JOIN `MediaType` m ON m.`MediaTypeId` = t.`MediaTypeId` WHERE m.`Name` = 'Protected MPEG-4 video file' AND YEAR(i.`InvoiceDate`) = 2013
```

Alternativa (ACCEPTADA):
```sql
DELETE FROM InvoiceLine WHERE InvoiceId IN (SELECT InvoiceId FROM Invoice WHERE InvoiceDate >= '2013-01-01' AND InvoiceDate < '2014-01-01') AND TrackId IN (SELECT TrackId FROM Track WHERE MediaTypeId = 3)
```

Incorrecta (REBUTJADA: The database's final content does not match what was expected after running your statement.):
```sql
DELETE l FROM InvoiceLine l JOIN Invoice i ON i.InvoiceId = l.InvoiceId JOIN Track t ON t.TrackId = l.TrackId WHERE t.MediaTypeId IN (2, 3) AND YEAR(i.InvoiceDate) = 2013
```

Incorrecta (REBUTJADA: The database's final content does not match what was expected after running your statement.):
```sql
DELETE FROM InvoiceLine WHERE InvoiceId IN (SELECT InvoiceId FROM Invoice WHERE InvoiceDate BETWEEN '2013-01-01' AND '2013-12-01') AND TrackId IN (SELECT TrackId FROM Track WHERE MediaTypeId = 3)
```


### 8. Esborra els empleats que no tenen ningú al seu càrrec (cap empleat els té a `ReportsTo`) i que no són representants de cap client (cap client els té a `SupportRepId`). Parany: amb `NOT IN (SELECT ReportsTo FROM Employee)` no s'esborra res, perquè la columna conté un `NULL` (el director general) i `x NOT IN (..., NULL)` mai és cert; fes servir `NOT EXISTS` o filtra els nuls.

Referència:
```sql
DELETE FROM `Employee` WHERE NOT EXISTS (SELECT 1 FROM `Employee` sub WHERE sub.`ReportsTo` = `Employee`.`EmployeeId`) AND NOT EXISTS (SELECT 1 FROM `Customer` c WHERE c.`SupportRepId` = `Employee`.`EmployeeId`)
```

Alternativa (ACCEPTADA):
```sql
DELETE FROM Employee WHERE EmployeeId NOT IN (SELECT x.ReportsTo FROM (SELECT ReportsTo FROM Employee WHERE ReportsTo IS NOT NULL) AS x) AND EmployeeId NOT IN (SELECT SupportRepId FROM Customer WHERE SupportRepId IS NOT NULL)
```

Incorrecta (REBUTJADA: The database's final content does not match what was expected after running your statement.):
```sql
DELETE FROM Employee WHERE EmployeeId NOT IN (SELECT x.ReportsTo FROM (SELECT ReportsTo FROM Employee) AS x) AND EmployeeId NOT IN (SELECT SupportRepId FROM Customer)
```

Incorrecta (REBUTJADA: SQL error: Cannot delete or update a parent row: a foreign key constraint fails (`w_Chinook`.`Employee`, CONSTRAINT `FK_EmployeeReportsTo` FOREIGN KEY (`ReportsTo`) REFERENCES `Employee` (`EmployeeId`) ON DELETE NO ACTION ON UPDATE NO ACTION)):
```sql
DELETE FROM Employee WHERE EmployeeId NOT IN (SELECT SupportRepId FROM Customer) AND Title <> 'General Manager' AND Title <> 'Sales Manager'
```


### 9. Hi ha llistes de reproducció repetides (amb el mateix `Name` que una altra de `PlaylistId` més petit). Esborra les repetides que estan buides (sense cap fila a `PlaylistTrack`); les repetides que tenen pistes s'han de quedar, i l'original (la de `PlaylistId` més petit) també.

Referència:
```sql
DELETE p FROM `Playlist` p JOIN `Playlist` orig ON orig.`Name` = p.`Name` AND orig.`PlaylistId` < p.`PlaylistId` WHERE NOT EXISTS (SELECT 1 FROM `PlaylistTrack` pt WHERE pt.`PlaylistId` = p.`PlaylistId`)
```

Alternativa (ACCEPTADA):
```sql
DELETE FROM Playlist WHERE PlaylistId NOT IN (SELECT PlaylistId FROM PlaylistTrack) AND PlaylistId NOT IN (SELECT primer FROM (SELECT MIN(PlaylistId) AS primer FROM Playlist GROUP BY Name) AS m)
```

Incorrecta (REBUTJADA: The database's final content does not match what was expected after running your statement.):
```sql
DELETE FROM Playlist WHERE PlaylistId NOT IN (SELECT PlaylistId FROM PlaylistTrack)
```

Incorrecta (REBUTJADA: The database's final content does not match what was expected after running your statement.):
```sql
DELETE p FROM Playlist p JOIN Playlist orig ON orig.Name = p.Name AND orig.PlaylistId <> p.PlaylistId WHERE NOT EXISTS (SELECT 1 FROM PlaylistTrack pt WHERE pt.PlaylistId = p.PlaylistId)
```


### 10. Esborra totes les línies de factura (`InvoiceLine`) de la factura més recent (`InvoiceDate` més gran) de cada client del Brasil (`Customer`.`Country` = `Brazil`).

Referència:
```sql
DELETE l FROM `InvoiceLine` l JOIN `Invoice` i ON i.`InvoiceId` = l.`InvoiceId` JOIN `Customer` c ON c.`CustomerId` = i.`CustomerId` WHERE c.`Country` = 'Brazil' AND i.`InvoiceDate` = (SELECT MAX(i2.`InvoiceDate`) FROM `Invoice` i2 WHERE i2.`CustomerId` = i.`CustomerId`)
```

Alternativa (ACCEPTADA):
```sql
DELETE FROM InvoiceLine WHERE InvoiceId IN (SELECT i.InvoiceId FROM Invoice i JOIN (SELECT CustomerId, MAX(InvoiceDate) AS darrera FROM Invoice GROUP BY CustomerId) AS d ON d.CustomerId = i.CustomerId AND d.darrera = i.InvoiceDate WHERE i.CustomerId IN (SELECT CustomerId FROM Customer WHERE Country = 'Brazil'))
```

Incorrecta (REBUTJADA: The database's final content does not match what was expected after running your statement.):
```sql
DELETE FROM InvoiceLine WHERE InvoiceId IN (SELECT MAX(InvoiceId) FROM Invoice WHERE BillingCountry = 'Brazil')
```

Incorrecta (REBUTJADA: The database's final content does not match what was expected after running your statement.):
```sql
DELETE l FROM InvoiceLine l JOIN Invoice i ON i.InvoiceId = l.InvoiceId JOIN Customer c ON c.CustomerId = i.CustomerId WHERE c.Country = 'Brazil' AND i.InvoiceDate = (SELECT MAX(InvoiceDate) FROM Invoice WHERE BillingCountry = 'Brazil')
```
