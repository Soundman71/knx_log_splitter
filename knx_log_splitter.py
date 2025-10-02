#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import xmltodict
import argparse
from typing import List
from tqdm import tqdm

def extract_group_address(rawdata: str, verbose: bool = False) -> str:
    """
    Extrahiert die Gruppenadresse im Format Haupt/Mittel/Untergruppe aus dem RawData-String.
    Die ersten 11 Bytes (22 Zeichen) sind der Header, danach kommt ein BC-Byte (Priorität),
    dann die Quelladresse (2 Bytes) und dann die Zieladresse (2 Bytes).
    Telegramme mit CC am Ende sind Bestätigungen und werden ignoriert.
    """
    try:
        # Kurze Bestätigungs-Telegramme (ACK) bestehen nur aus wenigen Bytes und
        # tragen keine Ziel-Gruppenadresse. Diese werden hier herausgefiltert.
        # Ignoriere Bestätigungen (nur kurze ACK-Frames, z.B. 12 Bytes = 24 Hex-Zeichen)
        if rawdata.endswith("CC") and len(rawdata) <= 24:
            if verbose:
                print(f"Ignoriere Bestätigung: {rawdata}")
            return "IGNORE"
            
        # Telegramme, die noch nicht lang genug sind, um Quell- und Zieladresse zu tragen,
        # werden als "IGNORE" klassifiziert.
        # Ignoriere zu kurze Telegramme (muss mindestens Header + BC + 4 Bytes Adressen haben)
        if len(rawdata) < 28:  # 22 (Header) + 2 (BC) + 4 (Adressen)
            if verbose:
                print(f"Ignoriere kurzes Telegramm: {rawdata}")
            return "IGNORE"
            
        # Nach dem Header (11 Bytes = 22 Zeichen) und BC (1 Byte = 2 Zeichen)
        # kommt die Quelladresse (2 Bytes), dann die Zieladresse (2 Bytes)
        ziel_start = 28  # 22 (Header) + 2 (BC) + 4 (Quelladresse)
        if len(rawdata) < ziel_start + 4:  # Prüfe, ob genug Bytes für die Zieladresse da sind
            if verbose:
                print(f"Telegramm zu kurz für Zieladresse: {rawdata}")
            return "IGNORE"
            
        byte1 = int(rawdata[ziel_start:ziel_start+2], 16)
        byte2 = int(rawdata[ziel_start+2:ziel_start+4], 16)
        
        # Debug-Ausgabe nur im verbose Modus
        if verbose:
            print(f"Nach Header+BC+Quell: {rawdata[ziel_start:ziel_start+4]} (Bytes: {byte1:02X} {byte2:02X})")
        
        # Gruppenadresse berechnen:
        # Hauptgruppe: obere 4 Bit von byte1
        # Mittelgruppe: untere 4 Bit von byte1
        # Untergruppe: byte2
        haupt = (byte1 & 0xF0) >> 4
        mittel = (byte1 & 0x0F)
        unter = byte2
        
        result = f"{haupt}/{mittel}/{unter}"
        if verbose:
            print(f"Berechnete Adresse: {result}")
        return result
    except Exception as e:
        if verbose:
            print(f"Fehler bei der Extraktion: {e}")
        return ""

class KNXSplitter:
    def __init__(self, input_file: str, group_addresses: List[str], verbose: bool = False, discard_others: bool = False):
        """Initialisiert den KNX-Splitter mit der Eingabedatei und der zu filternden Gruppenadresse."""
        self.input_file = input_file
        # Normalisiere und speichere alle Filter-Adressen (Suffix mit '/') sicherstellen
        self.filter_list = []
        for ga in group_addresses:
            if not ga:
                continue
            ga_norm = ga if ga.endswith('/') else ga + '/'
            self.filter_list.append(ga_norm)
        self.verbose = verbose
        self.discard_others = discard_others
        self.xml_data = None
        
        # Erstelle den Dateinamen aus der Gruppenadresse
        # Ersetze / durch _ und entferne führende/nachfolgende _
        parts = [ga.replace('/', '_').strip('_') for ga in self.filter_list]
        joined = '-'.join(parts) if parts else 'all'
        self.output_filename = f"knx_tel_{joined}.xml"
        self.other_filename = "knx_tel.xml"
        
    @staticmethod
    def get_physical_address(rawdata: str) -> str:
        """
        Extrahiert die physikalische Quelladresse im Format Haupt.Linie.Teilnehmer aus dem RawData-String.
        Die ersten 11 Bytes (22 Zeichen) sind der Header, dann kommt ein BC-Byte (Priorität),
        danach die Quelladresse (2 Bytes).
        Telegramme mit CC am Ende sind Bestätigungen und werden ignoriert.
        """
        try:
            # Ignoriere Bestätigungen (CC am Ende)
            if rawdata.endswith("CC"):
                return ""
                
            # Ignoriere zu kurze Telegramme
            if len(rawdata) < 26:  # 22 (Header) + 2 (BC) + 2 (Quelladresse)
                return ""
                
            # Nach dem Header (11 Bytes = 22 Zeichen) und BC (1 Byte = 2 Zeichen)
            # kommt die Quelladresse (2 Bytes)
            quell_start = 24  # 22 (Header) + 2 (BC)
            byte1 = int(rawdata[quell_start:quell_start+2], 16)
            byte2 = int(rawdata[quell_start+2:quell_start+4], 16)
            
            # Quelladresse berechnen:
            # Hauptgruppe: obere 4 Bit von byte1
            # Linie: untere 4 Bit von byte1
            # Teilnehmer: byte2
            haupt = (byte1 & 0xF0) >> 4
            linie = (byte1 & 0x0F)
            teilnehmer = byte2
            
            return f"{haupt}.{linie}.{teilnehmer}"
        except Exception:
            return ""

    def read_xml(self) -> None:
        """Liest die XML-Datei ein."""
        try:
            # Schritt 1: Anzahl Zeilen ermitteln, damit bei sehr großen Dateien ein grober
            # Fortschritt (ein Punkt je 1000 Zeilen) angezeigt werden kann.
            total_lines = 0
            with open(self.input_file, 'r', encoding='utf-8') as file:
                for _ in file:
                    total_lines += 1
                    if total_lines % 1000 == 0:
                        print(".", end="", flush=True)
            print()  # Neue Zeile nach dem Fortschrittsbalken

            # Schritt 2: Datei vollständig einlesen und per xmltodict parsen.
            with open(self.input_file, 'r', encoding='utf-8') as file:
                content = file.read()
                if self.verbose:
                    print(f"XML-Inhalt (erste 200 Zeichen): {content[:200]}")
                self.xml_data = xmltodict.parse(content)
            print(f"XML-Datei erfolgreich eingelesen ({total_lines} Zeilen).")
            
            # Optional: erste Telegramme zeigen (nur im verbose Modus)
            if self.verbose and 'CommunicationLog' in self.xml_data and 'Telegram' in self.xml_data['CommunicationLog']:
                telegrams = self.xml_data['CommunicationLog']['Telegram']
                if not isinstance(telegrams, list):
                    telegrams = [telegrams]
                print("\nErste 3 Telegramme:")
                for i, t in enumerate(telegrams[:3]):
                    print(f"Telegramm {i+1}: {t.get('@RawData', '')}")
        except Exception as e:
            print(f"Fehler beim Lesen der XML-Datei: {e}")
            sys.exit(1)

    def split_and_save(self) -> None:
        """Teilt die Telegramme und speichert sie in zwei separate XML-Dateien mit Adress-Kommentar nach dem selbstschließenden Telegram-Tag."""
        if self.xml_data is None:
            raise ValueError("Keine Daten geladen. Bitte zuerst read_xml() aufrufen.")

        # Sammler für beide Ausgaben aufbauen
        filtered_telegrams = []
        other_telegrams = []
        filtered_comments = []
        other_comments = []

        telegrams: List[dict] = []
        if 'CommunicationLog' in self.xml_data and 'Telegram' in self.xml_data['CommunicationLog']:
            telegrams = self.xml_data['CommunicationLog']['Telegram']
            if not isinstance(telegrams, list):
                telegrams = [telegrams]

        print(f"\nVerarbeite {len(telegrams)} Telegramme...")
        if self.verbose:
            print(f"Filtere nach Gruppenadresse(n): {', '.join(self.filter_list)}")
        
        # Fortschrittsbalken für die Verarbeitung
        # last_effective_ga: letzter ermittelter GA-Kontext für Nicht-ACK-Telegramme
        # last_destination: wohin der letzte Datensatz geschrieben wurde ('filtered' | 'other')
        last_effective_ga: str | None = None
        last_destination: str | None = None  # 'filtered' | 'other'
        for idx in tqdm(range(0, len(telegrams)), desc="Verarbeite Telegramme"):
            telegram = telegrams[idx]
            rawdata = telegram.get('@RawData', '')
            if not rawdata:
                continue

            # ACK-Frames sind kurz (z.B. 12 Bytes = 24 Hex-Zeichen) und enden mit CC
            is_ack = rawdata.endswith('CC') and len(rawdata) <= 24

            if is_ack:
                # Bestätigung folgt der letzten Zielentscheidung
                if last_destination == 'other':
                    other_telegrams.append(telegram)
                    other_comments.append("")
                else:
                    # Standard/Fallback: gefilterte Datei
                    filtered_telegrams.append(telegram)
                    filtered_comments.append("")
                continue

            # Nicht-ACK → GA regulär ermitteln
            group_address = extract_group_address(rawdata, self.verbose)
            if group_address == "IGNORE" or group_address == "":
                # Kein sinnvolles GA ermittelbar → IM ZWEIFEL zur gefilterten Datei
                physical_address = KNXSplitter.get_physical_address(rawdata)
                ign_comment = f"<!-- GA: IGNORE (unbestimmt) ; QA: {physical_address} -->"
                filtered_telegrams.append(telegram)
                filtered_comments.append(ign_comment)
                last_destination = 'filtered'
                continue

            last_effective_ga = group_address

            physical_address = KNXSplitter.get_physical_address(rawdata)
            comment = f"<!-- GA: {group_address} ; QA: {physical_address} -->"

            if any(group_address.startswith(f) for f in self.filter_list):
                filtered_telegrams.append(telegram)
                filtered_comments.append(comment)
                if self.verbose:
                    print(f"Gefunden: {group_address}")
                last_destination = 'filtered'
            else:
                other_telegrams.append(telegram)
                other_comments.append(comment)
                last_destination = 'other'

        commlog_attrs = {k: v for k, v in self.xml_data['CommunicationLog'].items() if not k == 'Telegram'}
        filtered_data = {'CommunicationLog': {**commlog_attrs, 'Telegram': filtered_telegrams}}
        other_data = {'CommunicationLog': {**commlog_attrs, 'Telegram': other_telegrams}}

        def insert_comments(xml_path, comments):
            # Fügt Kommentare an jede Telegramm-Zeile an und richtet diese
            # gemäß Spaltenvorgaben aus (Kommentarbeginn Spalte 165, Semikolon Spalte 183).
            with open(xml_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            new_lines = []
            comment_idx = 0
            for line in lines:
                if '<Telegram' in line and '</Telegram>' in line:
                    # Entferne alle Tabs und führende Leerzeichen
                    line = line.lstrip()
                    # Extrahiere den Teil bis zum RawData-Attribut
                    parts = line.split('RawData="')
                    if len(parts) == 2:
                        rawdata_part = parts[1].split('"')[0]
                        # Erstelle die neue Zeile mit selbstschließendem Tag
                        telegram_part = f'{parts[0]}RawData="{rawdata_part}" />'
                        
                        # Nur wenn ein Kommentar vorhanden ist, füge ihn hinzu
                        if comment_idx < len(comments) and comments[comment_idx]:
                            # Füge Leerzeichen hinzu, bis Spalte 165 erreicht ist
                            # Berücksichtige die 4 Leerzeichen am Anfang
                            spaces_needed = 165 - (len(telegram_part) + 4)  # +4 für die Einrückung
                            if spaces_needed > 0:
                                telegram_part = telegram_part + ' ' * spaces_needed
                            
                            # Formatiere den Kommentar mit Semikolon in Spalte 183
                            comment = comments[comment_idx].replace('<!-- ', '')  # Entferne <!-- vom Anfang
                            ga_part = comment.split(';')[0].strip()  # Teil bis zum Semikolon, ohne Leerzeichen
                            qa_part = comment.split(';')[1].strip()  # Teil nach dem Semikolon, ohne Leerzeichen
                            
                            # Berechne die aktuelle Position nach dem Telegram-Tag und den Leerzeichen
                            current_pos = len(telegram_part) + 4  # +4 für die Einrückung
                            
                            # Berechne die Position des Semikolons
                            semicolon_pos = current_pos + 5 + len(ga_part)  # Position des Semikolons
                            spaces_before_semicolon = 183 - semicolon_pos  # Leerzeichen bis Spalte 183
                            
                            if spaces_before_semicolon > 0:
                                # Füge Leerzeichen nach ga_part hinzu
                                ga_part = ga_part + ' ' * spaces_before_semicolon
                                # Stelle sicher, dass das Semikolon in Spalte 183 steht
                                comment = f'<!-- {ga_part}; {qa_part}'
                                # Keine weitere Debug-Ausgabe
                            
                            line = f'    {telegram_part}{comment}\n'  # 4 Leerzeichen für die Einrückung
                        else:
                            # Wenn kein Kommentar vorhanden ist, nur das Telegramm ohne Leerzeichen
                            line = f'    {telegram_part}\n'  # 4 Leerzeichen für die Einrückung
                        comment_idx += 1
                new_lines.append(line)
            with open(xml_path, 'w', encoding='utf-8') as f:
                f.writelines(new_lines)

        try:
            # Speichere die gefilterten Telegramme
            with open(self.output_filename, 'w', encoding='utf-8') as file:
                xmltodict.unparse(filtered_data, output=file, pretty=True)
            insert_comments(self.output_filename, filtered_comments)
            print(f"\nTelegramme mit Gruppenadresse {', '.join(self.filter_list)} wurden in {self.output_filename} gespeichert")
            print(f"Anzahl der Telegramme: {len(filtered_telegrams)}")

            # Speichere die anderen Telegramme (immer zweite Datei erzeugen)
            with open(self.other_filename, 'w', encoding='utf-8') as file:
                xmltodict.unparse(other_data, output=file, pretty=True)
            insert_comments(self.other_filename, other_comments)
            print(f"\nAndere Telegramme wurden in {self.other_filename} gespeichert")
            print(f"Anzahl der Telegramme: {len(other_telegrams)}")

        except Exception as e:
            print(f"Fehler beim Speichern der Dateien: {e}")
            sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description='Teilt KNX-Telegramme in zwei XML-Dateien auf (nach Gruppenadresse in RawData).')
    parser.add_argument('input_file', help='Pfad zur XML-Datei mit den KNX-Telegrammen')
    parser.add_argument('--group-address', '-g', default='0/7/', 
                      help='Gruppenadresse zum Filtern (z.B. 0/7/). Standard: 0/7/')
    # Zusätzliche Filter -g1..-g9
    parser.add_argument('-g1', dest='group_address1')
    parser.add_argument('-g2', dest='group_address2')
    parser.add_argument('-g3', dest='group_address3')
    parser.add_argument('-g4', dest='group_address4')
    parser.add_argument('-g5', dest='group_address5')
    parser.add_argument('-g6', dest='group_address6')
    parser.add_argument('-g7', dest='group_address7')
    parser.add_argument('-g8', dest='group_address8')
    parser.add_argument('-g9', dest='group_address9')
    parser.add_argument('--verbose', '-v', action='store_true',
                      help='Zeigt detaillierte Debug-Ausgaben an')
    parser.add_argument('--discard-others', action='store_true',
                       help='Verwirft alle nicht zur Filteradresse passenden Telegramme (keine knx_tel.xml Ausgabe)')
    args = parser.parse_args()

    # Sammle alle Filteradressen in Reihenfolge
    filters = [args.group_address]
    for key in ['group_address1','group_address2','group_address3','group_address4','group_address5','group_address6','group_address7','group_address8','group_address9']:
        val = getattr(args, key, None)
        if val:
            filters.append(val)

    splitter = KNXSplitter(args.input_file, filters, args.verbose, args.discard_others)
    splitter.read_xml()
    splitter.split_and_save()

if __name__ == "__main__":
    main() 