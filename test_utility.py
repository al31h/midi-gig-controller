import inspect
from typing import Callable, Any, List, Tuple, Union

# --- Fonction générique de conduite de test ---

def do_test(
    function_under_test: Callable, 
    expected_return: Union[Any, Tuple[Any, ...]], 
    function_arguments: List[Any]
) -> bool:
    """
    Exécute un test sur une fonction donnée avec des arguments spécifiques et compare 
    le résultat avec la valeur de retour attendue.

    Args:
        function_under_test: La fonction Python (Callable) à tester.
        expected_return: La valeur ou le tuple de valeurs que la fonction 
                                est censée retourner.
        function_arguments: Une liste de valeurs représentant les arguments à passer 
                        à la fonction à tester.

    Returns:
        True si le test est réussi (valeur de retour correspondante), False sinon.
    """
    
    # Récupération du nom de la fonction pour un affichage clair
    nom_fonction = function_under_test.__name__
    
    print(f"\n--- Démarrage du test pour : {nom_fonction} ---")
    print(f"Arguments d'entrée : {function_arguments}")
    print(f"Valeur de retour attendue : {expected_return}")
    
    try:
        # 1. Exécution de la fonction
        # Utilisation de l'unpacking d'arguments (*)
        resultat_obtenu = function_under_test(*function_arguments)
        
        print(f"Valeur de retour obtenue : {resultat_obtenu}")

        # 2. Vérification du résultat
        
        # Pour gérer le cas où la fonction retourne un seul élément 
        # qui est un tuple (ex: def f(): return (1, 2)), et 
        # valeur_retour_attendue est aussi un tuple (1, 2)
        # Python compare directement les tuples, donc pas besoin de conversion 
        # supplémentaire si `valeur_retour_attendue` est un tuple.
        
        test_reussi = resultat_obtenu == expected_return
        
        if test_reussi:
            print(f"✅ TEST RÉUSSI pour {nom_fonction} !")
            return True
        else:
            print(f"❌ ÉCHEC DU TEST pour {nom_fonction} !")
            print(f"Attendu : {expected_return}, Obtenu : {resultat_obtenu}")
            return False

    except Exception as e:
        # Gestion des exceptions levées par la fonction testée
        print(f"❌ ERREUR lors de l'exécution de {nom_fonction} : {e}")
        return False

# -----------------------------------------------
# --- Exemples de Fonctions à Tester (SUT) ---
# -----------------------------------------------

def addition(a: int, b: int) -> int:
    """Additionne deux nombres."""
    return a + b

def formater_nom_complet(prenom: str, nom: str) -> str:
    """Formate le nom et le prénom."""
    return f"{prenom.capitalize()} {nom.upper()}"

def infos_calcul(x: float, y: float) -> Tuple[float, float, float]:
    """Retourne la somme, la différence et le produit."""
    return (x + y, x - y, x * y)

# -----------------------------------------------
# --- Exécution des Tests ---
# -----------------------------------------------

print("==============================================")
print("     Début de la suite de tests personnalisée")
print("==============================================")

# Test 1 : Retour simple (int)
do_test(
    function_under_test=addition,
    expected_return=5,
    function_arguments=[2, 3]
)

# Test 2 : Retour simple (str)
do_test(
    function_under_test=formater_nom_complet,
    expected_return="Alice DURAND",
    function_arguments=["alice", "durand"]
)

# Test 3 : Retour multiple (Tuple)
do_test(
    function_under_test=infos_calcul,
    expected_return=(5.0, -1.0, 6.0),
    function_arguments=[2.0, 3.0]
)

# Test 4 : Échec attendu (pour démontrer le cas d'échec)
do_test(
    function_under_test=addition,
    expected_return=10, # Valeur INCORRECTE attendue
    function_arguments=[4, 5]
)

print("\n==============================================")
print("     Fin de la suite de tests")
print("==============================================")
