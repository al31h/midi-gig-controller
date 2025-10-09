# TODO
# reste à faire
# - tester le bpm metronome
# - tester le BPM / tap tempo sur CQ
# - coder le traitement des pédales d'effets

import json
import os
import re
import sys
import time
from argparse import ArgumentParser
from configparser import ConfigParser
import numpy as np

# Nécessite l'installation: pip install python-rtmidi
try:
    from rtmidi.midiutil import open_midiport
    import rtmidi
except ImportError:
    print("La bibliothèque 'python-rtmidi' est requise. Veuillez l'installer: pip install python-rtmidi")
    sys.exit(1)

import cq18t

def get_mix_canonical_name(intelliname, name_to_cq_map):
    
    if intelliname in name_to_cq_map:
        canonical_name = get_input_canonical_name([intelliname].upper())
    else:
        canonical_name = intelliname.upper()
        
    return canonical_name

def parse_mix_command(midi_channel, command, name_to_cq_map):
    """
    Analyse Chant_Emilie/send_main/0db ou USB/send_main/0db et le convertit en messages NRPN.
    """
    try:
        parts = [p.strip() for p in command.split('/', 3)]
        if len(parts) < 3: raise ValueError("Format de commande CQ invalide. Attendu Channel/Action/Bus/Valeur, ou Bus/Action/Valeur.")

        action = parts[1].lower()
        
        if action == 'send':
            # Exemple de commande dans le fichier 'chanson' : Chant_Toto/send/Facade/0
            # On résoud le nom du bus d'envoi (recherche nom canonique)
            input_channel_name = get_mix_canonical_name(parts[0], name_to_cq_map)
            bus_channel_name = get_mix_canonical_name(parts[2], name_to_cq_map)
            value = parts[3].lower()
            
            midi_msg = cq18t.cq_get_midi_msg_set_fader_to_bus(midi_channel, input_channel_name, bus_channel_name, value)
            
            if midi_msg == []:
                print(f"/!/ command {command} ignored")
                desc = ''
            else:
                desc = f"Fader {input_channel_name} to bus {bus_channel_name} set to {value}dB"
                
        elif action == 'pan':
            # Exemple de commande dans le fichier 'chanson' : Chant_Toto/pan/Facade/left 30%
            input_channel_name = get_mix_canonical_name(parts[0], name_to_cq_map)
            bus_channel_name = get_mix_canonical_name(parts[2], name_to_cq_map)
            value = parts[3].lower()
            
            midi_msg = cq18t.cq_get_midi_msg_set_pan_to_bus(midi_channel, input_channel_name, bus_channel_name, value)
            
            if midi_msg == []:
                print(f"/!/ command {command} ignored")
                desc = ''
            else:
                desc = f"Pan {input_channel_name} to bus {bus_channel_name} set to {value}"

        elif param == 'mute':
            # Exemple de commande dans le fichier 'chanson' : Chant_Toto/mute/ON
            channel_name = get_mix_canonical_name(parts[0], name_to_cq_map)
            value = 0
            if parts[2].lower() == 'on': value = 1
            
            midi_msg = cq18t.cq_get_midi_msg_set_mute_channel(midi_channel, channel_name, value)
            
            if midi_msg == []:
                print(f"/!/ command {command} ignored")
                desc = ''
            else:
                desc = f"Mute {channel_name} set to {parts[2].upper()}"

        elif action == 'level':
            # Exemple de commande dans le fichier 'chanson' : Facade/level/-6
            bus_channel_name = get_mix_canonical_name(parts[1], name_to_cq_map)
            value = parts[2].lower()
            
            midi_msg = cq18t.cq_get_midi_msg_set_bus_fader(midi_channel, bus_channel_name, value)
            
            if midi_msg == []:
                print(f"/!/ command {command} ignored")
                desc = ''
            else:
                desc = f"Bus Level {bus_channel_name} set to {value}dB"

            
        else:
            raise ValueError(f"Paramètre CQ non supporté: {param}")

        return midi_messages, desc

    except Exception as e:
        print(f"/!/ Erreur lors de l'analyse de la commande '{command}': {e}")
        return [], ""




# --- Contrôle de Pédales et Autres Périphériques ---

def parse_pedal_command(pedal_name, command, pedal_map):
    """Analyse les commandes pour les pédales d'effets (PC/CC)."""
    if pedal_name not in pedal_map:
        return [], f"Pedale '{pedal_name}' inconnue. Ignorée."
        
    midi_channel = pedal_map[pedal_name] - 1 # 0-indexed
    parts = [p.strip() for p in command.split('/')]

    if parts[0].upper() == 'PC':
        pc_num = int(parts[1])
        # [Program Change | channel, PC number]
        midi_msg = [rtmidi.MidiMessage.PROGRAM_CHANGE | midi_channel, pc_num]
        desc = f"Pédale {pedal_name} (Ch {pedal_map[pedal_name]}): PC {pc_num} envoyé."
        return [midi_msg], desc
        
    elif parts[0].upper() == 'CC':
        cc_num = int(parts[1])
        cc_val = int(parts[2])
        # [Control Change | channel, CC number, CC value]
        midi_msg = [rtmidi.MidiMessage.CONTROLLER | midi_channel, cc_num, cc_val]
        desc = f"Pédale {pedal_name} (Ch {pedal_map[pedal_name]}): CC {cc_num}/{cc_val} envoyé."
        return [midi_msg], desc
        
    else:
        return [], f"Format de commande pédale inconnu: {command}. Attendu PC/CC."


# --- Gestion des Fichiers et de la Configuration ---

def load_config(file_path):
    """Charge le fichier de configuration JSON général."""
    try:
        with open(file_path, 'r') as f:
            config = json.load(f)
            # Convertir les canaux des pédales en numéros (assurant qu'ils sont bien des entiers)
            pedals = config.get('pedals', {})
            config['pedals'] = {name: int(ch) for name, ch in pedals.items()}
            return config
    except Exception as e:
        print(f"/!/ Erreur de lecture/parsing du fichier de configuration général '{file_path}': {e}")
        sys.exit(1)

def load_mapping(file_path):
    """Charge le fichier de mappage PC -> Nom de fichier de chanson."""
    try:
        with open(file_path, 'r') as f:
            # Assurez-vous que les clés sont des entiers pour la recherche
            mapping = {int(k): v for k, v in json.load(f).items()}
            return mapping
    except Exception as e:
        print(f"/!/ Erreur de lecture/parsing du fichier de mappage PC '{file_path}': {e}")
        sys.exit(1)

def load_song_file(song_filename, songs_dir):
    """Charge et parse un fichier de chanson (.ini-like)."""
    filepath = os.path.join(songs_dir, song_filename)
    parser = ConfigParser()
    try:
        # Lire le fichier en tant que dictionnaire pour éviter les problèmes de section [DEFAULT]
        with open(filepath, 'r') as f:
             # Ajouter une section factice si le fichier n'en a pas, puis le re-parser
             content = "[commands]\n" + f.read()
             parser.read_string(content)
             
        data = {
            'BPM': parser.getfloat('SONG_INFO', 'BPM', fallback=None),
            'CQ_COMMANDS': parser.options('CQ_PRESETS') if parser.has_section('CQ_PRESETS') else [],
            'PEDAL_COMMANDS': []
        }
        
        # Lire les commandes CQ
        if parser.has_section('CQ_PRESETS'):
            data['CQ_COMMANDS'] = [
                f"{key}/{parser.get('CQ_PRESETS', key)}" 
                for key in parser.options('CQ_PRESETS')
            ]
        
        # Lire les commandes des pédales et les formater (PedalName/Command)
        if parser.has_section('PEDALS'):
            data['PEDAL_COMMANDS'] = [
                f"{key}/{parser.get('PEDALS', key)}"
                for key in parser.options('PEDALS')
            ]

        return data
        
    except Exception as e:
        print(f"/!/ Erreur lors du chargement/parsing du fichier de chanson '{filepath}': {e}")
        return None


# --- La Classe Contrôleur Principale ---

class MidiShowController:
    
    def __init__(self, config_file, mapping_file, test, verbose):
        self.config = load_config(config_file)
        self.pc_map = load_mapping(mapping_file)
        self.test = test
        self.verbose = verbose
        self.songs_dir = self.config.get("songs_directory", "song_sets")
        
        self.midi_in = None
        self.midi_out = None
        
        self.input_name = self.config.get('midi_in_name_part')
        self.output_name = self.config.get('midi_out_name_part')
        self.input_channel = self.config.get('midi_in_channel', 1)
        self.cq_midi_channel = self.config.get('cq_midi_channel', 1)
        self.midronome_channel = self.config.get('midronome_channel', 16)
        self.cq_tap_tempo_softkey = self.config.get('cq_tap_tempo_softkey', '')
        self.pedal_map = self.config.get('pedals', {})

        # NOUVEAU: Mappage Nom_Utilisateur -> Canal_CQ (ex: Chant_Emilie -> IN1)
        self.name_to_cq_map = {
            v: k for k, v in self.config.get('channel_names', {}).items()
        }

    def __enter__(self):
        """Ouvre les ports MIDI au début."""
        self.open_ports()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Ferme les ports MIDI à la fin."""
        self.close_ports()

    def open_ports(self):
        print("Initialisation des ports MIDI...")
        
        # Port de Sortie
        try:
            self.midi_out, out_name = open_midiport(
                self.output_name, use_virtual=False, interactive=False
            )
            print(f"- Port de sortie (pour CQ/Pédales) ouvert: {out_name}")
        except Exception as e:
            print(f"/!/ Erreur d'ouverture du port de sortie MIDI ({self.output_name}): {e}")
            sys.exit(1)

        # Port d'Entrée
        try:
            self.midi_in, in_name = open_midiport(
                self.input_name, use_virtual=False, interactive=False
            )
            print(f"- Port d'entrée (pour PC) ouvert: {in_name}")
            # self.midi_in.ignore_types(timing=False)    # autorise la réception de la MIDI Clock
            self.midi_in.set_callback(self.midi_callback)
        except Exception as e:
            print(f"/!/ Erreur d'ouverture du port d'entrée MIDI ({self.input_name}): {e}")
            self.midi_out.close()
            sys.exit(1)

    def close_ports(self):
        if self.midi_in: self.midi_in.close()
        if self.midi_out: self.midi_out.close()
        print("\nPorts MIDI fermés.")

    def send_midi(self, midi_messages, description):
        """Envoie un ou plusieurs messages MIDI et affiche si verbeux."""
        for msg in midi_messages:
            if self.verbose:
                # Formatage de l'affichage: Time, Canal, Type de message, Description
                msg_type = (msg[0] & 0xF0)
                channel = (msg[0] & 0x0F) + 1
                
                if msg_type == rtmidi.MidiMessage.PROGRAM_CHANGE:
                    msg_desc = f"PC {msg[1]}"
                elif msg_type == rtmidi.MidiMessage.CONTROLLER and msg[1] in [99, 98, 6, 38]:
                    msg_desc = f"NRPN: CC{msg[1]}={msg[2]}"
                elif msg_type == rtmidi.MidiMessage.CONTROLLER:
                    msg_desc = f"CC{msg[1]}={msg[2]}"
                else:
                    msg_desc = f"Raw: {msg}"
                
                print(f"[{time.strftime('%H:%M:%S')}] CH {channel:<2} | {msg_desc:<15} | {description}")

            if self.test == False:
                self.midi_out.send_message(msg)

    def send_tap_tempo(self, bpm):
        """Simule le Tap Tempo sur le CQ-18T en envoyant 20 SoftKey Note On/Off."""
        
        if bpm <= 0: return

        channel = self.cq_midi_channel - 1 
        tap_tempo_softkey = self.cq_tap_tempo_softkey 

        midi_msg = cq18t.cq_get_midi_tap_tempo(self.cq_midi_channel, tap_tempo_softkey)
        if midi_msg == []:
            return
            

        # Intervalle entre les taps (en secondes)
        # Tap Tempo = 60 / BPM
        interval = 60.0 / bpm
        

        print(f"= Envoi du Tap Tempo ({bpm} BPM) au CQ-18T (Note {note}, 20 frappes)...")

        for i in range(20): # 20 frappes pour une bonne précision
            self.send_midi(midi_msg)
            
            # Attendre l'intervalle du tempo
            if i < 19:
                time.sleep(interval) 

        print("Tap Tempo terminé.")

    def set_midronome_bpm(self, bpm):
        """Règle le BPM sur un métronome externe via MIDI Clock/Tempo."""
        # Le midronome se pilote en tempo par une commande CC : 0xB<channel-1> 0x57 <BPM-60>
        # Donc,par exemple, midronome sur canal 12, et BPM 165 : BB 57 69
        
        if bpm <= 0: return
        
        channel = self.midronome_channel - 1 
        midi_msg = [rtmidi.MidiMessage.CC | channel, 0x57, (bpm-60)]
        self.send_midi([midi_msg], f"Midronome BPM (CC) {bpm}")
        
        pass

    def execute_commands(self, song_data):
        """Exécute toutes les commandes pour la chanson chargée."""
        
        # 1. Gestion du BPM (Metronome et Tap Tempo CQ)
        bpm = song_data['BPM']
        if bpm is not None:
            print(f"BPM de la chanson: {bpm}")
            self.set_midronome_bpm(bpm)
            self.send_tap_tempo(bpm)

        # 2. Commandes CQ-18T (NRPN)
        print("\n--- Exécution des Commandes CQ-18T ---")
        for command in song_data['MIX']:
            try:
                if '=' in command:
                    key, value = command.split('=', 1)
                    intelligible_command = f"{key.replace('/', '/')}/{value}"
                else:
                    intelligible_command = command
            
                # NOUVEAU: Appel avec le mappage de noms
                messages, desc = parse_mix_command(self.cq_midi_channel, intelligible_command, self.name_to_cq_map)
                self.send_midi(messages, desc)
        
            except Exception as e:
                print(f"/!/ Commande CQ non exécutée: {e}")

        # 3. Commandes Pédales d'Effets (PC/CC)
        print("\n--- Exécution des Commandes Pédales d'Effets ---")
        for command_line in song_data['PEDAL_COMMANDS']:
            try:
                # Le format de fichier PEDALS utilise 'Delay_M=PC/5'
                pedal_name, command = command_line.split('=', 1)
                pedal_name = pedal_name.strip()
                command = command.strip()
                
                messages, desc = parse_pedal_command(pedal_name, command, self.pedal_map)
                self.send_midi(messages, desc)
            except Exception as e:
                print(f"/!/ Commande Pédale non exécutée: {e}")
        
        print("\n--- Exécution du set de commandes terminée ---")


    def execute_pc_commands(self, pc_number):
        """Charge et exécute le set de commandes pour le numéro PC reçu."""
        
        if pc_number not in self.pc_map:
            print(f"/!/ PC {pc_number} non mappé à une chanson. Ignoré.")
            return

        song_filename = self.pc_map[pc_number]
        print(f"\n- Mappage trouvé : PC {pc_number} -> Fichier '{song_filename}'")
        
        song_data = load_song_file(song_filename, self.songs_dir)
        
        if song_data:
            self.execute_commands(song_data)

    def midi_callback(self, message, data=None):
        """Gère la réception des messages MIDI (appelé par rtmidi)."""
        midi_data, delta_time = message
        
        message_type = midi_data[0] & 0xF0
        channel_received = (midi_data[0] & 0x0F) + 1 # 1-16
        
        if verbose:
            print(f"[{time.strftime('%H:%M:%S')}] Received MIDI command {midi_data}")
        
        # Vérifie si c'est un Program Change sur le canal d'entrée spécifié
        if (message_type == rtmidi.MidiMessage.PROGRAM_CHANGE and
            channel_received == self.input_channel):
            
            pc_number = midi_data[1]
            self.execute_pc_commands(pc_number)

def list_midi_ports():
    """Liste tous les ports MIDI disponibles en entrée et en sortie."""
    midi_in = rtmidi.MidiIn()
    midi_out = rtmidi.MidiOut()
    
    print("\n--- Ports MIDI d'ENTRÉE disponibles ---")
    in_ports = midi_in.get_ports()
    if in_ports:
        for i, port_name in enumerate(in_ports):
            print(f"  [{i}]: {port_name}")
    else:
        print("  Aucun port d'entrée MIDI trouvé.")

    print("\n--- Ports MIDI de SORTIE disponibles ---")
    out_ports = midi_out.get_ports()
    if out_ports:
        for i, port_name in enumerate(out_ports):
            print(f"  [{i}]: {port_name}")
    else:
        print("  Aucun port de sortie MIDI trouvé.")
    print("\nUtilisez une partie de ces noms dans 'config.json' pour spécifier vos interfaces.")


def main():

    parser = ArgumentParser(description="Contrôleur de show MIDI pour Allen & Heath CQ-18T et effets externes.")
    
    parser.add_argument('--list-ports', '-l', action='store_true', 
                        help="Affiche la liste des ports MIDI disponibles et quitte.")
    parser.add_argument('config_file', nargs='?', default='config.json', 
                        help="Chemin vers le fichier de configuration général (JSON).")
    parser.add_argument('mapping_file', nargs='?', default='pc_mapping.json',
                        help="Chemin vers le fichier de mappage PC -> Chanson (JSON).")
    parser.add_argument('--verbose', '-v', action='store_true', help="Affiche toutes les commandes MIDI envoyées.")
    parser.add_argument('--test', '-t', action='store_true', help="N'envoie pas les commandes MIDI, ne fait que les afficher.")
    
    args = parser.parse_args()
    print([args])

    # Logique pour le listage des ports
    if args.list_ports:
        list_midi_ports()
        return # Quitte après le listage

    # Si nous arrivons ici, nous avons besoin des fichiers de configuration
    if not args.config_file or not args.mapping_file:
        print("Erreur: Les fichiers de configuration et de mappage doivent être spécifiés.")
        parser.print_help()
        return

    try:
        controller = MidiShowController(args.config_file, args.mapping_file, args.test, args.verbose)
    except SystemExit:
        # Une erreur fatale (config/mapping non trouvé) s'est produite lors de l'init.
        return

    if args.test:
        print(f"Démarrage du contrôleur en mode Test. Aucune commande MIDI ne sera envoyée.")
    else:
        print(f"Démarrage du contrôleur (Mode Verbeux: {args.verbose}).")
    print(f"Écoute des commandes MIDI PC sur l'interface '{controller.input_name}', canal {controller.input_channel}...")
    print("Appuyez sur Ctrl+C pour arrêter.")
    
    try:
        with controller:
            # Boucle infinie pour écouter les messages MIDI
            while True:
                time.sleep(1)
    except KeyboardInterrupt:
        print("\nArrêt demandé par l'utilisateur.")
    except Exception as e:
        print(f"Une erreur inattendue s'est produite: {e}")


if __name__ == '__main__':
    main()
