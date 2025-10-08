import inspect
from typing import Callable, Any, List, Tuple, Union, Dict, TypedDict

# Définition d'un cas de test unique
class TestCase(TypedDict):
    """Structure pour un cas de test unique."""
    test_title: str                         # NOUVEAU: Titre spécifique du test
    function_under_test: Callable
    expected_return: Union[Any, Tuple[Any, ...]]
    function_arguments: List[Any]

# Définition d'un groupe de tests (Chapitre)
class TestGroup(TypedDict):
    """Structure pour un chapitre ou groupe de tests."""
    chapter_title: str                      # NOUVEAU: Titre du chapitre
    tests: List[TestCase]

TestPlan = List[TestGroup]
    
# --- Fonction générique de conduite de test ---

def do_test(
    test_title: str,
    function_under_test: Callable,
    expected_return: Union[Any, Tuple[Any, ...]],
    function_arguments: List[Any]
) -> bool:
    """
    Exécute la fonction avec les arguments donnés et compare le résultat
    avec le résultat attendu. Retourne True si le test passe, False sinon.
    """
    try:
        # Appelle la fonction avec les arguments décomposés (*function_arguments)
        actual_return = function_under_test(*function_arguments)

        # La comparaison dépend si on attend un seul résultat ou un tuple
        if isinstance(expected_return, Tuple):
            # Convertit le retour actuel en tuple si ce n'est pas déjà le cas
            if not isinstance(actual_return, Tuple):
                actual_return = (actual_return,)

            test_passed = (actual_return == expected_return)

        else:
            test_passed = (actual_return == expected_return)


        if test_passed:
            print(f"✅ TEST PASSE : {function_under_test.__name__}({function_arguments}) == {expected_return}")
        else:
            print(f"❌ TEST ECHOUÉ : {function_under_test.__name__}({function_arguments}). Attendu: {expected_return}, Obtenu: {actual_return}")

        return test_passed

    except Exception as e:
        print(f"💥 ERREUR lors de l'exécution du test {test_title} pour {function_under_test.__name__}: {e}")
        return False

def run_test_plan(test_plan: TestPlan):
    """Parcourt le plan de tests, chapitre par chapitre, et exécute chaque test."""
    print("==================================================")
    print("         DÉBUT DU PLAN D'EXÉCUTION DES TESTS")
    print("==================================================")
    
    total_tests = 0
    passed_tests = 0

    for chapter_config in test_plan:
        chapter_title = chapter_config["chapter_title"]
        test_list = chapter_config["tests"]
        
        print(f"\n--- {chapter_title} ({len(test_list)} tests) ---")

        for test_config in test_list:
            total_tests += 1
            
            # Récupère toutes les valeurs du dictionnaire de configuration du test
            title = test_config["test_title"]
            func = test_config["function_under_test"]
            expected = test_config["expected_return"]
            args = test_config["function_arguments"]

            # Appelle la fonction do_test avec les nouveaux arguments
            if do_test(title, func, expected, args):
                passed_tests += 1

    print("\n==================================================")
    print("         FIN DU PLAN D'EXÉCUTION DES TESTS")
    print("==================================================")
    print(f"RÉSUMÉ FINAL: {passed_tests} tests réussis sur {total_tests} au total.")


        
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


# --- 2. Définition du Plan de Tests (TEST_PLAN) ---

TEST_PLAN: TestPlan = [
    # --- Chapitre 1 : Tests de la fonction de base (add_numbers) ---
    {
        "chapter_title": "Chapitre 1: Tests d'addition simple",
        "tests": [
            {
                "test_title": "Addition de deux nombres positifs (2 + 3)",
                "function_under_test": addition,
                "expected_return": 5,
                "function_arguments": [2, 3]
            },
            {
                "test_title": "Formattage de nom",
                "function_under_test": formater_nom_complet,
                "expected_return": "Alice DURAND",
                "function_arguments": ["alice", "durand"]
            },
        ]
    },
    
    # --- Chapitre 2 : Tests de fonctions avancées (multiplication/tuple) ---
    {
        "chapter_title": "Chapitre 2: Tests de retour en tuple",
        "tests": [
            {
                "test_title": "Autre fonction de calcul",
                "function_under_test": infos_calcul,
                "expected_return": (5.0, -1.0, 6.0),
                "function_arguments": [2.0, 3.0]
            },
            {
                "test_title": "Test qui ÉCHOUERA intentionnellement",
                "function_under_test": infos_calcul,
                "expected_return": (5.0, -1.0, 7.0),
                "function_arguments": [2.0, 3.0]
            },
        ]
    }
]


if __name__ == "__main__":
    run_test_plan(TEST_PLAN)
    