#!/usr/bin/env python3
"""
Auditoria de complexidade ciclomatica estimada.

Conta, por funcao, os predicados (if, for, while, except, case,
ternario, and, or, comprehensions) e estima:

    M = predicados + 1

A contagem para na fronteira de funcao aninhada: cada funcao e
medida de forma independente, como na auditoria do EstudoPro.

Gate: exit code 1 se alguma funcao alvo exceder o limite.

Uso:
    python3 scripts/complexity_audit.py            # auditoria completa
    python3 scripts/complexity_audit.py --verbose  # mostra todas
    python3 scripts/complexity_audit.py --limit 12 # muda o gate
"""

import argparse
import ast
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

# Funcoes que concentram a logica de negocio. Sao o alvo do gate.
FUNCOES_ALVO = {
    'formatar_texto_legal',
    'formatar_para_anki',
    'mesclar_comentarios',
    'gerar_importacao_anki',
    'gerar_html_pdf',
    'atualizar_arquivo_anki',
    '_parse_blocos_tipados',
    '_parse_comentarios_pipe',
    '_parse_chave_comentario',
    '_separar_incidencia',
    '_parse_secoes_artigos',
    '_processar_callback',
    '_mesclar_callback',
    '_limpar_anotacoes',
    '_extrair_incidencia',
    '_extrair_estrutura',
    '_juntar_linhas_quebradas',
    '_dividir_fontes',
    '_parece_lista_de_bancas',
    '_eh_dispositivo_legal',
    '_normalizar_ordinais',
    '_hifenizar_palavra',
    '_hifenizar_html',
    '_serializar_anki_export',
    '_detalhes_blocos',
    '_empacotar_cartoes',
}

LIMITE_PADRAO = 15

# Funcoes que ja excedem o limite no momento em que a auditoria foi
# criada. Servem de baseline: a regra e nao piorar, nao reescrever o
# arquivo inteiro. Remova uma entrada aqui quando refatorar a funcao.
#
# Formato: funcao -> complexidade maxima aceita hoje.
BASELINE = {
    'mesclar_comentarios': 38,
    '_parse_secoes_artigos': 37,
    '_empacotar_cartoes': 29,
    '_parse_blocos_tipados': 24,
    'gerar_html_pdf': 24,
    'formatar_texto_legal': 23,
    'gerar_importacao_anki': 21,
    'atualizar_arquivo_anki': 21,
    'formatar_para_anki': 20,
}

# Predicados que aumentam a complexidade.
_NOS = (
    ast.If,
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.ExceptHandler,
    ast.IfExp,
    ast.Assert,
    ast.With,
    ast.AsyncWith,
)


class Contador(ast.NodeVisitor):
    """Conta os predicados de uma funcao, sem entrar em funcoes aninhadas."""

    def __init__(self):
        self.total = 0

    def visit_FunctionDef(self, node):
        # Funcao aninhada: nao entra no corpo. Cada funcao e medida
        # de forma independente.
        return

    def visit_AsyncFunctionDef(self, node):
        return

    def visit_Lambda(self, node):
        return

    def visit_If(self, node):
        self.total += 1
        self.generic_visit(node)

    def visit_For(self, node):
        self.total += 1
        self.generic_visit(node)

    def visit_AsyncFor(self, node):
        self.total += 1
        self.generic_visit(node)

    def visit_While(self, node):
        self.total += 1
        self.generic_visit(node)

    def visit_ExceptHandler(self, node):
        self.total += 1
        self.generic_visit(node)

    def visit_IfExp(self, node):
        self.total += 1
        self.generic_visit(node)

    def visit_Assert(self, node):
        self.total += 1
        self.generic_visit(node)

    def visit_BoolOp(self, node):
        # `a and b` conta como n-1 predicados.
        self.total += max(0, len(node.values) - 1)
        self.generic_visit(node)

    def visit_comprehension(self, node):
        self.total += 1 + len(node.ifs)
        self.generic_visit(node)

    def visit_Match(self, node):
        # `case` e um predicado por ramificacao.
        self.total += len(node.cases)
        self.generic_visit(node)

    def visit_Call(self, node):
        # `x if y else z` ja conta em visit_IfExp. `any()`/`all()`
        # com gerador sao contados pela comprehension.
        self.generic_visit(node)


def nome_funcao(node):
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return node.name
    return None


def coletar(arvore):
    """Devolve [(nome, predicados, linha, tamanho)] de todas as funcoes."""
    resultados = []

    def visit(node):
        nome = nome_funcao(node)
        if nome:
            contador = Contador()
            contador.raiz = None
            # Conta os predicados do corpo da funcao, sem as funcoes
            # aninhadas (visit_FunctionDef cuida disso).
            contador.generic_visit(node)
            resultados.append((
                nome,
                contador.total,
                node.lineno,
                (node.end_lineno or node.lineno) - node.lineno + 1,
            ))
        for filho in ast.iter_child_nodes(node):
            visit(filho)

    visit(arvore)
    return resultados


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=LIMITE_PADRAO)
    parser.add_argument('--verbose', action='store_true')
    parser.add_argument(
        '--file', default=str(RAIZ / 'Formatador_Lei_Anki_Colab.py')
    )
    args = parser.parse_args()

    caminho = Path(args.file)
    if not caminho.exists():
        print('[complexity] Arquivo nao encontrado: %s' % caminho)
        return 1

    arvore = ast.parse(caminho.read_text(encoding='utf-8'), str(caminho))
    funcoes = coletar(arvore)

    alvo = [f for f in funcoes if f[0] in FUNCOES_ALVO]
    outras = [f for f in funcoes if f[0] not in FUNCOES_ALVO]

    if args.verbose:
        alvo = funcoes

    if not alvo:
        print('[complexity] Nenhuma funcao alvo encontrada em %s' % caminho.name)
        return 1

    largura_nome = max(len(f[0]) for f in alvo) + 2
    print()
    print('── Complexidade Cicliomatica ─ %s ' % caminho.name)
    print('%-*s  %4s  %5s  %s' % (largura_nome, 'Funcao', 'M', 'Linhas', 'Status'))
    print('─' * (largura_nome + 26))

    violacoes = []
    for nome, predicados, linha, tamanho in sorted(alvo, key=lambda f: -f[1]):
        complexidade = predicados + 1
        aceito = BASELINE.get(nome, args.limit)
        if complexidade > aceito:
            status = 'VERMELHO'
            violacoes.append((nome, complexidade, linha, aceito))
        elif complexidade > 10:
            status = 'AMARELO'
        else:
            status = 'VERDE'
        nota = ''
        if nome in BASELINE:
            nota = '  (baseline %d)' % BASELINE[nome]
        print('%-*s  %4d  %5d  %s (linha %d)%s'
              % (largura_nome, nome, complexidade, tamanho, status, linha, nota))

    print('─' * (largura_nome + 26))
    print('Gate: M <= %d  |  Funcoes auditadas: %d  |  Total no arquivo: %d'
          % (args.limit, len(alvo), len(funcoes)))

    if violacoes:
        print()
        for nome, complexidade, linha, aceito in violacoes:
            print('VERMELHO  %s tem M=%d (linha %d), acima do aceito %d'
                  % (nome, complexidade, linha, aceito))
        print()
        print('FALHOU — uma ou mais funcoes pioraram em relacao ao baseline')
        return 1

    print()
    print('OK — todas as funcoes dentro do limite')
    return 0


if __name__ == '__main__':
    sys.exit(main())
