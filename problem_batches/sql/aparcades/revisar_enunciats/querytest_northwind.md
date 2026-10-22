# northwind — enunciats a revisar


## Northwind QT — Consultes intermèdies
- Complexitat molt alta i específic de MySQL (WITH, SUBSTRING_INDEX, LOCATE). Valora si el deixes en un problema avançat o el treus.
  Enunciat generat: Mostra l'identificador del proveïdor (`supplier_id`) i el nombre de comandes (`total_orders`) dels proveïdors que han subministrat productes venuts en més de 8 comandes. Nota: a `products` el camp `supplier_ids` guarda els identificadors de proveïdor separats per `;`.

## Northwind QT — Examen fusionat 1
- Enunciat RECONSTRUÏT des del SQL (a QueryTest només hi havia el títol «Pregunta 05. Enviament lent»).
  Enunciat generat: Mostra l'`id`, la data de comanda (`order_date`) i la data d'enviament (`shipped_date`) de les comandes (`orders`) que han trigat més de 2 dies a enviar-se. Si una comanda encara no s'ha enviat, compta els dies des de la data de comanda fins avui. Ordena per data de comanda de més recent a més antiga i, en cas d'empat, per `id`.
- Enunciat RECONSTRUÏT des del SQL («Pregunta 06. Coincidències geogràfiques»).
  Enunciat generat: Mostra els casos en què un client i un empleat viuen a la mateixa ciutat (`city`) i estat (`state_province`). De cada cas, mostra el nom i cognom del client i el nom i cognom de l'empleat (distingint-los clarament), la ciutat i l'estat.
- Enunciat RECONSTRUÏT des del SQL («Pregunta 03. I la factura?»).
  Enunciat generat: Mostra l'`id` i la data (`order_date`) de les comandes fetes durant l'abril de 2006 per a les quals no s'ha emès cap factura (taula `invoices`).
- Enunciat RECONSTRUÏT des del SQL («Pregunta 09. Client misteriós»).
  Enunciat generat: El client que va fer la comanda amb `id` 39 ens interessa: mostra el seu nom (`first_name`), cognom (`last_name`) i, de totes les seves comandes, l'`id` i la data (`order_date`), ordenades de més recent a més antiga.
- Enunciat RECONSTRUÏT des del SQL («Pregunta 10. Millors dies de l'any»).
  Enunciat generat: Mostra els 2 dies de l'any 2006 en què s'han venut més productes en total. De cada dia, mostra la data (sense hora) i la suma de quantitats (`quantity`). Ordena de més a menys productes venuts.
- Enunciat RECONSTRUÏT des del SQL («Pregunta 01. Nyoquis»).
  Enunciat generat: Mostra el nom (`first_name`) i el cognom (`last_name`), sense repeticions, dels clients que han comprat alguna vegada el producte anomenat 'Northwind Traders Gnocchi'. Ordena per cognom i, en empat, per nom.

## Northwind QT — Examen fusionat 2
- Enunciat RECONSTRUÏT des del SQL («Pregunta 02. Ventes»).
  Enunciat generat: Mostra el codi (`product_code`), el nom (`product_name`) i les unitats venudes (`sold_units`, suma de `quantity`) de tots els productes. Si un producte no s'ha venut mai, ha de sortir amb 0 unitats. Ordena per codi de producte.
- Enunciat RECONSTRUÏT des del SQL («Pregunta 08. Empreses d'enviament»).
  Enunciat generat: Mostra el nom de l'empresa transportista (`company`) i el nombre d'enviaments (`n_shipments`) de les transportistes que han fet més d'un enviament amb data d'enviament entre el 20 d'abril i el 20 de maig de 2006. Ordena pel nom de l'empresa.
- Enunciat RECONSTRUÏT des del SQL («Pregunta 04. Clients poc habituals»).
  Enunciat generat: Mostra el nom (`first_name`), el cognom (`last_name`) i el nombre de comandes (`n_orders`) dels clients que han fet 3 comandes o menys. Inclou també els clients que no n'han fet cap.
- Enunciat RECONSTRUÏT des del SQL («Pregunta 07. Fucking money man»).
  Enunciat generat: Per a cada producte, mostra el seu `id`, el nom (`product_name`), el cost total de compra (`cost`, suma de `quantity * unit_cost` a `purchase_order_details`), el benefici brut de venda (`benefit`, suma de `quantity * unit_price - discount` a `order_details`) i el benefici net (`net_benefit`, benefici menys cost). Mostra només els productes amb benefici net positiu i ordena'ls de més a menys benefici net.