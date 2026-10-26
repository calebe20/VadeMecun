"""
Carrega o Formatador_Lei_Anki_Colab.py como modulo comum.

O arquivo foi escrito para rodar dentro do Google Colab: no topo ele
faz `from IPython.display import display, HTML` e no fim chama
`display(HTML(_HTML_UI))` quando detecta o runtime do Colab.

Fora do Colab, `IN_COLAB` fica False e o arquivo apenas imprime um
aviso. O que precisa ser stubado e o `IPython.display.JSON`, usado
para devolver os callbacks ao kernel.

Se o arquivo mudar e os stubs deixarem de bater, a validacao abaixo
falha com mensagem explicativa, em vez de um AttributeError obscuro.
"""

import importlib.util
import sys
import types
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
ALVO = RAIZ / 'Formatador_Lei_Anki_Colab.py'


class _FakeJSON:
    """Substituto de IPython.display.JSON.

    O kernel do Colab serializa esse objeto para JSON e o JavaScript
    le em `result.data['application/json']`. Nos testes, basta um
    dicionario comum.
    """

    def __init__(self, data):
        self.data = data


def _instalar_stub_ipython():
    """Cria um IPython.display minimo, se o IPython real nao existir."""
    try:
        import IPython.display  # noqa: F401
        return
    except ImportError:
        pass

    ipython = types.ModuleType('IPython')
    display_mod = types.ModuleType('IPython.display')

    def display(*args, **kwargs):
        return None

    def HTML(text):
        return text

    display_mod.display = display
    display_mod.HTML = HTML
    display_mod.JSON = _FakeJSON
    ipython.display = display_mod
    sys.modules['IPython'] = ipython
    sys.modules['IPython.display'] = display_mod


def _carregar_formatador():
    _instalar_stub_ipython()

    if str(RAIZ) not in sys.path:
        sys.path.insert(0, str(RAIZ))

    spec = importlib.util.spec_from_file_location('formatador_lei_anki', ALVO)
    modulo = importlib.util.module_from_spec(spec)
    sys.modules['formatador_lei_anki'] = modulo
    spec.loader.exec_module(modulo)
    return modulo


@pytest.fixture(scope='session')
def fmt():
    """Instancia do formatador, importada uma vez por sessao."""
    return _carregar_formatador()


@pytest.fixture(scope='session')
def simbolos_esperados():
    """Lista de simbolos que a suite usa. Serve de contrato."""
    return [
        'formatar_texto_legal',
        'formatar_para_anki',
        'mesclar_comentarios',
        'gerar_importacao_anki',
        'gerar_html_pdf',
        'atualizar_arquivo_anki',
        '_parse_blocos_tipados',
        '_parse_comentarios_pipe',
        '_separar_incidencia',
        '_parse_chave_comentario',
        '_processar_callback',
        '_mesclar_callback',
    ]
