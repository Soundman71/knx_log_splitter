**Teilt KNX-Telegramme aus einer Logdatei eines GIRA-KNX/IP-Router in zwei XML-Dateien auf (nach Gruppenadresse, nur Haupt- und Mittelgruppe!).**

Hintergrund ist der, dass die ETS nur sehr eingeschränkte Filterfunktionen im Gruppenmonitor hat.

Das kleine Tool splittet die Eingangsdatei in 2 Dateielen auf:
* knx_[GA].xml: enthält alles, was den angegebenen Gruppenadressen entspricht.
* knx_tel.xml : enthält alles, was NICHT den angegebenen Gruppenadressen entspricht.

*Bei der Gruppenadresse wird nur die Haupt- und Mittelgruppe berücksichtigt!*

Die erzeugten Dateien kann man dann in der ETS in den Gruppenmonitor laden und einfacher analysieren.

Bei mir laufen relative viele Energiemessewerte über den Bus, diese sind unter der GA 0/7/x erfasst.
Diese filtere ich mir damit erst mal raus und schaue dann, was in bestimmten Situationen los war. 
Dafür reicht mir dann i.d.R die Filtermöglichkeit der ETS.

Verwendet Python 3.12

Aufruf: python knx_log_splitter.py
```
usage: knx_log_splitter.py [-h] [--group-address GROUP_ADDRESS] [-g1 GROUP_ADDRESS1] [-g2 GROUP_ADDRESS2] [-g3 GROUP_ADDRESS3] [-g4 GROUP_ADDRESS4] [-g5 GROUP_ADDRESS5]
                           [-g6 GROUP_ADDRESS6] [-g7 GROUP_ADDRESS7] [-g8 GROUP_ADDRESS8] [-g9 GROUP_ADDRESS9] [--verbose] [--discard-others]
                           input_file


positional arguments:
  input_file            Pfad zur XML-Datei mit den KNX-Telegrammen

options:
  -h, --help            show this help message and exit
  --group-address GROUP_ADDRESS, -g GROUP_ADDRESS
                        Gruppenadresse zum Filtern (z.B. 0/7/). Standard: 0/7/
  -g1 GROUP_ADDRESS1
  -g2 GROUP_ADDRESS2
  -g3 GROUP_ADDRESS3
  -g4 GROUP_ADDRESS4
  -g5 GROUP_ADDRESS5
  -g6 GROUP_ADDRESS6
  -g7 GROUP_ADDRESS7
  -g8 GROUP_ADDRESS8
  -g9 GROUP_ADDRESS9
  --verbose, -v         Zeigt detaillierte Debug-Ausgaben an
  --discard-others      Verwirft alle nicht zur Filteradresse passenden Telegramme (keine knx_tel.xml Ausgabe)
```


Beispiel 1:
```
python knx_log_splitter.py 2025_09_29_TP1.xml
...........................................................................................................................................................................
XML-Datei erfolgreich eingelesen (171017 Zeilen).

Verarbeite 171014 Telegramme...
Verarbeite Telegramme: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████| 171014/171014 [00:00<00:00, 305569.12it/s]

Telegramme mit Gruppenadresse 0/7/ wurden in knx_tel_0_7.xml gespeichert
Anzahl der Telegramme: 124914

Andere Telegramme wurden in knx_tel.xml gespeichert
Anzahl der Telegramme: 46100
```

Beispiel 2:
```
python knx_log_splitter.py 2025_09_29_TP1.xml -g 0/7/ -g1 2/1/
...........................................................................................................................................................................
XML-Datei erfolgreich eingelesen (171017 Zeilen).

Verarbeite 171014 Telegramme...
Verarbeite Telegramme: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████| 171014/171014 [00:00<00:00, 306196.42it/s]

Telegramme mit Gruppenadresse 0/7/, 2/1/ wurden in knx_tel_0_7-2_1.xml gespeichert
Anzahl der Telegramme: 125042

Andere Telegramme wurden in knx_tel.xml gespeichert
Anzahl der Telegramme: 45972
```
