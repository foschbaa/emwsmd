emwsmd - Ey Mann, wo sind meine Drohnen!
Version 3.2.0 GUI Beta
===========================================



         !!!  WICHTIGES VORWEG  !!!
  !!!  GIB NIEMALS DEN TOKENCACHE WEITER  !!!


Was macht diese GUI-Version?
----------------------------
 emwsmd zaehlt ALLE deine Drohnen in EVE Online (egal ob Civilian, Mining,
 Salvage, Combat oder Heavy Sentry) und zeigt dir:

  - Wie viele Drohnen du insgesamt hast (nach Name gruppiert)
  - An welcher Station/Struktur sie liegen
  - Wie viel Transportvolumen du fuer den Abtransport brauchst

Die GUI-Version erledigt genau diesen Ablauf in einer einfachen grafischen
Oberflaeche statt ueber die Konsole.

===========================================
SCHRITT 1: GUI-Datei zum ersten Mal starten
===========================================

1. Entpacke die ZIP-Datei in einen Ordner deiner Wahl (z.B. Desktop).
2. Doppelklicke auf "emwsmd-gui.exe" unter Windows oder auf "emwsmd-gui"
   unter macOS/Linux.
3. Es oeffnet sich das GUI-Fenster.
4. Es oeffnet sich automatisch dein Browser mit der Login-Seite.
5. Logge dich mit dem Charakter ein, dessen Drohnen du zaehlen willst.
6. Klicke auf "Autorisieren" / "Authorize".
7. Der Browser zeigt "Autorisierung erfolgreich" - das Fenster kannst
   du jetzt schliessen.
8. Zurueck in der GUI siehst du die Drohnen-Auswertung.
9. Im selben Ordner liegt jetzt eine Datei:
       emwsmd_drohnenbericht.html

===========================================
SCHRITT 2: Aus dem Quellcode starten
===========================================

Falls du die GUI direkt aus dem Repository starten möchtest:

1. Erstelle oder aktiviere ein virtuelles Python-Environment.
2. Installiere die Abhaengigkeiten:
       pip install -r requirements_gui.txt
3. Starte die GUI mit:
       python emwsmd_gui.py

Hinweise:
- Die GUI nutzt dieselbe Auth- und Auswertungslogik wie die CLI-Version.
- Der erzeugte HTML-Bericht ist derselbe wie bei der Konsolen-Version.
- Die Datei "tokencache" speichert deine Login-Daten lokal fuer den
  naechsten Start.


