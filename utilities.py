# module: utilities

import re
from typing import List, Any
import test_utility

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
    
def split_list_into_chunks(input_list: List[Any], chunk_size: int = 3) -> List[List[Any]]:
    """
    Scinde une liste en sous-listes (morceaux) d'une taille maximale spécifiée.
    
    Si la liste d'entrée a 3 éléments ou moins, elle est retournée comme
    une seule sous-liste dans la liste de résultat.

    Args:
        input_list (List[Any]): La liste à scinder.
        chunk_size (int): La taille maximale des sous-listes (par défaut à 3).

    Returns:
        List[List[Any]]: Une liste de sous-listes.
    """
    list_length = len(input_list)
    
    # Vérifie si le split est nécessaire (selon votre condition de base)
    if list_length <= chunk_size:
        # Retourne la liste complète comme un seul élément dans la liste de résultats
        return [input_list]

    # Utilise une compréhension de liste pour un découpage efficace
    # La boucle parcourt la liste avec un pas de 'chunk_size' (3)
    # et utilise le slicing pour extraire les sous-listes.
    return [
        input_list[i:i + chunk_size] 
        for i in range(0, list_length, chunk_size)
    ]

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
    }
]  

def run_unitary_tests():
    return (test_utility.run_test_plan(TEST_PLAN))