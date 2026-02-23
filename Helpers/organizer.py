import sys
from pathlib import Path

def path_organizer():
    """
    Identifica a raiz do projeto (um nível acima da pasta atual 'Helpers')
    Adiciona ao sys.path se ainda não estiver lá
    """

    # Identifica a raiz do projeto (um nível acima da pasta atual 'Helpers')
    root_path = Path().absolute().parent
    # Adiciona ao sys.path se ainda não estiver lá
    if str(root_path) not in sys.path:
        sys.path.append(str(root_path))
        
    print(f"Raiz do projeto adicionada: {root_path}")