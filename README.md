emwsmd - Ey Mann, wo sind meine Drohnen!
Version 3.2.0 Beta
===========================================




         !!!  WICHTIGES VORWEG  !!!
  !!!  GIB NIEMALS DEN TOKENCACHE WEITER  !!!




Was macht dieses Tool?
-----------------------
emwsmd zaehlt ALLE deine Drohnen in EVE Online (egal ob Civilian, Mining,
Salvage, Combat oder Heavy Sentry) und zeigt dir:

  - Wie viele Drohnen du insgesamt hast (nach Name gruppiert)
  - An welcher Station/Struktur sie liegen
  - Wie viel Transportvolumen du fuer den Abtransport brauchst

Das Ergebnis bekommst du als huebschen HTML-Bericht ("emwsmd Drohnenbericht"),
den du einfach im Browser oeffnen kannst.

===========================================
SCHRITT 1: emwsmd.exe zum ersten Mal starten
===========================================

1. Entpacke die ZIP-Datei in einen Ordner deiner Wahl (z.B. Desktop).
2. Doppelklicke auf "emwsmd.exe".
3. Es oeffnet sich ein schwarzes Konsolenfenster. Das ist normal!
4. Es oeffnet sich automatisch dein Browser mit der Login-Seite.
5. Logge dich mit dem Charakter ein, dessen Drohnen du zaehlen willst.
6. Klicke auf "Autorisieren" / "Authorize".
7. Der Browser zeigt "Autorisierung erfolgreich" - das Fenster kannst
   du jetzt schliessen.
8. Zurueck im Konsolenfenster siehst du die Drohnen-Auswertung.
9. Im selben Ordner liegt jetzt eine Datei:
       emwsmd_drohnenbericht.html
   Doppelklicke sie - sie oeffnet sich in deinem Browser mit einer
   schoenen Tabelle.

===========================================
SCHRITT 2: Spaetere Nutzung
===========================================

Ab jetzt reicht ein einfacher Doppelklick auf "emwsmd.exe" - das Tool
loggt sich automatisch mit dem gespeicherten Zugang ein und erstellt
sofort den aktuellen Bericht. Kein erneutes Eintippen von Zugangsdaten
oder Passwoertern notwendig.

Falls dein Login mal abgelaufen ist (z.B. nach sehr langer Pause),
oeffnet emwsmd automatisch wieder den Browser zum erneuten Einloggen -
du musst nichts extra tun.

===========================================
Der Bericht: Was bedeuten die zwei Tabellen?
===========================================

1. "Drohnen nach Name" (steht direkt offen)
   Zeigt jede Drohnenart einzeln mit Anzahl und Volumen.

2. Button "Transport-Uebersicht pro Station anzeigen/verstecken"
   Zeigt dir pro Station: Anzahl Drohnen + Gesamtvolumen.
   Das brauchst du, um zu wissen, wie viel Frachtraum du fuer den
   Abtransport von jeder Station einplanen musst.

===========================================
Verknuepfung auf dem Desktop erstellen (optional)
===========================================

1. Rechtsklick auf "emwsmd.exe" -> "Verknuepfung erstellen".
2. Verschiebe die Verknuepfung z.B. auf den Desktop.
3. Fertig - Doppelklick auf die Verknuepfung startet das Tool.

Wenn du eine ZWEITE Verknuepfung fuer einen erneuten Login brauchst
(z.B. um einen anderen Charakter zu hinterlegen):

1. Rechtsklick auf die Verknuepfung -> "Eigenschaften".
2. Im Feld "Ziel" nach dem Pfad ein Leerzeichen und "install" anhaengen, z.B.:
       "C:\Pfad\zu\emwsmd.exe" install
3. Diese Verknuepfung startet dann immer den Login-Vorgang neu.

===========================================
Haeufige Probleme
===========================================

- "Es tut sich nichts nach dem Login im Browser":
  Schlieﬂe das Browserfenster erst, wenn dort steht, dass die Autorisierung
  erfolgreich war.

- "Windows Defender / SmartScreen blockiert die exe":
  Klicke auf "Weitere Informationen" und dann "Trotzdem ausfuehren".
  Das passiert bei selbst erstellten .exe-Dateien ohne Code-Signatur,
  ist aber unbedenklich, wenn du dem Ersteller vertraust.

- "Ich will nochmal von Null anfangen (alles zuruecksetzen)":
  Loesche einfach die Datei "config.ini" im selben Ordner und starte
  emwsmd.exe erneut - dann beginnt der Login wieder von vorne.

===========================================
Systemvoraussetzungen
===========================================

- Windows 10 oder Windows 11 (64-bit)
- Internetverbindung
- Ein EVE Online Account mit mindestens einem Charakter

Kompatibel getestet fuer Windows 10 und Windows 11.

===========================================
Kontakt / Support
===========================================

Bei Problemen: Screenshot vom Konsolenfenster machen und an den
Ersteller des Tools schicken.

Viel Spass beim Drohnen-Zaehlen!
