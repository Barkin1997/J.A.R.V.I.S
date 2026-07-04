JARVIS-ANREDE PFLICHT

Diese Version führt Befehle nur aus, wenn sie mit Jarvis beginnen.

Richtig:

Jarvis, suche auf Google RTX 5080
Jarvis, lies meinen Bildschirm
Jarvis, erstelle Projekt in C++ Taschenrechner
Jarvis, erstelle KI Bild orange Roboter
Jarvis, stopp

Auch bei Bestätigung:

BESTÄTIGE Jarvis, lösche Datei ...

Falsch:

suche auf Google RTX 5080
lies meinen Bildschirm
stopp

Diese Befehle werden ignoriert.

Einstellung in .env:

REQUIRE_WAKE_WORD=1
WAKE_WORD=jarvis

Wenn du die Pflicht ausschalten willst:

REQUIRE_WAKE_WORD=0
