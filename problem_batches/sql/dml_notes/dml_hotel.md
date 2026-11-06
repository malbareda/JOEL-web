# Verificació dels exercicis DML de `hotel`
Cada sentència s'ha provat amb `dmoj.checkers.mysqlwrite.check` contra la referència.

## Hotel — INSERT avançat

### 1. L'hotel ofereix tres instal·lacions noves. Afegeix a `Facilities` les files amb nom (`Name`) `Minibar`, `Balcony` i `Safe`, amb una sola sentència `INSERT` (l'`Id` el posa la base de dades).

Referència:
```sql
INSERT INTO Facilities (Name) VALUES ('Minibar'), ('Balcony'), ('Safe')
```
Alternativa (passa, esperat: passa):
```sql
INSERT INTO Facilities (Name) SELECT 'Safe' UNION ALL SELECT 'Balcony' UNION ALL SELECT 'Minibar'
```
Alternativa (passa, esperat: passa):
```sql
INSERT INTO Facilities (Id, Name) VALUES (NULL, 'Minibar'), (NULL, 'Balcony'), (NULL, 'Safe')
```
Incorrecta (falla (The database's final content does not match what was expected after running your statement.), esperat: falla):
```sql
INSERT INTO Facilities (Name) VALUES ('Minibar'), ('Balcony')
```

### 2. S'han habilitat dues habitacions noves: una del tipus `Suite` i una del tipus `Room for 6 with private bathroom`, totes dues buides (`Empty` = 1). Afegeix-les a `Rooms` buscant el `RoomTypeId` pel nom del tipus a `RoomTypes` (no escriguis els identificadors a mà); el `RoomNumber` el posa la base de dades.

Referència:
```sql
INSERT INTO Rooms (RoomTypeId, Empty) SELECT Id, 1 FROM RoomTypes WHERE Name IN ('Suite', 'Room for 6 with private bathroom')
```
Alternativa (passa, esperat: passa):
```sql
INSERT INTO Rooms (RoomTypeId) VALUES ((SELECT Id FROM RoomTypes WHERE Name = 'Suite')), ((SELECT Id FROM RoomTypes WHERE Name = 'Room for 6 with private bathroom'))
```
Alternativa (passa, esperat: passa):
```sql
INSERT INTO Rooms (RoomTypeId, Empty) VALUES (8, TRUE), (7, TRUE)
```
Incorrecta (falla (The database's final content does not match what was expected after running your statement.), esperat: falla):
```sql
INSERT INTO Rooms (RoomTypeId, Empty) SELECT Id, 0 FROM RoomTypes WHERE Name IN ('Suite', 'Room for 6 with private bathroom')
```

### 3. Cal donar d'alta la temporada següent a l'última que hi ha a `Seasons`. Afegeix-hi una temporada anomenada `Spring 2025` el dia d'inici (`StartingDay`) de la qual sigui exactament 3 mesos després del `StartingDay` més recent de la taula. Calcula la data amb `MAX()` i `DATE_ADD` dins de la mateixa sentència.

Referència:
```sql
INSERT INTO Seasons (StartingDay, Name) SELECT DATE_ADD(MAX(StartingDay), INTERVAL 3 MONTH), 'Spring 2025' FROM Seasons
```
Alternativa (passa, esperat: passa):
```sql
INSERT INTO Seasons (Name, StartingDay) VALUES ('Spring 2025', '2025-03-21')
```
Alternativa (passa, esperat: passa):
```sql
INSERT INTO Seasons (StartingDay, Name) SELECT StartingDay + INTERVAL 3 MONTH, 'Spring 2025' FROM Seasons ORDER BY StartingDay DESC, Id DESC LIMIT 1
```
Incorrecta (falla (The database's final content does not match what was expected after running your statement.), esperat: falla):
```sql
INSERT INTO Seasons (StartingDay, Name) SELECT DATE_ADD(MAX(StartingDay), INTERVAL 1 MONTH), 'Spring 2025' FROM Seasons
```
Incorrecta (falla (SQL error: Duplicate entry '2020-06-21' for key 'StartingDay'), esperat: falla):
```sql
INSERT INTO Seasons (StartingDay, Name) SELECT DATE_ADD(MIN(StartingDay), INTERVAL 3 MONTH), 'Spring 2025' FROM Seasons
```

### 4. Registra a `Hosts` aquests tres hostes: (`DocType` `Passport`, `DocNumber` `PA1029384`, `FirstName` `LUCY`, `LastName` `MORGAN`, `Nationality` `English`), (`National ID`, `Y2345678Z`, `JORDI`, `PUIG SALA`, `Spanish`) i (`National ID`, `67588708B`, `SANTIAGO`, `LAGE GRADO`, `Spanish`). El `DocNumber` és únic: si ja existeix un hoste amb aquest document, aquella fila s'ha de descartar sense modificar l'hoste existent, i les altres s'han d'inserir igualment.

Referència:
```sql
INSERT IGNORE INTO Hosts (DocType, DocNumber, FirstName, LastName, Nationality) VALUES ('Passport', 'PA1029384', 'LUCY', 'MORGAN', 'English'), ('National ID', 'Y2345678Z', 'JORDI', 'PUIG SALA', 'Spanish'), ('National ID', '67588708B', 'SANTIAGO', 'LAGE GRADO', 'Spanish')
```
Alternativa (passa, esperat: passa):
```sql
INSERT INTO Hosts (DocType, DocNumber, FirstName, LastName, Nationality) VALUES ('Passport', 'PA1029384', 'LUCY', 'MORGAN', 'English'), ('National ID', 'Y2345678Z', 'JORDI', 'PUIG SALA', 'Spanish'), ('National ID', '67588708B', 'SANTIAGO', 'LAGE GRADO', 'Spanish') ON DUPLICATE KEY UPDATE DocNumber = DocNumber
```
Alternativa (passa, esperat: passa):
```sql
INSERT INTO Hosts (DocType, DocNumber, FirstName, LastName, Nationality) SELECT * FROM (SELECT 'Passport' AS t, 'PA1029384' AS d, 'LUCY' AS f, 'MORGAN' AS l, 'English' AS n UNION ALL SELECT 'National ID', 'Y2345678Z', 'JORDI', 'PUIG SALA', 'Spanish' UNION ALL SELECT 'National ID', '67588708B', 'SANTIAGO', 'LAGE GRADO', 'Spanish') x WHERE x.d NOT IN (SELECT DocNumber FROM Hosts)
```
Incorrecta (falla (The database's final content does not match what was expected after running your statement.), esperat: falla):
```sql
INSERT INTO Hosts (DocType, DocNumber, FirstName, LastName, Nationality) VALUES ('Passport', 'PA1029384', 'LUCY', 'MORGAN', 'English'), ('National ID', 'Y2345678Z', 'JORDI', 'PUIG SALA', 'Spanish'), ('National ID', '67588708B', 'SANTIAGO', 'LAGE GRADO', 'Spanish') ON DUPLICATE KEY UPDATE LastName = VALUES(LastName)
```
Incorrecta (falla (SQL error: Duplicate entry '67588708B' for key 'DocNumber'), esperat: falla):
```sql
INSERT INTO Hosts (DocType, DocNumber, FirstName, LastName, Nationality) VALUES ('Passport', 'PA1029384', 'LUCY', 'MORGAN', 'English'), ('National ID', 'Y2345678Z', 'JORDI', 'PUIG SALA', 'Spanish'), ('National ID', '67588708B', 'SANTIAGO', 'LAGE GRADO', 'Spanish')
```

### 5. Tots els tipus d'habitació (`RoomTypes`) amb capacitat (`Capacity`) de 3 o més han de tenir les instal·lacions `Flat-screen TV` i `Sofa` a `RoomTypeFacilities`. Alguns ja en tenen alguna: només s'han d'afegir les parelles que faltin. Fes-ho amb un sol `INSERT ... SELECT` que combini `RoomTypes` i `Facilities` buscant les instal·lacions pel nom (per exemple amb `INSERT IGNORE`, que descarta les files que repetirien la clau primària).

Referència:
```sql
INSERT IGNORE INTO RoomTypeFacilities (RoomTypeId, FacilityId) SELECT r.Id, f.Id FROM RoomTypes r CROSS JOIN Facilities f WHERE r.Capacity >= 3 AND f.Name IN ('Flat-screen TV', 'Sofa')
```
Alternativa (passa, esperat: passa):
```sql
INSERT INTO RoomTypeFacilities (RoomTypeId, FacilityId) SELECT r.Id, f.Id FROM RoomTypes r JOIN Facilities f ON f.Name IN ('Flat-screen TV', 'Sofa') WHERE r.Capacity >= 3 AND NOT EXISTS (SELECT 1 FROM RoomTypeFacilities x WHERE x.RoomTypeId = r.Id AND x.FacilityId = f.Id)
```
Alternativa (passa, esperat: passa):
```sql
REPLACE INTO RoomTypeFacilities (RoomTypeId, FacilityId) SELECT r.Id, f.Id FROM RoomTypes r, Facilities f WHERE r.Capacity > 2 AND (f.Name = 'Sofa' OR f.Name = 'Flat-screen TV')
```
Incorrecta (falla (The database's final content does not match what was expected after running your statement.), esperat: falla):
```sql
INSERT IGNORE INTO RoomTypeFacilities (RoomTypeId, FacilityId) SELECT r.Id, f.Id FROM RoomTypes r CROSS JOIN Facilities f WHERE r.Capacity > 3 AND f.Name IN ('Flat-screen TV', 'Sofa')
```
Incorrecta (falla (SQL error: Duplicate entry '5-4' for key 'PRIMARY'), esperat: falla):
```sql
INSERT INTO RoomTypeFacilities (RoomTypeId, FacilityId) SELECT r.Id, f.Id FROM RoomTypes r CROSS JOIN Facilities f WHERE r.Capacity >= 3 AND f.Name IN ('Flat-screen TV', 'Sofa')
```

### 6. S'insonoritzen les habitacions dels tipus més habituals. Afegeix la instal·lació `Soundproofing` (busca-la pel nom a `Facilities`) a cada tipus d'habitació que tingui almenys 4 habitacions a `Rooms`. Agrupa les habitacions per `RoomTypeId` i filtra amb `HAVING`.

Referència:
```sql
INSERT INTO RoomTypeFacilities (RoomTypeId, FacilityId) SELECT r.RoomTypeId, (SELECT Id FROM Facilities WHERE Name = 'Soundproofing') FROM Rooms r GROUP BY r.RoomTypeId HAVING COUNT(*) >= 4
```
Alternativa (passa, esperat: passa):
```sql
INSERT INTO RoomTypeFacilities (RoomTypeId, FacilityId) SELECT t.Id, f.Id FROM RoomTypes t JOIN Facilities f ON f.Name = 'Soundproofing' WHERE (SELECT COUNT(*) FROM Rooms r WHERE r.RoomTypeId = t.Id) >= 4
```
Alternativa (passa, esperat: passa):
```sql
INSERT IGNORE INTO RoomTypeFacilities (FacilityId, RoomTypeId) SELECT f.Id, r.RoomTypeId FROM Rooms r JOIN Facilities f ON f.Name = 'Soundproofing' GROUP BY f.Id, r.RoomTypeId HAVING COUNT(r.RoomNumber) > 3
```
Incorrecta (falla (The database's final content does not match what was expected after running your statement.), esperat: falla):
```sql
INSERT INTO RoomTypeFacilities (RoomTypeId, FacilityId) SELECT r.RoomTypeId, (SELECT Id FROM Facilities WHERE Name = 'Soundproofing') FROM Rooms r GROUP BY r.RoomTypeId HAVING COUNT(*) > 4
```

### 7. Arriben dues altes de clients a `Customers`: (`Email` `andrea_estevezbaragano@fastcompany.com`, `FirstName` `Andrea`, `LastName` `Estévez Baragaño`, `Nationality` `Spanish`, `PhoneNumber` `+34600111222`) i (`nuria_puigvert@ies-exemple.cat`, `NURIA`, `PUIGVERT SOLA`, `Spanish`, `+34611222333`). L'`Email` és únic. Si ja hi ha un client amb aquest email, **només** se li ha d'actualitzar el telèfon (`PhoneNumber`) amb el nou valor; la resta de les seves columnes es queden com estaven. Si no existeix, s'insereix el client nou. Fes-ho amb un sol `INSERT ... ON DUPLICATE KEY UPDATE` (amb `REPLACE` no funcionaria: esborraria el client, que té reserves).

Referència:
```sql
INSERT INTO Customers (Email, FirstName, LastName, Nationality, PhoneNumber) VALUES ('andrea_estevezbaragano@fastcompany.com', 'Andrea', 'Estévez Baragaño', 'Spanish', '+34600111222'), ('nuria_puigvert@ies-exemple.cat', 'NURIA', 'PUIGVERT SOLA', 'Spanish', '+34611222333') ON DUPLICATE KEY UPDATE PhoneNumber = VALUES(PhoneNumber)
```
Alternativa (passa, esperat: passa):
```sql
INSERT INTO Customers (Email, FirstName, LastName, Nationality, PhoneNumber) VALUES ('nuria_puigvert@ies-exemple.cat', 'NURIA', 'PUIGVERT SOLA', 'Spanish', '+34611222333'), ('andrea_estevezbaragano@fastcompany.com', 'Andrea', 'Estévez Baragaño', 'Spanish', '+34600111222') ON DUPLICATE KEY UPDATE PhoneNumber = VALUE(PhoneNumber)
```
Alternativa (passa, esperat: passa):
```sql
INSERT INTO Customers (Email, FirstName, LastName, Nationality, PhoneNumber) SELECT 'andrea_estevezbaragano@fastcompany.com', 'Andrea', 'Estévez Baragaño', 'Spanish', '+34600111222' UNION ALL SELECT 'nuria_puigvert@ies-exemple.cat', 'NURIA', 'PUIGVERT SOLA', 'Spanish', '+34611222333' ON DUPLICATE KEY UPDATE PhoneNumber = '+34600111222'
```
Incorrecta (falla (The database's final content does not match what was expected after running your statement.), esperat: falla):
```sql
INSERT INTO Customers (Email, FirstName, LastName, Nationality, PhoneNumber) VALUES ('andrea_estevezbaragano@fastcompany.com', 'Andrea', 'Estévez Baragaño', 'Spanish', '+34600111222'), ('nuria_puigvert@ies-exemple.cat', 'NURIA', 'PUIGVERT SOLA', 'Spanish', '+34611222333') ON DUPLICATE KEY UPDATE PhoneNumber = VALUES(PhoneNumber), FirstName = VALUES(FirstName), LastName = VALUES(LastName)
```
Incorrecta (falla (SQL error: Cannot delete or update a parent row: a foreign key constraint fails (`w_hotel`.`Bookings`, CONSTRAINT `Bookings_ibfk_1` FOREIGN KEY (`CustomerId`) REFERENCES `Customers` (`Id`) ON DELETE NO ACTION ON UPDATE CASCADE)), esperat: falla):
```sql
REPLACE INTO Customers (Email, FirstName, LastName, Nationality, PhoneNumber) VALUES ('andrea_estevezbaragano@fastcompany.com', 'Andrea', 'Estévez Baragaño', 'Spanish', '+34600111222'), ('nuria_puigvert@ies-exemple.cat', 'NURIA', 'PUIGVERT SOLA', 'Spanish', '+34611222333')
```
Incorrecta (falla (The database's final content does not match what was expected after running your statement.), esperat: falla):
```sql
INSERT IGNORE INTO Customers (Email, FirstName, LastName, Nationality, PhoneNumber) VALUES ('andrea_estevezbaragano@fastcompany.com', 'Andrea', 'Estévez Baragaño', 'Spanish', '+34600111222'), ('nuria_puigvert@ies-exemple.cat', 'NURIA', 'PUIGVERT SOLA', 'Spanish', '+34611222333')
```

### 8. Es revisen les tarifes de 2024: per a cada tipus d'habitació i cada estació, el preu (`Price`) de `PriceSeasons` de la temporada de 2024 ha de passar a ser el de la mateixa estació de 2023 incrementat un 5%, `ROUND(preu_2023 * 1.05, 2)`. Les temporades s'identifiquen pel nom (`Seasons.Name`): `Winter 2023` correspon a `Winter 2024`, `Spring 2023` a `Spring 2024`, etc. Les files de 2024 ja existeixen, però s'ha de fer amb un `INSERT ... SELECT` que sobreescrigui el preu: amb `ON DUPLICATE KEY UPDATE` o amb `REPLACE` (aquí `REPLACE` sí que funciona: `PriceSeasons` no té files filles).

Referència:
```sql
INSERT INTO PriceSeasons (RoomTypeId, SeasonId, Price) SELECT p.RoomTypeId, s24.Id, ROUND(p.Price * 1.05, 2) FROM PriceSeasons p JOIN Seasons s23 ON s23.Id = p.SeasonId JOIN Seasons s24 ON s24.Name = REPLACE(s23.Name, '2023', '2024') WHERE s23.Name LIKE '% 2023' ON DUPLICATE KEY UPDATE Price = VALUES(Price)
```
Alternativa (passa, esperat: passa):
```sql
REPLACE INTO PriceSeasons (RoomTypeId, SeasonId, Price) SELECT p.RoomTypeId, s24.Id, ROUND(p.Price * 1.05, 2) FROM PriceSeasons p JOIN Seasons s23 ON s23.Id = p.SeasonId JOIN Seasons s24 ON SUBSTRING_INDEX(s24.Name, ' ', 1) = SUBSTRING_INDEX(s23.Name, ' ', 1) WHERE s23.Name LIKE '%2023' AND s24.Name LIKE '%2024'
```
Alternativa (passa, esperat: passa):
```sql
INSERT INTO PriceSeasons (RoomTypeId, SeasonId, Price) SELECT p.RoomTypeId, s24.Id, ROUND(p.Price * 1.05, 2) FROM PriceSeasons p JOIN Seasons s23 ON s23.Id = p.SeasonId JOIN Seasons s24 ON s24.StartingDay = DATE_ADD(s23.StartingDay, INTERVAL 1 YEAR) WHERE YEAR(s23.StartingDay) = 2023 ON DUPLICATE KEY UPDATE Price = VALUES(Price)
```
Incorrecta (falla (The database's final content does not match what was expected after running your statement.), esperat: falla):
```sql
INSERT INTO PriceSeasons (RoomTypeId, SeasonId, Price) SELECT p.RoomTypeId, p.SeasonId, ROUND(p.Price * 1.05, 2) FROM PriceSeasons p JOIN Seasons s ON s.Id = p.SeasonId WHERE s.Name LIKE '% 2024' ON DUPLICATE KEY UPDATE Price = VALUES(Price)
```

### 9. Avui (13 de novembre de 2023) entren els clients de totes les reserves (`Bookings`) en estat `Reserved` amb `CheckIn` el `2023-11-13`. Registra'n les estades a `Stays`: `CheckIn` el de la reserva, `RoomNumber` l'habitació assignada a la reserva al calendari (`BookingCalendar.AssignedRoom`) per al dia d'entrada, `CheckOut`, `PaymentType` i `PaymentDateTime` a `NULL` (encara no han marxat ni pagat), `TotalPrice` el preu de la reserva (`Bookings.Price`) i `BookingId` l'`Id` de la reserva. L'`Id` de l'estada el posa la base de dades.

Referència:
```sql
INSERT INTO Stays (CheckIn, RoomNumber, CheckOut, TotalPrice, PaymentType, BookingId, PaymentDateTime) SELECT b.CheckIn, k.AssignedRoom, NULL, b.Price, NULL, b.Id, NULL FROM Bookings b JOIN BookingCalendar k ON k.BookingId = b.Id AND k.BookedDate = b.CheckIn WHERE b.State = 'Reserved' AND b.CheckIn = '2023-11-13'
```
Alternativa (passa, esperat: passa):
```sql
INSERT INTO Stays (BookingId, CheckIn, TotalPrice, RoomNumber) SELECT b.Id, b.CheckIn, b.Price, (SELECT k.AssignedRoom FROM BookingCalendar k WHERE k.BookingId = b.Id AND k.BookedDate = '2023-11-13') FROM Bookings b WHERE b.CheckIn = '2023-11-13' AND b.State <> 'Cancelled'
```
Incorrecta (falla (The database's final content does not match what was expected after running your statement.), esperat: falla):
```sql
INSERT INTO Stays (CheckIn, RoomNumber, CheckOut, TotalPrice, BookingId) SELECT b.CheckIn, k.AssignedRoom, b.CheckOut, b.Price, b.Id FROM Bookings b JOIN BookingCalendar k ON k.BookingId = b.Id AND k.BookedDate = b.CheckIn WHERE b.State = 'Reserved' AND b.CheckIn = '2023-11-13'
```

### 10. L'hotel regala una estada al client més fidel: el `CustomerId` amb més reserves a `Bookings` (de qualsevol estat; en cas d'empat, el de `CustomerId` més petit). Crea-li una reserva a `Bookings` amb: `ReservationDateTime` `2023-11-13 09:00:00`, tipus d'habitació `Suite` (busca'n l'`Id` pel nom), `CheckIn` `2024-03-25`, `CheckOut` `2024-03-28`, `State` `Reserved`, `NHosts` 2 i `Price` = nombre de nits × preu de la `Suite` a `PriceSeasons` en la temporada vigent el dia d'entrada (la de `StartingDay` més recent que no sigui posterior al `2024-03-25`) × 0.8 (un 20% de descompte), arrodonit amb `ROUND(..., 2)`. Calcula-ho tot dins de la sentència (nits amb `DATEDIFF`); l'`Id` de la reserva el posa la base de dades.

Referència:
```sql
INSERT INTO Bookings (ReservationDateTime, CustomerId, RoomTypeId, CheckIn, CheckOut, Price, State, NHosts) SELECT '2023-11-13 09:00:00', (SELECT CustomerId FROM Bookings GROUP BY CustomerId ORDER BY COUNT(*) DESC, CustomerId LIMIT 1), r.Id, '2024-03-25', '2024-03-28', ROUND(DATEDIFF('2024-03-28', '2024-03-25') * p.Price * 0.8, 2), 'Reserved', 2 FROM RoomTypes r JOIN PriceSeasons p ON p.RoomTypeId = r.Id WHERE r.Name = 'Suite' AND p.SeasonId = (SELECT Id FROM Seasons WHERE StartingDay <= '2024-03-25' ORDER BY StartingDay DESC, Id DESC LIMIT 1)
```
Alternativa (passa, esperat: passa):
```sql
INSERT INTO Bookings (ReservationDateTime, CustomerId, RoomTypeId, CheckIn, CheckOut, Price, State, NHosts) SELECT '2023-11-13 09:00:00', c.CustomerId, r.Id, '2024-03-25', '2024-03-28', ROUND(3 * p.Price * 0.8, 2), 'Reserved', 2 FROM (SELECT CustomerId, COUNT(*) n FROM Bookings GROUP BY CustomerId ORDER BY n DESC, CustomerId ASC LIMIT 1) c JOIN RoomTypes r ON r.Name = 'Suite' JOIN PriceSeasons p ON p.RoomTypeId = r.Id JOIN Seasons s ON s.Id = p.SeasonId WHERE s.StartingDay = (SELECT MAX(StartingDay) FROM Seasons WHERE StartingDay <= '2024-03-25')
```
Alternativa (passa, esperat: passa):
```sql
INSERT INTO Bookings (ReservationDateTime, CustomerId, RoomTypeId, CheckIn, CheckOut, Price, State, NHosts) VALUES ('2023-11-13 09:00:00', 145, 8, '2024-03-25', '2024-03-28', 256.32, 'Reserved', 2)
```
Incorrecta (falla (The database's final content does not match what was expected after running your statement.), esperat: falla):
```sql
INSERT INTO Bookings (ReservationDateTime, CustomerId, RoomTypeId, CheckIn, CheckOut, Price, State, NHosts) SELECT '2023-11-13 09:00:00', (SELECT CustomerId FROM Bookings GROUP BY CustomerId ORDER BY COUNT(*) DESC, CustomerId DESC LIMIT 1), r.Id, '2024-03-25', '2024-03-28', ROUND(3 * p.Price * 0.8, 2), 'Reserved', 2 FROM RoomTypes r JOIN PriceSeasons p ON p.RoomTypeId = r.Id JOIN Seasons s ON s.Id = p.SeasonId WHERE r.Name = 'Suite' AND s.Name = 'Spring 2024'
```
Incorrecta (falla (The database's final content does not match what was expected after running your statement.), esperat: falla):
```sql
INSERT INTO Bookings (ReservationDateTime, CustomerId, RoomTypeId, CheckIn, CheckOut, Price, State, NHosts) SELECT '2023-11-13 09:00:00', 145, r.Id, '2024-03-25', '2024-03-28', ROUND(3 * p.Price * 0.8, 2), 'Reserved', 2 FROM RoomTypes r JOIN PriceSeasons p ON p.RoomTypeId = r.Id JOIN Seasons s ON s.Id = p.SeasonId WHERE r.Name = 'Suite' AND s.Name = 'Winter 2024'
```

## Hotel — UPDATE amb JOIN i subconsultes

### 1. Es volen escurçar els noms dels tipus d'habitació: a `RoomTypes`, substitueix la paraula `bathroom` per `bath` dins del nom (`Name`) de tots els tipus que la contenen (per exemple `Double room with private bathroom` passa a `Double room with private bath`). Fes servir la funció de text `REPLACE`.

Referència:
```sql
UPDATE RoomTypes SET Name = REPLACE(Name, 'bathroom', 'bath') WHERE Name LIKE '%bathroom%'
```
Alternativa (passa, esperat: passa):
```sql
UPDATE RoomTypes SET Name = REPLACE(Name, 'bathroom', 'bath')
```
Alternativa (passa, esperat: passa):
```sql
UPDATE RoomTypes SET Name = CONCAT(LEFT(Name, CHAR_LENGTH(Name) - 4)) WHERE Name LIKE '%bathroom'
```
Incorrecta (falla (The database's final content does not match what was expected after running your statement.), esperat: falla):
```sql
UPDATE RoomTypes SET Name = REPLACE(Name, ' bathroom', '') WHERE Name LIKE '%bathroom%'
```
Incorrecta (falla (The database's final content does not match what was expected after running your statement.), esperat: falla):
```sql
UPDATE RoomTypes SET Name = REPLACE(Name, 'bathroom', 'Bath') WHERE Name LIKE '%bathroom%'
```

### 2. Les temporades que comencen l'any 2020 queden arxivades: a `Seasons`, afegeix el text ` (archived)` (amb un espai al davant) al final del nom (`Name`) de les temporades el `StartingDay` de les quals és de l'any 2020. Fes servir `CONCAT` i `YEAR`.

Referència:
```sql
UPDATE Seasons SET Name = CONCAT(Name, ' (archived)') WHERE YEAR(StartingDay) = 2020
```
Alternativa (passa, esperat: passa):
```sql
UPDATE Seasons SET Name = CONCAT_WS(' ', Name, '(archived)') WHERE StartingDay BETWEEN '2020-01-01' AND '2020-12-31'
```
Alternativa (passa, esperat: passa):
```sql
UPDATE Seasons SET Name = CONCAT(Name, ' (archived)') WHERE Name LIKE '% 2020'
```
Incorrecta (falla (The database's final content does not match what was expected after running your statement.), esperat: falla):
```sql
UPDATE Seasons SET Name = CONCAT(Name, '(archived)') WHERE YEAR(StartingDay) = 2020
```
Incorrecta (falla (The database's final content does not match what was expected after running your statement.), esperat: falla):
```sql
UPDATE Seasons SET Name = CONCAT(Name, ' (archived)') WHERE StartingDay < '2020-12-01'
```

### 3. Les reserves futures llargues tenen descompte: a `Bookings`, per a les reserves en estat `Reserved` amb `CheckIn` a partir del `2023-11-13` (inclòs) i una durada de 7 nits o més (`DATEDIFF(CheckOut, CheckIn)`), posa el preu (`Price`) a `ROUND(Price * 0.93, 2)`.

Referència:
```sql
UPDATE Bookings SET Price = ROUND(Price * 0.93, 2) WHERE State = 'Reserved' AND CheckIn >= '2023-11-13' AND DATEDIFF(CheckOut, CheckIn) >= 7
```
Alternativa (passa, esperat: passa):
```sql
UPDATE Bookings SET Price = ROUND(Price - Price * 0.07, 2) WHERE State <> 'Cancelled' AND CheckIn > '2023-11-12' AND CheckOut >= DATE_ADD(CheckIn, INTERVAL 7 DAY)
```
Incorrecta (falla (The database's final content does not match what was expected after running your statement.), esperat: falla):
```sql
UPDATE Bookings SET Price = ROUND(Price * 0.93, 2) WHERE State = 'Reserved' AND CheckIn >= '2023-11-13' AND DATEDIFF(CheckOut, CheckIn) > 7
```
Incorrecta (falla (The database's final content does not match what was expected after running your statement.), esperat: falla):
```sql
UPDATE Bookings SET Price = ROUND(Price * 0.93, 2) WHERE State = 'Reserved' AND CheckIn >= '2023-11-13' AND DATEDIFF(CheckIn, CheckOut) >= 7
```

### 4. L'estiu de 2024 s'apuja un 3% el preu de les habitacions amb bany privat. A `PriceSeasons`, posa `Price` a `ROUND(Price * 1.03, 2)` de les files de la temporada anomenada `Summer 2024` dels tipus d'habitació que tenen la instal·lació `Private bathroom` (segons `RoomTypeFacilities`). Fes-ho amb un `UPDATE` multitaula amb `JOIN` (temporades i instal·lacions buscades pel nom).

Referència:
```sql
UPDATE PriceSeasons p JOIN Seasons s ON s.Id = p.SeasonId JOIN RoomTypeFacilities rf ON rf.RoomTypeId = p.RoomTypeId JOIN Facilities f ON f.Id = rf.FacilityId SET p.Price = ROUND(p.Price * 1.03, 2) WHERE s.Name = 'Summer 2024' AND f.Name = 'Private bathroom'
```
Alternativa (passa, esperat: passa):
```sql
UPDATE PriceSeasons SET Price = ROUND(Price * 1.03, 2) WHERE SeasonId = (SELECT Id FROM Seasons WHERE Name = 'Summer 2024') AND RoomTypeId IN (SELECT rf.RoomTypeId FROM RoomTypeFacilities rf JOIN Facilities f ON f.Id = rf.FacilityId WHERE f.Name = 'Private bathroom')
```
Incorrecta (falla (The database's final content does not match what was expected after running your statement.), esperat: falla):
```sql
UPDATE PriceSeasons p JOIN Seasons s ON s.Id = p.SeasonId SET p.Price = ROUND(p.Price * 1.03, 2) WHERE s.Name = 'Summer 2024'
```
Incorrecta (falla (The database's final content does not match what was expected after running your statement.), esperat: falla):
```sql
UPDATE PriceSeasons p JOIN Seasons s ON s.Id = p.SeasonId JOIN RoomTypes r ON r.Id = p.RoomTypeId SET p.Price = ROUND(p.Price * 1.03, 2) WHERE s.Name = 'Summer 2024' AND r.Name LIKE '%private bathroom%'
```

### 5. Promoció d'hivern per trams de capacitat: a `PriceSeasons`, per a la temporada `Winter 2024`, el preu de cada tipus d'habitació (`Price`) es multiplica per 0.90 si la capacitat del tipus (`RoomTypes.Capacity`) és 1, per 0.95 si és 2 o 3, i per 0.85 si és 4 o més. El resultat s'arrodoneix amb `ROUND(..., 2)`. Fes-ho amb un sol `UPDATE` que faci servir `CASE`.

Referència:
```sql
UPDATE PriceSeasons p JOIN RoomTypes r ON r.Id = p.RoomTypeId JOIN Seasons s ON s.Id = p.SeasonId SET p.Price = ROUND(p.Price * CASE WHEN r.Capacity = 1 THEN 0.90 WHEN r.Capacity <= 3 THEN 0.95 ELSE 0.85 END, 2) WHERE s.Name = 'Winter 2024'
```
Alternativa (passa, esperat: passa):
```sql
UPDATE PriceSeasons SET Price = CASE WHEN (SELECT Capacity FROM RoomTypes r WHERE r.Id = RoomTypeId) >= 4 THEN ROUND(Price * 0.85, 2) WHEN (SELECT Capacity FROM RoomTypes r WHERE r.Id = RoomTypeId) IN (2, 3) THEN ROUND(Price * 0.95, 2) ELSE ROUND(Price * 0.9, 2) END WHERE SeasonId IN (SELECT Id FROM Seasons WHERE Name = 'Winter 2024')
```
Incorrecta (falla (The database's final content does not match what was expected after running your statement.), esperat: falla):
```sql
UPDATE PriceSeasons p JOIN RoomTypes r ON r.Id = p.RoomTypeId JOIN Seasons s ON s.Id = p.SeasonId SET p.Price = ROUND(p.Price * CASE WHEN r.Capacity = 1 THEN 0.90 WHEN r.Capacity < 3 THEN 0.95 ELSE 0.85 END, 2) WHERE s.Name = 'Winter 2024'
```

### 6. Hi ha estades obertes (`Stays.CheckOut` és `NULL`) la reserva de les quals acaba (`Bookings.CheckOut`) el `2023-11-14` o abans. Tanca-les: posa a l'estada `CheckOut` = el `CheckOut` de la seva reserva, `PaymentType` = `Card` i `PaymentDateTime` = el dia de sortida a les `11:00:00` (calcula-ho, per exemple, amb `TIMESTAMP(data, '11:00:00')` o `DATE_ADD(data, INTERVAL 11 HOUR)`). Fes-ho amb un `UPDATE` multitaula `Stays JOIN Bookings`.

Referència:
```sql
UPDATE Stays s JOIN Bookings b ON b.Id = s.BookingId SET s.CheckOut = b.CheckOut, s.PaymentType = 'Card', s.PaymentDateTime = TIMESTAMP(b.CheckOut, '11:00:00') WHERE s.CheckOut IS NULL AND b.CheckOut <= '2023-11-14'
```
Alternativa (passa, esperat: passa):
```sql
UPDATE Stays s SET s.CheckOut = (SELECT b.CheckOut FROM Bookings b WHERE b.Id = s.BookingId), s.PaymentType = 'Card', s.PaymentDateTime = DATE_ADD((SELECT b.CheckOut FROM Bookings b WHERE b.Id = s.BookingId), INTERVAL 11 HOUR) WHERE s.CheckOut IS NULL AND s.BookingId IN (SELECT Id FROM Bookings WHERE CheckOut < '2023-11-15')
```
Incorrecta (falla (The database's final content does not match what was expected after running your statement.), esperat: falla):
```sql
UPDATE Stays s JOIN Bookings b ON b.Id = s.BookingId SET s.CheckOut = b.CheckOut, s.PaymentType = 'Card', s.PaymentDateTime = TIMESTAMP(b.CheckOut, '11:00:00') WHERE s.CheckOut IS NULL AND b.CheckOut < '2023-11-14'
```
Incorrecta (falla (The database's final content does not match what was expected after running your statement.), esperat: falla):
```sql
UPDATE Stays s JOIN Bookings b ON b.Id = s.BookingId SET s.CheckOut = b.CheckOut, s.PaymentType = 'Card', s.PaymentDateTime = b.CheckOut WHERE s.CheckOut IS NULL AND b.CheckOut <= '2023-11-14'
```

### 7. Hi ha massa reserves de la `Suite` per a les properes setmanes. A `Bookings`, passa a estat `Cancelled` les 3 reserves en estat `Reserved` del tipus d'habitació `Suite` (busca l'`Id` pel nom amb una subconsulta) que tenen el `CheckIn` més tardà; en cas d'empat de `CheckIn`, primer les d'`Id` més gran. Fes servir `ORDER BY ... LIMIT`. Atenció: MySQL no admet `ORDER BY` ni `LIMIT` en un `UPDATE` multitaula (amb `JOIN`), per això el tipus s'ha de buscar amb una subconsulta.

Referència:
```sql
UPDATE Bookings SET State = 'Cancelled' WHERE State = 'Reserved' AND RoomTypeId = (SELECT Id FROM RoomTypes WHERE Name = 'Suite') ORDER BY CheckIn DESC, Id DESC LIMIT 3
```
Alternativa (passa, esperat: passa):
```sql
UPDATE Bookings SET State = 'Cancelled' WHERE Id IN (SELECT Id FROM (SELECT b.Id FROM Bookings b JOIN RoomTypes r ON r.Id = b.RoomTypeId WHERE r.Name = 'Suite' AND b.State = 'Reserved' ORDER BY b.CheckIn DESC, b.Id DESC LIMIT 3) t)
```
Incorrecta (falla (The database's final content does not match what was expected after running your statement.), esperat: falla):
```sql
UPDATE Bookings SET State = 'Cancelled' WHERE State = 'Reserved' AND RoomTypeId = (SELECT Id FROM RoomTypes WHERE Name = 'Suite') ORDER BY ReservationDateTime DESC, Id DESC LIMIT 3
```
Incorrecta (falla (The database's final content does not match what was expected after running your statement.), esperat: falla):
```sql
UPDATE Bookings SET State = 'Cancelled' WHERE State = 'Reserved' AND RoomTypeId = (SELECT Id FROM RoomTypes WHERE Name = 'Suite') ORDER BY CheckIn, Id LIMIT 3
```

### 8. El nombre d'hostes (`NHosts`) d'algunes reserves no coincideix amb els hostes realment registrats. Per a cada reserva de `Bookings` amb `CheckIn` de l'any 2023 que tingui almenys un hoste registrat a `StayHosts` (a través de la seva estada a `Stays`), posa `NHosts` igual al nombre d'hostes registrats a les seves estades. Les reserves sense cap hoste registrat no es toquen. Fes-ho amb una subconsulta correlacionada.

Referència:
```sql
UPDATE Bookings b SET b.NHosts = (SELECT COUNT(*) FROM Stays s JOIN StayHosts sh ON sh.StayId = s.Id WHERE s.BookingId = b.Id) WHERE b.CheckIn BETWEEN '2023-01-01' AND '2023-12-31' AND EXISTS (SELECT 1 FROM Stays s JOIN StayHosts sh ON sh.StayId = s.Id WHERE s.BookingId = b.Id)
```
Alternativa (passa, esperat: passa):
```sql
UPDATE Bookings b JOIN (SELECT s.BookingId, COUNT(*) AS n FROM Stays s JOIN StayHosts sh ON sh.StayId = s.Id GROUP BY s.BookingId) t ON t.BookingId = b.Id SET b.NHosts = t.n WHERE YEAR(b.CheckIn) = 2023
```
Incorrecta (falla (The database's final content does not match what was expected after running your statement.), esperat: falla):
```sql
UPDATE Bookings b SET b.NHosts = (SELECT COUNT(*) FROM Stays s JOIN StayHosts sh ON sh.StayId = s.Id WHERE s.BookingId = b.Id) WHERE YEAR(b.CheckIn) = 2023
```
Incorrecta (falla (The database's final content does not match what was expected after running your statement.), esperat: falla):
```sql
UPDATE Bookings b JOIN Stays s ON s.BookingId = b.Id SET b.NHosts = (SELECT COUNT(*) FROM StayHosts sh WHERE sh.StayId = s.Id) WHERE YEAR(b.CheckIn) = 2022
```

### 9. Les tarifes de 2024 més cares baixen: a `PriceSeasons`, les files de les temporades amb nom acabat en `2024` que tinguin un preu superior a la mitjana de **tots** els preus de les temporades de 2024 (calculada abans del canvi) passen a `ROUND(Price * 0.95, 2)`. Parany: a MySQL, `UPDATE PriceSeasons ... WHERE Price > (SELECT AVG(Price) FROM PriceSeasons ...)` dona l'error 1093 (no es pot llegir de la taula que s'està modificant); la solució portable és posar la subconsulta dins d'una taula derivada (`SELECT ... FROM (SELECT AVG(...) ...) AS t`), que es calcula una sola vegada abans de modificar res. MariaDB també accepta la subconsulta directa.

Referència:
```sql
UPDATE PriceSeasons SET Price = ROUND(Price * 0.95, 2) WHERE SeasonId IN (SELECT Id FROM Seasons WHERE Name LIKE '% 2024') AND Price > (SELECT m FROM (SELECT AVG(p.Price) AS m FROM PriceSeasons p JOIN Seasons s ON s.Id = p.SeasonId WHERE s.Name LIKE '% 2024') AS t)
```
Alternativa (passa, esperat: passa):
```sql
UPDATE PriceSeasons p JOIN Seasons s ON s.Id = p.SeasonId JOIN (SELECT AVG(p2.Price) AS m FROM PriceSeasons p2 JOIN Seasons s2 ON s2.Id = p2.SeasonId WHERE s2.Name LIKE '%2024') t SET p.Price = ROUND(p.Price * 0.95, 2) WHERE s.Name LIKE '%2024' AND p.Price > t.m
```
Alternativa (passa, esperat: passa):
```sql
UPDATE PriceSeasons SET Price = ROUND(Price * 0.95, 2) WHERE SeasonId IN (SELECT Id FROM Seasons WHERE YEAR(StartingDay) = 2024) AND Price > (SELECT AVG(p.Price) FROM PriceSeasons p JOIN Seasons s ON s.Id = p.SeasonId WHERE YEAR(s.StartingDay) = 2024)
```
Incorrecta (falla (The database's final content does not match what was expected after running your statement.), esperat: falla):
```sql
UPDATE PriceSeasons SET Price = ROUND(Price * 0.95, 2) WHERE Price > (SELECT m FROM (SELECT AVG(p.Price) AS m FROM PriceSeasons p JOIN Seasons s ON s.Id = p.SeasonId WHERE s.Name LIKE '% 2024') AS t)
```

### 10. Descompte de fidelitat per als clients que són ara a l'hotel: per a cada estada oberta (`Stays.CheckOut` és `NULL`) d'un client que té 2 o més reserves a `Bookings` (de qualsevol estat), aplica un 5% de descompte **alhora** al `TotalPrice` de l'estada i al `Price` de la seva reserva: tots dos passen a `ROUND(valor * 0.95, 2)`. Fes-ho amb un sol `UPDATE` multitaula que modifiqui les dues taules (el recompte de reserves per client, amb una taula derivada amb `GROUP BY`).

Referència:
```sql
UPDATE Stays s JOIN Bookings b ON b.Id = s.BookingId JOIN (SELECT CustomerId, COUNT(*) AS n FROM Bookings GROUP BY CustomerId) c ON c.CustomerId = b.CustomerId SET s.TotalPrice = ROUND(s.TotalPrice * 0.95, 2), b.Price = ROUND(b.Price * 0.95, 2) WHERE s.CheckOut IS NULL AND c.n >= 2
```
Alternativa (passa, esperat: passa):
```sql
UPDATE Bookings b JOIN Stays s ON s.BookingId = b.Id SET b.Price = ROUND(b.Price * 0.95, 2), s.TotalPrice = ROUND(s.TotalPrice * 0.95, 2) WHERE s.CheckOut IS NULL AND b.CustomerId IN (SELECT CustomerId FROM (SELECT CustomerId FROM Bookings GROUP BY CustomerId HAVING COUNT(*) > 1) AS t)
```
Incorrecta (falla (The database's final content does not match what was expected after running your statement.), esperat: falla):
```sql
UPDATE Stays s JOIN Bookings b ON b.Id = s.BookingId JOIN (SELECT CustomerId, COUNT(*) AS n FROM Bookings GROUP BY CustomerId) c ON c.CustomerId = b.CustomerId SET s.TotalPrice = ROUND(s.TotalPrice * 0.95, 2) WHERE s.CheckOut IS NULL AND c.n >= 2
```
Incorrecta (falla (The database's final content does not match what was expected after running your statement.), esperat: falla):
```sql
UPDATE Stays s JOIN Bookings b ON b.Id = s.BookingId JOIN (SELECT CustomerId, COUNT(*) AS n FROM Bookings WHERE State = 'Reserved' GROUP BY CustomerId) c ON c.CustomerId = b.CustomerId SET s.TotalPrice = ROUND(s.TotalPrice * 0.95, 2), b.Price = ROUND(b.Price * 0.95, 2) WHERE s.CheckOut IS NULL AND c.n >= 3
```

## Hotel — DELETE

### 1. Esborra de `Seasons` les temporades el `StartingDay` de les quals és de l'any 2020 (entre l'1 de gener i el 31 de desembre de 2020, tots dos inclosos). Com que `PriceSeasons` té `ON DELETE CASCADE` cap a `Seasons`, també desapareixeran soles les tarifes d'aquestes temporades.

Referència:
```sql
DELETE FROM Seasons WHERE StartingDay BETWEEN '2020-01-01' AND '2020-12-31'
```
Alternativa (passa, esperat: passa):
```sql
DELETE FROM Seasons WHERE Name LIKE '%2020'
```
Alternativa (passa, esperat: passa):
```sql
DELETE FROM Seasons WHERE YEAR(StartingDay) = 2020
```
Incorrecta (falla (The database's final content does not match what was expected after running your statement.), esperat: falla):
```sql
DELETE FROM Seasons WHERE StartingDay BETWEEN '2020-01-01' AND '2020-12-01'
```
Incorrecta (falla (The database's final content does not match what was expected after running your statement.), esperat: falla):
```sql
DELETE FROM PriceSeasons WHERE SeasonId IN (SELECT Id FROM Seasons WHERE YEAR(StartingDay) = 2020)
```

### 2. L'hotel deixa de publicar tarifes d'hivern per a les habitacions amb bany compartit. Esborra de `PriceSeasons` les files de les temporades el nom de les quals comença per `Winter` i dels tipus d'habitació el nom dels quals conté `shared bathroom`. Només s'han d'esborrar tarifes: ni temporades ni tipus d'habitació.

Referència:
```sql
DELETE FROM PriceSeasons WHERE SeasonId IN (SELECT Id FROM Seasons WHERE Name LIKE 'Winter%') AND RoomTypeId IN (SELECT Id FROM RoomTypes WHERE Name LIKE '%shared bathroom%')
```
Alternativa (passa, esperat: passa):
```sql
DELETE p FROM PriceSeasons p JOIN Seasons s ON s.Id = p.SeasonId JOIN RoomTypes r ON r.Id = p.RoomTypeId WHERE s.Name LIKE 'Winter %' AND r.Name LIKE '%shared bathroom'
```
Incorrecta (falla (The database's final content does not match what was expected after running your statement.), esperat: falla):
```sql
DELETE FROM PriceSeasons WHERE SeasonId IN (SELECT Id FROM Seasons WHERE Name LIKE 'Winter%')
```
Incorrecta (falla (The database's final content does not match what was expected after running your statement.), esperat: falla):
```sql
DELETE FROM PriceSeasons WHERE SeasonId IN (SELECT Id FROM Seasons WHERE Name LIKE '%Winter%') AND RoomTypeId IN (SELECT Id FROM RoomTypes WHERE Name LIKE '%private bathroom%')
```

### 3. Esborra de `Customers` els clients de nacionalitat (`Nationality`) `French` que no han fet mai cap reserva (no apareixen a `Bookings`). Fes-ho amb `NOT EXISTS` o `NOT IN`.

Referència:
```sql
DELETE FROM Customers WHERE Nationality = 'French' AND NOT EXISTS (SELECT 1 FROM Bookings b WHERE b.CustomerId = Customers.Id)
```
Alternativa (passa, esperat: passa):
```sql
DELETE FROM Customers WHERE Nationality = 'French' AND Id NOT IN (SELECT CustomerId FROM Bookings)
```
Alternativa (passa, esperat: passa):
```sql
DELETE c FROM Customers c LEFT JOIN Bookings b ON b.CustomerId = c.Id WHERE c.Nationality = 'French' AND b.Id IS NULL
```
Incorrecta (falla (The database's final content does not match what was expected after running your statement.), esperat: falla):
```sql
DELETE FROM Customers WHERE Nationality <> 'French' AND NOT EXISTS (SELECT 1 FROM Bookings b WHERE b.CustomerId = Customers.Id)
```
Incorrecta (falla (SQL error: Cannot delete or update a parent row: a foreign key constraint fails (`w_hotel`.`Bookings`, CONSTRAINT `Bookings_ibfk_1` FOREIGN KEY (`CustomerId`) REFERENCES `Customers` (`Id`) ON DELETE NO ACTION ON UPDATE CASCADE)), esperat: falla):
```sql
DELETE FROM Customers WHERE Nationality = 'French' AND Id NOT IN (SELECT CustomerId FROM Bookings WHERE State = 'Reserved')
```

### 4. Esborra de `Bookings` les 5 reserves en estat `Cancelled` que es van fer primer (`ReservationDateTime` més antic; en cas d'empat, primer l'`Id` més petit). Fes servir `ORDER BY ... LIMIT`. (Les reserves cancel·lades no tenen estades ni calendari, així que l'esborrat no topa amb cap clau forana.)

Referència:
```sql
DELETE FROM Bookings WHERE State = 'Cancelled' ORDER BY ReservationDateTime, Id LIMIT 5
```
Alternativa (passa, esperat: passa):
```sql
DELETE FROM Bookings WHERE Id IN (SELECT Id FROM (SELECT Id FROM Bookings WHERE State = 'Cancelled' ORDER BY ReservationDateTime ASC, Id ASC LIMIT 5) AS t)
```
Incorrecta (falla (The database's final content does not match what was expected after running your statement.), esperat: falla):
```sql
DELETE FROM Bookings WHERE State = 'Cancelled' ORDER BY CheckIn, Id LIMIT 5
```
Incorrecta (falla (The database's final content does not match what was expected after running your statement.), esperat: falla):
```sql
DELETE FROM Bookings WHERE State = 'Cancelled' ORDER BY ReservationDateTime DESC, Id DESC LIMIT 5
```

### 5. S'han de tornar a registrar els hostes de les estades a habitacions del tipus `Suite` amb `CheckIn` del gener de 2021. Esborra de `StayHosts` els registres d'aquestes estades amb un `DELETE` multitaula (`DELETE sh FROM StayHosts sh JOIN Stays ... JOIN Rooms ... JOIN RoomTypes ...`). Les estades i els hostes no s'esborren.

Referència:
```sql
DELETE sh FROM StayHosts sh JOIN Stays s ON s.Id = sh.StayId JOIN Rooms r ON r.RoomNumber = s.RoomNumber JOIN RoomTypes t ON t.Id = r.RoomTypeId WHERE t.Name = 'Suite' AND s.CheckIn >= '2021-01-01' AND s.CheckIn < '2021-02-01'
```
Alternativa (passa, esperat: passa):
```sql
DELETE FROM StayHosts WHERE StayId IN (SELECT s.Id FROM Stays s WHERE s.CheckIn BETWEEN '2021-01-01' AND '2021-01-31' AND s.RoomNumber IN (SELECT RoomNumber FROM Rooms WHERE RoomTypeId = (SELECT Id FROM RoomTypes WHERE Name = 'Suite')))
```
Incorrecta (falla (The database's final content does not match what was expected after running your statement.), esperat: falla):
```sql
DELETE sh FROM StayHosts sh JOIN Stays s ON s.Id = sh.StayId JOIN Bookings b ON b.Id = s.BookingId JOIN RoomTypes t ON t.Id = b.RoomTypeId WHERE t.Name = 'Suite' AND s.CheckIn >= '2021-01-01' AND s.CheckIn < '2021-03-01'
```

### 6. L'hotel tancarà per obres a partir de l'1 de febrer de 2024 i anul·la les reserves afectades. Esborra de `Bookings` les reserves en estat `Reserved` amb `CheckIn` el `2024-02-01` o més tard. Pensa què passarà amb les seves files de `BookingCalendar`: com que la clau forana té `ON DELETE CASCADE`, s'esborraran soles amb la reserva (i per això la sentència no falla).

Referència:
```sql
DELETE FROM Bookings WHERE State = 'Reserved' AND CheckIn >= '2024-02-01'
```
Alternativa (passa, esperat: passa):
```sql
DELETE b FROM Bookings b WHERE b.CheckIn > '2024-01-31' AND b.State <> 'Cancelled'
```
Incorrecta (falla (The database's final content does not match what was expected after running your statement.), esperat: falla):
```sql
DELETE FROM Bookings WHERE CheckIn >= '2024-02-01'
```
Incorrecta (falla (The database's final content does not match what was expected after running your statement.), esperat: falla):
```sql
DELETE FROM BookingCalendar WHERE BookedDate >= '2024-02-01'
```

### 7. Esborra de `RoomTypes` els tipus d'habitació que no tenen cap habitació a `Rooms` i cap reserva a `Bookings` (amb `NO ACTION`, un tipus amb habitacions o reserves faria fallar la sentència sencera; per això s'han de filtrar). Reflexiona: quines files de `PriceSeasons` i `RoomTypeFacilities` desapareixen també, i per què?

Referència:
```sql
DELETE FROM RoomTypes WHERE NOT EXISTS (SELECT 1 FROM Rooms r WHERE r.RoomTypeId = RoomTypes.Id) AND NOT EXISTS (SELECT 1 FROM Bookings b WHERE b.RoomTypeId = RoomTypes.Id)
```
Alternativa (passa, esperat: passa):
```sql
DELETE FROM RoomTypes WHERE Id NOT IN (SELECT RoomTypeId FROM Rooms) AND Id NOT IN (SELECT RoomTypeId FROM Bookings)
```
Alternativa (passa, esperat: passa):
```sql
DELETE t FROM RoomTypes t LEFT JOIN Rooms r ON r.RoomTypeId = t.Id LEFT JOIN Bookings b ON b.RoomTypeId = t.Id WHERE r.RoomNumber IS NULL AND b.Id IS NULL
```
Incorrecta (falla (The database's final content does not match what was expected after running your statement.), esperat: falla):
```sql
DELETE FROM RoomTypeFacilities WHERE RoomTypeId NOT IN (SELECT RoomTypeId FROM Rooms)
```
Incorrecta (falla (The database's final content does not match what was expected after running your statement.), esperat: falla):
```sql
DELETE FROM PriceSeasons WHERE RoomTypeId NOT IN (SELECT RoomTypeId FROM Rooms)
```

### 8. Esborra de `Bookings` les reserves en estat `Cancelled` fetes (`ReservationDateTime`) abans de l'1 d'abril de 2021 per clients de nacionalitat `English`. Fes-ho amb un `DELETE` multitaula: `DELETE b FROM Bookings b JOIN Customers c ON ...` (els clients no s'esborren).

Referència:
```sql
DELETE b FROM Bookings b JOIN Customers c ON c.Id = b.CustomerId WHERE c.Nationality = 'English' AND b.State = 'Cancelled' AND b.ReservationDateTime < '2021-04-01'
```
Alternativa (passa, esperat: passa):
```sql
DELETE FROM Bookings WHERE State = 'Cancelled' AND ReservationDateTime < '2021-04-01 00:00:00' AND CustomerId IN (SELECT Id FROM Customers WHERE Nationality = 'English')
```
Incorrecta (falla (The database's final content does not match what was expected after running your statement.), esperat: falla):
```sql
DELETE b FROM Bookings b JOIN Customers c ON c.Id = b.CustomerId WHERE c.Nationality = 'English' AND b.State = 'Cancelled' AND b.CheckIn < '2021-04-01'
```
Incorrecta (falla (The database's final content does not match what was expected after running your statement.), esperat: falla):
```sql
DELETE b FROM Bookings b JOIN Customers c ON c.Id = b.CustomerId WHERE c.Nationality = 'English' AND b.State = 'Cancelled' AND b.ReservationDateTime <= '2021-03-01'
```

### 9. Es retiren les tarifes de 2024 més barates: esborra de `PriceSeasons` les files de les temporades que comencen l'any 2024 (`Seasons.StartingDay`) el preu de les quals és inferior a la mitjana de **tots** els preus del mateix tipus d'habitació (de totes les temporades de tots els anys, calculada abans d'esborrar res). Fes-ho amb un `DELETE` multitaula contra una taula derivada amb `GROUP BY RoomTypeId`.

Referència:
```sql
DELETE p FROM PriceSeasons p JOIN Seasons s ON s.Id = p.SeasonId JOIN (SELECT RoomTypeId, AVG(Price) AS m FROM PriceSeasons GROUP BY RoomTypeId) t ON t.RoomTypeId = p.RoomTypeId WHERE YEAR(s.StartingDay) = 2024 AND p.Price < t.m
```
Alternativa (passa, esperat: passa):
```sql
DELETE FROM PriceSeasons WHERE SeasonId IN (SELECT Id FROM Seasons WHERE StartingDay BETWEEN '2024-01-01' AND '2024-12-31') AND Price < (SELECT m FROM (SELECT RoomTypeId, AVG(Price) AS m FROM PriceSeasons GROUP BY RoomTypeId) a WHERE a.RoomTypeId = PriceSeasons.RoomTypeId)
```
Alternativa (passa, esperat: passa):
```sql
DELETE FROM PriceSeasons WHERE SeasonId IN (SELECT Id FROM Seasons WHERE Name LIKE '% 2024') AND Price < (SELECT AVG(p2.Price) FROM PriceSeasons p2 WHERE p2.RoomTypeId = PriceSeasons.RoomTypeId)
```
Incorrecta (falla (The database's final content does not match what was expected after running your statement.), esperat: falla):
```sql
DELETE p FROM PriceSeasons p JOIN Seasons s ON s.Id = p.SeasonId JOIN (SELECT RoomTypeId, AVG(Price) AS m FROM PriceSeasons p2 JOIN Seasons s2 ON s2.Id = p2.SeasonId WHERE YEAR(s2.StartingDay) = 2024 GROUP BY RoomTypeId) t ON t.RoomTypeId = p.RoomTypeId WHERE YEAR(s.StartingDay) = 2024 AND p.Price < t.m
```
Incorrecta (falla (The database's final content does not match what was expected after running your statement.), esperat: falla):
```sql
DELETE p FROM PriceSeasons p JOIN (SELECT RoomTypeId, AVG(Price) AS m FROM PriceSeasons GROUP BY RoomTypeId) t ON t.RoomTypeId = p.RoomTypeId WHERE p.Price < t.m
```

### 10. Esborra de `Facilities` les instal·lacions que només té un únic tipus d'habitació a `RoomTypeFacilities` (exactament un). Calcula-les amb `GROUP BY` i `HAVING` en una subconsulta. Reflexiona: què passa amb les files de `RoomTypeFacilities` que les referenciaven?

Referència:
```sql
DELETE FROM Facilities WHERE Id IN (SELECT FacilityId FROM RoomTypeFacilities GROUP BY FacilityId HAVING COUNT(*) = 1)
```
Alternativa (passa, esperat: passa):
```sql
DELETE f FROM Facilities f JOIN (SELECT FacilityId FROM RoomTypeFacilities GROUP BY FacilityId HAVING COUNT(RoomTypeId) < 2) t ON t.FacilityId = f.Id
```
Alternativa (passa, esperat: passa):
```sql
DELETE FROM Facilities WHERE (SELECT COUNT(*) FROM RoomTypeFacilities rf WHERE rf.FacilityId = Facilities.Id) = 1
```
Incorrecta (falla (The database's final content does not match what was expected after running your statement.), esperat: falla):
```sql
DELETE FROM Facilities WHERE Id IN (SELECT FacilityId FROM RoomTypeFacilities GROUP BY FacilityId HAVING COUNT(*) <= 2)
```
Incorrecta (falla (The database's final content does not match what was expected after running your statement.), esperat: falla):
```sql
DELETE FROM RoomTypeFacilities WHERE FacilityId IN (SELECT FacilityId FROM (SELECT FacilityId FROM RoomTypeFacilities GROUP BY FacilityId HAVING COUNT(*) = 1) t)
```
