import inspect
from typing import Callable, Any, List, Tuple, Union

# --- Fonction générique de conduite de test ---

def executer_test(
    fonction_a_tester: Callable, 
    valeur_retour_attendue: Union[Any, Tuple[Any, ...]], 
    arguments_test: List[Any]
) -> bool:
    """
    Exécute un test sur une fonction donnée avec des arguments spécifiques et compare 
    le résultat avec la valeur de retour attendue.

    Args:
        fonction_a_tester: La fonction Python (Callable) à tester.
        valeur_retour_attendue: La valeur ou le tuple de valeurs que la fonction 
                                est censée retourner.
        arguments_test: Une liste de valeurs représentant les arguments à passer 
                        à la fonction à tester.

    Returns:
        True si le test est réussi (valeur de retour correspondante), False sinon.
    """
    
    # Récupération du nom de la fonction pour un affichage clair
    nom_fonction = fonction_a_tester.__name__
    
    print(f"\n--- Démarrage du test pour : {nom_fonction} ---")
    print(f"Arguments d'entrée : {arguments_test}")
    print(f"Valeur de retour attendue : {valeur_retour_attendue}")
    
    try:
        # 1. Exécution de la fonction
        # Utilisation de l'unpacking d'arguments (*)
        resultat_obtenu = fonction_a_tester(*arguments_test)
        
        print(f"Valeur de retour obtenue : {resultat_obtenu}")

        # 2. Vérification du résultat
        
        # Pour gérer le cas où la fonction retourne un seul élément 
        # qui est un tuple (ex: def f(): return (1, 2)), et 
        # valeur_retour_attendue est aussi un tuple (1, 2)
        # Python compare directement les tuples, donc pas besoin de conversion 
        # supplémentaire si `valeur_retour_attendue` est un tuple.
        
        test_reussi = resultat_obtenu == valeur_retour_attendue
        
        if test_reussi:
            print(f"✅ TEST RÉUSSI pour {nom_fonction} !")
            return True
        else:
            print(f"❌ ÉCHEC DU TEST pour {nom_fonction} !")
            print(f"Attendu : {valeur_retour_attendue}, Obtenu : {resultat_obtenu}")
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
executer_test(
    fonction_a_tester=addition,
    valeur_retour_attendue=5,
    arguments_test=[2, 3]
)

# Test 2 : Retour simple (str)
executer_test(
    fonction_a_tester=formater_nom_complet,
    valeur_retour_attendue="Alice DURAND",
    arguments_test=["alice", "durand"]
)

# Test 3 : Retour multiple (Tuple)
executer_test(
    fonction_a_tester=infos_calcul,
    valeur_retour_attendue=(5.0, -1.0, 6.0),
    arguments_test=[2.0, 3.0]
)

# Test 4 : Échec attendu (pour démontrer le cas d'échec)
executer_test(
    fonction_a_tester=addition,
    valeur_retour_attendue=10, # Valeur INCORRECTE attendue
    arguments_test=[4, 5]
)

print("\n==============================================")
print("     Fin de la suite de tests")
print("==============================================")
