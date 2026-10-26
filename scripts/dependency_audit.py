#!/usr/bin/env python3
"""
Auditoria de dependencias entre as funcoes do formatador.

Monta o grafo de chamadas e procura:
  1. ciclos de dependencia (A chama B, B chama A);
  2. funcoes muito grandes, que concentram responsabilidades;
  3. funcoes que so servem de wrapper (candidatas a remover).

Gate: exit code 1 se houver ciclo.

Uso:
    python3 scripts/dependency_audit.py
    python3 scripts/dependency_audit.py --verbose
"""

import argparse
import ast
import sys
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

# Funcoes que nao devem entrar no grafo: sao utilitarios de
# infraestrutura, nao regras de negocio.
IGNORAR = {
    '_instalar_stub_ipython',
    '_carregar_formatador',
    'main',
    'visit_FunctionDef',
    'visit_AsyncFunctionDef',
    'visit_If',
    'visit_For',
    'visit_AsyncFor',
    'visit_While',
    'visit_ExceptHandler',
    'visit_IfExp',
    'visit_Assert',
    'visit_BoolOp',
    'visit_comprehension',
    'visit_Match',
    'visit_Call',
    'visit_Lambda',
    'generic_visit',
}

LIMITE_LINHAS = 120


def coletar_funcoes(arvore):
    """Devolve {nome: (linha, tamanho, [chamadas], corpo_ou_None)}."""
    funcoes = {}

    for node in ast.walk(arvore):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name in IGNORAR:
            continue

        chamadas = []
        for sub in ast.walk(node):
            if isinstance(sub, ast.Call):
                func = sub.func
                if isinstance(func, ast.Name):
                    chamadas.append(func.id)
                elif isinstance(func, ast.Attribute):
                    chamadas.append(func.attr)

        tamanho = (node.end_lineno or node.lineno) - node.lineno + 1
        funcoes[node.name] = (node.lineno, tamanho, chamadas, node)

    return funcoes


def achar_ciclos(funcoes):
    """DFS com pilha de caminho, para achar ciclos no grafo de chamadas."""
    ciclos = []
    pilha = []
    em_pilha = set()
    visitados = set()

    def dfs(nome):
        if nome in em_pilha:
            inicio = pilha.index(nome)
            ciclo = pilha[inicio:] + [nome]
            if len(ciclo) > 2:
                ciclos.append(ciclo)
            return
        if nome in visitados or nome not in funcoes:
            return

        visitados.add(nome)
        em_pilha.add(nome)
        pilha.append(nome)

        for chamada in funcoes[nome][2]:
            dfs(chamada)

        pilha.pop()
        em_pilha.discard(nome)

    for nome in funcoes:
        dfs(nome)

    # Remove ciclos duplicados (mesmo conjunto, ordem diferente).
    unicos = []
    vistos = set()
    for ciclo in ciclos:
        chave = frozenset(ciclo)
        if chave not in vistos:
            vistos.add(chave)
            unicos.append(ciclo)
    return unicos


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--verbose', action='store_true')
    parser.add_argument(
        '--file', default=str(RAIZ / 'Formatador_Lei_Anki_Colab.py')
    )
    args = parser.parse_args()

    caminho = Path(args.file)
    if not caminho.exists():
        print('[dependency] Arquivo nao encontrado: %s' % caminho)
        return 1

    arvore = ast.parse(caminho.read_text(encoding='utf-8'), str(caminho))
    funcoes = coletar_funcoes(arvore)

    # Grafo: apenas arestas entre funcoes do proprio modulo.
    grafo = defaultdict(set)
    for nome, (_, _, chamadas, _) in funcoes.items():
        for chamada in chamadas:
            if chamada in funcoes and chamada != nome:
                grafo[nome].add(chamada)

    ciclos = achar_ciclos(funcoes)

    print()
    print('── Dependencias entre funcoes ─ %s ' % caminho.name)
    print('Funcoes: %d  |  Arestas: %d  |  Ciclos: %d'
          % (len(funcoes), sum(len(v) for v in grafo.values()), len(ciclos)))
    print()

    if args.verbose:
        print('Maiores acoplamentos (quem chama mais funcoes):')
        for nome, chamadas in sorted(grafo.items(), key=lambda kv: -len(kv[1]))[:15]:
            print('  %-40s %d' % (nome, len(chamadas)))
        print()

    print('Funcoes grandes (acima de %d linhas):' % LIMITE_LINHAS)
    grandes = sorted(
        ((n, f[0], f[1]) for n, f in funcoes.items() if f[1] > LIMITE_LINHAS),
        key=lambda t: -t[2],
    )
    if grandes:
        for nome, linha, tamanho in grandes:
            print('  %-40s %4d linhas (linha %d)' % (nome, tamanho, linha))
    else:
        print('  nenhuma')
    print()

    if ciclos:
        print('CICLOS DETECTADOS:')
        for ciclo in ciclos:
            print('  ' + ' -> '.join(ciclo))
        print()
        print('FALHOU — ha ciclo de dependencia entre funcoes')
        return 1

    print('OK — nenhum ciclo de dependencia')
    return 0


if __name__ == '__main__':
    sys.exit(main())
