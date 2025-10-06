# TODO
# reste à faire
# - finir le codage des faders, tester
# - codage des pans
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

# --- Constantes du Protocole Allen & Heath CQ ---
# RAPPEL : CES VALEURS DOIVENT ÊTRE CONFIRMÉES PAR LE MANUEL OFFICIEL CQ-18T !
CQ_MIDI_CHANNEL = 1  # Le CQ utilise par défaut le Canal 1 (0 en indexation 0)

# Adresses de Paramètres NRPN (MSB - Most Significant Byte)
PARAM_FADER_MSB = 0x01   # Placeholder
PARAM_PAN_MSB = 0x02     # Placeholder
PARAM_MUTE_MSB = 0x03    # Placeholder
PARAM_SEND_BASE_MSB = 0x10 # Placeholder + index du mix (fx1 = 1, fx2 = 2, mix1 = 3...)

# Valeurs Mute (14-bit)
MUTE_ON_VALUE = 16383  # Valeur max
MUTE_OFF_VALUE = 0     # Valeur min

# Pan (Valeur 14-bit: 0-16383)
PAN_CENTER = 8192
PAN_MAX = 16383

# --- Mappage NRPN LSB (Index du Canal) ---
CQ_CHANNEL_MAP = {
    # 16 Canaux Mono (IN1-IN16) -> LSB 0 à 15
    'IN1': 0x00, 'IN2':  0x01, 'IN3':  0x02, 'IN4':  0x03, 'IN5':  0x04, 'IN6':  0x05, 'IN7':  0x06, 'IN8':  0x07, 
    'IN9': 0x08, 'IN10': 0x09, 'IN11': 0x0A, 'IN12': 0x0B, 'IN13': 0x0C, 'IN14': 0x0D, 'IN15': 0x0E, 'IN16': 0x0F,

    # Entrées Stéréo Linkées (Le contrôle se fait via l'index du premier canal)
    'ST1': 0x00, 'ST3':  0x02, 'ST5':  0x04, 'ST7':  0x06, 'ST9':  0x08, 'ST11': 0x0A, 'ST13': 0x0C, 'ST15': 0x0E,

    # Entrées Stéréo Dédiées et Retours Numériques (Hypothèses)
    'ST17': 0x18,     # ST17/18 (assumé)
    'USB':  0x1C,      # USB (assumé)
    'BT':   0x1E,       # Bluetooth (assumé)
    
    # Send FX
    
    # Sorties Mix (OUT1-OUT6) / FX (FX1-FX4)
    # Note: Les sorties n'utilisent généralement pas le même LSB que les entrées, 
    # elles sont souvent contrôlées par un MSB différent (PARAM_SEND_BASE_MSB) 
    # et une LSB de destination. Nous gardons les LSB d'Entrée ici pour la cohérence 
    # si jamais elles sont utilisées comme Entrées de Mix.
}
# La fonction parse_cq_command utilisera ce mapping pour trouver le LSB.

# Mappage des bus de sortie
#### Ce map est une base de calcul pour la fonction get_fader_index
SEND_BUS_MAP = {
    'FX1':  0x14, # canal pour le send IN01 vers FX1
    'FX2':  0x15, # canal pour le send IN01 vers FX2
    'FX3':  0x16, # canal pour le send IN01 vers FX3
    'FX4':  0x17, # canal pour le send IN01 vers FX4
    'MAIN': 0x00, # canal pour le send IN01 vers MAIN
    'OUT1': 0x44, # canal pour le send IN01 vers OUT1
    'OUT2': 0x45, # canal pour le send IN01 vers OUT2
    'OUT3': 0x46, # canal pour le send IN01 vers OUT3
    'OUT4': 0x47, # canal pour le send IN01 vers OUT4
    'OUT5': 0x48, # canal pour le send IN01 vers OUT5
    'OUT6': 0x49, # canal pour le send IN01 vers OUT6
}

def convert_hex_to14bits(value16):
    # les valeurs MIDI sont codées sur des octets de 7 bits
    msb = int((value16 & 0xff00)*2 + (value16 & 0x80)*2))
    lsb = int(value16 & 0x7f)
    return msb*0x100 + lsb
        
def convert_14bits_to_hex(value14):
    # les valeurs dans les tables d'interpolation de la doc CQ18 sont codées sur 2 octets de 7 bits (MIDI)
    msb = int((value14 & 0xff00) / 0x200)
    lsb = int((value14 & 0x7f) + ((value14 & 0x0100)/2))
    return msb * 0x100 + lsb
    
def get_fader_index(in_canonical_name, bus_canonical_name):
    """Retourne un integer sur 16 bits utilisé pour les commandes de fader - cf protocole MIDI page 17"""
    # Exemple : in_send_bus("IN3", "OUT4") doit retourner 0x405F
    in_index = CQ_CHANNEL_MAP[in_canonical_name]
    bus_index = SEND_BUS_MAP[bus_canonical_name]
    
    if bus_index == 0x00: # main
        fader_index = 0x4000 + in_index
    elif bus_index >= 0x14 and bus_index <= 0x17: # FX
        fader_index = 0x4C14 + in_index*4 + (bus_index-0x14)
    elif bus_index >= 0x44 and bus_index <= 0x49: # OUT
        fader_index = 0x4044 + in_index*12 + (bus_index-0x44)
    else:
        print(f"/!\ internal ERROR: invalid bus_index for {bus_canonical_name}")
        fader_index = 0

    msb = int((fader_index & 0xff00) + (fader_index & 0x80)*2))
    lsb = int(fader_index & 0x7f)
    return msb*0x100 + lsb


# Calcul des valeurs VC/VF nécessaire au contrôle des faders de la CQ18T et des PAN
# Les 2 tables "VAL14" contiennent les valeurs définies dans la doc A&H Protocole MIDI
# Elles sont codées sous forme de 2 octets de 7 bits (compatibilité MIDI)
TABLE_VCVF_FADER_VAL14 = [
    [-89, 0x0140], [-85, 0x0200], [-80, 0x0240], [-75, 0x0300], [-70, 0x0400], [-65, 0x0500], [-60, 0x0600], [-55, 0x0700],
    [-50, 0x0800], [-45, 0x0C00], [-40, 0x0F40], [-38, 0x1240], [-36, 0x1540], [-35, 0x1700], [-34, 0x1900], [-33, 0x1A00],
    [-32, 0x1C00], [-31, 0x1D40], [-30, 0x1F00], [-29, 0x2040], [-28, 0x2200], [-27, 0x2340], [-26, 0x2500], [-25, 0x2640],
    [-24, 0x2840], [-23, 0x2A00], [-22, 0x2B40], [-21, 0x2D00], [-20, 0x2E40], [-19, 0x3000], [-18, 0x3140], [-17, 0x3300],
    [-16, 0x3440], [-15, 0x3600], [-14, 0x3800], [-13, 0x3940], [-12, 0x3B00], [-11, 0x3C40], [-10, 0x3E00], [-9,  0x4140],
    [-8,  0x4440], [-7,  0x4800], [-6,  0x4B00], [-5,  0x4E40], [-4,  0x5240], [-3,  0x5640], [-2,  0x5A00], [-1,  0x5E00],
    [0,   0x6200], [1,   0x6540], [2,   0x6900], [3,   0x6C40], [4,   0x7000], [5,   0x7340], [6,   0x7540], [7,   0x7800],
    [8,   0x7A40], [9,   0x7D00], [10,  0x7F40]
]

TABLE_VCVF_PAN_VAL14 = [
    [-100, 0x0000], [-90, 0x0633], [-80, 0x0C66], [-70, 0x1319], [-60, 0x194C], [-50, 0x1F7F], [-40, 0x2632], [-30, 0x2C65],
    [-20,  0x3318], [-15, 0x3632], [-10, 0x394B], [-5,  0x3C65], [0,   0x4000], [5,   0x4318], [10,  0x4632], [15,  0x494B],
    [20,   0x4C65], [30,  0x5318], [40, 0x594B],  [50,  0x5F7F], [60,  0x6632], [60,  0x6632], [70,  0x6C65], [80,  0x7318],
    [90,   0x764B], [100, 0x7F7F]
]

# tables globales : valeurs VCVF recalculées en hexa sur 16 bits pour permettre les calculs d'interpolation
table_vcvf_fader_hex = []
table_vcvf_pan_hex = []

compute_table_val14_to_hex(table_vcvf_fader_hex, TABLE_VCVF_FADER_VAL14)
compute_table_val14_to_hex(table_vcvf_pan_hex, TABLE_VCVF_PAN_VAL14)

def compute_table_val14_to_hex(table_hex, table_val14):
    table_hex = []
    for dec_value, val14 in table_val14:
        # 1. Calcul de la valeur entière 16 bits
        val16 = convert_14bits_to_hex(val14)
        
        # 2. Ajout du nouveau doublet à la table finale
        table_hex.append([dec_value, val16])        
        
def hex_to_dec(hex_value):
    """Convertit une chaîne hexadécimale en entier décimal."""
    # La fonction int() avec base 16 gère la conversion.
    # On ajoute le préfixe '0x' si manquant pour plus de robustesse.
    if not hex_value.startswith('0x') and not hex_value.startswith('0X'):
        hex_value = '0x' + hex_value
    return int(hex_value, 16)

def dec_to_hex_16bit(dec_value):
    """Convertit un entier décimal en chaîne hexadécimale de 16 bits (4 caractères)."""
    # On s'assure que la valeur reste dans la plage 16 bits (0 à 65535)
    dec_value = max(0, min(65535, round(dec_value)))
    # Utilise le formatage de chaîne pour obtenir 4 chiffres hexadécimaux
    return f'{dec_value:04X}'
    
def interpoler_vcvf(table_interpolation, valeur_entree):
    """
    Calcule une valeur interpolée à partir d'une table avec une colonne VCVF en hexadécimal 16 bits.

    Args:
        table_interpolation (list): Liste de listes/tuples, par ex. [[X1, VCVF_DEC1, VCVF_HEX1], [X2, VCVF_DEC2, VCVF_HEX2], ...]
            La 3ème colonne (VCVF_HEX) est ignorée si elle est passée, mais une table formatée avec 3 colonnes est acceptée.
            Les colonnes 0 (X) et 1 (VCVF_DEC) doivent être des nombres.
        valeur_entree (float): La valeur X pour laquelle on cherche le VCVF interpolé.

    Returns:
        str: La valeur VCVF interpolée, arrondie à l'entier le plus proche et formatée en hexadécimal 16 bits (4 chiffres).
    """

    # 1. Préparation des données pour numpy.interp
    # Extraction des colonnes X et VCVF (en décimal)
    xp = np.array([row[0] for row in table_interpolation]) # Colonne des valeurs recherchées (X)
    
    # On suppose que la colonne VCVF (colonne 2) est en hexadécimal et doit être convertie.
    # On utilise un test pour savoir si la colonne VCVF est déjà en décimal ou en hexadécimal string
    # Si la colonne est déjà numérique (float/int), on l'utilise directement (colonne 1).
    # Sinon, on prend la colonne 2 et on la convertit.
    
    try:
        # Test si la 2ème colonne (indice 1) est déjà numérique
        # Cela suppose que si la table a 3 colonnes, les colonnes sont [X, VCVF_DEC, VCVF_HEX]
        # Dans ce cas, nous devons utiliser la colonne 2 (indice 2) pour l'hexadécimal ou la colonne 1 (indice 1) si elle a été pré-convertie.
        # Pour être plus robuste, nous allons forcer l'extraction des données X et Y (VCVF)
        
        # Nous allons supposer que la colonne des valeurs recherchées (X) est la première (indice 0) 
        # et que la colonne VCVF (la valeur à interpoler) est la deuxième (indice 1).
        # Si VCVF est un string, c'est l'hexadécimal et on doit convertir.
        
        y_raw = [row[1] for row in table_interpolation]
        
        if isinstance(y_raw[0], str):
            # La colonne VCVF est une chaîne hexa, on la convertit en décimal
            yp = np.array([hex_to_dec(h) for h in y_raw])
        else:
            # La colonne VCVF est déjà numérique (décimal)
            yp = np.array(y_raw)
            
    except (IndexError, TypeError, ValueError) as e:
        print(f"Erreur lors du traitement de la table : {e}. Assurez-vous que la table a au moins 2 colonnes où la 1ère est la valeur X et la 2ème est la valeur VCVF (décimale ou hexadécimale string).")
        return "ERREUR"


    # 2. Définition des bornes d'extrapolation
    # Selon la demande:
    # Si < min(X), retourne VCVF min (yp[0])
    # Si > max(X), retourne VCVF max (yp[-1])
    # C'est la gestion par défaut de np.interp qui n'est pas tout à fait celle demandée (np.interp utilise les bornes pour l'interpolation)
    # L'option fill_value=(yp[0], yp[-1]), bounds_error=False de interp1d est plus explicite.
    
    # Pour respecter EXACTEMENT la règle (valeur MIN/MAX en cas d'extrapolation),
    # nous utilisons une approche manuelle ou la fonction `np.interp` mais en bornant l'entrée.
    
    # Avec np.interp, nous avons la gestion native de l'interpolation.
    # Pour l'extrapolation :
    # Si l'entrée est hors limites, nous renvoyons les valeurs aux extrémités.

    if valeur_entree <= xp[0]:
        valeur_vcvf_dec = yp[0]
    elif valeur_entree >= xp[-1]:
        valeur_vcvf_dec = yp[-1]
    else:
        # Interpolation linéaire
        # y = np.interp(x, xp, fp)
        # x est la valeur à évaluer (valeur_entree)
        # xp est le tableau des points d'abscisse (valeur recherchée)
        # fp est le tableau des valeurs à interpoler (VCVF)
        valeur_vcvf_dec = np.interp(valeur_entree, xp, yp)

    # 3. Formatage de la sortie
    return dec_to_hex_16bit(valeur_vcvf_dec)
    
    
# --- Conversion de Commandes Intelligibles vers MIDI ---
def fader_db_to_nrpn(fader_db):
    """convertit une valeur en db (chaine de caracteres) en un double MSB/LSB compatible avec le protocole CQ18T)"""
    # la valeur fader_db est un string car il peut valoir "-inf" ou "off"
    # On calcule les valeurs VC/VF  envoyer à la console via la table d'interpolation table_vcvf_fader_hex
    if fader_db.lower()  == 'off' or fader_db.lower()  == '-inf':
        return (0x00,0x00)
    else:
        vcvf = interpoler_vcvf(table_vcvf_fader_hex, int(fader_db))
        vcvf14 = convert_hex_to14bits(vcvf)
        nrpn_msb = vcvf14 & 0xff00
        nrpn_lsb = vcvf14 & 0x00ff
        return (nrpn_msb, nrpn_lsb)
    
def pan_to_nrpn(pan):
    """convertit une valeur de pan (chaine de caracteres) en un double MSB/LSB compatible avec le protocole CQ18T)"""
    # la valeur pan est un string car il peut valoir "center" ou "left 30%", ou "right 50%"
    # On calcule les valeurs VC/VF  envoyer à la console via la table d'interpolation table_vcvf_pan_hex
    
    pan_str = pan.lower().strip()
    if 'center' in pan_str:
        return (0x40,0x00)
    
    match = re.match(r'(left|right)\s*(\d+)\s*%', pan_str)
    if match:
        direction = match.group(1)
        percent = int(match.group(2))
        val = int(percent * (PAN_CENTER / 100.0))
        if direction == 'left':
            val = -1 * percent
        else:
            val = percent

        vcvf = interpoler_vcvf(table_vcvf_pan_hex, int(val))
        vcvf14 = convert_hex_to14bits(vcvf)
        nrpn_msb = vcvf14 & 0xff00
        nrpn_lsb = vcvf14 & 0x00ff
        return (nrpn_msb, nrpn_lsb)         

    # par defaut, retourner la valeur CENTER
    return (0x40,0x00)

def nrpn_to_midi_messages(nrpn_msb, nrpn_lsb, value_14bit):
    """Crée la séquence de 4 messages CC NRPN."""
    
    value_msb = (value_14bit >> 7) & 0x7F # Bits 7-13
    value_lsb = value_14bit & 0x7F        # Bits 0-6
    midi_channel = CQ_MIDI_CHANNEL - 1 

    # 1. NRPN MSB (Contrôleur 99)
    msg1 = [rtmidi.MidiMessage.CONTROLLER | midi_channel, 99, nrpn_msb] 
    # 2. NRPN LSB (Contrôleur 98)
    msg2 = [rtmidi.MidiMessage.CONTROLLER | midi_channel, 98, nrpn_lsb] 
    # 3. Data Entry MSB (Contrôleur 6)
    msg3 = [rtmidi.MidiMessage.CONTROLLER | midi_channel, 6, value_msb] 
    # 4. Data Entry LSB (Contrôleur 38)
    msg4 = [rtmidi.MidiMessage.CONTROLLER | midi_channel, 38, value_lsb]

    return [msg1, msg2, msg3, msg4]

# Dans midi_controller.py, modification de la signature de la fonction et ajout de la logique de résolution:

# Dans midi_controller.py, modification de la fonction parse_cq_command:

def parse_cq_command(command, name_to_cq_map):
    """
    Analyse Chant_Emilie/send_main/0db ou USB/send_main/0db et le convertit en messages NRPN.
    """
    try:
        parts = [p.strip() for p in command.split('/', 3)]
        if len(parts) < 3: raise ValueError("Format de commande CQ invalide. Attendu Nom/Param/Valeur.")

        input_channel_name = parts[0]
        # 1. Résoudre le nom du canal d'entrée en nom de canal CQ (ex: Piano_Stéréo -> ST9)
        if input_channel_name in name_to_cq_map:
            # Récupère le nom CQ canonique à partir du nom utilisateur (ex: ST9)
            input_canonical_name = name_to_cq_map[input_channel_name].upper()
        else:
            # Le nom est déjà canonique ou non mappé (ex: IN1, IN2...)
            input_canonical_name = input_channel_name.upper()
        # 2. Déterminer l'index LSB NRPN à partir du nom canonique
        if input_canonical_name not in CQ_CHANNEL_MAP:
             raise ValueError(f"Canal CQ non supporté ou non défini: {input_canonical_name}")

        input_channel_index = CQ_CHANNEL_MAP[input_canonical_name]

        action = parts[1].lower()
        

        nrpn_lsb = channel_index & 0x7F
        midi_messages = []

        # ... (Le reste du code reste inchangé, il détermine le MSB et la valeur 14-bit)
        
        if action == 'send_main':
            # Exemple de commande dans le fichier 'chanson' : Chant_Toto/send/Facade/0
            # On résoud le nom du bus d'envoi (recherche nom canonique)
            bus_channel_name = parts[2]
            # 1. Résoudre le nom du canal d'entrée en nom de canal CQ (ex: Piano_Stéréo -> ST9)
            if bus_channel_name in name_to_cq_map:
                # Récupère le nom CQ canonique à partir du nom utilisateur (ex: ST9)
                bus_canonical_name = name_to_cq_map[bus_channel_name].upper()
            else:
                # Le nom est déjà canonique ou non mappé (ex: IN1, IN2...)
                bus_canonical_name = bus_channel_name.upper()

            # resoudre le numéro de canal de mixage (page 17 protocole MIDI)
            fader_index = get_fader_index(input_canonical_name, bus_canonical_name)
            
            # On calcule les valeurs VC/VF  envoyer à la console via la table d'interpolation table_vcvf_fader_hex
            if value_str.lower()  == 'off' or value_str.lower()  == '-inf':
                value_str='-100'
                
            vcvf = interpoler_vcvf(table_vcvf_fader_hex, int(value_str))
            nrpn_msb = vcvf & 0xff00
            nrpn_lsb = vsvf & 0x00ff

            # TODO
            midi_messages = nrpn_to_midi_messages(nrpn_msb, nrpn_lsb, value_14bit)
            desc = f"CQ: {channel_name_or_cq} Fader réglé à {value_str}"            
            
            
            desc = f"CQ: {user_channel_name} Fader réglé à {value_str}"

            print(f"DEBUG: action = {action} / param {param} / value_str = {value_str}")
        


        elif action == 'pan':
            # Exemple de commande dans le fichier 'chanson' : Chant_Toto/pan/left 30%
            # on convertit la valeur "left 30%" en valeur numérique : left negatif, right positif -> -30
            # On calcule les valeurs VC/VF  envoyer à la console via la table d'interpolation TABLE_VCVF_PAN_HEX
            # ... (logique pan)
            desc = f"CQ: {user_channel_name} Pan réglé à {value_str}"

        elif param == 'mute':
            # ... (logique mute)
            desc = f"CQ: {user_channel_name} Mute réglé à {value_str}"

        elif action == 'send':
            # ... (logique send)
            desc = f"CQ: {user_channel_name} Send à {bus_name} réglé à {value_str}"
            
        else:
            raise ValueError(f"Paramètre CQ non supporté: {param}")

        return midi_messages, desc

    except Exception as e:
        print(f"/!\ Erreur lors de l'analyse de la commande '{command}': {e}")
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
        print(f"/!\ Erreur de lecture/parsing du fichier de configuration général '{file_path}': {e}")
        sys.exit(1)

def load_mapping(file_path):
    """Charge le fichier de mappage PC -> Nom de fichier de chanson."""
    try:
        with open(file_path, 'r') as f:
            # Assurez-vous que les clés sont des entiers pour la recherche
            mapping = {int(k): v for k, v in json.load(f).items()}
            return mapping
    except Exception as e:
        print(f"/!\ Erreur de lecture/parsing du fichier de mappage PC '{file_path}': {e}")
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
        print(f"/!\ Erreur lors du chargement/parsing du fichier de chanson '{filepath}': {e}")
        return None


# --- La Classe Contrôleur Principale ---

class MidiShowController:
    
    def __init__(self, config_file, mapping_file, verbose):
        self.config = load_config(config_file)
        self.pc_map = load_mapping(mapping_file)
        self.verbose = verbose
        self.songs_dir = self.config.get("songs_directory", "song_sets")
        
        self.midi_in = None
        self.midi_out = None
        
        self.input_name = self.config.get('midi_in_name_part')
        self.output_name = self.config.get('midi_out_name_part')
        self.input_channel = self.config.get('midi_in_channel', 1)
        self.cq_midi_channel = self.config.get('cq_midi_channel', 1)
        self.midronome_channel = self.config.get('midronome_channel', 16)
        self.cq_tap_tempo_note = self.config.get('cq_tap_tempo_note', 48)
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
            print(f"/!\ Erreur d'ouverture du port de sortie MIDI ({self.output_name}): {e}")
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
            print(f"/!\ Erreur d'ouverture du port d'entrée MIDI ({self.input_name}): {e}")
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

            self.midi_out.send_message(msg)

    def send_tap_tempo(self, bpm):
        """Simule le Tap Tempo sur le CQ-18T en envoyant 20 SoftKey Note On/Off."""
        if bpm <= 0: return

        # Intervalle entre les taps (en secondes)
        # Tap Tempo = 60 / BPM
        interval = 60.0 / bpm
        
        # La documentation A&H indique que les Soft Keys sont contrôlées par Note On/Off
        note = self.cq_tap_tempo_note 
        channel = self.cq_midi_channel - 1 

        print(f"= Envoi du Tap Tempo ({bpm} BPM) au CQ-18T (Note {note}, 20 frappes)...")

        for i in range(20): # 20 frappes pour une bonne précision
            # Note ON (Soft Key Press)
            note_on = [rtmidi.MidiMessage.NOTE_ON | channel, note, 127]
            # Note OFF (Soft Key Release)
            note_off = [rtmidi.MidiMessage.NOTE_OFF | channel, note, 0]
            
            self.send_midi([note_on], f"CQ Tap Tempo (Note ON) - Hit {i+1}")
            
            # Temps de relâchement très court
            time.sleep(0.01) 
            
            self.send_midi([note_off], f"CQ Tap Tempo (Note OFF) - Hit {i+1}")
            
            # Attendre l'intervalle du tempo
            if i < 19:
                time.sleep(interval - 0.01) # interval - temps de frappe

        print("Tap Tempo terminé.")

    def set_midronome_bpm(self, bpm):
        """Règle le BPM sur un métronome externe via MIDI Clock/Tempo."""
        # Le midronome se pilote en tempo par une commande CC : 0xB<channel-1> 0x57 <BPM-60>
        # Donc,par exemple, midronome sur canal 12, et BPM 165 : BB 57 69
        
        channel = self.midronome_channel - 1 
        midro_bpm = [rtmidi.MidiMessage.CC | channel, 0x57, (bpm-60)]
        self.send_midi([midro_bpm], f"Midronome BPM (CC) {bpm}")
        
        # Pour un contrôle standard, on enverrait un Start/Stop et des messages MIDI Clock.
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
        for command in song_data['CQ_COMMANDS']:
            try:
                if '=' in command:
                    key, value = command.split('=', 1)
                    intelligible_command = f"{key.replace('/', '/')}/{value}"
                else:
                    intelligible_command = command
            
                # NOUVEAU: Appel avec le mappage de noms
                messages, desc = parse_cq_command(intelligible_command, self.name_to_cq_map)
                self.send_midi(messages, desc)
        
    except Exception as e:
        print(f"/!\ Commande CQ non exécutée: {e}")

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
                print(f"/!\ Commande Pédale non exécutée: {e}")
        
        print("\n--- Exécution du set de commandes terminée ---")


    def execute_pc_commands(self, pc_number):
        """Charge et exécute le set de commandes pour le numéro PC reçu."""
        
        if pc_number not in self.pc_map:
            print(f"/!\ PC {pc_number} non mappé à une chanson. Ignoré.")
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
    
    # prépare les tables d'interpolation pour la console CQ18T
    compute_table_val14_to_hex(table_vcvf_fader_hex, TABLE_VCVF_FADER_VAL14)
    compute_table_val14_to_hex(table_vcvf_pan_hex, TABLE_VCVF_PAN_VAL14)


    parser = ArgumentParser(description="Contrôleur de show MIDI pour Allen & Heath CQ-18T et effets externes.")
    
    # NOUVEAU: Option pour lister les ports
    parser.add_argument('--list-ports', '-l', action='store_true', 
                        help="Affiche la liste des ports MIDI disponibles et quitte.")
    
    # Les arguments existants sont rendus optionnels pour ne pas les exiger lors du listage des ports
    parser.add_argument('config_file', nargs='?', default='config.json', 
                        help="Chemin vers le fichier de configuration général (JSON).")
    parser.add_argument('mapping_file', nargs='?', default='pc_mapping.json',
                        help="Chemin vers le fichier de mappage PC -> Chanson (JSON).")
    parser.add_argument('--verbose', '-v', action='store_true', help="Affiche toutes les commandes MIDI envoyées.")
    
    args = parser.parse_args()

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
        controller = MidiShowController(args.config_file, args.mapping_file, args.verbose)
    except SystemExit:
        # Une erreur fatale (config/mapping non trouvé) s'est produite lors de l'init.
        return

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