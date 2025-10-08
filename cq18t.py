# cq18t.py library
import re
import test_utility

CQ_HEXVALUE_ERROR = 0xFFFF  # valeur impossible car les valeurs transmises sur MIDI sont sur 7 bits

# ==============================================================================
# FONCTIONS GENERIQUES
# ==============================================================================

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
    
def convert_hex_to_14bits(value16):
    # les valeurs MIDI sont codées sur des octets de 7 bits
    msb = int(value16 & 0x3F80) >> 7
    lsb = int(value16 & 0x7f)
    
    value14 = (msb << 8) + lsb
    
    return value14
        
def convert_14bits_to_hex(value14):
    # les valeurs dans les tables d'interpolation de la doc CQ18 sont codées sur 2 octets de 7 bits (MIDI)
    msb = int(value14 & 0x7f00) >> 8
    lsb = int(value14 & 0x007f)
    
    value16 = (msb << 7) + lsb
    return value16
    
def compute_table_val14_to_hex(table_val14):
    table_hex = []
    for dec_value, val14 in table_val14:
        # 1. Calcul de la valeur entière 16 bits
        val16 = convert_14bits_to_hex(val14)
        
        # 2. Ajout du nouveau doublet à la table finale
        table_hex.append([dec_value, val16])        
        
    return table_hex
    
def extraire_chaine_et_nombre(s):
    match = re.match(r"([A-Z]+)(\d*)", s)
    if match:
        lettres = match.group(1)
        nombre = int(match.group(2)) if match.group(2) else 0
        return lettres, nombre
    else:
        return s, 0
        
        
def get_interpolated_value(table_valeurs, x_cible):
    """
    Effectue une interpolation linéaire sur une table de valeurs et 
    retourne le résultat arrondi à l'entier le plus proche.

    Args:
        table_valeurs (list of tuple): Une liste de tuples (x, y) représentant 
                                       la table de valeurs. La liste doit être 
                                       triée par ordre croissant de x.
        x_cible (float): La valeur x pour laquelle on cherche la valeur y interpolée.

    Returns:
        int: La valeur y interpolée, arrondie à l'entier.

    Raises:
        ValueError: Si x_cible est en dehors de la plage des x dans la table.
    """
    
    # 1. Vérification des limites
    x_min = table_valeurs[0][0]
    x_max = table_valeurs[-1][0]
    
    if x_cible < x_min:
        x_cible = x_min
        
    if x_cible > x_max:
        x_cible = x_max
        
#    if not (x_min <= x_cible <= x_max):
#        raise ValueError(f"La valeur cible ({x_cible}) est hors de la plage des x ({x_min} à {x_max}).")

    # 2. Recherche des points encadrants (x1, y1) et (x2, y2)
    x1, y1 = None, None
    x2, y2 = None, None

    # Parcourir la table pour trouver les deux points (x1, y1) et (x2, y2) qui encadrent x_cible
    for i in range(len(table_valeurs) - 1):
        x_i, y_i = table_valeurs[i]
        x_i1, y_i1 = table_valeurs[i+1]
        
        if x_i <= x_cible <= x_i1:
            x1, y1 = x_i, y_i
            x2, y2 = x_i1, y_i1
            break
            
    # Cas où x_cible correspond exactement à un point de la table
    if x1 is None:
        if x_cible == x_min:
            return int(round(y1))
        elif x_cible == x_max:
             return int(round(y2))
        # Si x_cible est à la dernière valeur, mais la boucle ne l'a pas trouvé (ne devrait pas arriver avec les vérifs)
        elif x_cible == table_valeurs[-1][0]:
            return int(round(table_valeurs[-1][1]))
        else:
            # Cette erreur ne devrait pas se produire si les vérifications initiales sont correctes
            raise Exception("Erreur interne lors de la recherche des points.")

    # 3. Calcul de l'interpolation linéaire
    
    # Éviter la division par zéro si les points sont identiques (ce qui signifie x_cible=x1=x2)
    if x2 - x1 == 0:
        y_interpole = y1
    else:
        # Formule de l'interpolation linéaire : 
        # y = y1 + (y2 - y1) * (x_cible - x1) / (x2 - x1)
        y_interpole = y1 + (y2 - y1) * (x_cible - x1) / (x2 - x1)

    # 4. Retourner la valeur arrondie à l'entier (selon la demande)
    return int(round(y_interpole))
    
        
# ==============================================================================
# TABLES DE VALEURS CQ18T
# Issues de la documentation MIDI Protocol V1.2
# ==============================================================================

CQ_TABLE_SOFTKEYS_MAP = {
    'Soft Key #1': 0x30,
    'Soft Key #2': 0x31,
    'Soft Key #3': 0x32
}

def get_softkey_midicode_by_name(softkey_canonical_name):
    """
    Retourne un integer sur 2x7 bits utilisé pour les commandes de fader - cf protocole MIDI page 17
    Fonction utile pour piloter le niveau des bus (par exemple, la sortie MAIN générale)
    """
    try:
        sk_code = CQ_TABLE_SOFTKEYS_MAP[softkey_canonical_name]
    except:
        return CQ_HEXVALUE_ERROR
        
    return sk_code

# ==============================================================================
# MUTE
# ==============================================================================
CQ_MUTE_CHANNELS_MAP = {
    # 16 Canaux Mono (IN1-IN16) 
    'IN1':    0x0000, 'IN2':     0x0001, 'IN3':     0x0002, 'IN4':     0x0003, 
    'IN5':    0x0004, 'IN6':     0x0005, 'IN7':     0x0006, 'IN8':     0x0007, 
    'IN9':    0x0008, 'IN10':    0x0009, 'IN11':    0x000A, 'IN12':    0x000B, 
    'IN13':   0x000C, 'IN14':    0x000D, 'IN15':    0x000E, 'IN16':    0x000F,

    # Entrées Stéréo Linkées (Le contrôle se fait via l'index du premier canal)
    'ST1/2':  0x0000, 'ST3/4':   0x0002, 'ST5/6':   0x0004, 'ST7/8':   0x0006, 
    'ST9/10': 0x0008, 'ST11/12': 0x000A, 'ST13/14': 0x000C, 'ST15/16': 0x000E,

    # Entrées Stéréo Dédiées et Retours Numériques
    'ST1':    0x0018,     # ST17/18
    'ST2':    0x001A,
    'USB':    0x001C,     # USB 
    'BT':     0x001E,     # Bluetooth
    
    # Sorties Bus FX
    'FX1':    0x0051, 'FX2':     0x0052, 'FX3':     0x0053, 'FX4':     0x0054, 
    
    # Sorties Bus mix
    'MAIN':   0x0044,
    'OUT1':   0x0045, 'OUT2':    0x0046, 'OUT3':    0x0047, 'OUT4':    0x0048, 'OUT5':    0x0049, 'OUT6':    0x004A, 
    'OUT1/2': 0x0045, 'OUT3/4':  0x0047, 'OUT5/6':  0x0049,
    
    # MIX GROUPS
    'MGRP1':  0x0400, 'MGRP2':   0x0401, 'MGRP3':   0x0402, 'MGRP3':  0x0403, 
    
    # DCA
    'DCA1':   0x0200, 'DCA2':    0x0201, 'DCA3':    0x0202, 'DCA4':    0x0203
}

def get_channel_mute_vcvf(channel_canonical_name):
    """
    Retourne un integer sur 2x7 bits utilisé pour les commandes de fader - cf protocole MIDI page 17
    Fonction utile pour piloter le niveau des bus (par exemple, la sortie MAIN générale)
    """
    try:
        ch_index_hex = CQ_MUTE_CHANNELS_MAP[channel_canonical_name]
    except:
        return CQ_HEXVALUE_ERROR
        
    return ch_index_hex

# ==============================================================================
# INPUT FADERS (TO MAIN, OUTx and FXx)
# ==============================================================================
CQ_FADER_TO_MAIN_MAP = {
    # 16 Canaux Mono (IN1-IN16) 
    'IN1':    0x4000, 'IN2':     0x4001, 'IN3':     0x4002, 'IN4':     0x4003, 
    'IN5':    0x4004, 'IN6':     0x4005, 'IN7':     0x4006, 'IN8':     0x4007, 
    'IN9':    0x4008, 'IN10':    0x4009, 'IN11':    0x400A, 'IN12':    0x400B, 
    'IN13':   0x400C, 'IN14':    0x400D, 'IN15':    0x400E, 'IN16':    0x400F,

    # Entrées Stéréo Linkées (Le contrôle se fait via l'index du premier canal)
    'ST1/2':  0x4000, 'ST3/4':   0x4002, 'ST5/6':   0x4004, 'ST7/8':   0x4006, 
    'ST9/10': 0x4008, 'ST11/12': 0x400A, 'ST13/14': 0x400C, 'ST15/16': 0x400E,

    # Entrées Stéréo Dédiées et Retours Numériques
    'ST1':    0x4018,     # ST17/18
    'ST2':    0x401A,
    'USB':    0x401C,     # USB 
    'BT':     0x401E,     # Bluetooth
    
    # Sorties Bus FX
    'FX1':    0x403C, 'FX2':     0x403D, 'FX3':     0x403E, 'FX4':     0x403F   
}

CQ_FADER_TO_OUT_MAP = {
    # 16 Canaux Mono (IN1-IN16) 
    'IN1':    0x4044, 'IN2':     0x4050, 'IN3':     0x405C, 'IN4':     0x4068, 
    'IN5':    0x4074, 'IN6':     0x4100, 'IN7':     0x410C, 'IN8':     0x4118, 
    'IN9':    0x4124, 'IN10':    0x4130, 'IN11':    0x413C, 'IN12':    0x4148, 
    'IN13':   0x4154, 'IN14':    0x4160, 'IN15':    0x416C, 'IN16':    0x4178,

    # Entrées Stéréo Linkées (Le contrôle se fait via l'index du premier canal)
    'ST1/2':  0x4044, 'ST3/4':   0x405C, 'ST5/6':   0x4074, 'ST7/8':   0x410C, 
    'ST9/10': 0x4124, 'ST11/12': 0x413C, 'ST13/14': 0x4154, 'ST15/16': 0x416C,

    # Entrées Stéréo Dédiées et Retours Numériques
    'ST1':    0x4264,     # ST17/18
    'ST2':    0x427C,
    'USB':    0x4314,     # USB 
    'BT':     0x432C,     # Bluetooth
    
    # Sorties Bus FX
    'FX1':    0x4614, 'FX2':     0x4620, 'FX3':     0x462C, 'FX4':     0x4638   
}

CQ_FADER_TO_FX_MAP = {
    # 16 Canaux Mono (IN1-IN16) 
    'IN1':    0x4C14, 'IN2':     0x4C18, 'IN3':     0x4C1C, 'IN4':     0x4C20, 
    'IN5':    0x4C24, 'IN6':     0x4C28, 'IN7':     0x4C2C, 'IN8':     0x4C30, 
    'IN9':    0x4C34, 'IN10':    0x4C38, 'IN11':    0x4C3C, 'IN12':    0x4C40, 
    'IN13':   0x4C44, 'IN14':    0x4C48, 'IN15':    0x4C4C, 'IN16':    0x4C50,

    # Entrées Stéréo Linkées (Le contrôle se fait via l'index du premier canal)
    'ST1/2':  0x4C14, 'ST3/4':   0x4C1C, 'ST5/6':   0x4C24, 'ST7/8':   0x4C2C, 
    'ST9/10': 0x4C34, 'ST11/12': 0x4C3C, 'ST13/14': 0x4C44, 'ST15/16': 0x4C4C,

    # Entrées Stéréo Dédiées et Retours Numériques
    'ST1':    0x4C74,     # ST17/18
    'ST2':    0x4C7C,
    'USB':    0x4D04,     # USB 
    'BT':     0x4D0C,     # Bluetooth
    
    # Sorties Bus FX
    'FX1':    0x4E04, 'FX2':     0x4E08, 'FX3':     0x4E0C, 'FX4':     0x4E10   
}

def get_fader_to_bus_vcvf(in_canonical_name, bus_canonical_name):
    """
    Retourne un integer sur 2x7 bits utilisé pour les commandes de fader - cf protocole MIDI page 17
    Fonction utile pour piloter les faders d'envoi des entrées vers les bus
    """
    # Exemple : in_send_bus("IN3", "OUT4") doit retourner 0x405F
    bus_type, bus_number = extraire_chaine_et_nombre(bus_canonical_name)
    
    if bus_type == 'MAIN':
        bus_number = 1 # to compensate the -1 when computing fader_vcvf_hex
        try:
            in_index_14 = CQ_FADER_TO_MAIN_MAP[in_canonical_name]
        except:
            return CQ_HEXVALUE_ERROR

    elif bus_type == 'OUT': 
        try:
            in_index_14 = CQ_FADER_TO_OUT_MAP[in_canonical_name]
        except:
            return CQ_HEXVALUE_ERROR
            
    elif bus_type == 'FX': 
        try:
            in_index_14 = CQ_FADER_TO_FX_MAP[in_canonical_name]
        except:
            return CQ_HEXVALUE_ERROR
            
    else:
        print(f"/!/ internal ERROR: invalid bus_index for {bus_canonical_name}")
        return CQ_HEXVALUE_ERROR

    in_index_hex = convert_14bits_to_hex(in_index_14)
    fader_vcvf_hex = in_index_hex + bus_number - 1
    fader_vcvf_14 = convert_hex_to_14bits(fader_vcvf_hex)
    
    return fader_vcvf_14


# ==============================================================================
# OUTPUT/BUS FADERS
# ==============================================================================
CQ_BUS_FADER_MAP = {
    'MAIN':   0x4F00,
    'OUT1':   0x4F01, 'OUT2':   0x4F02, 'OUT3':   0x4F03, 'OUT4':   0x4F04, 'OUT5':   0x4F05, 'OUT6':   0x4F06, 
    'OUT1/2': 0x4F01, 'OUT3/4': 0x4F03, 'OUT5/6': 0x4F05, 
    'FX1':    0x4F0D, 'FX2':    0x4F0E, 'FX3':    0x4F0F, 'FX4':    0x4F10, 
    'DCA1':   0x4F20, 'DCA2':   0x4F21, 'DCA3':   0x4F22, 'DCA4':   0x4F23 
}

def get_bus_fader_vcvf(bus_canonical_name):
    """
    Retourne un integer sur 2x7 bits utilisé pour les commandes de fader - cf protocole MIDI page 17
    Fonction utile pour piloter le niveau des bus (par exemple, la sortie MAIN générale)
    """
    try:
        fader_index_hex = CQ_BUS_FADER_MAP[bus_canonical_name]
    except:
        return CQ_HEXVALUE_ERROR
        
    return fader_index_hex

# ==============================================================================
# PAN TO BUS MAPPING
# ==============================================================================
CQ_PAN_TO_MAIN_MAP = {
    # 16 Canaux Mono (IN1-IN16) 
    'IN1':    0x5000, 'IN2':     0x5001, 'IN3':     0x5002, 'IN4':     0x5003, 
    'IN5':    0x5004, 'IN6':     0x5005, 'IN7':     0x5006, 'IN8':     0x5007, 
    'IN9':    0x5008, 'IN10':    0x5009, 'IN11':    0x500A, 'IN12':    0x500B, 
    'IN13':   0x500C, 'IN14':    0x500D, 'IN15':    0x500E, 'IN16':    0x500F,

    # Entrées Stéréo Linkées (Le contrôle se fait via l'index du premier canal)
    'ST1/2':  0x5000, 'ST3/4':   0x5002, 'ST5/6':   0x5004, 'ST7/8':   0x5006, 
    'ST9/10': 0x5008, 'ST11/12': 0x500A, 'ST13/14': 0x500C, 'ST15/16': 0x500E,

    # Entrées Stéréo Dédiées et Retours Numériques
    'ST1':    0x5018,     # ST17/18
    'ST2':    0x501A,
    'USB':    0x501C,     # USB 
    'BT':     0x501E,     # Bluetooth
    
    # Sorties Bus FX
    'FX1':    0x503C, 'FX2':     0x503D, 'FX3':     0x503E, 'FX4':     0x503F   
}

CQ_PAN_TO_OUT_MAP = {
    # 16 Canaux Mono (IN1-IN16) 
    'IN1':    0x5044, 'IN2':     0x5050, 'IN3':     0x505C, 'IN4':     0x5068, 
    'IN5':    0x5074, 'IN6':     0x5100, 'IN7':     0x510C, 'IN8':     0x5118, 
    'IN9':    0x5124, 'IN10':    0x5130, 'IN11':    0x513C, 'IN12':    0x5148, 
    'IN13':   0x5154, 'IN14':    0x5160, 'IN15':    0x516C, 'IN16':    0x5178,

    # Entrées Stéréo Linkées (Le contrôle se fait via l'index du premier canal)
    'ST1/2':  0x5044, 'ST3/4':   0x505C, 'ST5/6':   0x5074, 'ST7/8':   0x510C, 
    'ST9/10': 0x5124, 'ST11/12': 0x513C, 'ST13/14': 0x5154, 'ST15/16': 0x516C,

    # Entrées Stéréo Dédiées et Retours Numériques
    'ST1':    0x5264,     # ST17/18
    'ST2':    0x527C,
    'USB':    0x5314,     # USB 
    'BT':     0x532C,     # Bluetooth
    
    # Sorties Bus FX
    'FX1':    0x5614, 'FX2':     0x5620, 'FX3':     0x562C, 'FX4':     0x5638   
}

def get_pan_to_bus_vcvf(in_canonical_name, bus_canonical_name):
    """
    Retourne un integer sur 2x7 bits utilisé pour les commandes de fader - cf protocole MIDI page 17
    Fonction utile pour piloter les faders d'envoi des entrées vers les bus
    """
    # Exemple : in_send_bus("IN3", "OUT4") doit retourner 0x405F
    bus_type, bus_number = extraire_chaine_et_nombre(bus_canonical_name)
    
    if bus_type == 'MAIN':
        bus_number = 1 # to compensate the -1 when computing pan_vcvf_hex
        try:
            in_index_14 = CQ_PAN_TO_MAIN_MAP[in_canonical_name]
        except:
            return CQ_HEXVALUE_ERROR
            
    elif bus_type == 'OUT': 
        try:
            in_index_14 = CQ_PAN_TO_OUT_MAP[in_canonical_name]
        except:
            return CQ_HEXVALUE_ERROR
            
    else:
        print(f"/!/ internal ERROR: invalid bus_index for {bus_canonical_name}")
        return CQ_HEXVALUE_ERROR

    in_index_hex = convert_14bits_to_hex(in_index_14)
    pan_vcvf_hex = in_index_hex + bus_number - 1
    pan_vcvf_14 = convert_hex_to_14bits(pan_vcvf_hex)
    
    return pan_vcvf_14


# ==============================================================================
# FADER VALUES
# ==============================================================================
# tables globales : valeurs VCVF recalculées en hexa sur 16 bits pour permettre les calculs d'interpolation
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

table_vcvf_fader_hex = []

def get_fader_vcvf(value_db):
    
    global table_vcvf_fader_hex

    # initialize the PAN table if not already done
    if len(table_vcvf_fader_hex) == 0:
        table_vcvf_fader_hex = compute_table_val14_to_hex(TABLE_VCVF_FADER_VAL14)
        
    if value_db == '-inf' or value_db == 'off':
        return 0x0000
    
    vcvf_hex = get_interpolated_value(table_vcvf_fader_hex, float(value_db))
    vcvf_14 = convert_hex_to_14bits(vcvf_hex)
    
    return vcvf_14 


# ==============================================================================
# PAN VALUES
# ==============================================================================

TABLE_VCVF_PAN_VAL14 = [
    [-100, 0x0000], [-90, 0x0633], [-80, 0x0C66], [-70, 0x1319], [-60, 0x194C], [-50, 0x1F7F], [-40, 0x2632], [-30, 0x2C65],
    [-20,  0x3318], [-15, 0x3632], [-10, 0x394B], [-5,  0x3C65], [0,   0x4000], [5,   0x4318], [10,  0x4632], [15,  0x494B],
    [20,   0x4C65], [30,  0x5318], [40, 0x594B],  [50,  0x5F7F], [60,  0x6632], [60,  0x6632], [70,  0x6C65], [80,  0x7318],
    [90,   0x764B], [100, 0x7F7F]
]

table_vcvf_pan_hex = []

def get_pan_vcvf(pan):
    global table_vcvf_pan_hex
    
    # initialize the PAN table if not already done
    if len(table_vcvf_pan_hex) == 0:
        table_vcvf_pan_hex = compute_table_val14_to_hex(TABLE_VCVF_PAN_VAL14)        
        
    pan_str = pan.lower().strip()
    if 'center' in pan_str:
        val = 0
    else:
        match = re.match(r'(left|right)\s*(\d+)\s*%', pan_str)
        if match:
            direction = match.group(1)
            percent = int(match.group(2))
            if direction == 'left':
                val = -1 * percent
            else:
                val = percent
        else:
            val = 0

    vcvf_hex = get_interpolated_value(table_vcvf_pan_hex, float(val))
    vcvf_14 = convert_hex_to_14bits(vcvf_hex)
    return vcvf_14


# ==============================================================================
# BUILD MIDI MESSAGES FOR CQ18T
# ==============================================================================

def cq_get_midi_msg_set_scene(midi_channel, scene_id):
    channel = midi_channel -1
    msg = [ 0xB0 | channel, 0x00, 0x00 , 0xC0 | channel , scene_id - 1]
    return msg

def cq_get_midi_msg_press_softkey(midi_channel, softkey_canonical_name):
    channel = midi_channel -1
    softkey_code = get_softkey_midicode_by_name(softkey_canonical_name)
    if softkey_code == CQ_HEXVALUE_ERROR:
        return []
        
    msg = [ 0x90 | channel, softkey_code, 0x7F , 0x80 | channel , softkey_code, 0x00]
    return msg
    
def cq_get_midi_msg_set_fader_to_bus(midi_channel, in_canonical_name, bus_canonical_name, value_db):
    channel = midi_channel -1

    fader_vcvf_14 = get_fader_to_bus_vcvf(in_canonical_name, bus_canonical_name)
    if fader_vcvf_14 == CQ_HEXVALUE_ERROR:
        return []

    fader_msb = (fader_vcvf_14 & 0x7F00) >> 8
    fader_lsb = fader_vcvf_14 & 0x007F
    
    value_vcvf_14 = get_fader_vcvf(value_db)
    value_msb = (value_vcvf_14 & 0x7F00) >> 8
    value_lsb = value_vcvf_14 & 0x007F


    msg = [ 0xB0 | channel, 0x63, fader_msb, 
            0xB0 | channel, 0x62, fader_lsb, 
            0xB0 | channel, 0x06, value_msb, 
            0xB0 | channel, 0x26, value_lsb
          ]
    return msg
    
def cq_get_midi_msg_set_pan_to_bus(midi_channel, in_canonical_name, bus_canonical_name, pan):
    channel = midi_channel -1
    
    pan_vcvf_14 = get_pan_to_bus_vcvf(in_canonical_name, bus_canonical_name)
    if pan_vcvf_14 == CQ_HEXVALUE_ERROR:
        return []

    pan_msb = (pan_vcvf_14 & 0x7F00) >> 8
    pan_lsb = pan_vcvf_14 & 0x007F
    
    value_vcvf_14 = get_pan_vcvf(pan)
    value_msb = (value_vcvf_14 & 0x7F00) >> 8
    value_lsb = value_vcvf_14 & 0x007F

    if pan_vcvf_14 == 0x0000:
        return []

    msg = [ 0xB0 | channel, 0x63, pan_msb, 
            0xB0 | channel, 0x62, pan_lsb, 
            0xB0 | channel, 0x06, value_msb, 
            0xB0 | channel, 0x26, value_lsb
          ]
    return msg

def cq_get_midi_msg_set_bus_fader(midi_channel, bus_canonical_name, value_db):
    channel = midi_channel -1

    fader_vcvf_14 = get_bus_fader_vcvf(bus_canonical_name)
    if fader_vcvf_14 == CQ_HEXVALUE_ERROR:
        return []

    fader_msb = (fader_vcvf_14 & 0x7F00) >> 8
    fader_lsb = fader_vcvf_14 & 0x007F
    
    value_vcvf_14 = get_fader_vcvf(value_db)
    value_msb = (value_vcvf_14 & 0x7F00) >> 8
    value_lsb = value_vcvf_14 & 0x007F


    msg = [ 0xB0 | channel, 0x63, fader_msb, 
            0xB0 | channel, 0x62, fader_lsb, 
            0xB0 | channel, 0x06, value_msb, 
            0xB0 | channel, 0x26, value_lsb
          ]
    return msg

def cq_get_midi_msg_set_mute_channel(midi_channel, channel_canonical_name, mute_on):
    channel = midi_channel -1

    mute_vcvf_14 = get_channel_mute_vcvf(channel_canonical_name)
    if mute_vcvf_14 == CQ_HEXVALUE_ERROR:
        return []

    mute_msb = (mute_vcvf_14 & 0x7F00) >> 8
    mute_lsb = mute_vcvf_14 & 0x007F

    mute_val = 0x00
    if mute_on:
        mute_val = 0x01
    
    msg = [ 0xB0 | channel, 0x63, mute_msb, 
            0xB0 | channel, 0x62, mute_lsb, 
            0xB0 | channel, 0x06, 0x00, 
            0xB0 | channel, 0x26, mute_val
          ]
    return msg

def cq_get_midi_tap_tempo(midi_channel, softkey_canonical_name):
    return cq_get_midi_msg_press_softkey(midi_channel, softkey_canonical_name)




# ==============================================================================
# UNITARY TESTS
# ==============================================================================

TEST_PLAN: test_utility.TestPlan = [
    {
        "chapter_title": "1: Test des fonctions de conversion",
        "tests": [
            {
                "test_title": "Conversion valeur hexa string en valeur entière numérique",
                "function_under_test": hex_to_dec,
                "expected_return": 0x1234,
                "function_arguments": ['0x1234']
            },
            {
                "test_title": "Conversion valeur hexa string en valeur entière numérique",
                "function_under_test": hex_to_dec,
                "expected_return": 0x1234,
                "function_arguments": ['0x1234']
            },
        ]
    },
    
    {
        "chapter_title": "Chapitre 2: Fonctions CQ18T basiques",
        "tests": [
            {
                "test_title": "Récupération ID Softkey",
                "function_under_test": get_softkey_midicode_by_name,
                "expected_return": 0x31,
                "function_arguments": ['Soft Key #2']
            },
            {
                "test_title": "Récupération ID d'erreur d'une Softkey qui n'existe pas",
                "function_under_test": get_softkey_midicode_by_name,
                "expected_return": CQ_HEXVALUE_ERROR,
                "function_arguments": ['Soft Key #4']
            },
        ]
    }
]

def run_unitary_tests():
    return (test_utility.run_test_plan(TEST_PLAN))
    
# ==============================================================================
# INITIALISATION DU MODULE
# ==============================================================================

if __name__ == '__main__':
    print(f"/!/ ERROR: This module cannot be used in standalone")
    exit(1)


