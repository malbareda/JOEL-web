# JOEL — Jutge Online Educatiu Lliure

**JOEL** és una plataforma per aprendre a programar, un repositori de problemes, i un sistema per
fer córrer concursos de programació. Va néixer per ajudar telemàticament a l'ensenyament de
Programació a l'Institut Sabadell arran de la pandèmia de Covid-19, però està obert a qualsevol
institut o persona que vulgui aprendre a programar pel seu compte.

Veure'l en viu a **[jo-el.es](https://jo-el.es)**.

JOEL corre sobre **JODER** (Jutge Online Destinat a l'Ensenyament amb Retroacció), un fork molt
divergent de [DMOJ](https://github.com/DMOJ), el jutge online competitiu de codi obert, adaptat per
complir una funció educativa en lloc de purament competitiva.

## Què el fa diferent d'un jutge competitiu normal

* **Educatiu, no competitiu.** Els problemes tenen etiquetatge per saber quins coneixements calen
  per resoldre'ls, i en comptes de valorar-se amb un simple correcte/incorrecte, donen una nota
  parcial segons els casos de prova superats, per no desanimar a qui intenta un problema difícil.
* **Sistema de pistes instantani**: si un enviament falla, es pot demanar una pista sobre quin cas
  concret està fallant, sense recarregar la pàgina.
* **Guies per a problemes d'introducció**: els problemes pensats per començar cada tema tenen una
  guia d'ajuda pròpia, adaptada tant a l'idioma com al llenguatge de programació que es faci servir.
* **Mode Bases de Dades**: a més de programar, es pot practicar SQL i MongoDB amb problemes propis
  (checkers fets a mida, explorador d'esquema visual, i un rànquing separat del de programació).
* **Sistema d'Instituts**: cada institut té la seva pròpia pàgina pública, separada dels equips o
  classes que en formen part, amb bandera i nom propis a les llistes i concursos.
* **Concursos configurables**: congelació del marcador, colors de "first blood", comptador
  d'intents incorrectes per problema, i "concurs en grups" (l'alumnat tria un nom d'equip en lloc
  del nom d'usuari a la classificació).
* **Sistema de personalització (Gacha)**: stickers, icones i temes visuals que es desbloquegen
  jugant, amb un bonus diari pel primer problema nou resolt cada dia.
* **Traduccions completes**: problemes, guies, notícies i pàgines estàtiques es poden traduir per
  idioma (català, castellà, anglès, alemany, i parcialment xinès), amb selecció automàtica segons
  l'idioma de qui llegeix.
* **Generació de PDF** dels enunciats, per a qui prefereixi imprimir-los o treballar sense
  connexió.
* **Dos jutges de correcció en paral·lel**, per aprofitar millor els recursos del servidor durant
  moments de molta afluència (per exemple, durant la Lliga de Programació).
* **Sense dependències externes de CDN**: MathJax i totes les llibreries de tercers estan
  allotjades al propi servidor.

## Documentació

Aquest projecte té documentació tècnica exhaustiva, escrita sencera en català, pensada per a
qualsevol persona amb accés al codi —professorat, alumnat avançat, o qui hagi de mantenir el
projecte en el futur:

* **[docs/](docs/README.md)** — arquitectura, cada sistema explicat de dalt a baix, el flux intern
  d'un enviament, particularitats de la programació del projecte, i els sistemes mecànics
  (comunicació amb el jutge, base de dades, checkers de SQL i Mongo...).
* **[CANVIS_I_MILLORES.md](CANVIS_I_MILLORES.md)** — registre cronològic de cada canvi tècnic
  rellevant fet al servidor i al codi: què estava abans, què es va decidir fer, per què, i quin és
  el resultat final.

## Basat en DMOJ

JOEL/JODER és un fork de [DMOJ: Modern Online Judge](https://github.com/DMOJ), un jutge online
competitiu de codi obert que ha allotjat centenars de concursos, incloent-hi diverses olimpíades
nacionals. Es manté sota la mateixa llicència que el projecte original, la [GNU AGPL
v3](LICENSE).
