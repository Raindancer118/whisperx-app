Die WhisperX-App, die hier entwickelt werden soll, soll eine native Python-CLI-Applikation sein, die es ermöglicht, OpenAI's Whisper auf einem beliebigen PC oder Server schnell aufzusetzen und schnell laufen zu lassen. Hierfür ist folgende Idee angedacht: 
1. WhisperX-App wird installiert
2. App wird über Kommandozeile gestartet
3. App prüft ob aktuelles WhisperX-Modell installiert ist -> Wenn nein: Bietet Download eines aktuellen Modelles an, installiert dieses im Hintergrund (mit echtem Ladebalken) und zeigt anschließend einen Bildschirm an, wo eine beliebige Datei ausgewählt werden kann. Am Liebsten wäre mir, wenn dies über Drag- & Drop in die Kommandozeile möglich wäre.
4. Die Applikation sollte selbstständig feststellen, ob eine GPU installiert ist oder nicht, wenn ja, sollte sie den Nutzer fragen, ob diese verwendet werden soll oder CPU-only. Es soll bitte eine Zeitschätzung für die Datei abgegeben werden. 
5. Der Nutzer sollte angeben können, wo die Ergebnis-Datei abgelegt werden soll, oder ob das Ergebnis nur im Chat gezeigt werden soll.
6. Es soll zwischen Sprechern unterschieden werden können, und diese Unterscheidung muss extrem akkurat sein.
7. Die Applikation soll bitte APIs haben, sodass über ein Web-Projekt darauf zugegriffen werden kann.