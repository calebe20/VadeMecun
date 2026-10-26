# @title 🎓 FORMATADOR DE LEI - ANKI + PDF
# Interface visual moderna para Google Colab (Dark Theme + Gold Accents)
#
# ADAPTACAO: o campo "Mesclar Comentarios da IA" agora aceita os blocos
# tipados que a IA devolve seguindo o PROMPT_IA.md:
#
#     TIPO|ALVO|SUBTITULO|RELEVANCIA
#     corpo...
#
# Tipos: COMENTARIO, TABELA, ESQUEMA, QUESTAO, JURISPRUDENCIA, DOUTRINA, NOTA.
#
# O formato antigo (Art. 15|texto) continua funcionando normalmente.

import re

try:
    import pyphen
    _HIFENIZADOR = pyphen.Pyphen(lang='pt_BR')
except Exception:
    # No Colab o pyphen nao vem instalado. Sem ele a justificacao em
    # coluna estreita abre buracos entre as palavras, mas o documento
    # continua sendo gerado normalmente.
    _HIFENIZADOR = None
    try:
        import subprocess
        import sys
        subprocess.run(
            [sys.executable, '-m', 'pip', 'install', '-q', 'pyphen'],
            check=True, capture_output=True)
        import pyphen
        _HIFENIZADOR = pyphen.Pyphen(lang='pt_BR')
    except Exception:
        _HIFENIZADOR = None
import html as html_lib
from html.parser import HTMLParser

import IPython
from IPython.display import display, HTML

# ============================================================
# LÓGICA DE FORMATAÇÃO DO TEXTO
# ============================================================

def _remover_parenteses_balanceado(texto, padrao_inicio):
    """
    Remove anotações do tipo '(Redação dada... (90) dias...)' respeitando
    parênteses aninhados, em vez de parar no primeiro ')' encontrado
    (o que cortava o texto no lugar errado quando a própria anotação
    continha parênteses internos, ex: 'com efeitos a partir de 90
    (noventa) dias após a publicação)').
    """
    m = re.search(padrao_inicio, texto, re.IGNORECASE)
    while m:
        start = m.start()
        idx_abre = texto.index('(', start)
        depth = 0
        i = idx_abre
        fim = None
        while i < len(texto):
            if texto[i] == '(':
                depth += 1
            elif texto[i] == ')':
                depth -= 1
                if depth == 0:
                    fim = i
                    break
            i += 1
        if fim is None:
            break
        fim2 = fim + 1
        if fim2 < len(texto) and texto[fim2] in '.:':
            fim2 += 1
        texto = texto[:start] + texto[fim2:]
        m = re.search(padrao_inicio, texto, re.IGNORECASE)
    return texto


_PADRAO_ANOTACAO = (
    r'\s*\('
    r'(?:'
    r'Incluíd[oa]|Redação\s+(?:d[oa]\s+\w+\s+)?dada|Revogad[oa]|Acrescid[oa]|Acrescentad[oa]|'
    r'Alterad[oa]|Inserid[oa]|Renumerad[oa]|Vigência|Vide|Regulamento|'
    r'Supressão de texto|Vetad[oa]|'
    r'(?:Artigo|Parágrafo|Inciso|Alínea|Item)\s+(?:acrescentad[oa]|incluíd[oa]|alterad[oa]|revogad[oa])'
    r')'
)


def _normalizar_ordinais(texto):
    # Converte o "o" usado como ordinal nos marcadores e referências.
    # Não altera o restante das palavras nem o corpo da norma.
    return re.sub(r'(\barts?\.\s*\d+(?:\.\d+)*|§{1,2}\s*\d+)\s*[oO]\b',
                  r'\1º', texto, flags=re.IGNORECASE)


def _limpar_anotacoes(texto):
    # CORRIGIDO: usa remoção com parênteses balanceados em vez de regex
    # gulosa simples, que cortava no primeiro ')' e quebrava anotações
    # que continham parênteses internos (datas, prazos etc).
    texto = _remover_parenteses_balanceado(texto, _PADRAO_ANOTACAO)
    texto = re.sub(r'\s*Vide\s+Lei\s+n[º°]\s*[\d\.]+.*?(?=\s{2,}|$)', '', texto)
    texto = re.sub(r'\s+Vigência\s*$', '', texto)
    texto = re.sub(r'\s{2,}', ' ', texto).strip()
    # CORRIGIDO: espaço antes do 'o' agora é opcional (\s*), pois o caso
    # mais comum copiado do planalto.gov.br é "1o"/"2o" SEM espaço.
    # Antes a regex exigia \s+ e nunca convertia para º.
    texto = re.sub(r'^(Art\.\s*\d+)\s*[oO]\b', r'\1º', texto)
    texto = re.sub(r'^(§\s*\d+)\s*[oO]\b', r'\1º', texto)
    return _normalizar_ordinais(texto)


def _linha_contem_vetado(linha):
    return bool(re.search(r'\(vetad[oa]\)', linha, re.IGNORECASE))


def _normalizar_espacos(texto):
    texto = texto.replace('\t', ' ')
    texto = re.sub(r' {2,}', ' ', texto)
    texto = re.sub(r' +([;,\.:])', r'\1', texto)
    return texto.strip()


def _colapsar_espacos(texto):
    """
    Remove espacos duplicados do texto que vem do material.

    O material da IA traz as marcacoes de banca com espacos duplos:
    '(PGM-Fortaleza/CE-2017)  (PGM-POA/RS-2022)'. Isso aparece no
    texto limpo e no HTML, com um espaco a mais entre as marcacoes.
    """
    if not texto:
        return texto
    texto = re.sub(r'[ \t\u00a0]{2,}', ' ', texto)
    texto = re.sub(r' ?\n ?', '\n', texto)
    return texto.strip()


def _eh_titulo_descritivo(linha):
    t = _limpar_anotacoes(linha.strip())
    if not t: return False
    if t == t.upper(): return False
    if re.match(r'^(Art\.|§|Parágrafo|Pena\s)', t, re.IGNORECASE): return False
    if re.match(r'^[IVXLCDM]+\s*[-–—]', t): return False
    if re.match(r'^[a-z]\)', t): return False
    if re.match(r'^\d+[\.\)]\s', t): return False
    if not t[0].isupper(): return False
    if len(t.split()) > 15: return False
    if t[-1] in '.;:,': return False
    if 'Art.' in t: return False
    return True


def _eh_inicio_dispositivo_ou_estrutura(s):
    """Linhas que SEMPRE iniciam um novo bloco e nunca devem ser fundidas
    com a linha anterior (Art., §, inciso, alínea, marcador estrutural ou
    título TUDO EM MAIÚSCULAS)."""
    return bool(re.match(
        r'^(Art\.?\s*\d|§|Parágrafo\s|TÍTULO\s|CAPÍTULO\s|Seção\s|Subseção\s|'
        r'[IVXLCDM]+\s*[-–—]|[a-z]\)|\d+[º°]?\)|Pena\s)',
        s, re.IGNORECASE
    )) or (s == s.upper() and re.search(r'[A-Za-zÀ-Úà-ú]', s))

def _normalizar_marcador_inciso(linha):
    """
    Padroniza somente o marcador inicial de um inciso.

    Reconhece:
        II - texto
        ii - texto
        II – texto
        II — texto
        II ‑ texto
        II − texto
        Ⅱ - texto

    Também tolera caracteres invisíveis junto ao numeral
    e ao separador.

    O conteúdo depois do marcador não é reescrito.
    """
    import unicodedata

    padrao = (
        r'^[\s\u200b\u200c\u200d\ufeff]*'
        r'(?P<num>'
        r'(?:[IVXLCDM\u2160-\u217f]'
        r'[\u200b\u200c\u200d\ufeff]*)+'
        r')'
        r'(?P<sufixo>-[A-Za-z])?'
        r'[\s\u200b\u200c\u200d\ufeff]*'
        r'[-\u00ad\u2010-\u2015\u2212]'
        r'[\s\u200b\u200c\u200d\ufeff]*'
        r'(?P<texto>.*)$'
    )

    match = re.match(
        padrao,
        linha,
        flags=re.IGNORECASE
    )

    if not match:
        return linha

    numero = re.sub(
        r'[\u200b\u200c\u200d\ufeff]',
        '',
        match.group('num')
    )

    numero = unicodedata.normalize(
        'NFKC',
        numero
    ).upper()

    sufixo = (match.group('sufixo') or '').upper()
    texto = match.group('texto')

    return f'{numero}{sufixo} - {texto}'



def _juntar_linhas_quebradas(texto):
    """
    Une continuações de dispositivos sem incorporar
    o início do dispositivo seguinte.

    Normaliza os marcadores dos incisos antes de verificar
    onde cada novo dispositivo começa.
    """
    linhas = [
        _normalizar_marcador_inciso(linha)
        for linha in texto.split('\n')
    ]

    marcador_estrutural = re.compile(
        r'^(TÍTULO\s|CAPÍTULO\s|Seção\s|Subseção\s)',
        re.IGNORECASE
    )

    saida = []
    i = 0
    n = len(linhas)

    while i < n:
        bruta = linhas[i]
        s = bruta.strip()

        if not s:
            saida.append(bruta)
            i += 1
            continue

        if marcador_estrutural.match(s):
            saida.append(bruta)
            i += 1
            continue

        if _eh_inicio_dispositivo_ou_estrutura(s):
            buffer = s
            j = i + 1

            while j < n:
                prox = linhas[j].strip()

                if not prox:
                    break

                if _eh_inicio_dispositivo_ou_estrutura(prox):
                    break

                if marcador_estrutural.match(prox):
                    break

                buffer += ' ' + prox
                j += 1

            saida.append(buffer)
            i = j
            continue

        saida.append(bruta)
        i += 1

    return '\n'.join(saida)



def _eh_dispositivo_legal(linha):
    """Distingue dispositivos de títulos sem mudar o texto do dispositivo."""
    return bool(re.match(
        r'^(?:Art\.?\s*\d|§|Par[aá]grafo\b|Pena\b|'
        r'[IVXLCDM]+\s*[-–—]|[a-z]\)|\d+[º°ª]?\s*[.)])',
        linha.strip(), re.IGNORECASE
    ))


def _extrair_estrutura(linha):
    """Reconhece títulos com nome na mesma linha ou separado na próxima."""
    m = re.match(r'^(TÍTULO|CAPÍTULO|SEÇÃO|SUBSEÇÃO)\b\s*(.*)$',
                 linha.strip(), re.IGNORECASE)
    if not m:
        return None
    tipos = {'TÍTULO':'T', 'CAPÍTULO':'C', 'SEÇÃO':'S', 'SUBSEÇÃO':'SUB'}
    restante = m.group(2).strip()
    numero = re.match(
        r'^(?:[IVXLCDM]+|\d+[º°ªoO]?|ÚNIC[OA])(?=\s|$|[-–—.:])'
        r'\s*(?:[-–—.:]\s*)?(.*)$', restante, re.IGNORECASE
    )
    nome = numero.group(1).strip() if numero else restante.lstrip('-–—: ').strip()
    return tipos[m.group(1).upper()], nome




def _eh_dispositivo_legal(linha):
    """Distingue dispositivos de títulos sem mudar o texto do dispositivo."""
    return bool(re.match(
        r'^(?:Art\.?\s*\d|§|Par[aá]grafo\b|Pena\b|'
        r'[IVXLCDM]+\s*[-–—]|[a-z]\)|\d+[º°ª]?\s*[.)])',
        linha.strip(), re.IGNORECASE
    ))


def _extrair_estrutura(linha):
    """Reconhece títulos com nome na mesma linha ou separado na próxima."""
    m = re.match(r'^(TÍTULO|CAPÍTULO|SEÇÃO|SUBSEÇÃO)\b\s*(.*)$',
                 linha.strip(), re.IGNORECASE)
    if not m:
        return None
    tipos = {'TÍTULO':'T', 'CAPÍTULO':'C', 'SEÇÃO':'S', 'SUBSEÇÃO':'SUB'}
    restante = m.group(2).strip()
    numero = re.match(
        r'^(?:[IVXLCDM]+|\d+[º°ªoO]?|ÚNIC[OA])(?=\s|$|[-–—.:])'
        r'\s*(?:[-–—.:]\s*)?(.*)$', restante, re.IGNORECASE
    )
    nome = numero.group(1).strip() if numero else restante.lstrip('-–—: ').strip()
    return tipos[m.group(1).upper()], nome


def formatar_texto_legal(texto):
    texto = _juntar_linhas_quebradas(texto)
    linhas = texto.split('\n')
    resultado = []
    i = 0
    dentro_de_artigo = False

    while i < len(linhas):
        linha = linhas[i].strip()
        if not linha or _linha_contem_vetado(linha):
            i += 1
            continue

        estrutura = _extrair_estrutura(linha)
        if estrutura:
            tipo, nome = estrutura
            # Um nome que já está no cabeçalho nunca consome a próxima linha.
            if not nome:
                j = i + 1
                while j < len(linhas) and not linhas[j].strip():
                    j += 1
                if j < len(linhas):
                    proxima = linhas[j].strip()
                    # Artigos, parágrafos, incisos, alíneas e outros títulos
                    # devem continuar no fluxo mesmo quando o nome falta.
                    if not _eh_dispositivo_legal(proxima) and not _extrair_estrutura(proxima):
                        nome = proxima
                        i = j
            nome = _limpar_anotacoes(nome) if nome else linha
            if resultado:
                resultado.extend(['', ''])
            resultado.extend([f'#{tipo}:{nome.upper()}', ''])
            dentro_de_artigo = False
            i += 1
            continue

        linha = _normalizar_espacos(_limpar_anotacoes(linha))
        if not linha:
            i += 1
            continue
        if re.match(r'^([IVXLCDM]+\s*[-–—]|[a-z]\)|§\s*\d+[º°.]?|Parágrafo único\.?)\s*$', linha, re.IGNORECASE):
            i += 1
            continue

        if _eh_dispositivo_legal(linha):
            if re.match(r'^Art\.?\s*\d', linha, re.IGNORECASE):
                dentro_de_artigo = True
            # A incidencia do dispositivo vem entre parenteses no fim
            # do texto. Ela sobe para uma linha propria, ACIMA do
            # dispositivo, para que a banca veja a incidencia antes
            # de ler a regra.
            corpo, incidencia = _separar_incidencia(linha)
            if incidencia:
                resultado.append('#INC:' + incidencia)
            resultado.append(corpo)
        elif not dentro_de_artigo and (
                (linha == linha.upper() and re.search(r'[A-Za-zÀ-Ú]', linha))
                or _eh_titulo_descritivo(linha)):
            # A inferência de título só é permitida fora do corpo de um artigo.
            if resultado:
                resultado.extend(['', ''])
            resultado.extend([f'#S:{linha.upper()}', ''])
        else:
            resultado.append(linha)
        i += 1

    return re.sub(r'\n{4,}', '\n\n\n', '\n'.join(resultado)).strip()


# A incidencia e uma sequencia de grupos entre parenteses no fim da
# linha: '(PGESP-2002) (MPSP-2005/2008/2013)'.
_RE_INCIDENCIA = re.compile(
    r'\s*((?:\([^()]+\)\s*)+)$'
)


def _separar_incidencia(linha):
    """
    Separa a incidencia do dispositivo, que vem entre parenteses no
    fim do texto.

    'Art. 3o Somente sera admitido ... (PGESP-2002) (MPSP-2013)'
    vira
        ('Art. 3o Somente sera admitido ...', 'PGESP-2002; MPSP-2013')

    Devolve (texto_do_dispositivo, incidencia). A incidencia vem sem
    os parenteses e com as bancas separadas por '; '.
    """
    m = _RE_INCIDENCIA.search(linha)
    if not m:
        return linha, ''

    # So e incidencia se todas as partes entre parenteses parecerem
    # marcadores de banca. Qualquer outro parenteses (nota do
    # planalto, "Revogado", etc.) fica onde esta.
    partes = [p.strip() for p in re.findall(r'\(([^()]*)\)', m.group(1))]
    if not partes:
        return linha, ''
    for parte in partes:
        if not _RE_ITEM_BANCA.match(parte):
            return linha, ''

    itens = []
    for parte in partes:
        for item in _dividir_fontes(parte):
            if item and item not in itens:
                itens.append(item)

    if not itens:
        return linha, ''

    texto = linha[:m.start()].rstrip()
    return texto, '; '.join(itens)


# ============================================================
# GERAÇÃO HTML COM HIERARQUIA E ESPAÇAMENTO CONFIGURÁVEL
# ============================================================

def formatar_para_anki(texto_formatado,
                      espacamento=2,
                      indent_par=2,
                      indent_inc=8,
                      indent_ali=8,
                      entrelinha=1.0):
    entrelinha = max(1.0, min(2.0, float(entrelinha)))
    linhas = texto_formatado.split('\n')
    blocos = []

    stats = {
        'artigos': 0,
        'incisos': 0,
        'alineas': 0,
        'paragrafos': 0
    }

    for linha in linhas:
        linha = _normalizar_marcador_inciso(
            linha.strip()
        )

        if not linha:
            continue

        mb = f"margin-bottom:{espacamento}px;line-height:{entrelinha}"

        if linha.startswith('#'):
            tipo, _, nome = linha[1:].partition(':')

            if not nome:
                nome = tipo
                tipo = 'S'

            nome = nome.strip()

            if tipo == 'SUB':
                blocos.append(
                    '<span style="display:block;'
                    'padding-left:14px;'
                    'margin-bottom:10px;'
                    'font-weight:bold;'
                    'color:#a8d8ea;">'
                    f'[{nome}]</span>'
                )

            elif tipo == 'S':
                blocos.append(
                    '<span style="display:block;'
                    'padding-left:0px;'
                    'margin-bottom:10px;'
                    'font-weight:bold;'
                    'color:#4a0000;">'
                    f'[{nome}]</span>'
                )

            elif tipo == 'INC':
                # A incidencia do dispositivo: fica logo ACIMA do
                # dispositivo, em linha propria e menor.
                # O tamanho e padronizado pelo painel de fontes.
                marcas = _marcas_html(
                    nome, _rel(_fonte('marcas'), _fonte('incidencia')))
                blocos.append(
                    '<span class="incidencia-dispositivo" '
                    'style="display:block;'
                    'padding-left:0px;'
                    'margin-bottom:2px;'
                    f'font-size:{_fonte("incidencia")}%;">'
                    f'{marcas}</span>'
                )

            continue

        if re.match(r'^Art\.', linha):
            match = re.match(
                r'^(Art\.\s+[\d\w\-º°\.]+)',
                linha
            )

            if match:
                art_num = match.group(1)
                resto = linha[len(art_num):].strip()

                conteudo = (
                    f'<b>{art_num}</b> {resto}'
                    if resto
                    else f'<b>{art_num}</b>'
                )

            else:
                conteudo = linha

            blocos.append(
                '<span data-dispositivo="artigo" style="display:block;'
                f'padding-left:0px;{mb}">'
                f'{conteudo}</span>'
            )

            stats['artigos'] += 1

        elif re.match(r'^§', linha):
            match = re.match(
                r'^(§\s*\d+(?:[º°]\.?|\.))(.*)',
                linha
            )

            if match:
                par_num = match.group(1)
                resto = match.group(2).strip()

                conteudo = (
                    f'<b>{par_num}</b> {resto}'
                    if resto
                    else f'<b>{par_num}</b>'
                )

            else:
                conteudo = linha

            blocos.append(
                '<span data-dispositivo="paragrafo" style="display:block;'
                f'padding-left:{indent_par}px;{mb}">'
                f'{conteudo}</span>'
            )

            stats['paragrafos'] += 1

        elif re.match(
            r'^Parágrafo único',
            linha,
            re.IGNORECASE
        ):
            blocos.append(
                '<span data-dispositivo="paragrafo" style="display:block;'
                f'padding-left:{indent_par}px;{mb}">'
                f'{linha}</span>'
            )

            stats['paragrafos'] += 1

        elif re.match(
            r'^[IVXLCDM]+(?:-[A-Za-z])?\s*[-–—]',
            linha
        ):
            match = re.match(
                r'^([IVXLCDM]+(?:-[A-Za-z])?)'
                r'(\s*[-–—]\s*)(.*)',
                linha
            )

            if match:
                numeral = match.group(1)
                separador = match.group(2)
                texto_resto = match.group(3)

                conteudo = (
                    f'<b>{numeral}</b>'
                    f'{separador}{texto_resto}'
                )

            else:
                conteudo = linha

            recuo = indent_inc

            blocos.append(
                '<span data-dispositivo="inciso" style="display:block;'
                f'padding-left:{recuo}px;{mb}">'
                f'{conteudo}</span>'
            )

            stats['incisos'] += 1

        elif re.match(r'^[a-z]\)', linha):
            blocos.append(
                '<span data-dispositivo="alinea" style="display:block;'
                f'padding-left:{indent_ali}px;{mb}">'
                f'{linha}</span>'
            )

            stats['alineas'] += 1

        elif (
            re.match(r'^\d+[\u00ba°ªª]º?\)', linha)
            or re.match(r'^\d+°\)', linha)
        ):
            recuo = indent_inc

            blocos.append(
                '<span data-dispositivo="inciso" style="display:block;'
                f'padding-left:{recuo}px;{mb}">'
                f'{linha}</span>'
            )

            stats['incisos'] += 1

        else:
            blocos.append(
                '<span data-dispositivo="texto" style="display:block;'
                f'padding-left:0px;{mb}">'
                f'{linha}</span>'
            )

    html_final = '\n'.join(blocos)

    return html_final, stats


# ============================================================
# MESCLAGEM DE COMENTÁRIOS DA IA
# Suporta comentários gerais e comentários de elementos específicos:
#   Art. 19|comentário geral
#   Art. 19, inciso II|comentário do inciso
#   Art. 19, § 1º|comentário do parágrafo
#   Art. 19, § 1º, inciso III|comentário do inciso do parágrafo
#   Art. 19, inciso II, alínea a|comentário da alínea
# ============================================================

def _normalizar_num_artigo(valor):
    valor = valor.strip()
    valor = re.sub(r'[º°\.]+$', '', valor)
    return re.sub(r'[º°]', '', _normalizar_ordinais('Art. ' + valor)[5:]).replace('.', '').replace(' ', '').upper()


def _normalizar_romano(valor):
    return valor.strip().upper()


def _normalizar_alinea(valor):
    return valor.strip().lower().rstrip(')')


def _parse_chave_comentario(chave):
    """
    Converte a chave do PIPE numa posição hierárquica:
      (artigo, parágrafo, inciso, alínea)

    Exemplos aceitos:
      Art. 6º
      Art. 6º, inciso I
      Art. 6º, § 1º
      Art. 6º, § 1º, inciso II
      Art. 6º, inciso XXIII, alínea a
      Art. 6º, parágrafo único
    """
    chave = _normalizar_ordinais(chave)
    m_art = re.match(
        r'^\s*Art\.\s*([\d.]+(?:[º°]?\s*-[A-Za-z])?)[º°.]*(?=\s*(?:,|$))',
        chave, re.IGNORECASE
    )
    if not m_art:
        return None

    art = _normalizar_num_artigo(m_art.group(1))
    restante = chave[m_art.end():]
    par = inc = ali = None

    m_par_unico = re.search(r'(?:§\s*)?par[aá]grafo\s+[úu]nico', restante, re.IGNORECASE)
    if m_par_unico:
        par = 'unico'
    else:
        m_par = re.search(r'(?:§|par[aá]grafo)\s*(\d+)[º°.]?', restante, re.IGNORECASE)
        if m_par:
            par = str(int(m_par.group(1)))

    m_inc = re.search(r'inciso\s+([IVXLCDM]+(?:-[A-Za-z])?)\b', restante, re.IGNORECASE)
    if m_inc:
        inc = _normalizar_romano(m_inc.group(1))

    m_ali = re.search(r'al[ií]nea\s+([a-z])\)?\b', restante, re.IGNORECASE)
    if m_ali:
        ali = _normalizar_alinea(m_ali.group(1))

    return (art, par, inc, ali)


def _rotulo_alvo(alvo):
    art, par, inc, ali = alvo
    partes = [f'Art. {art}']
    if par == 'unico':
        partes.append('parágrafo único')
    elif par is not None:
        partes.append(f'§ {par}º')
    if inc is not None:
        partes.append(f'inciso {inc}')
    if ali is not None:
        partes.append(f'alínea {ali}')
    return ', '.join(partes)


# ============================================================
# BLOCOS TIPADOS (output do prompt de IA)
# ============================================================

# Cada bloco começa com uma linha de cabecalho:
#   TIPO|ALVO|SUBTITULO|RELEVANCIA
# e o corpo vem nas linhas seguintes, ate o proximo cabecalho.
#
# Tipos: COMENTARIO, TABELA, ESQUEMA, QUESTAO, JURISPRUDENCIA,
#        DOUTRINA, NOTA.
#
# O formato antigo (Art. 15|texto) continua funcionando: vira
# COMENTARIO.

_TIPOS_BLOCO = (
    'COMENTARIO', 'TABELA', 'ESQUEMA', 'QUESTAO', 'JURISPRUDENCIA',
    'DOUTRINA', 'NOTA', 'MARCAS',
)

_ROTULOS_TIPO = {
    'COMENTARIO': 'Comentário',
    'TABELA': 'Tabela',
    'ESQUEMA': 'Esquema',
    'QUESTAO': 'Questão',
    'JURISPRUDENCIA': 'Jurisprudência',
    'DOUTRINA': 'Doutrina',
    'NOTA': 'Nota',
    'MARCAS': 'Marcas',
}

# Ordem de exibicao dentro de um mesmo dispositivo.
_ORDEM_TIPOS = {
    'QUESTAO': 0,
    'COMENTARIO': 1,
    'TABELA': 2,
    'ESQUEMA': 3,
    'JURISPRUDENCIA': 4,
    'DOUTRINA': 5,
    'NOTA': 6,
}

# ============================================================
# TAMANHO DAS FONTES (padronizacao)
# ============================================================
#
# MODELO DE TAMANHO
#
#   "bloco", "juris" e "questao" sao ABSOLUTOS: percentual da fonte
#   do cartao (a fonte do texto legal). 100 = mesmo tamanho da lei.
#   Eles definem o container de cada tipo de bloco.
#
#   Os demais sao RELATIVOS ao container em que vivem. Ex.: "corpo"
#   a 100 mantem o mesmo tamanho do container; a 120 o amplia 20%.
#
#   "marcas" e "incidencia" sao absolutos, porque vivem no texto
#   legal (fora de qualquer bloco de comentario).
#
# O tamanho e gravado como estilo INLINE no HTML gerado. Assim o
# resultado e identico no Anki e no PDF, qualquer que seja o CSS do
# deck: o inline sempre ganha da folha de estilo.

_CONFIG_FONTE_PADRAO = {
    'bloco':      94,   # container: comentario, nota, tabela, esquema
    'juris':      80,   # container: jurisprudence e doutrina
    'questao':    80,   # container: questoes
    'corpo':     100,   # corpo do bloco (relativo ao container)
    'ident':      80,   # linha de identificacao do julgado
    'meta':       66,   # linha de incidencia do bloco
    'fontes':     72,   # lista de bancas das fontes
    'gabarito':   80,   # gabarito da questao
    'marcas':     65,   # marcadores de banca no texto legal
    'incidencia': 76,   # incidencia do dispositivo (linha acima)
    'esquema':    86,   # diagramas
    'tabela':     88,   # tabelas
}

# Estado atual (alterado pelo painel da interface).
_CONFIG_FONTE = dict(_CONFIG_FONTE_PADRAO)

# Container de cada tipo de bloco.
_FONTE_CONTAINER_TIPO = {
    'COMENTARIO': 'bloco',
    'NOTA': 'bloco',
    'TABELA': 'bloco',
    'ESQUEMA': 'bloco',
    'MARCAS': 'bloco',
    'QUESTAO': 'questao',
    'JURISPRUDENCIA': 'juris',
    'DOUTRINA': 'juris',
}

_LIMITE_FONTE = (30, 200)


def _configurar_fontes(valores=None):
    """
    Aplica o painel de tamanhos de fonte.

    `valores` pode ser um dicionario {chave: percentual} ou uma lista
    na ordem de _CONFIG_FONTE_PADRAO. Valores fora da faixa sao
    ajustados para o limite permitido.
    """
    global _CONFIG_FONTE

    novo = dict(_CONFIG_FONTE_PADRAO)

    if isinstance(valores, dict):
        pares = list(valores.items())
    elif isinstance(valores, (list, tuple)):
        pares = list(zip(_CONFIG_FONTE_PADRAO.keys(), valores))
    else:
        pares = []

    for chave, valor in pares:
        if chave not in novo:
            continue
        try:
            numero = float(valor)
        except (TypeError, ValueError):
            continue
        numero = max(_LIMITE_FONTE[0], min(_LIMITE_FONTE[1], numero))
        novo[chave] = numero

    _CONFIG_FONTE = novo
    return dict(_CONFIG_FONTE)


def _fonte(chave):
    """Percentual configurado para um elemento."""
    return _CONFIG_FONTE.get(chave, _CONFIG_FONTE_PADRAO.get(chave, 100))


def _container_absoluto(tipo):
    """Tamanho absoluto (em % da fonte do cartao) do container do bloco."""
    chave = _FONTE_CONTAINER_TIPO.get(tipo, 'bloco')
    return _fonte(chave)


def _abs(chave, base):
    """
    Tamanho absoluto (em % da fonte do cartao) de um elemento.

    `base` e o tamanho absoluto do container do elemento.
    """
    return float(base) * _fonte(chave) / 100.0


def _rel(valor_absoluto, pai_absoluto):
    """
    Converte um tamanho absoluto em percentual RELATIVO ao pai.

    O CSS resolve 'font-size' percentual em relacao ao tamanho
    computado do pai. Dividir pelo pai garante que o tamanho final
    pedido seja alcancado, mesmo com elementos aninhados.
    """
    try:
        pai = float(pai_absoluto)
    except (TypeError, ValueError):
        pai = 100.0
    if not pai:
        pai = 100.0
    return 'font-size:%s%%;' % round(float(valor_absoluto) * 100.0 / pai, 2)

_RE_CABECALHO_TIPADO = re.compile(
    r'^(?P<tipo>' + '|'.join(_TIPOS_BLOCO) + r')\s*\|(?P<resto>.*)$',
    re.IGNORECASE,
)


def _remover_cercas_codigo(texto):
    """
    Remove a cerca de codigo (``` ... ```) que delimita o output da IA.

    O prompt pede que a IA entregue tudo dentro de um unico bloco de
    codigo, para que a copia seja segura. O conteudo interno e
    preservado; apenas a primeira e a ultima linha da cerca saem.
    """
    if not texto:
        return texto
    linhas = texto.splitlines()
    inicio = 0
    while inicio < len(linhas) and not linhas[inicio].strip():
        inicio += 1
    if inicio < len(linhas) and linhas[inicio].strip().startswith('```'):
        linhas.pop(inicio)
    fim = len(linhas) - 1
    while fim >= 0 and not linhas[fim].strip():
        fim -= 1
    if fim >= 0 and linhas[fim].strip().startswith('```'):
        del linhas[fim]
    return '\n'.join(linhas)


_RE_FONTES = re.compile(
    r'(?:^|(?<=[.;!?])\s)(?:FONTES|FONTE|Fontes|Fonte)\s*[:：]\s*(.*)$'
)


def _dividir_fontes(texto):
    """Quebra a lista de bancas em itens individuais."""
    partes = re.split(r'[;,\n\u00b7|]', texto)
    return [p.strip(' .\t\u2013-') for p in partes if p.strip(' .\t\u2013-')]


def _marcas_html(texto, estilo=''):
    """
    Converte a lista de bancas em marcadores entre parenteses.

    'PGESP-2002; MPSP-2005/2008/2013' vira
    '(PGESP-2002) (MPSP-2005/2008/2013)'

    `estilo` e um trecho de estilo inline (ex.: 'font-size:65%;')
    aplicado aos marcadores. Vazio = herda o tamanho do pai.
    """
    itens = _dividir_fontes(texto)
    if not itens:
        return ''
    vistos = set()
    unicos = []
    for item in itens:
        chave = item.lower()
        if chave in vistos:
            continue
        vistos.add(chave)
        unicos.append(item)
    if not unicos:
        return ''
    attr = (' style="%s"' % estilo) if estilo else ''
    return ' '.join(
        '<span class="marcas-banca"%s>(%s)</span>' % (attr, html_lib.escape(i))
        for i in unicos
    )


_RE_ITEM_BANCA = re.compile(
    r'^[A-Za-zÀ-ú][\wÀ-ú./\s\u00b7-]{0,40}?[\s-]\d{4}'
    r'(?:\s*[-/]\s*\d{2,4})*(?:\s+[A-Za-zÀ-ú][\wÀ-ú.\s]{0,20})?$'
)


def _parece_lista_de_bancas(texto):
    """
    Diz se a linha e so uma lista de bancas (e nao incidencia).

    Ex.: 'MPSP-2008; MPSC-2012; Cartorios/TJDFT-2014'
    """
    itens = _dividir_fontes(texto)
    if not itens or len(itens) > 12:
        return False
    for item in itens:
        if not _RE_ITEM_BANCA.match(item):
            return False
    return True


def _extrair_fontes(corpo):
    """
    Separa a lista de bancas (FONTES/Fonte) do corpo do bloco.

    Devolve (texto_sem_fontes, lista_de_bancas).
    A linha de fontes pode vir no formato 'FONTES: a; b' ou embutida
    no fim de um paragrafo.
    """
    linhas = []
    fontes = []
    for linha in corpo.split('\n'):
        m = _RE_FONTES.search(linha)
        if m:
            antes = linha[:m.start()].rstrip()
            if antes:
                linhas.append(antes)
            fontes.extend(_dividir_fontes(m.group(1)))
            continue
        linhas.append(linha)
    return '\n'.join(linhas), fontes

_RE_CAMPO_RESPOSTA = re.compile(
    r'^\s*(?:RESPOSTA|GABARITO|RESPOSTA\s+CORRETA|CONFIRMADO)\s*[:：]\s*(.*)$',
    re.IGNORECASE,
)

_RE_CAMPO_ENUNCIADO = re.compile(
    r'^\s*(?:ENUNCIADO|QUESTAO|QUESTÃO|TEXTO)\s*[:：]\s*(.*)$',
    re.IGNORECASE,
)


def _extrair_enunciado_questao(corpo):
    """
    Devolve o enunciado da questao, sem campos e sem rotulos.

    Aceita tanto o corpo cru (o enunciado transcrito, com a marca da
    banca inline) quanto o corpo com campo ENUNCIADO.
    Remove as linhas de campo (RESPOSTA, FUNDAMENTO, BANCA, FONTES) e
    as linhas soltas de gabarito.
    """
    linhas = []
    for linha in corpo.split('\n'):
        t = linha.strip()
        if not t:
            continue
        if _RE_CAMPO_RESPOSTA.match(t):
            continue
        m_enun = _RE_CAMPO_ENUNCIADO.match(t)
        if m_enun:
            linhas.append(m_enun.group(1).strip())
            continue
        if re.match(r'^\s*(?:FUNDAMENTO|FONTE|FONTES|BANCA|DAS|BL)\s*[:：]',
                    t, re.IGNORECASE):
            continue
        if _parece_gabarito(t):
            continue
        linhas.append(t)
    return '\n'.join(linhas).strip()


_RE_INICIO_QUESTAO = re.compile(r'^\(')


def _dividir_questoes(enunciado):
    """
    Divide o enunciado do material em questoes individuais.

    Cada questao comeca com a marca da banca entre parenteses, no
    inicio da linha: '(DPERO-2023-CESPE) Julgue o item...'. As linhas
    seguintes sao continuacao do enunciado e nao viram questao nova.
    """
    if not enunciado:
        return []

    blocos = []
    atual = []
    for linha in enunciado.split('\n'):
        t = linha.strip()
        if not t:
            continue
        if _RE_INICIO_QUESTAO.match(t) and atual:
            blocos.append('\n'.join(atual))
            atual = []
        atual.append(t)
    if atual:
        blocos.append('\n'.join(atual))

    return blocos


def _extrair_gabarito_questao(corpo):
    """
    Devolve a resposta da questao, se o material trouxer.

    Aceita RESPOSTA: Certo e gabarito solto na ultima linha.
    """
    for linha in corpo.split('\n'):
        m = _RE_CAMPO_RESPOSTA.match(linha.strip())
        if m and m.group(1).strip():
            return m.group(1).strip()
    nao_vazias = [l.strip() for l in corpo.split('\n') if l.strip()]
    if nao_vazias:
        ultima = nao_vazias[-1]
        if _parece_gabarito(ultima):
            return ultima
    return ''


def _parece_gabarito(texto):
    """Diz se a linha e so o gabarito da questao."""
    t = (texto or '').strip()
    if not t:
        return False
    if re.match(r'^(?:Certo|Errado|Certa|Errada|Verdadeiro|Falso)\b',
                t, re.IGNORECASE) and len(t) < 60:
        return True
    if re.match(r'^[A-Ea-e]\)\s+\S', t) and len(t) < 120:
        return True
    if re.match(r'^[A-Ea-e]$', t):
        return True
    return False


_RE_CAMPO_INCIDENCIA = re.compile(
    r'^\s*(?:INCID[EÊ]NCIA|INCIDENCIA)(?:\s+EM\s+PROVAS)?\s*[:：]?\s*(.*)$',
    re.IGNORECASE,
)

# O VERBETE (a sintese da orientacao firmada pelo tribunal) e a ultima
# linha do bloco JURISPRUDENCIA, marcada pela IA com asteriscos.
_RE_VERBETE = re.compile(r'^\*(?!\*)(.+?)(?<!\*)\*$', re.DOTALL)

_CAMPOS_QUE_INTERROMPEM = re.compile(
    r'^\s*(?:RESPOSTA|GABARITO|ENUNCIADO|QUEST[AÃ]O|TEXTO|TRIBUNAL|'
    r'[OÓ]RG[AÃ]O|PROCESSO|RELATOR|DATA(?:\s+JUDICIAL)?|LEADING|LEANDING|'
    r'EMENTA|ELEMENTA|TESE|AUTOR|OBRA|EDITORA|ANO|PAGINA|P[GÁ]GINA|'
    r'CAP[IÍ]TULO|SE[CÇ][AÃ]O|FUNDAMENTO|BANCA|FONTES|FONTE|DAS|BL)\s*[:：]',
    re.IGNORECASE,
)


def _extrair_incidencia(corpo, permitir_verbete=False):
    """
    Separa a linha de incidencia do material do corpo do bloco.

    Devolve (corpo_sem_incidencia, texto_incidencia, bancas).
    No material a incidencia vem logo apos o enunciado/ementa e leva a
    lista de bancas. Aqui ela e renderizada em fonte pequena e cinza.

    `permitir_verbete` (bloco JURISPRUDENCIA) impede que a ultima
    linha do bloco, o verbete marcado com asteriscos, seja engolida
    pela incidencia.
    """
    linhas = []
    incidencia = ''
    bancas = []
    coletando = False

    for linha in corpo.split('\n'):
        t = linha.strip()
        if not t:
            if coletando:
                break
            continue

        m = _RE_CAMPO_INCIDENCIA.match(t)
        if m:
            # A linha do material e transcrita como esta, sem rotulo
            # acrescentado e sem nada removido.
            incidencia = t
            coletando = True
            continue

        if coletando:
            # O VERBETE (a ultima linha do bloco) nao faz parte da
            # incidencia: ele volta para o corpo do bloco.
            if permitir_verbete and _RE_VERBETE.match(t):
                linhas.append(t)
                break
            # A lista de bancas pode ocupar varias linhas; para quando
            # comeca outro campo conhecido.
            if _CAMPOS_QUE_INTERROMPEM.match(t):
                break
            # Uma linha so de bancas (MPSP-2008; MPSC-2012; ...) nao e
            # incidencia: ela vai para o rodape de fontes.
            if _parece_lista_de_bancas(t):
                bancas.extend(_dividir_fontes(t))
                continue
            incidencia += (' ' if incidencia else '') + t
            continue

        linhas.append(t)

    return '\n'.join(linhas), _colapsar_espacos(incidencia), bancas


# Tags liberadas no HTML que vem da IA.
_TAGS_PERMITIDAS = {
    'table': (), 'thead': (), 'tbody': (), 'tfoot': (), 'tr': (),
    'th': ('colspan', 'rowspan'), 'td': ('colspan', 'rowspan'),
    'b': (), 'strong': (), 'i': (), 'em': (), 'u': (), 'br': (),
    'code': (), 'pre': (), 'ul': (), 'ol': (), 'li': (), 'p': (),
    'sup': (), 'sub': (), 'hr': (), 'div': (), 'blockquote': (),
    'span': (), 'small': (), 'mark': (), 'abbr': (),
}

_TAGS_DESCARTADAS = {'script', 'style', 'iframe', 'object', 'embed', 'link'}


class _SanitizadorIA(HTMLParser):
    """Reconstroi o HTML da IA mantendo apenas uma lista branca de tags."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.partes = []
        self._pular = 0
        self._abertos = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if self._pular:
            return
        if tag in _TAGS_DESCARTADAS:
            self._pular = 1
            return
        if tag in _TAGS_PERMITIDAS:
            permitidos = _TAGS_PERMITIDAS[tag]
            extras = ' '.join(
                '%s="%s"' % (nome, valor)
                for nome, valor in attrs
                if nome.lower() in permitidos and valor is not None
            )
            self.partes.append(
                '<%s%s>' % (tag, (' ' + extras) if extras else ''))
            self._abertos.append(tag)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if self._pular:
            if tag in _TAGS_DESCARTADAS:
                self._pular = 0
            return
        if tag in _TAGS_PERMITIDAS:
            if tag in self._abertos:
                while self._abertos:
                    aberta = self._abertos.pop()
                    self.partes.append('</%s>' % aberta)
                    if aberta == tag:
                        break
            else:
                self.partes.append('</%s>' % tag)

    def handle_data(self, data):
        if self._pular:
            return
        self.partes.append(html_lib.escape(data))

    def result(self):
        while self._abertos:
            self.partes.append('</%s>' % self._abertos.pop())
        return ''.join(self.partes)


def _higienizar_html(texto):
    """Sanitiza o HTML vindo da IA."""
    parser = _SanitizadorIA()
    try:
        parser.feed(texto)
        parser.close()
    except Exception:
        return html_lib.escape(texto)
    return parser.result()


def _md_para_html(texto):
    """Negrito e italico do Markdown, com o resto escapado."""
    texto = _colapsar_espacos(texto)
    texto = html_lib.escape(texto)
    texto = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', texto, flags=re.DOTALL)
    texto = re.sub(r'(?<![\w*])\*([^*\n]+?)\*(?![\w*])', r'<i>\1</i>',
                   texto)
    return texto.replace('\n', '<br>')


def _tabela_markdown_para_html(linhas):
    """Converte a tabela Markdown da IA em <table>."""
    if not linhas:
        return ''
    celulas = []
    for linha in linhas:
        partes = [p.strip() for p in linha.strip().strip('|').split('|')]
        celulas.append(partes)

    # Descarta a linha de separadores (---).
    if len(celulas) > 1 and all(
        set(c) <= {'-', ':', ' '} and c for c in celulas[1]
    ):
        cabecalho = celulas[0]
        corpo = celulas[2:]
    else:
        cabecalho = celulas[0]
        corpo = celulas[1:]

    html = ['<table>']
    if cabecalho:
        html.append('<thead><tr>')
        for celula in cabecalho:
            html.append('<th>%s</th>' % _md_para_html(celula))
        html.append('</tr></thead>')
    if corpo:
        html.append('<tbody>')
        for linha in corpo:
            html.append('<tr>')
            for celula in linha:
                html.append('<td>%s</td>' % _md_para_html(celula))
            html.append('</tr>')
        html.append('</tbody>')
    html.append('</table>')
    return ''.join(html)


def _campos_do_corpo(corpo, chaves):
    """Le as linhas 'CAMPO: valor' do corpo de um bloco."""
    campos = {}
    for chave in chaves:
        m = re.search(
            r'^\s*%s\s*[:：]\s*(.*)$' % re.escape(chave),
            corpo, re.IGNORECASE | re.MULTILINE)
        if m:
            campos[chave] = m.group(1).strip()
    return campos


_CAMPOS_QUESTAO = ('ENUNCIADO', 'QUESTAO', 'QUESTÃO', 'RESPOSTA',
                   'GABARITO', 'FUNDAMENTO', 'DAS', 'BL', 'BANCA')

_CAMPOS_JURISPRUDENCIA = ('TRIBUNAL', 'ORGÃO', 'ORGAO', 'PROCESSO',
                          'RELATOR', 'DATA JUDICIAL', 'DATAJUDICIAL', 'DATA',
                          'LEADING', 'LEANDING', 'EMENTA', 'ELEMENTA', 'TESE')

_CAMPOS_DOUTRINA = ('AUTOR', 'OBRA', 'CAPÍTULO', 'CAPITULO', 'SEÇÃO', 'SECAO',
                    'PAGINA', 'PÁGINA', 'EDITORA', 'ANO', 'TESE')


def _fontes_html(fontes, estilo=''):
    """Linha compacta e discreta com as bancas de origem."""
    if not fontes:
        return ''
    vistos = set()
    unicos = []
    for f in fontes:
        f = f.strip()
        if not f:
            continue
        chave = f.lower()
        if chave in vistos:
            continue
        vistos.add(chave)
        unicos.append(f)
    if not unicos:
        return ''
    attr = (' style="%s"' % estilo) if estilo else ''
    return (
        '<div class="bloco-fontes"%s>'
        '<span class="bloco-fontes-rotulo">Fontes:</span> '
        + ' <span class="bloco-fontes-sep">·</span> '.join(
            html_lib.escape(f) for f in unicos)
        + '</div>'
    )


def _fontes_inline(fontes, estilo=''):
    """Lista de bancas em linha, sem bloco proprio."""
    if not fontes:
        return ''
    vistos = set()
    unicos = []
    for f in fontes:
        f = f.strip()
        if not f:
            continue
        chave = f.lower()
        if chave in vistos:
            continue
        vistos.add(chave)
        unicos.append(f)
    if not unicos:
        return ''
    attr = (' style="%s"' % estilo) if estilo else ''
    return ('<span class="bloco-fontes"%s>%s</span>'
            % (attr, ' · '.join(html_lib.escape(f) for f in unicos)))


def _nota_html(texto, estilo=''):
    """Linha auxiliar discreta (ex.: fundamento, ressalva)."""
    texto = (texto or '').strip()
    if not texto:
        return ''
    attr = (' style="%s"' % estilo) if estilo else ''
    return '<div class="bloco-nota"%s>%s</div>' % (attr, _md_para_html(texto))


def _ident_html(texto, estilo=''):
    """Linha compacta de identificacao (julgado, referencia doutrinaria)."""
    texto = (texto or '').strip()
    if not texto:
        return ''
    attr = (' style="%s"' % estilo) if estilo else ''
    return '<div class="bloco-ident"%s>%s</div>' % (attr, html_lib.escape(texto))


def _estilos_tipo(tipo):
    """
    Tamanhos (em % da fonte do cartao) de um tipo de bloco.

    Devolve os valores absolutos de cada elemento do bloco. O
    container define a base; os demais sao relativos a ele.
    """
    cont = _container_absoluto(tipo)
    return {
        'cont': cont,
        'corpo': cont * _fonte('corpo') / 100.0,
        'ident': cont * _fonte('ident') / 100.0,
        'meta': cont * _fonte('meta') / 100.0,
        'fontes': cont * _fonte('fontes') / 100.0,
        'gabarito': cont * _fonte('gabarito') / 100.0,
        'esquema': cont * _fonte('esquema') / 100.0,
        'tabela': cont * _fonte('tabela') / 100.0,
    }


def _bloco_linha_html(linha, est):
    """
    Uma linha de prosa do bloco.

    O VERBETE (a sintese da orientacao firmada pelo tribunal) e
    reconhecido pelos asteriscos com que a IA o marca e sai em
    italico explicito.
    """
    m = _RE_VERBETE.match(linha.strip())
    if m:
        conteudo = '<i>%s</i>' % _md_para_html(m.group(1))
    else:
        conteudo = _md_para_html(linha)
    return ('<div class="bloco-linha" style="%s">%s</div>'
            % (_rel(est['corpo'], est['cont']), conteudo))


def _render_jurisprudencia(corpo, est):
    """
    Julgado em duas partes: identificacao numa linha e ementa em prosa.

    Aceita o corpo em campos (TRIBUNAL:, PROCESSO:, ...) ou ja em texto
    corrido, transcrito do material.
    """
    partes = []
    campos = _campos_do_corpo(corpo, _CAMPOS_JURISPRUDENCIA)

    if campos:
        tribunal = (campos.get('TRIBUNAL') or campos.get('ORGÃO')
                    or campos.get('ORGAO') or '')
        processo = campos.get('PROCESSO') or ''
        relator = campos.get('RELATOR') or ''
        data = (campos.get('DATA JUDICIAL') or campos.get('DATAJUDICIAL')
                or campos.get('DATA') or '')
        leading = campos.get('LEADING') or campos.get('LEANDING') or ''

        ident = ' · '.join(x for x in (tribunal, processo, relator, data)
                           if x)
        if leading and leading not in ident:
            ident = (ident + ' · ' + leading) if ident else leading
        if ident:
            partes.append(_ident_html(ident, _rel(est['ident'], est['cont'])))

        ementa = (campos.get('EMENTA') or campos.get('ELEMENTA')
                  or campos.get('TESE') or '')
        if ementa:
            partes.append('<div class="bloco-linha" style="%s">%s</div>'
                          % (_rel(est['corpo'], est['cont']),
                             _md_para_html(ementa)))
    else:
        linhas = [l.strip() for l in corpo.split('\n') if l.strip()]
        if linhas:
            partes.append(_ident_html(linhas[0],
                                      _rel(est['ident'], est['cont'])))
            for linha in linhas[1:]:
                partes.append(_bloco_linha_html(linha, est))

    return partes


def _render_doutrina(corpo, est):
    """Referencia completa numa linha e a tese em prosa."""
    partes = []
    campos = _campos_do_corpo(corpo, _CAMPOS_DOUTRINA)

    if campos:
        autor = campos.get('AUTOR') or ''
        obra = campos.get('OBRA') or ''
        editora = campos.get('EDITORA') or ''
        ano = campos.get('ANO') or ''
        pagina = (campos.get('PAGINA') or campos.get('PÁGINA') or '')

        ref = obra
        if editora or ano:
            ref = (ref + ', ' if ref else '') + ', '.join(
                x for x in (editora, ano) if x)
        if pagina:
            ref = (ref + ', ' if ref else '') + 'p. ' + pagina
        ident = ' · '.join(x for x in (autor, ref) if x)
        if ident:
            partes.append(_ident_html(ident, _rel(est['ident'], est['cont'])))

        tese = campos.get('TESE') or ''
        if tese:
            partes.append('<div class="bloco-linha" style="%s">%s</div>'
                          % (_rel(est['corpo'], est['cont']),
                             _md_para_html(tese)))
    else:
        linhas = [l.strip() for l in corpo.split('\n') if l.strip()]
        if linhas:
            partes.append(_ident_html(linhas[0],
                                      _rel(est['ident'], est['cont'])))
            for linha in linhas[1:]:
                partes.append('<div class="bloco-linha" style="%s">%s</div>'
                              % (_rel(est['corpo'], est['cont']),
                                 _md_para_html(linha)))

    return partes


def _render_bloco_tipado(tipo, subtitulo, corpo, aberta=True, fontes=None,
                         rotulo=''):
    """Gera o HTML de um bloco tipado."""
    # O subtitulo NAO aparece: o bloco mostra apenas o tipo.
    rotulo = _ROTULOS_TIPO.get(tipo, tipo)

    # Tamanhos padronizados do bloco (em % da fonte do cartao).
    est = _estilos_tipo(tipo)

    corpo, fontes_do_corpo = _extrair_fontes(corpo)
    if fontes_do_corpo:
        fontes = list(fontes or []) + fontes_do_corpo

    # A linha de incidencia do material vem logo apos o texto. Fica
    # separada para ser renderizada em fonte pequena e cinza claro.
    corpo, incidencia, bancas_incidencia = \
        _extrair_incidencia(corpo, permitir_verbete=(tipo == 'JURISPRUDENCIA'))
    if bancas_incidencia:
        fontes = list(fontes or []) + bancas_incidencia

    # Uma linha so de bancas (MPSP-2008; MPSC-2012) nao faz parte do
    # texto: vai para o rodape compacto.
    linhas_corpo = []
    for linha in corpo.split('\n'):
        t = linha.strip()
        if t and _parece_lista_de_bancas(t):
            fontes = list(fontes or []) + _dividir_fontes(t)
            continue
        linhas_corpo.append(linha)
    corpo = '\n'.join(linhas_corpo)

    partes = []

    if tipo == 'TABELA':
        corpo_limpo = corpo.strip()
        if corpo_limpo.startswith('<table'):
            tabela_html = _higienizar_html(corpo_limpo)
        else:
            tabela_html = _tabela_markdown_para_html(
                [l for l in corpo_limpo.splitlines() if l.strip()])
        # O tamanho da tabela e padronizado: o inline vence o CSS do deck.
        tabela_html = re.sub(
            r'<table\b',
            '<table style="%s"' % _rel(est['tabela'], est['cont']),
            tabela_html, count=1)
        partes.append(tabela_html)

    elif tipo == 'ESQUEMA':
        linhas = [l.rstrip() for l in corpo.splitlines() if l.strip()]
        partes.append('<pre class="esquema" style="%s">%s</pre>'
                      % (_rel(est['esquema'], est['cont']),
                         html_lib.escape('\n'.join(linhas))))

    elif tipo == 'QUESTAO':
        # O corpo do bloco QUESTAO e o ENUNCIADO, transcrito do material,
        # sem campos e sem rotulos. A marca da banca vem inline, tal
        # como aparece no material. Uma linha por questao: quando o
        # material traz varias questoes no mesmo bloco, cada uma vira
        # uma .bloco-linha e o CSS põe a divisoria entre elas.
        enunciado = _extrair_enunciado_questao(corpo)
        gabarito = _extrair_gabarito_questao(corpo)
        questoes = _dividir_questoes(enunciado)
        if not questoes and gabarito:
            questoes = ['']
        for i, questao in enumerate(questoes):
            linha = _md_para_html(questao)
            if gabarito and i == len(questoes) - 1:
                # O gabarito entra inline, no fim da ultima questao.
                linha += (' <span class="bloco-gabarito" style="%s">%s</span>'
                          % (_rel(est['gabarito'], est['corpo']),
                             _md_para_html(gabarito)))
            partes.append('<div class="bloco-linha" style="%s">%s</div>'
                          % (_rel(est['corpo'], est['cont']), linha))
        if not partes:
            paragrafos = [p for p in corpo.split('\n') if p.strip()]
            partes.append('<div class="bloco-linha" style="%s">%s</div>'
                          % (_rel(est['corpo'], est['cont']),
                             '<br>'.join(_md_para_html(p) for p in paragrafos)))

    elif tipo == 'JURISPRUDENCIA':
        partes.extend(_render_jurisprudencia(corpo, est))

    elif tipo == 'DOUTRINA':
        partes.extend(_render_doutrina(corpo, est))

    else:
        paragrafos = []
        for p in corpo.split('\n'):
            t = p.strip()
            if not t:
                continue
            paragrafos.append(t)
        if paragrafos:
            partes.append('<div class="bloco-linha" style="%s">%s</div>'
                          % (_rel(est['corpo'], est['cont']),
                             '<br>'.join(_md_para_html(p) for p in paragrafos)))

    # A incidencia e as fontes vao numa UNICA linha pequena, logo apos
    # o texto, para o bloco ocupar o minimo de espaco.
    meta = []
    if incidencia:
        meta.append(_md_para_html(incidencia))
    if fontes:
        meta.append(_fontes_inline(fontes,
                                   _rel(est['fontes'], est['meta'])))
    if meta:
        partes.append('<div class="bloco-meta" style="%s">%s</div>'
                      % (_rel(est['meta'], est['cont']),
                         ' <span class="bloco-meta-sep">·</span> '.join(meta)))

    attr = ' open' if aberta else ''
    # O summary fica vazio: o rotulo ("Questão", "Jurisprudência", ...)
    # so ocupa espaco no PDF e no Anki. O tipo continua marcado em
    # data-bloco, que e o que o CSS usa para colorir a caixa.
    # O tamanho do container e gravado inline, para o bloco ter o
    # tamanho padronizado independente do CSS do deck.
    # data-alvo identifica o dispositivo: permite trocar o bloco
    # antigo pelo novo na atualizacao do arquivo do Anki.
    alvo_attr = ''
    if rotulo:
        alvo_attr = ' data-alvo="%s"' % html_lib.escape(rotulo, quote=True)
    return (
        '<details class="comentario" data-bloco="%s"%s%s style="%s">'
        '<summary></summary>'
        '<div class="bloco-corpo">%s</div>'
        '</details>'
    ) % (tipo.lower(), alvo_attr, attr,
         _rel(est['cont'], 100.0), ''.join(partes))


def _parse_blocos_tipados(comentarios_txt):
    """
    Divide o texto da IA em blocos.

    Devolve (grupos, sintese), onde grupos mapeia a chave do alvo para
    a lista de blocos (dictionarios com tipo, subtitulo, corpo e
    relevancia) e sintese e o texto da sintese final, se houver.
    """
    comentarios_txt = _remover_cercas_codigo(comentarios_txt)

    grupos = {}
    sintese = None

    atual = None
    partes = []
    ordem = 0

    def salvar():
        """Fecha o bloco atual. Devolve o texto da sintese, se for o caso."""
        nonlocal atual, partes
        if atual is None:
            return None
        # O corpo nao e normalizado aqui: o bloco ESQUEMA guarda um
        # diagrama alinhado, que perderia o espacamento.
        atual['corpo'] = '\n'.join(partes).strip('\n')
        bloco = atual
        atual = None
        partes = []
        if bloco['alvo'] is None:
            if bloco['tipo'] == 'COMENTARIO':
                return bloco['corpo']
            return None
        grupos.setdefault(bloco['alvo'], []).append(bloco)
        return None

    for linha in comentarios_txt.splitlines():
        texto = linha.strip()
        if not texto:
            continue

        m_tipo = _RE_CABECALHO_TIPADO.match(texto)
        if m_tipo:
            sintese = salvar() or sintese
            tipo = m_tipo.group('tipo').upper()
            campos = m_tipo.group('resto').split('|')
            alvo_texto = campos[0].strip() if campos else ''
            subtitulo = campos[1].strip() if len(campos) > 1 else ''
            try:
                relevancia = int(re.sub(r'\D', '', campos[2]) or 0) \
                    if len(campos) > 2 else 0
            except ValueError:
                relevancia = 0

            alvo = None
            if alvo_texto and alvo_texto.upper() != 'SINTESE':
                alvo = _parse_chave_comentario(alvo_texto)
                if alvo is None:
                    atual = None
                    partes = []
                    continue

            atual = {
                'tipo': tipo,
                'alvo': alvo,
                'subtitulo': subtitulo,
                'relevancia': relevancia,
                'ordem': ordem,
                'corpo': '',
                'fontes': [],
            }
            ordem += 1
            partes = []
            continue

        # Formato antigo: "Art. 15|texto" ou continuacao de corpo.
        chave, sep, resto = linha.partition('|')
        chave_limpo = chave.strip()
        if sep and (chave_limpo.upper() == 'SINTESE'
                    or chave_limpo.startswith('Art.')):
            sintese = salvar() or sintese
            tipo = 'COMENTARIO'
            if chave_limpo.upper() == 'SINTESE':
                alvo = None
                corpo_inicial = resto
            else:
                alvo = _parse_chave_comentario(chave_limpo)
                if alvo is None:
                    atual = None
                    partes = []
                    continue
                corpo_inicial = resto
            atual = {
                'tipo': tipo,
                'alvo': alvo,
                'subtitulo': '',
                'relevancia': 0,
                'ordem': ordem,
                'corpo': '',
                'fontes': [],
            }
            ordem += 1
            partes = [corpo_inicial]
            continue

        if atual is not None:
            partes.append(linha)

    sintese = salvar() or sintese
    return grupos, sintese


def _ordenar_blocos(lista):
    """Maior relevancia primeiro; desempate pela ordem dos tipos."""
    return sorted(
        lista,
        key=lambda b: (-b['relevancia'],
                       _ORDEM_TIPOS.get(b['tipo'], 9),
                       b['ordem'])
    )


def _detalhes_blocos(alvo, lista, entrelinha_comentario=1.0):
    """Renderiza os blocos de um alvo."""
    rotulo = _rotulo_alvo(alvo)
    return '\n'.join(
        _render_bloco_tipado(
            b['tipo'], b['subtitulo'], b['corpo'],
            fontes=b.get('fontes'), rotulo=rotulo)
        for b in lista if b['tipo'] != 'MARCAS'
    )


def _anexar_marcas(linha_html, marcas):
    """
    Anexa os marcadores de banca no fim do texto do dispositivo.

    'Art. 3 ... (PGESP-2002) (MPSP-2005)': os marcadores entram
    dentro do span, depois do ultimo texto.
    """
    if not marcas:
        return linha_html
    pos = linha_html.rfind('</span>')
    if pos == -1:
        return linha_html
    antes = linha_html[:pos].rstrip()
    return antes + ' ' + marcas + linha_html[pos:]


def _parse_comentarios_pipe(comentarios_txt):
    """Mantem o formato antigo: dicionario de chave -> lista de textos."""
    comentarios = {}
    sintese = None
    alvo_atual = None
    partes = []

    def salvar():
        nonlocal sintese
        if alvo_atual is None or not partes:
            return
        texto = '<br>'.join(_normalizar_ordinais(p.strip()) for p in partes if p.strip())
        if not texto:
            return
        if alvo_atual == 'SINTESE':
            sintese = texto
        else:
            comentarios.setdefault(alvo_atual, []).append(texto)

    for linha in comentarios_txt.splitlines():
        linha = linha.strip()
        if not linha:
            continue
        chave, sep, texto = linha.partition('|')
        novo_alvo = None
        if sep:
            novo_alvo = 'SINTESE' if chave.strip().upper() == 'SINTESE' else _parse_chave_comentario(chave)
        if novo_alivo is not None:
            salvar()
            alvo_atual = novo_alvo
            partes = [texto]
        elif alvo_atual is not None:
            # Comentários de várias linhas pertencem à última chave válida.
            partes.append(linha)
    salvar()
    return comentarios, sintese


def _details_alvo(alvo, textos, entrelinha_comentario=1.0):
    rotulo = _rotulo_alvo(alvo)
    if len(textos) == 1:
        return (
            f'<details class="comentario" style="line-height:{entrelinha_comentario}">'
            f'<summary>Comentário ({rotulo})</summary>'
            f'{textos[0]}</details>'
        )
    return '\n'.join(
        f'<details class="comentario" style="line-height:{entrelinha_comentario}">'
        f'<summary>Comentário {idx} ({rotulo})</summary>'
        f'{texto}</details>'
        for idx, texto in enumerate(textos, start=1)
    )


def mesclar_comentarios(html_anki, comentarios_txt, add_sintese=True,
                       entrelinha_comentario=1.0):
    """
    Recebe o HTML já formatado e o texto de comentários.

    Formatos aceitos:

    1. Blocos tipados (output do prompt de IA):
         TIPO|ALVO|SUBTITULO|RELEVANCIA
         corpo...
       Tipos: COMENTARIO, TABELA, ESQUEMA, QUESTAO, JURISPRUDENCIA,
       DOUTRINA, NOTA.

    2. Formato antigo:
         Art. X|comentário
         Art. X, inciso I|comentário
         Art. X, § 1º|comentário
         Art. X, § 1º, inciso III|comentário
         Art. X, inciso I, alínea a|comentário
         SINTESE|texto

    O comentário geral é inserido ao final do artigo. Comentários de
    parágrafo, inciso ou alínea são inseridos imediatamente após o
    elemento correspondente. Chaves repetidas geram <details> separados.
    """
    entrelinha_comentario = max(1.0, min(2.0, float(entrelinha_comentario)))

    grupos, sintese = _parse_blocos_tipados(comentarios_txt)

    if not grupos and not sintese:
        return html_anki

    for alvo in grupos:
        grupos[alvo] = _ordenar_blocos(grupos[alvo])

    # O HTML recém-formatado usa uma linha por <span>, mas o arquivo
    # exportado pelo Anki costuma compactar tudo em uma única linha.
    # A divisão por início de <span> atende aos dois formatos.
    linhas = re.split(r'\s*(?=<span\b)', html_anki)
    resultado = []
    art_atual = par_atual = inc_atual = ali_atual = None
    alvos_inseridos = set()

    def inserir_comentario_elemento():
        if art_atual is None:
            return
        alvo = (art_atual, par_atual, inc_atual, ali_atual)
        if alvo in grupos and any(x is not None for x in alvo[1:]):
            resultado.append(
                _detalhes_blocos(alvo, grupos[alvo], entrelinha_comentario))
            alvos_inseridos.add(alvo)

    def marcas_do_alvo(alvo):
        """Marcadores de banca de um alvo, prontos para o texto."""
        blocos = [b for b in grupos.get(alvo, []) if b['tipo'] == 'MARCAS']
        if not blocos:
            return ''
        textos = []
        for bloco in blocos:
            for linha in bloco['corpo'].split('\n'):
                if linha.strip():
                    textos.append(linha.strip())
        # As marcas vivem no texto legal: tamanho absoluto em relacao
        # a fonte do cartao.
        return _marcas_html(' '.join(textos),
                            _rel(_fonte('marcas'), 100.0))

    def fechar_artigo():
        if art_atual is None:
            return
        alvo_artigo = (art_atual, None, None, None)
        if alvo_artigo in grupos:
            resultado.append(
                _detalhes_blocos(alvo_artigo, grupos[alvo_artigo],
                                 entrelinha_comentario))
            alvos_inseridos.add(alvo_artigo)
        # Se o marcador específico estiver ausente ou junto a outro dispositivo
        # no texto colado, preserva o comentário ao final do artigo, com seu rótulo.
        for alvo, lista in grupos.items():
            if (alvo[0] == art_atual and any(x is not None for x in alvo[1:])
                    and alvo not in alvos_inseridos):
                resultado.append(
                    _detalhes_blocos(alvo, lista, entrelinha_comentario))
                alvos_inseridos.add(alvo)

    for linha in linhas:
        m_art = re.search(r'<b>(?:★+&nbsp;|★+\s*)?Art\.\s*([\d.]+(?:[º°]?\s*-[A-Za-z])?)[º°.]*</b>', linha, re.IGNORECASE)
        if m_art:
            fechar_artigo()
            art_atual = _normalizar_num_artigo(m_art.group(1))
            par_atual = inc_atual = ali_atual = None
            marcas = marcas_do_alvo((art_atual, None, None, None))
            if marcas and linha.startswith('<span'):
                linha = _anexar_marcas(linha, marcas)
            resultado.append(linha)
            continue

        m_par = re.search(r'<b>§\s*(\d+)[º°.]*</b>', linha, re.IGNORECASE)
        m_par_unico = re.search(r'>\s*Par[aá]grafo\s+[úu]nico\b', linha, re.IGNORECASE)
        m_inc = re.search(r'<b>([IVXLCDM]+(?:-[A-Za-z])?)</b>\s*[-–—]', linha)
        m_ali = re.search(r'>\s*([a-z])\)\s*', linha, re.IGNORECASE)

        if m_par or m_par_unico:
            par_atual = str(int(m_par.group(1))) if m_par else 'unico'
            inc_atual = ali_atual = None
        elif m_inc:
            inc_atual = _normalizar_romano(m_inc.group(1))
            ali_atual = None
        elif m_ali:
            ali_atual = _normalizar_alinea(m_ali.group(1))

        # Os marcadores de banca entram no fim do texto do dispositivo.
        # O alvo e montado com o contexto atual (artigo, paragrafo,
        # inciso, alinea).
        alvo_atual = (art_atual, par_atual, inc_atual, ali_atual)
        marcas = marcas_do_alvo(alvo_atual)
        if marcas and linha.startswith('<span'):
            linha = _anexar_marcas(linha, marcas)

        resultado.append(linha)
        if m_par or m_par_unico or m_inc or m_ali:
            inserir_comentario_elemento()

    fechar_artigo()

    html_final = '\n'.join(resultado)

    if add_sintese and sintese:
        html_final += (
            f'\n<details class="comentario" style="line-height:{entrelinha_comentario};'
            f'{_rel(_fonte("bloco"), 100.0)}">'
            f'<summary>Síntese Final</summary>{_md_para_html(sintese)}</details>'
        )

    return html_final


# ============================================================
# GERAÇÃO DO ARQUIVO DE IMPORTAÇÃO PARA O ANKI
# ============================================================

def _extrair_capitulos_pdf(texto_bruto):
    """Preserva o número e o nome dos capítulos para a hierarquia do PDF."""
    linhas = _juntar_linhas_quebradas(texto_bruto).splitlines()
    capitulos = []
    for i, linha in enumerate(linhas):
        estrutura = _extrair_estrutura(linha)
        if not estrutura or estrutura[0] != 'C':
            continue
        nome = estrutura[1]
        numero = re.match(
            r'^CAPÍTULO\s+([IVXLCDM]+|\d+[º°ªoO]?|ÚNIC[OA])(?=\s|$|[-–—.:])',
            linha.strip(), re.IGNORECASE
        )
        rotulo = 'CAPÍTULO' + (' ' + numero.group(1).upper() if numero else '')
        if not nome:
            j = i + 1
            while j < len(linhas) and not linhas[j].strip():
                j += 1
            if j < len(linhas):
                proxima = linhas[j].strip()
                if not _eh_dispositivo_legal(proxima) and not _extrair_estrutura(proxima):
                    nome = proxima
        capitulos.append({
            'rotulo': rotulo,
            'titulo': _limpar_anotacoes(nome).upper() if nome else '',
            'ordem': len(capitulos) + 1,
        })
    return capitulos


def _parse_secoes_artigos(texto_formatado, assunto_tipo='capitulo', capitulos=None):
    linhas = texto_formatado.split('\n')
    secoes = []

    assunto_atual = 'GERAL'
    capitulo_atual = {}
    sequencia_capitulos = iter(capitulos or [])

    def registrar_secao():
        if capitulos is None:
            secoes.append((assunto_atual, artigos))
        else:
            pai = capitulo_atual.copy() if assunto_atual.startswith(('S:', 'SUB:')) else {}
            secoes.append((assunto_atual, artigos, pai))

    art_atual = []
    artigos = []
    dentro_de_secao = False
    incidencia_pendente = ''

    for linha in linhas:
        s = linha.strip()
        if not s:
            continue
        if s.startswith('#'):
            tipo, _, nome = s[1:].partition(':')

            if tipo == 'INC':
                # A incidencia pertence ao artigo seguinte. Fica
                # guardada para ser prependida quando o artigo for
                # montado.
                incidencia_pendente = nome.strip()
                continue

            if assunto_tipo == 'secao':
                if art_atual:
                    artigos.append(art_atual)
                    art_atual = []
                if artigos:
                    registrar_secao()
                    artigos = []
                assunto_atual = s[1:].strip()
                if tipo in ('C', 'T'):
                    dentro_de_secao = False
                elif tipo in ('S', 'SUB'):
                    dentro_de_secao = True
            else:
                if tipo in ('C', 'T'):
                    if art_atual:
                        artigos.append(art_atual)
                        art_atual = []
                    if artigos:
                        registrar_secao()
                        artigos = []
                    assunto_atual = s[1:].strip()
                    dentro_de_secao = False
                elif tipo in ('S', 'SUB'):
                    so_cabecalho = all(l.startswith('#S:') or l.startswith('#SUB:') for l in art_atual) if art_atual else False
                    if art_atual and not so_cabecalho:
                        artigos.append(art_atual)
                        art_atual = [s]
                    else:
                        art_atual.append(s)
                    dentro_de_secao = True
                else:
                    if art_atual:
                        artigos.append(art_atual)
                        art_atual = []
                    if artigos:
                        registrar_secao()
                        artigos = []
                    assunto_atual = s[1:].strip()
                    dentro_de_secao = False

            # Só troca o capítulo depois de registrar o grupo anterior.
            if tipo == 'C':
                capitulo_atual = next(sequencia_capitulos, {
                    'rotulo': 'CAPÍTULO', 'titulo': nome.strip(),
                })
            elif tipo == 'T':
                capitulo_atual = {}

        elif re.match(r'^Art\.', s):
            # A incidencia pendente entra ANTES do artigo.
            prefixo = (
                ['#INC:' + incidencia_pendente]
                if incidencia_pendente else []
            )
            incidencia_pendente = ''
            if assunto_tipo == 'capitulo' and dentro_de_secao:
                art_atual.extend(prefixo)
                art_atual.append(s)
            else:
                so_cabecalho = all(l.startswith('#S:') or l.startswith('#SUB:') for l in art_atual) if art_atual else False
                if art_atual and not so_cabecalho:
                    artigos.append(art_atual)
                    art_atual = prefixo + [s]
                else:
                    art_atual.extend(prefixo)
                    art_atual.append(s)
        else:
            art_atual.append(s)

    if art_atual:
        artigos.append(art_atual)
    if artigos:
        registrar_secao()

    return secoes


def _artigo_para_html(linhas_artigo, esp, ipar, iinc, iali, entrelinha=1.0):
    texto = '\n'.join(linhas_artigo)
    html, _ = formatar_para_anki(texto, esp, ipar, iinc, iali, entrelinha)
    return html


def _len_texto(html):
    html_sem_comentarios = re.sub(r'<details class="comentario"[^>]*>.*?</details>', '', html, flags=re.DOTALL)
    return len(re.sub(r'<[^>]+>', '', html_sem_comentarios))


def _empacotar_cartoes(secao, artigos_html, chars_alvo):
    cartoes = []
    estado = {'frente': [], 'verso': [], 'fl': 0, 'vl': 0}
    avisos = []

    def _salvar():
        f = estado['frente']
        v = estado['verso']
        if not f and not v:
            return
        if not v and f:
            # Só reúne a sobra ao cartão anterior se ela couber no alvo.
            # A junção incondicional fazia o último verso crescer sem limite.
            tamanho_sobra = sum(_len_texto(a) for a in f)
            if cartoes and _len_texto(cartoes[-1]['verso']) + tamanho_sobra <= chars_alvo:
                if cartoes[-1]['verso']:
                    cartoes[-1]['verso'] += ' ' + ' '.join(f)
                else:
                    cartoes[-1]['verso'] = ' '.join(f)
                estado['frente'] = []
                estado['verso']  = []
                estado['fl']     = 0
                estado['vl']     = 0
                return
            if len(f) > 1:
                mid = max(1, len(f) // 2)
                f, v = f[:mid], f[mid:]
            else:
                avisos.append(f'ℹ️  [{secao}] Cartão #{len(cartoes)+1}: VERSO vazio (apenas 1 artigo disponível).')
        if not f and v:
            avisos.append(f'⚠️  [{secao}] Cartão #{len(cartoes)+1}: FRENTE vazia — verso promovido para frente.')
            f, v = v, []
        cartoes.append({
            'secao':  secao,
            'frente': ' '.join(f),
            'verso':  ' '.join(v),
        })
        estado['frente'] = []
        estado['verso']  = []
        estado['fl']     = 0
        estado['vl']     = 0

    arts_validos = [a.strip() for a in artigos_html if a.strip()]
    total_txt    = sum(_len_texto(a) for a in arts_validos)

    if len(arts_validos) > 1 and total_txt <= chars_alvo * 2:
        mid = max(1, len(arts_validos) // 2)
        frente_len = sum(_len_texto(a) for a in arts_validos[:mid])
        verso_len  = sum(_len_texto(a) for a in arts_validos[mid:])
        if frente_len <= chars_alvo and verso_len <= chars_alvo:
            return [{
                'secao':  secao,
                'frente': ' '.join(arts_validos[:mid]),
                'verso':  ' '.join(arts_validos[mid:]),
            }]

    for art in artigos_html:
        art = art.strip()
        if not art:
            continue
        art_len = _len_texto(art)
        fl = estado['fl']
        vl = estado['vl']

        if fl == 0:
            estado['frente'].append(art)
            estado['fl'] = art_len
        elif not estado['verso'] and fl + art_len <= chars_alvo:
            estado['frente'].append(art)
            estado['fl'] += art_len
        elif vl == 0:
            estado['verso'].append(art)
            estado['vl'] = art_len
        elif vl + art_len <= chars_alvo:
            estado['verso'].append(art)
            estado['vl'] += art_len
        else:
            _salvar()
            estado['frente'].append(art)
            estado['fl'] = art_len

    _salvar()
    for aviso in avisos:
        print(aviso)
    return cartoes


def gerar_importacao_anki(texto_bruto, comentarios_txt='', chars_alvo=1500,
                          espacamento=2, indent_par=2,
                          indent_inc=8, indent_ali=8,
                          assunto_tipo='capitulo', _retornar_cartoes=False,
                          entrelinha=1.0, entrelinha_comentario=1.0):
    texto_fmt = formatar_texto_legal(texto_bruto)
    secoes = _parse_secoes_artigos(
        texto_fmt, assunto_tipo, capitulos=_extrair_capitulos_pdf(texto_bruto))

    linhas = []
    cartoes_pdf = []
    for nome_secao, artigos, capitulo in secoes:
        artigos_html = [
            _artigo_para_html(a, espacamento, indent_par, indent_inc, indent_ali, entrelinha)
            for a in artigos
        ]
        artigos_html = [h for h in artigos_html if h.strip()]

        if comentarios_txt.strip():
            artigos_html = [mesclar_comentarios(h, comentarios_txt, add_sintese=False,
                                               entrelinha_comentario=entrelinha_comentario)
                            for h in artigos_html]

        if not artigos_html:
            continue
        for c in _empacotar_cartoes(nome_secao, artigos_html, chars_alvo):
            tipo, _, nome = c['secao'].partition(':')
            if not nome:
                nome = tipo
                tipo = 'S'
            nome = nome.strip()

            frente = c['frente'].replace('\n', ' ')
            verso  = c['verso'].replace('\n', ' ')

            if assunto_tipo == 'secao':
                if nome.upper() != 'GERAL' and tipo == 'SUB':
                    header = f'<span style="display:block;padding-left:14px;margin-bottom:10px;font-weight:bold;color:#a8d8ea;">[{nome}]</span> '
                    frente = header + frente
                elif nome.upper() != 'GERAL' and tipo == 'S':
                    header = f'<span style="display:block;padding-left:0px;margin-bottom:10px;font-weight:bold;color:#4a0000;">[{nome}]</span> '
                    frente = header + frente

            linhas.append(f"{nome}|{frente}|{verso}")
            cartoes_pdf.append({'assunto': nome, 'frente': frente, 'verso': verso,
                                'capitulo': capitulo})

    total_cartoes = len(linhas)
    sem_verso     = sum(1 for l in linhas if l.endswith('|'))
    sem_frente    = sum(1 for l in linhas if '||' in l)
    com_ambos     = total_cartoes - sem_verso - sem_frente

    print('\n' + '═' * 50)
    print(f'📦  RELATÓRIO DE GERAÇÃO DE CARTÕES')
    print('═' * 50)
    print(f'  Total de cartões criados : {total_cartoes}')
    print(f'  ✅ Com frente e verso     : {com_ambos}')
    print(f'  ℹ️  Verso vazio           : {sem_verso}')
    if sem_frente:
        print(f'  ⚠️  Frente vazia (bug!)  : {sem_frente}')
    print('═' * 50 + '\n')

    return cartoes_pdf if _retornar_cartoes else '\n'.join(linhas)


# Patch para adicionar ao formatador_lei_anki.py
# Coloque ANTES do bloco "INTEGRAÇÃO COM O KERNEL DO COLAB"

import csv, io

# ============================================================
# ATUALIZAÇÃO DE ARQUIVO EXPORTADO DO ANKI
# ============================================================

def _export_tem_coluna_guid(cabecalho):
    """
    Diz se o arquivo exportado pelo Anki tem a coluna #guid.

    O header "#guid column:1" e a forma padrao do Anki quando o
    checkbox "Include GUID" esta marcado. Sem essa linha, a primeira
    coluna ja e o campo "frente".
    """
    for linha in cabecalho or []:
        if linha.lower().startswith('#guid'):
            return True
    return False


def _parse_anki_export(conteudo_txt):
    """
    Lê o arquivo exportado pelo Anki (File > Export, com #guid column:1).
    Retorna: (cabecalho_linhas, linhas_parsed)
      cabecalho_linhas: lista de strings das linhas que começam com #
      linhas_parsed: lista de dicts {guid, frente, assunto, verso, extra_cols}
    """
    linhas_raw = conteudo_txt.splitlines()
    cabecalho = []
    dados = []

    for linha in linhas_raw:
        if linha.startswith('#'):
            cabecalho.append(linha)
            continue
        if not linha.strip():
            continue
        # Usa csv para lidar com aspas duplas escapadas (doublequote=True)
        try:
            reader = csv.reader(io.StringIO(linha), delimiter='\t',
                                quotechar='"', doublequote=True)
            cols = next(reader)
        except Exception:
            dados.append({'guid': '', 'frente': linha, 'assunto': '', 'verso': '',
                          'extra_cols': [], '_raw': linha})
            continue

        # O arquivo pode vir com ou sem a coluna #guid. Quando ela
        # existe, a coluna 1 e o GUID e o conteudo comeca na coluna 2.
        # Sem a coluna #guid, a coluna 1 ja e o campo "frente".
        tem_guid = _export_tem_coluna_guid(cabecalho)
        offset = 1 if tem_guid else 0

        guid   = cols[0] if (tem_guid and len(cols) > 0) else ''
        frente = cols[offset] if len(cols) > offset else ''
        assunto= cols[offset + 1] if len(cols) > offset + 1 else ''
        verso  = cols[offset + 2] if len(cols) > offset + 2 else ''
        extra  = cols[offset + 3:] if len(cols) > offset + 3 else []
        dados.append({'guid': guid, 'frente': frente, 'assunto': assunto,
                      'verso': verso, 'extra_cols': extra, '_raw': linha})
    return cabecalho, dados


def _serializar_anki_export(cabecalho, linhas_parsed):
    """
    Reconstrói o arquivo .txt no formato do Anki a partir do cabecalho e linhas.
    """
    saida = list(cabecalho)
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter='\t', quotechar='"',
                        doublequote=True, quoting=csv.QUOTE_ALL,
                        lineterminator='')
    # A coluna #guid so e escrita se ela existia no arquivo original.
    tem_guid = _export_tem_coluna_guid(cabecalho)
    for item in linhas_parsed:
        buf.seek(0); buf.truncate()
        cols = []
        if tem_guid:
            cols.append(item['guid'])
        cols.extend([item['frente'], item['assunto'], item['verso']])
        cols.extend(item['extra_cols'])
        writer.writerow(cols)
        saida.append(buf.getvalue())
    return '\n'.join(saida)


def _extrair_nums_artigo_do_html(html):
    """
    Retorna set de strings de números de artigo presentes no HTML de uma célula.
    Ex: '<b>Art. 19</b>' → {'19'}
    Lida com estrelas (★) antes do Art.
    """
    nums = set()
    for m in re.finditer(r'<b>(?:★+&nbsp;|★+\s*)?Art\.\s*([\d\w\-º°\.]+)', html):
        num = _normalizar_num_artigo(m.group(1))
        nums.add(num)
    return nums


def atualizar_arquivo_anki(conteudo_txt, comentarios_txt):
    """
    Recebe o conteúdo do arquivo .txt exportado do Anki e o bloco de comentários.
    Para cada cartão (linha), injeta comentários novos nos artigos correspondentes,
    preservando GUIDs, estrelas e comentários já existentes.
    Retorna: (novo_conteudo_txt, relatorio_str)
    """
    if not conteudo_txt.strip():
        return '', '⚠️ Arquivo do Anki vazio.'
    if not comentarios_txt.strip():
        return conteudo_txt, '⚠️ Nenhum comentário fornecido.'

    cabecalho, linhas = _parse_anki_export(conteudo_txt)

    # Mesmo parser usado na mesclagem normal: aceita blocos tipados
    # (TIPO|ALVO|SUBTITULO|RELEVANCIA) e o formato antigo (Art. X|texto).
    grupos, sintese_nova = _parse_blocos_tipados(comentarios_txt)

    if not grupos and not sintese_nova:
        return conteudo_txt, '⚠️ Nenhum comentário válido encontrado.'

    artigos_com_comentario = {alvo[0] for alvo in grupos}
    total_inseridos = 0
    total_cartoes_afetados = 0

    def _injetar_comentarios_na_celula(html_celula, nums_do_cartao):
        """
        Substitui apenas os comentários cujos alvos foram novamente
        fornecidos e preserva os comentários dos demais elementos.
        """
        nonlocal total_inseridos
        resultado_html = html_celula
        alvos_da_celula = {
            alvo: lista for alvo, lista in grupos.items()
            if alvo[0] in nums_do_cartao
        }

        # Remove versões anteriores somente dos mesmos alvos.
        # O padrão aceita o bloco tipado (com data-bloco) e o antigo.
        for alvo in alvos_da_celula:
            rotulo = re.escape(_rotulo_alvo(alvo))
            padrao = (
                r'<details class="comentario"[^>]*>'
                r'<summary>[^<]*\(' + rotulo + r'\)</summary>'
                r'.*?</details>\s*'
            )
            resultado_html = re.sub(padrao, '', resultado_html, flags=re.DOTALL)

        if alvos_da_celula:
            resultado_html = mesclar_comentarios(
                resultado_html, comentarios_txt, add_sintese=False
            )
            total_inseridos += sum(len(v) for v in alvos_da_celula.values())

        return resultado_html

    for item in linhas:
        nums_frente = _extrair_nums_artigo_do_html(item['frente'])
        nums_verso  = _extrair_nums_artigo_do_html(item['verso'])
        nums_relevantes_f = nums_frente & artigos_com_comentario
        nums_relevantes_v = nums_verso  & artigos_com_comentario

        if not nums_relevantes_f and not nums_relevantes_v:
            continue

        total_cartoes_afetados += 1
        if nums_relevantes_f:
            item['frente'] = _injetar_comentarios_na_celula(
                item['frente'], nums_relevantes_f)
        if nums_relevantes_v:
            item['verso'] = _injetar_comentarios_na_celula(
                item['verso'], nums_relevantes_v)

    novo_conteudo = _serializar_anki_export(cabecalho, linhas)
    nao_encontrados = [f'Art. {n}' for n in artigos_com_comentario
                       if not any(n in _extrair_nums_artigo_do_html(item['frente']) or
                                  n in _extrair_nums_artigo_do_html(item['verso'])
                                  for item in linhas)]

    relatorio = (
        f'✅ {total_inseridos} comentário(s) inserido(s) em '
        f'{total_cartoes_afetados} cartão(ões)'
    )
    if nao_encontrados:
        relatorio += f' | ⚠️ Não encontrados: {", ".join(nao_encontrados)}'

    return novo_conteudo, relatorio


# ============================================================
# EXPORTAÇÃO DIRETA EM PDF (CHROMIUM / PLAYWRIGHT)
# ============================================================

import base64
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


_PDF_CSS = r"""
/*
CONTROLE DA ENTRELINHA DO PDF

--pdf-entrelinha:
    distância entre as linhas dos dispositivos legais.

--pdf-entrelinha-comentario:
    distância entre as linhas dos comentários.

Use ponto nos valores:
    1.10 = mais compacto
    1.05 = configuração inicial
    1.25 = mais espaçado
*/
:root {
    --pdf-entrelinha: 1.05;
    --pdf-entrelinha-comentario: 1.05;
}

* {
    box-sizing: border-box;
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
}

html,
body {
    margin: 0;
    padding: 0;
    background: white;
    color: #171717;
    font-family: Arial, 'DejaVu Sans', sans-serif;
}

body {
    font-size: var(--pdf-font, 11px);
    line-height: var(--pdf-entrelinha);
}

.pdf-title {
    margin: 0 0 7px;
    padding-bottom: 4px;
    border-bottom: 2px solid #3b0a0a;
    font-size: 21px;
    line-height: 1.2;
    text-align: left;
    break-after: avoid;
}

/* Espaço entre os grupos de assuntos. */
.note-container {
    margin: 0 0 6px;
    break-inside: auto;
}

/* O capítulo engloba as seções e aparece antes da primeira delas. */
.pdf-capitulo {
    background: #260606;
    color: white;
    padding: 6px 8px;
    margin: 0 0 4px;
    font-size: 14px;
    font-weight: 700;
    line-height: 1.25;
    text-align: left;
    break-inside: avoid;
    break-after: avoid;
}
.pdf-capitulo-numero {
    display: block;
    font-size: 14px;
    margin-bottom: 4px;
}
.pdf-capitulo-titulo {
    display: block;
}

/* Cabeçalho do assunto. */
.pdf-assunto {
    background: #3b0a0a;
    color: white;
    padding: 4px 7px;
    margin: 0 0 3px;
    font-size: 12px;
    font-weight: 700;
    line-height: 1.2;
    text-align: left;
    break-inside: avoid;
    break-after: avoid;
}

.pdf-sides {
    display: block;
    width: 100%;
    break-inside: auto;
}

.card-wrapper {
    display: block;
    width: 100%;
    margin: 0 0 3px;
    break-inside: auto;
}

/* Sem rótulos de cartão, frente e verso. */
.card-side-label {
    display: none !important;
}

/* Caixa de conteúdo. */
.estilo-lei {
    padding: 3px 3px;
    background: #f3f3f3;
    border: 1px solid #ccc;
    border-radius: 3px;
    line-height: var(--pdf-entrelinha) !important;
    overflow-wrap: break-word;
    break-inside: auto;
    box-decoration-break: clone;
    -webkit-box-decoration-break: clone;
}

/*
DISPOSITIVOS LEGAIS

A entrelinha é aplicada diretamente a cada dispositivo.

O espaçamento entre dispositivos vem do controle do painel e é aplicado
pela variável --pdf-espaco, inclusive para arquivos Anki já formatados.
*/
.estilo-lei > span {
    line-height: var(--pdf-entrelinha) !important;
    text-align: justify !important;
    text-align-last: left !important;
    break-inside: auto !important;
    orphans: 2;
    widows: 2;
    /* Sem hifenizacao, a justificacao em coluna estreira abre
       buracos enormes entre as palavras. */
    hyphens: auto;
    -webkit-hyphens: auto;
    hyphenate-limit-chars: 6 3 3;
}

/* Os controles do painel prevalecem sobre estilos de arquivos Anki antigos. */
.estilo-lei > span[data-dispositivo] {
    display: block !important;
    margin-bottom: var(--pdf-espaco) !important;
}
.estilo-lei > span[data-dispositivo="artigo"],
.estilo-lei > span[data-dispositivo="texto"] {
    padding-left: 0 !important;
}
.estilo-lei > span[data-dispositivo="paragrafo"] {
    padding-left: var(--pdf-recuo-par) !important;
}
.estilo-lei > span[data-dispositivo="inciso"] {
    padding-left: var(--pdf-recuo-inc) !important;
}
.estilo-lei > span[data-dispositivo="alinea"] {
    padding-left: var(--pdf-recuo-ali) !important;
}

/* Evita entrelinha diferente nos destaques internos. */
.estilo-lei > span b,
.estilo-lei > span strong,
.estilo-lei > span em,
.estilo-lei > span i,
.estilo-lei > span a,
.estilo-lei > span span {
    line-height: inherit !important;
}

/* Cabeçalhos internos alinhados à esquerda. */
.estilo-lei > span[style*="font-weight:bold"],
.estilo-lei > span[style*="font-weight: bold"],
.estilo-lei > span[style*="font-weight:700"],
.estilo-lei > span[style*="font-weight: 700"] {
    text-align: left !important;
    text-align-last: left !important;
}

/*
DUAS OU TRÊS COLUNAS:
mantém uma caixa por assunto e o fluxo do texto para impressão.
*/
.layout-combined .pdf-flow,
.layout-three .pdf-flow {
    column-count: 2;
    column-gap: 6mm;
    column-rule: 1px solid #d0d0d0;
    column-fill: balance;
    padding: 3px 3px;
    background: #f3f3f3;
    border: 1px solid #ccc;
    border-radius: 3px;
}

/* TRÊS COLUNAS: menor espaço entre elas para aproveitar a largura do A4. */
.layout-three .pdf-flow {
    column-count: 3;
    column-gap: 4.5mm;
}

/* TEXTO CORRIDO: caixa em toda a largura. */
.layout-continuous .pdf-flow {
    column-count: 1;
    padding: 3px 3px;
    background: #f3f3f3;
    border: 1px solid #ccc;
    border-radius: 3px;
}

/* SEQUENCIAL: cada campo em sua caixa. */
.layout-split .estilo-lei {
    padding: 3px 3px;
    background: #f3f3f3;
    border: 1px solid #ccc;
    border-radius: 3px;
}

/* Comentários com entrelinha própria. */
details.comentario {
    display: block;
    font-size: .94em;
    line-height: var(--pdf-entrelinha-comentario) !important;
    margin: 2px 0;
    padding: 2px 3px;
    background: #eae4da;
    font-style: normal;
    break-inside: auto;
    orphans: 2;
    widows: 2;
    box-decoration-break: clone;
    -webkit-box-decoration-break: clone;
}

details.comentario p,
details.comentario div,
details.comentario li,
details.comentario span {
    line-height: var(--pdf-entrelinha-comentario) !important;
}

details.comentario summary {
    display: block;
    font-weight: 700;
    line-height: var(--pdf-entrelinha-comentario) !important;
    margin-bottom: 4px;
    break-after: avoid;
}

/* Blocos tipados: sem titulo, o summary fica vazio e nao deve
   reservar espaco nem exibir marcador. */
details.comentario[data-bloco] summary {
    display: none;
    margin: 0;
}

details.comentario[data-bloco] .bloco-corpo {
    margin-top: 0;
}

details.comentario summary::marker {
    content: '';
}

details.comentario summary::-webkit-details-marker {
    display: none;
}

details.comentario p {
    margin: 1px 0;
    orphans: 2;
    widows: 2;
}

details.comentario a {
    color: inherit;
    text-decoration: underline;
}

/* Blocos tipados devolvidos pela IA (TABELA, ESQUEMA, QUESTAO, ...). */
details.comentario[data-bloco] {
    background: #eae4da;
}

details.comentario[data-bloco] summary {
    break-after: avoid;
}

details.comentario[data-bloco] .bloco-corpo {
    line-height: var(--pdf-entrelinha-comentario) !important;
}

details.comentario[data-bloco] .bloco-linha {
    margin: 0;
    orphans: 2;
    widows: 2;
}

/*
BLOCO JUSTIFICADO

O conteudo dos blocos (jurisprudencia, questao, doutrina, comentario)
segue a mesma justificacao da letra da lei: o ultimo alinhamento fica
a esquerda, como no texto do dispositivo.
*/
details.comentario[data-bloco] .bloco-corpo,
details.comentario[data-bloco] .bloco-linha {
    text-align: justify !important;
    text-align-last: left !important;
    hyphens: auto;
    -webkit-hyphens: auto;
    hyphenate-limit-chars: 6 3 3;
}

/* Identificacao e gabarito sao curtos: ficam a esquerda. */
details.comentario[data-bloco] .bloco-ident,
details.comentario[data-bloco] .bloco-gabarito {
    text-align: left !important;
    text-align-last: left !important;
}

/* Identificacao do julgado / da referencia: uma linha so. */
details.comentario[data-bloco] .bloco-ident {
    margin: 0 0 1px;
    font-size: .80em;
    font-weight: 700;
    color: #4b4636;
}

/*
BLOCO COMPACTO

A incidencia e a lista de bancas ficam numa unica linha pequena e
cinza claro, logo apos o texto. Sem borda, sem quebra, sem titulo.
*/
details.comentario[data-bloco] .bloco-meta {
    margin: 1px 0 0;
    font-size: .66em;
    line-height: 1.15;
    color: #a39d8d;
    font-style: italic;
}

details.comentario[data-bloco] .bloco-meta-sep {
    color: #c2bcae;
    font-style: normal;
}

details.comentario[data-bloco] .bloco-fontes {
    color: #a39d8d;
    font-size: .72em;
    line-height: 1.15;
}

details.comentario[data-bloco] .bloco-fontes-rotulo {
    font-size: .92em;
    font-style: italic;
}

/* Separador entre as bancas: espaco minimo. */
details.comentario[data-bloco] .bloco-fontes-sep,
details.comentario[data-bloco] .bloco-meta-sep {
    font-size: .85em;
}

/* Gabarito inline, no fim do enunciado. */
details.comentario[data-bloco] .bloco-gabarito {
    font-size: .80em;
    font-weight: 700;
    color: #24506b;
    white-space: nowrap;
}

/* Marcadores de banca no fim do texto legal. */
.estilo-lei > span[data-dispositivo] .marcas-banca {
    font-size: .65em;
    color: #7d7768;
    letter-spacing: -.01em;
}

/*
INCIDENCIA DO DISPOSITIVO

A banca do dispositivo (PGESP-2002, MPSP-2013, ...) fica numa linha
propria, logo ACIMA do texto do dispositivo, em corpo menor.
*/
.incidencia-dispositivo {
    font-size: .76em;
    line-height: 1.2;
    color: #7d7768;
    text-align: left !important;
    text-align-last: left !important;
    break-after: avoid;
    orphans: 2;
    widows: 2;
}

.incidencia-dispositivo .marcas-banca {
    font-size: 1em;
    color: inherit;
}

details.comentario[data-bloco] pre.esquema {
    background: #f7f4ee;
    border: 1px solid #ccc9c0;
    padding: 2px 4px;
    margin: 1px 0;
    font-size: .86em;
    white-space: pre;
    overflow-x: auto;
    line-height: 1.2;
}

details.comentario[data-bloco] table {
    width: 100%;
    border-collapse: collapse;
    font-size: .88em;
    margin: 1px 0;
}

details.comentario[data-bloco] table th {
    background: #e0d8cc;
    font-weight: 700;
}

details.comentario[data-bloco] table td,
details.comentario[data-bloco] table th {
    border: 1px solid #8a857a;
    padding: 1px 3px;
    vertical-align: top;
}

details.comentario[data-bloco="questao"] {
    /* A questao vira caixa: borda completa em vez de bloco colorido. */
    background: #fafcfd;
    border: 1px solid #9db4c6;
    padding: 2px 3px;
    margin: 2px 0;
    font-size: .80em;
}

/* SEPARADOR ENTRE QUESTOES

 A linha fica entre duas questoes de verdade: nunca acima da primeira
 questao de um artigo, e nunca acima da primeira questao do dispositivo.

 Quando duas questoes vem em caixas <details> seguidas, as caixas sao
 fundidas visualmente: a borda de baixo da primeira e a de cima da
 segunda saem, e a linha divisoria fica no meio.

 A marcacao nao vem do seletor CSS adjacente: as questoes de artigos
 distintos nao sao irmas no DOM. Quem marca e o JavaScript do PDF, que
 conhece a ordem real dos blocos.
*/
details.comentario[data-bloco="questao"].bloco-questao-fundida {
    margin-bottom: 0;
    border-bottom: none;
    border-bottom-left-radius: 0;
    border-bottom-right-radius: 0;
    padding-bottom: 3px;
}

details.comentario[data-bloco="questao"].bloco-questao-separada {
    margin-top: 0;
    border-top: none;
    border-top-left-radius: 0;
    border-top-right-radius: 0;
    padding-top: 0;
}

details.comentario[data-bloco="questao"].bloco-questao-separada .bloco-corpo {
    border-top: 1px solid #aaa;
    padding-top: 3px;
}

/* Mais de uma questao dentro do MESMO <details>: a linha entra a
   partir da segunda, nunca antes da primeira. */
details.comentario[data-bloco="questao"] .bloco-linha + .bloco-linha {
    border-top: 1px solid #aaa;
    margin-top: 3px;
    padding-top: 3px;
}

details.comentario[data-bloco="jurisprudencia"] {
    background: #e7e6f0;
    /* A jurisprudencia ganha caixa propria: borda completa para
       separar do texto da lei. */
    border: 1px solid #b9b3d0;
    padding: 2px 3px;
    margin: 2px 0;
    font-size: .80em;
}

details.comentario[data-bloco="doutrina"] {
    background: #eceadf;
}

details.comentario[data-bloco="tabela"] {
    background: #eceae5;
}

details.comentario[data-bloco="esquema"] {
    background: #f0efe8;
}

details.comentario[data-bloco="nota"] {
    background: #f0ece2;
}

table {
    width: 100%;
    border-collapse: collapse;
    font-size: .92em;
    margin: 6px 0;
    break-inside: auto;
}

th,
td {
    border: 1px solid #777;
    padding: 5px 6px;
    vertical-align: top;
    overflow-wrap: break-word;
}

th {
    background: #e0d8cc;
}

thead {
    display: table-header-group;
}

tr {
    break-inside: avoid;
}

img {
    max-width: 100%;
    height: auto;
}

pre {
    white-space: pre-wrap;
    overflow-wrap: anywhere;
}

p,
li {
    orphans: 2;
    widows: 2;
}
"""


_RE_PALAVRA = re.compile(r'([A-Za-zÀ-ÿ]{7,})')


def _hifenizar_html(html):
    """
    Aplica a hifenizacao apenas no texto visivel do HTML.

    As tags ficam intactas: cada trecho entre '<' e '>' e' tratado
    separadamente.
    """
    if not _HIFENIZADOR or not html:
        return html

    partes = re.split(r'(<[^>]*>)', html)
    for i, parte in enumerate(partes):
        if parte.startswith('<'):
            continue
        partes[i] = _hifenizar_texto(parte)
    return ''.join(partes)


_MIN_PARTES = 3
_MAX_PARTES = 3


def _hifenizar_palavra(palavra):
    """
    Insere hifens de divisao em uma palavra longa.

    O pyphen devolve TODOS os pontos de divisao possiveis. Usar todos
    deixaria o texto pontilhado. Aqui cada ponto e usado, no maximo,
    a cada duas divisoes, e cada pedaco precisa ter ao menos 3
    caracteres.
    """
    pontos = _HIFENIZADOR.positions(palavra)
    if not pontos:
        return palavra

    n = len(palavra)
    validos = [i for i in pontos if i >= _MIN_PARTES and n - i >= _MIN_PARTES]
    if not validos:
        return palavra

    # Um ponto de divisao a cada _MAX_PARTES divisoes possiveis.
    escolhidos = validos[::_MAX_PARTES]

    saida = []
    anterior = 0
    for i in escolhidos:
        saida.append(palavra[anterior:i])
        saida.append('&shy;')
        anterior = i
    saida.append(palavra[anterior:])
    return ''.join(saida)


def _hifenizar_texto(texto):
    """
    Insere hifens de divisao em palavras longas.

    O Chromium nao aplica hifenizacao automatica mesmo com o CSS
    correto, e sem ela a justificacao em coluna estreita abre buracos
    enormes entre as palavras. A hifenizacao e feita aqui, por
    software, antes de o texto chegar ao HTML.
    """
    if not _HIFENIZADOR or not texto:
        return texto

    def sub(m):
        return _hifenizar_palavra(m.group(1))

    return _RE_PALAVRA.sub(sub, texto)


def gerar_html_pdf(cartoes, layout_mode='three',
                   titulo='Texto legal comentado',
                   incluir_comentarios=False, fonte=11, css_anki='',
                   espacamento=2, indent_par=2, indent_inc=8, indent_ali=8,
                   entrelinha=1.0, entrelinha_comentario=1.0,
                   assunto_tipo='capitulo'):
    """
    Gera o HTML do PDF sem título visível.

    Preserva:
        caixas;
        cabeçalhos dos assuntos;
        recuos;
        justificação;
        entrelinha;
        separadores acima dos artigos.

    Não modifica os cartões do Anki.
    """
    if layout_mode not in ('split', 'combined', 'three', 'continuous'):
        raise ValueError('Layout do PDF inválido.')

    fonte = max(8, min(20, int(fonte)))
    espacamento = max(0, min(40, int(espacamento)))
    indent_par = max(0, min(60, int(indent_par)))
    indent_inc = max(0, min(80, int(indent_inc)))
    indent_ali = max(0, min(100, int(indent_ali)))
    entrelinha = max(1.0, min(2.0, float(entrelinha)))
    entrelinha_comentario = max(1.0, min(2.0, float(entrelinha_comentario)))
    titulo = titulo or ''
    corpo = []
    grupos = []

    # Não acrescenta o título ao corpo do PDF.

    for cartao in cartoes:
        assunto = str(
            cartao.get('assunto') or 'GERAL'
        ).strip()

        assunto = assunto or 'GERAL'
        capitulo = (cartao.get('capitulo') or {}) if assunto_tipo == 'secao' else {}
        campos = []

        for chave in ('frente', 'verso'):
            campo = cartao.get(chave) or ''

            if campo.strip():
                campos.append((chave, campo))

        if not campos:
            continue

        if (grupos and grupos[-1]['assunto'] == assunto
                and grupos[-1]['capitulo'] == capitulo):
            grupos[-1]['campos'].extend(campos)

        else:
            grupos.append({
                'assunto': assunto,
                'campos': campos,
                'capitulo': capitulo,
            })

    capitulo_anterior = None
    for grupo in grupos:
        capitulo = grupo['capitulo']
        if capitulo and capitulo != capitulo_anterior:
            corpo.append(
                '<div class="pdf-capitulo">'
                '<span class="pdf-capitulo-titulo">'
                + html_lib.escape(capitulo.get('titulo', ''))
                + '</span></div>'
            )
        capitulo_anterior = capitulo
        cabecalho = (
            '<div class="pdf-assunto">'
            + html_lib.escape(grupo['assunto'])
            + '</div>'
        )

        if layout_mode in ('combined', 'three', 'continuous'):
            conteudo = '\n'.join(
                campo
                for _, campo in grupo['campos']
            )

            miolo = (
                '<div class="estilo-lei pdf-flow">'
                + _hifenizar_html(conteudo)
                + '</div>'
            )

        else:
            lados = []

            for chave, campo in grupo['campos']:
                lados.append(
                    '<div class="card-wrapper">'
                    f'<div class="estilo-lei {chave}">'
                    + campo
                    + '</div></div>'
                )

            miolo = (
                '<div class="pdf-sides">'
                + ''.join(lados)
                + '</div>'
            )

        corpo.append(
            '<section class="note-container">'
            + cabecalho
            + miolo
            + '</section>'
        )

    css_separadores = r"""
    .estilo-lei > span.pdf-inicio-artigo {
        border-top: 1px solid #aaa !important;
        margin-top: 6px !important;
        padding-top: 5px !important;
    }
    .estilo-lei > span.pdf-inicio-artigo.pdf-primeiro-artigo {
        border-top: 0 !important;
        margin-top: 0 !important;
        padding-top: 0 !important;
    }
    """

    js = r"""
    // No modo Seção, o assunto já aparece na barra do cabeçalho do PDF.
    if (MODO_SECAO) {
        const normalizarTitulo = texto => texto.replace(/\s+/g, ' ').trim().toUpperCase();
        document.querySelectorAll('.note-container').forEach(secao => {
            const cabecalho = secao.querySelector('.pdf-assunto');
            if (!cabecalho) return;
            const titulo = normalizarTitulo(cabecalho.textContent);
            secao.querySelectorAll('.estilo-lei > span').forEach(el => {
                const repeticao = el.textContent.trim().match(/^\[([\s\S]*)\]$/);
                if (repeticao && normalizarTitulo(repeticao[1]) === titulo) el.remove();
            });
        });
    }

    document.querySelectorAll('details').forEach(el => {
        if (!INCLUIR_COMENTARIOS) {
            el.remove();
            return;
        }

        el.open = true;

        const walker = document.createTreeWalker(
            el,
            NodeFilter.SHOW_TEXT
        );

        const nodes = [];

        while (walker.nextNode()) {
            const n = walker.currentNode;

            if (
                n.parentElement &&
                !n.parentElement.closest(
                    'summary, pre, code, script, style'
                )
            ) {
                nodes.push(n);
            }
        }

        nodes.forEach(n => {
            const s = n.textContent;

            if (!s.includes('**')) return;

            const frag = document.createDocumentFragment();
            const re = /\*\*(.+?)\*\*/g;

            let last = 0;
            let m;

            while ((m = re.exec(s))) {
                frag.append(
                    document.createTextNode(
                        s.slice(last, m.index)
                    )
                );

                const b = document.createElement('b');
                b.textContent = m[1];
                frag.append(b);

                last = re.lastIndex;
            }

            frag.append(
                document.createTextNode(s.slice(last))
            );

            n.replaceWith(frag);
        });
    });

    document.querySelectorAll(
        '.estilo-lei > span'
    ).forEach(el => {
        const texto = el.textContent
            .replace(/[\u200b\u200c\u200d\ufeff]/g, '')
            .trim();

        if (/^(?:★\s*)*Art\.?\s*\d/i.test(texto)) {
            el.classList.add('pdf-inicio-artigo');
            el.dataset.dispositivo = 'artigo';
        } else if (/^(?:§|Par[aá]grafo\s+[úu]nico\b)/i.test(texto)) {
            el.dataset.dispositivo = 'paragrafo';
        } else if (/^[IVXLCDM]+(?:-[A-Za-z])?\s*[-–—]/.test(texto) ||
                   /^\d+[º°ª]?\)/.test(texto)) {
            el.dataset.dispositivo = 'inciso';
        } else if (/^[a-z]\)/.test(texto)) {
            el.dataset.dispositivo = 'alinea';
        }
    });

    // O primeiro artigo após cada cabeçalho dispensa o separador superior.
    document.querySelectorAll('.note-container').forEach(secao => {
        const primeiroArtigo = secao.querySelector(
            '.estilo-lei > span.pdf-inicio-artigo'
        );
        if (primeiroArtigo) primeiroArtigo.classList.add('pdf-primeiro-artigo');
    });

    // SEPARADOR ENTRE QUESTOES
    //
    // A divisoria entra apenas entre duas questoes consecutivas: a
    // questao marcada e a que vem logo depois dela no DOM. A marcacao
    // e feita aqui, e nao por seletor CSS adjacente, porque as
    // questoes de artigos distintos nao sao irmas no DOM.
    document.querySelectorAll(
        'details.comentario[data-bloco="questao"]'
    ).forEach(el => {
        const anterior = el.previousElementSibling;
        if (!anterior) return;
        if (!anterior.matches(
            'details.comentario[data-bloco="questao"]'
        )) return;
        el.classList.add('bloco-questao-separada');
        anterior.classList.add('bloco-questao-fundida');
    });

    document.querySelectorAll(
        '.estilo-lei span[style]'
    ).forEach(el => {
        const cor = getComputedStyle(el).color;

        const m = cor.match(
            /^rgba?\((\d+),\s*(\d+),\s*(\d+)/
        );

        if (
            m &&
            (
                +m[1] * .299 +
                +m[2] * .587 +
                +m[3] * .114
            ) > 170
        ) {
            el.style.color = '#333333';
        }
    });
    """.replace(
        'INCLUIR_COMENTARIOS',
        'true' if incluir_comentarios else 'false'
    ).replace('MODO_SECAO', 'true' if assunto_tipo == 'secao' else 'false')

    css_anki = re.sub(
        r'</style',
        r'<\\/style',
        css_anki or '',
        flags=re.I
    )

    estilos = (
        css_anki
        + '\n'
        + _PDF_CSS
        + '\n'
        + css_separadores
    )

    return (
        '<!DOCTYPE html>'
        '<html lang="pt-BR" class="layout-'
        + layout_mode
        + '">'
        '<head>'
        '<meta charset="UTF-8">'
        '<title>'
        + html_lib.escape(titulo)
        + '</title>'
        '<style>'
        + estilos
        + '</style>'
        '</head>'
        f'<body style="--pdf-font:{fonte}px;'
        f'--pdf-espaco:{espacamento}px;'
        f'--pdf-recuo-par:{indent_par}px;'
        f'--pdf-recuo-inc:{indent_inc}px;'
        f'--pdf-recuo-ali:{indent_ali}px;'
        f'--pdf-entrelinha:{entrelinha};'
        f'--pdf-entrelinha-comentario:{entrelinha_comentario}">'
        + ''.join(corpo)
        + '<script>'
        + js
        + '</script>'
        '</body></html>'
    )


_PDF_RENDERER = r'''
import asyncio
import sys
from pathlib import Path
from playwright.async_api import async_playwright


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=['--no-sandbox']
        )

        try:
            page = await browser.new_page()

            await page.emulate_media(media='print')

            await page.goto(
                Path(sys.argv[1]).resolve().as_uri(),
                wait_until='networkidle'
            )

            await page.evaluate(
                'async () => { await document.fonts.ready; }'
            )

            await page.evaluate("""async () => {
                await Promise.all(
                    Array.from(document.images).map(img => {
                        if (img.complete) {
                            return Promise.resolve();
                        }

                        return new Promise(resolve => {
                            img.addEventListener(
                                'load',
                                resolve,
                                { once: true }
                            );

                            img.addEventListener(
                                'error',
                                resolve,
                                { once: true }
                            );
                        });
                    })
                );
            }""")

            await page.pdf(
                path=sys.argv[2],
                format='A4',
                print_background=True,
                margin={
                    'top': '6mm',
                    'bottom': '7mm',
                    'left': '6mm',
                    'right': '6mm'
                },
                display_header_footer=True,
                header_template='<span></span>',
                footer_template=(
                    '<div style="font-size:9px;'
                    'width:100%;text-align:center;color:#777">'
                    '<span class="pageNumber"></span>'
                    ' / '
                    '<span class="totalPages"></span>'
                    '</div>'
                )
            )

        finally:
            await browser.close()


asyncio.run(main())
'''


def _executar_pdf_comando(comando, timeout=300):
    proc = subprocess.run(comando, capture_output=True, text=True, timeout=timeout)
    if proc.returncode:
        erro = (proc.stderr or proc.stdout or 'Erro desconhecido.').strip()[-1800:]
        raise RuntimeError(erro)
    return proc


def renderizar_pdf(html_content):
    """Processo separado: funciona mesmo com o event loop ativo do Colab."""
    import importlib.util
    if importlib.util.find_spec('playwright') is None:
        _executar_pdf_comando([sys.executable, '-m', 'pip', 'install', '-q', 'playwright==1.52.0'])
    with tempfile.TemporaryDirectory(prefix='lei_pdf_') as pasta:
        origem = Path(pasta) / 'conteudo.html'
        destino = Path(pasta) / 'saida.pdf'
        origem.write_text(html_content, encoding='utf-8')
        comando = [sys.executable, '-c', _PDF_RENDERER, str(origem), str(destino)]
        try:
            _executar_pdf_comando(comando)
        except RuntimeError as exc:
            mensagem = str(exc).lower()
            if 'executable doesn' in mensagem or 'playwright install' in mensagem:
                # Instala o navegador apenas no primeiro uso.
                _executar_pdf_comando([sys.executable, '-m', 'playwright', 'install',
                                      '--with-deps', 'chromium'], timeout=600)
                _executar_pdf_comando(comando)
            else:
                raise
        pdf = destino.read_bytes()
        if not pdf.startswith(b'%PDF-'):
            raise RuntimeError('O renderizador não produziu um PDF válido.')
        return pdf


def _exportar_pdf_callback(texto_bruto, comentarios_txt, espacamento, indent_par,
                           indent_inc, indent_ali, chars_alvo, assunto_tipo='capitulo',
                           layout='three', titulo='Texto legal comentado',
                           incluir_comentarios=False, fonte=11, css_anki='',
                           conteudo_anki='', entrelinha=1.0,
                           entrelinha_comentario=1.0, fontes=None):
    if fontes:
        _configurar_fontes(fontes)
    try:
        if conteudo_anki.strip():
            _, cartoes = _parse_anki_export(conteudo_anki)
            if not any(c['frente'].strip() or c['verso'].strip() for c in cartoes):
                raise ValueError('O arquivo do Anki não contém cartões para converter.')
            txt_anki = ''
        else:
            if not texto_bruto.strip():
                raise ValueError('Cole o texto legal antes de exportar o PDF.')
            cartoes = gerar_importacao_anki(
                texto_bruto, comentarios_txt, int(chars_alvo), int(espacamento),
                int(indent_par), int(indent_inc), int(indent_ali), assunto_tipo,
                _retornar_cartoes=True, entrelinha=entrelinha,
                entrelinha_comentario=entrelinha_comentario)
            if not cartoes:
                raise ValueError('Não foram encontrados cartões para exportar.')
            txt_anki = '\n'.join(f"{c['assunto']}|{c['frente']}|{c['verso']}" for c in cartoes)
        html = gerar_html_pdf(
            cartoes, layout, titulo, incluir_comentarios, fonte, css_anki,
            espacamento, indent_par, indent_inc, indent_ali,
            entrelinha, entrelinha_comentario, assunto_tipo=assunto_tipo)
        pdf = renderizar_pdf(html)
        return IPython.display.JSON({
            'erro': False, 'pdf_base64': base64.b64encode(pdf).decode('ascii'),
            'nome_pdf': 'lei_comentada.pdf', 'conteudo_anki': txt_anki,
            'stats': f'✅ PDF gerado com {len(cartoes)} cartão(ões).'
        })
    except Exception as exc:
        return IPython.display.JSON({'erro': True, 'stats': f'❌ Falha ao gerar PDF: {exc}'})


# ============================================================
# INTEGRAÇÃO COM O KERNEL DO COLAB
# ============================================================

try:
    from google.colab import output as colab_output
    IN_COLAB = True
except ImportError:
    IN_COLAB = False


def _mesclar_no_texto(texto_formatado, comentarios_txt):
    """
    Insere os blocos no TEXTO FORMATADO (sem HTML).

    Usado pelo modo "Texto Limpo". Cada bloco vira um paragrafo
    delimitado por marcadores, logo apos o dispositivo correspondente.
    """
    grupos, sintese = _parse_blocos_tipados(comentarios_txt)
    if not grupos and not sintese:
        return texto_formatado

    for alvo in grupos:
        grupos[alvo] = _ordenar_blocos(grupos[alvo])

    linhas = texto_formatado.split('\n')
    resultado = []
    estado = {'artigo': None, 'paragrafo': None, 'inciso': None,
              'alinea': None}
    alvos_inseridos = set()

    def chave_atual():
        art = estado['artigo']
        if not art:
            return None
        par = estado['paragrafo']
        inc = estado['inciso']
        ali = estado['alinea']
        if inc or ali:
            return (art, par, inc, ali)
        if par:
            return (art, par, None, None)
        return (art, None, None, None)

    def inserir(alvo):
        if alvo is None or alvo in alvos_inseridos:
            return
        for bloco in grupos.get(alvo, []):
            # O ESQUEMA guarda um diagrama alinhado: o espacamento faz
            # parte do desenho e nao pode ser normalizado.
            colapsar = bloco['tipo'] != 'ESQUEMA'
            for linha in bloco['corpo'].split('\n'):
                if linha.strip():
                    # No texto puro o verbete perde os asteriscos: o
                    # italico e do HTML, nao do texto.
                    m_verbete = _RE_VERBETE.match(linha.strip())
                    if m_verbete:
                        resultado.append(m_verbete.group(1).strip())
                        continue
                    resultado.append(
                        _colapsar_espacos(linha) if colapsar else linha.strip()
                    )
            resultado.append('')
        alvos_inseridos.add(alvo)

    for linha in linhas:
        t = linha.strip()
        if t.startswith('#'):
            resultado.append(linha)
            continue

        antes_artigo = estado['artigo']
        _ancora_texto(t, estado)

        if estado['artigo'] != antes_artigo:
            # Fecha o artigo anterior.
            if antes_artigo:
                inserir((antes_artigo, None, None, None))
                for chave in list(grupos.keys()):
                    if chave[0] == antes_artigo and chave not in alvos_inseridos:
                        inserir(chave)

        resultado.append(linha)

        chave = chave_atual()
        if chave is not None and chave in grupos:
            inserir(chave)

    # Alvos remanescentes vao para o fim.
    for chave in list(grupos.keys()):
        if chave not in alvos_inseridos:
            inserir(chave)

    if sintese:
        resultado.append('')
        for linha in sintese.split('\n'):
            if linha.strip():
                resultado.append(linha.strip())

    return '\n'.join(resultado)


def _ancora_texto(linha, estado):
    """Deduz o dispositivo de uma linha do texto formatado."""
    m_art = re.search(r'\bArt\.\s*(\d+(?:\s*[º°])?(?:\s*-\s*[A-Za-z])?)',
                      linha, re.IGNORECASE)
    if m_art:
        estado['artigo'] = _normalizar_num_artigo(m_art.group(1))
        estado['paragrafo'] = None
        estado['inciso'] = None
        estado['alinea'] = None
        return estado

    m_par = re.search(r'§\s*(\d+)', linha)
    m_unico = re.search(r'par[aá]grafo\s+[úu]nico', linha, re.IGNORECASE)
    if m_par or m_unico:
        estado['paragrafo'] = str(int(m_par.group(1))) if m_par else 'unico'
        estado['inciso'] = None
        estado['alinea'] = None
        return estado

    m_inc = re.search(r'(?:^|\s)([IVXLCDM]{1,6}(?:-[A-Za-z])?)\s*[-–—]',
                      linha, re.IGNORECASE)
    if m_inc:
        estado['inciso'] = m_inc.group(1).upper()
        estado['alinea'] = None
        return estado

    m_ali = re.search(r'(?:^|\s)([a-z])\)\s', linha, re.IGNORECASE)
    if m_ali:
        estado['alinea'] = m_ali.group(1).lower()

    return estado


def _processar_callback(texto_bruto, formato, espacamento, indent_par, indent_inc,
                       indent_ali, comentarios_txt='', chars_alvo=1500,
                       assunto_tipo='capitulo', entrelinha=1.0,
                       entrelinha_comentario=1.0, fontes=None):
    if fontes:
        _configurar_fontes(fontes)
    if not texto_bruto.strip():
        return IPython.display.JSON({'resultado': '', 'stats': '⚠️ Cole o texto legal antes de formatar!', 'erro': True})

    esp  = int(espacamento)
    ipar = int(indent_par)
    iinc = int(indent_inc)
    iali = int(indent_ali)

    texto_formatado = formatar_texto_legal(texto_bruto)

    if formato == 'texto':
        res = texto_formatado
        stats_str = 'Formatação de texto aplicada.'
        if comentarios_txt.strip():
            # Mescla também no texto limpo: o bloco vira texto corrido
            # logo abaixo do dispositivo, entre chaves, para não perder
            # a posição do comentário na leitura.
            res = _mesclar_no_texto(texto_formatado, comentarios_txt)
            stats_str += ' (+ Comentários)'
    elif formato == 'anki':
        html_anki, stats = formatar_para_anki(texto_formatado, esp, ipar, iinc, iali, entrelinha)
        if comentarios_txt.strip():
            html_anki = mesclar_comentarios(html_anki, comentarios_txt,
                                           entrelinha_comentario=entrelinha_comentario)
            stats_str = f"Art: {stats['artigos']} | Inc: {stats['incisos']} | Alín: {stats['alineas']} | §: {stats['paragrafos']} (+ Comentários)"
        else:
            stats_str = f"Art: {stats['artigos']} | Inc: {stats['incisos']} | Alín: {stats['alineas']} | §: {stats['paragrafos']}"
        res = html_anki
    else:
        html_anki, stats = formatar_para_anki(texto_formatado, esp, ipar, iinc, iali, entrelinha)
        if comentarios_txt.strip():
            html_anki = mesclar_comentarios(html_anki, comentarios_txt,
                                           entrelinha_comentario=entrelinha_comentario)
            stats_str = f"Art: {stats['artigos']} | Inc: {stats['incisos']} | Alín: {stats['alineas']} | §: {stats['paragrafos']} (+ Comentários)"
        else:
            stats_str = f"Art: {stats['artigos']} | Inc: {stats['incisos']} | Alín: {stats['alineas']} | §: {stats['paragrafos']}"
        res = (
            "═══ TEXTO FORMATADO ═══\n\n"
            + texto_formatado
            + "\n\n\n═══ HTML ANKI ═══\n\n"
            + html_anki
        )

    cartoes = gerar_importacao_anki(
        texto_bruto, comentarios_txt, int(chars_alvo), esp, ipar, iinc, iali,
        assunto_tipo, _retornar_cartoes=True, entrelinha=entrelinha,
        entrelinha_comentario=entrelinha_comentario)
    stats_str += f' | {len(cartoes)} cartão(ões) no visualizador'
    return IPython.display.JSON({
        'resultado': res, 'stats': stats_str, 'erro': False, 'cartoes': cartoes})


def _mesclar_callback(html_anki, comentarios_txt, entrelinha_comentario=1.0,
                     cartoes=None, fontes=None):
    if fontes:
        _configurar_fontes(fontes)
    if not html_anki.strip():
        return IPython.display.JSON({'resultado': '', 'stats': '⚠️ Formate o texto primeiro!', 'erro': True})
    if not comentarios_txt.strip():
        return IPython.display.JSON({'resultado': '', 'stats': '⚠️ Cole os comentários da IA!', 'erro': True})

    resultado = mesclar_comentarios(html_anki, comentarios_txt,
                                   entrelinha_comentario=entrelinha_comentario)
    cartoes_atualizados = []
    for cartao in cartoes or []:
        atualizado = dict(cartao)
        for campo in ('frente', 'verso'):
            if atualizado.get(campo, '').strip():
                atualizado[campo] = mesclar_comentarios(
                    atualizado[campo], comentarios_txt, add_sintese=False,
                    entrelinha_comentario=entrelinha_comentario)
        cartoes_atualizados.append(atualizado)
    return IPython.display.JSON({
        'resultado': resultado, 'stats': '✅ Comentários mesclados com sucesso!',
        'erro': False, 'cartoes': cartoes_atualizados})


def _exportar_callback(texto_bruto, comentarios_txt, espacamento, indent_par,
                      indent_inc, indent_ali, chars_alvo, assunto_tipo='capitulo',
                      entrelinha=1.0, entrelinha_comentario=1.0, fontes=None):
    if fontes:
        _configurar_fontes(fontes)
    if not texto_bruto.strip():
        return IPython.display.JSON({'conteudo': '', 'stats': '⚠️ Texto vazio!', 'erro': True})
    cartoes = gerar_importacao_anki(
        texto_bruto,
        comentarios_txt=comentarios_txt,
        chars_alvo=int(chars_alvo),
        espacamento=int(espacamento),
        indent_par=int(indent_par),
        indent_inc=int(indent_inc),
        indent_ali=int(indent_ali),
        assunto_tipo=assunto_tipo,
        _retornar_cartoes=True,
        entrelinha=entrelinha,
        entrelinha_comentario=entrelinha_comentario
    )
    conteudo = '\n'.join(f"{c['assunto']}|{c['frente']}|{c['verso']}" for c in cartoes)
    n = len(cartoes)
    return IPython.display.JSON({
        'conteudo': conteudo,
        'stats': f'✅ {n} cartão(ões) gerados para importação no Anki',
        'erro': False,
        'cartoes': cartoes
    })




def _atualizar_callback(conteudo_anki, comentarios_txt, fontes=None):
    if fontes:
        _configurar_fontes(fontes)
    if not conteudo_anki.strip():
        return IPython.display.JSON({'conteudo': '', 'stats': '⚠️ Cole o conteúdo do arquivo exportado do Anki!', 'erro': True})
    if not comentarios_txt.strip():
        return IPython.display.JSON({'conteudo': '', 'stats': '⚠️ Cole os novos comentários!', 'erro': True})
    novo_conteudo, relatorio = atualizar_arquivo_anki(conteudo_anki, comentarios_txt)
    erro = novo_conteudo == conteudo_anki and '⚠️' in relatorio
    return IPython.display.JSON({'conteudo': novo_conteudo, 'stats': relatorio, 'erro': erro})

if IN_COLAB:
    colab_output.register_callback('_processar_callback', _processar_callback)
    colab_output.register_callback('_mesclar_callback',   _mesclar_callback)
    colab_output.register_callback('_exportar_callback',  _exportar_callback)
    colab_output.register_callback('_atualizar_callback', _atualizar_callback)
    colab_output.register_callback('_exportar_pdf_callback', _exportar_pdf_callback)


# ============================================================
# INTERFACE VISUAL (HTML / CSS / JS)
# ============================================================

_HTML_UI = r"""
<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<style>
  :root {
    --bg-dark:      #1a1a2e;
    --bg-panel:     #16213e;
    --bg-textarea:  #141429;
    --fg-text:      #e0e0e0;
    --fg-label:     #a0a0b8;
    --fg-title:     #4a0000;
    --accent-gold:  #e8a838;
    --accent-hover: #4a0000;
    --accent-green: #2ecc71;
    --accent-red:   #e74c3c;
    --accent-blue:  #3a7ca5;
    --accent-teal:  #2a9d8f;
    --border:       #2a2a4a;
    --btn-gray:     #555570;
  }

  * { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    background: var(--bg-dark);
    color: var(--fg-text);
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    padding: 20px;
    border-radius: 10px;
  }

  .header {
    background: var(--bg-panel);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 16px 22px;
    margin-bottom: 16px;
  }
  .header h1 { color: var(--fg-title); font-size: 21px; margin-bottom: 4px; }
  .header p  { color: var(--fg-label); font-size: 13px; }

  .section-divider {
    border: none;
    border-top: 1px solid var(--border);
    margin: 18px 0 14px 0;
  }

  .section-label {
    color: var(--accent-gold);
    font-size: 13px;
    font-weight: 700;
    margin-bottom: 7px;
    display: flex;
    align-items: center;
    gap: 7px;
  }
  .section-label.teal { color: var(--accent-teal); }

  textarea {
    width: 100%;
    background: var(--bg-textarea);
    color: var(--fg-text);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 12px 14px;
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 13px;
    resize: vertical;
    transition: border-color .2s;
    line-height: 1.55;
  }
  textarea:focus { outline: none; border-color: var(--accent-gold); }
  #input-texto       { height: 185px; }
  #output-texto      { height: 170px; }
  #input-comentarios { height: 130px; border-color: #2a4a3a; }
  #input-comentarios:focus { border-color: var(--accent-teal); }

  .options-bar {
    background: var(--bg-panel);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 13px 18px;
    margin: 14px 0;
    display: flex;
    align-items: center;
    gap: 16px;
    flex-wrap: wrap;
  }
  .opt-label { color: var(--fg-label); font-size: 13px; font-weight: 600; }
  .radio-group { display: flex; gap: 20px; }
  .radio-group label {
    display: flex; align-items: center; gap: 7px;
    font-size: 14px; cursor: pointer; color: var(--fg-text);
  }
  input[type="radio"] {
    accent-color: var(--accent-gold); width: 15px; height: 15px; cursor: pointer;
  }

  .indent-panel {
    background: var(--bg-panel);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 14px 18px;
    margin-bottom: 14px;
  }
  .indent-title {
    color: var(--accent-gold);
    font-size: 13px;
    font-weight: 700;
    margin-bottom: 12px;
    display: flex;
    align-items: center;
    gap: 7px;
  }
  .indent-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px 24px;
  }
  .slider-row {
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .slider-row label {
    color: var(--fg-label);
    font-size: 12.5px;
    min-width: 170px;
    white-space: nowrap;
  }
  .slider-row input[type="range"] {
    flex: 1;
    accent-color: var(--accent-gold);
    cursor: pointer;
  }
  .slider-val {
    color: var(--accent-gold);
    font-weight: 700;
    font-size: 13px;
    min-width: 32px;
    text-align: right;
  }

  .comentario-panel {
    background: #0d1f1a;
    border: 1px solid #2a4a3a;
    border-radius: 8px;
    padding: 14px 18px;
    margin-bottom: 14px;
  }
  .comentario-panel .indent-title { color: var(--accent-teal); }

  .formato-hint {
    background: #0a1a14;
    border: 1px solid #1a3a2a;
    border-radius: 5px;
    padding: 8px 12px;
    margin-bottom: 10px;
    font-family: 'Consolas', monospace;
    font-size: 12px;
    color: #6fcf97;
    line-height: 1.6;
  }

  .btn-group { display: flex; gap: 10px; margin-bottom: 16px; flex-wrap: wrap; }
  button {
    padding: 10px 22px; border: none; border-radius: 6px;
    font-weight: 700; font-size: 14px; cursor: pointer;
    display: flex; align-items: center; gap: 8px;
    transition: background .18s, transform .1s;
  }
  button:active { transform: scale(.97); }
  .btn-primary   { background: var(--accent-gold);  color: #000; }
  .btn-primary:hover   { background: var(--accent-hover); color: #fff; }
  .btn-secondary { background: var(--btn-gray);     color: #fff; }
  .btn-secondary:hover { background: #6a6a8a; }
  .btn-tertiary  { background: var(--accent-blue);  color: #fff; }
  .btn-tertiary:hover  { background: #4b8eb8; }
  .btn-teal      { background: var(--accent-teal);  color: #fff; }
  .btn-teal:hover      { background: #38b2a3; }
  .btn-green     { background: #3a6b3a;             color: #fff; }
  .btn-green:hover     { background: #4a8b4a; }

  .status-bar {
    background: var(--bg-panel);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 11px 18px;
    margin-top: 16px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 13px;
    flex-wrap: wrap;
    gap: 8px;
  }
  #msg   { color: var(--fg-label); }
  #stats { color: var(--accent-gold); font-weight: 700; }

  /* ── Visualizador ── */
  .viz-card {
    background: var(--bg-panel);
    border: 1px solid #2a2a4a;
    border-radius: 8px;
    overflow: hidden;
    transition: border-color .2s;
  }
  .viz-card:hover { border-color: #4a3a7a; }
  .viz-card-header {
    background: #0f0f28;
    padding: 7px 14px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1px solid #2a2a4a;
  }
  .viz-card-guid { color: #4a4a7a; font-size: 11px; font-family: monospace; }
  .viz-card-assunto { color: var(--accent-gold); font-size: 11px; font-weight: 700; }
  .viz-card-body {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0;
  }
  .viz-lado {
    padding: 12px 14px;
    font-size: 12.5px;
    line-height: 1.55;
    color: var(--fg-text);
    min-height: 60px;
  }
  .viz-lado:first-child {
    border-right: 1px solid #2a2a4a;
  }
  .viz-lado-label {
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    color: #4a4a7a;
    margin-bottom: 6px;
    letter-spacing: .06em;
  }
  .viz-lado details {
    margin-top: 6px;
    border: 1px solid #2a3a5a;
    border-radius: 4px;
    padding: 4px 8px;
    background: #0a0a1e;
  }
  .viz-lado details summary {
    cursor: pointer;
    color: #7c9fd4;
    font-size: 11.5px;
    font-weight: 600;
    padding: 2px 0;
    list-style: none;
  }
  .viz-lado details summary::before { content: "▶ "; font-size: 9px; }
  .viz-lado details[open] summary::before { content: "▼ "; font-size: 9px; }
  .viz-lado details p, .viz-lado details div { font-size: 12px; margin-top: 4px; color: #b0b8d0; }
  .viz-vazio { color: #3a3a5a; font-style: italic; font-size: 12px; }
</style>
</head>
<body>

<div class="header">
  <h1>🎓 Formatador de Lei · ANKI + PDF</h1>
  <p>Cole o texto legal bruto, configure a hierarquia, formate e opcionalmente mescle comentários da IA</p>
</div>

<div class="section-label">📋 Texto Legal Bruto:</div>
<textarea id="input-texto" placeholder="Cole a lei aqui..."></textarea>

<div class="options-bar">
  <span class="opt-label">⚙ Formato:</span>
  <div class="radio-group" style="margin-right:20px;">
    <label><input type="radio" name="fmt" value="texto"> Texto Limpo</label>
    <label><input type="radio" name="fmt" value="anki" checked> HTML Anki</label>
    <label><input type="radio" name="fmt" value="ambos"> Ambos</label>
  </div>

  <span class="opt-label" style="margin-left:10px;">📌 Assunto (Tag):</span>
  <div class="radio-group">
    <label><input type="radio" name="assunto_tipo" value="secao"> Seção</label>
    <label><input type="radio" name="assunto_tipo" value="capitulo" checked> Capítulo</label>
  </div>
</div>

<div class="indent-panel">
  <div class="indent-title">📐 Hierarquia e Espaçamento</div>
  <div class="indent-grid">
    <div class="slider-row">
      <label>Espaço entre dispositivos:</label>
      <input type="range" id="sl-espaco" min="0" max="40" value="2"
             oninput="updateVal('val-espaco', this.value + 'px')">
      <span class="slider-val" id="val-espaco">5px</span>
    </div>
    <div class="slider-row">
      <label>Recuo — Parágrafo (§):</label>
      <input type="range" id="sl-par" min="0" max="60" step="4" value="2"
             oninput="updateVal('val-par', this.value + 'px')">
      <span class="slider-val" id="val-par">4px</span>
    </div>
    <div class="slider-row">
      <label>Recuo — Inciso (I, II, III):</label>
      <input type="range" id="sl-inc" min="0" max="80" step="4" value="8"
             oninput="updateVal('val-inc', this.value + 'px')">
      <span class="slider-val" id="val-inc">12px</span>
    </div>
    <div class="slider-row">
      <label>Recuo — Alínea (a), b)):</label>
      <input type="range" id="sl-ali" min="0" max="100" step="4" value="8"
             oninput="updateVal('val-ali', this.value + 'px')">
      <span class="slider-val" id="val-ali">12px</span>
    </div>
    <div class="slider-row">
      <label>📜 Tamanho alvo por lado (Anki):</label>
      <input type="range" id="sl-chars" min="600" max="3000" step="100" value="1500"
             oninput="updateVal('val-chars', this.value + ' ch')">
      <span class="slider-val" id="val-chars">1500 ch</span>
    </div>
    <div class="slider-row">
      <label>Entrelinha do texto legal:</label>
      <input type="range" id="sl-entrelinha" min="1" max="2" step="0.01" value="1"
             oninput="updateVal('val-entrelinha', Number(this.value).toFixed(2))">
      <span class="slider-val" id="val-entrelinha">1.05</span>
    </div>
    <div class="slider-row">
      <label>Entrelinha dos comentários:</label>
      <input type="range" id="sl-entrelinha-comentario" min="1" max="2" step="0.01" value="1"
             oninput="updateVal('val-entrelinha-comentario', Number(this.value).toFixed(2))">
      <span class="slider-val" id="val-entrelinha-comentario">1.05</span>
    </div>
  </div>
  <p style="font-size:12px;margin-top:10px;color:#aaa;">Após alterar os controles, clique em Formatar para atualizar o visualizador. A exportação usa os valores atuais. O tamanho alvo agrupa os cartões do Anki e do visualizador; no PDF em colunas, o texto flui conforme a largura e a altura da página. Artigos são mantidos inteiros nos cartões e podem ultrapassar o tamanho alvo.</p>
</div>

<div class="indent-panel">
  <div class="indent-title">🔠 Tamanho das Fontes (padronização)</div>
  <div class="indent-grid">
    <div class="slider-row">
      <label>Bloco (comentário/nota):</label>
      <input type="range" id="sl-f-bloco" min="30" max="200" step="1" value="94"
             oninput="updateVal('val-f-bloco', this.value + '%')">
      <span class="slider-val" id="val-f-bloco">94%</span>
    </div>
    <div class="slider-row">
      <label>Jurisprudência/Doutrina:</label>
      <input type="range" id="sl-f-juris" min="30" max="200" step="1" value="80"
             oninput="updateVal('val-f-juris', this.value + '%')">
      <span class="slider-val" id="val-f-juris">80%</span>
    </div>
    <div class="slider-row">
      <label>Questão:</label>
      <input type="range" id="sl-f-questao" min="30" max="200" step="1" value="80"
             oninput="updateVal('val-f-questao', this.value + '%')">
      <span class="slider-val" id="val-f-questao">80%</span>
    </div>
    <div class="slider-row">
      <label>Corpo do bloco:</label>
      <input type="range" id="sl-f-corpo" min="30" max="200" step="1" value="100"
             oninput="updateVal('val-f-corpo', this.value + '%')">
      <span class="slider-val" id="val-f-corpo">100%</span>
    </div>
    <div class="slider-row">
      <label>Identificação do julgado:</label>
      <input type="range" id="sl-f-ident" min="30" max="200" step="1" value="80"
             oninput="updateVal('val-f-ident', this.value + '%')">
      <span class="slider-val" id="val-f-ident">80%</span>
    </div>
    <div class="slider-row">
      <label>Linha de incidência:</label>
      <input type="range" id="sl-f-meta" min="30" max="200" step="1" value="66"
             oninput="updateVal('val-f-meta', this.value + '%')">
      <span class="slider-val" id="val-f-meta">66%</span>
    </div>
    <div class="slider-row">
      <label>Lista de bancas (fontes):</label>
      <input type="range" id="sl-f-fontes" min="30" max="200" step="1" value="72"
             oninput="updateVal('val-f-fontes', this.value + '%')">
      <span class="slider-val" id="val-f-fontes">72%</span>
    </div>
    <div class="slider-row">
      <label>Gabarito da questão:</label>
      <input type="range" id="sl-f-gabarito" min="30" max="200" step="1" value="80"
             oninput="updateVal('val-f-gabarito', this.value + '%')">
      <span class="slider-val" id="val-f-gabarito">80%</span>
    </div>
    <div class="slider-row">
      <label>Marcadores no texto legal:</label>
      <input type="range" id="sl-f-marcas" min="30" max="200" step="1" value="65"
             oninput="updateVal('val-f-marcas', this.value + '%')">
      <span class="slider-val" id="val-f-marcas">65%</span>
    </div>
    <div class="slider-row">
      <label>Incidência do dispositivo:</label>
      <input type="range" id="sl-f-incidencia" min="30" max="200" step="1" value="76"
             oninput="updateVal('val-f-incidencia', this.value + '%')">
      <span class="slider-val" id="val-f-incidencia">76%</span>
    </div>
    <div class="slider-row">
      <label>Esquema (diagrama):</label>
      <input type="range" id="sl-f-esquema" min="30" max="200" step="1" value="86"
             oninput="updateVal('val-f-esquema', this.value + '%')">
      <span class="slider-val" id="val-f-esquema">86%</span>
    </div>
    <div class="slider-row">
      <label>Tabela:</label>
      <input type="range" id="sl-f-tabela" min="30" max="200" step="1" value="88"
             oninput="updateVal('val-f-tabela', this.value + '%')">
      <span class="slider-val" id="val-f-tabela">88%</span>
    </div>
  </div>
  <div class="btn-group" style="margin-top:12px;margin-bottom:0">
    <button class="btn-secondary" onclick="restaurarFontes()">↩️ Restaurar tamanhos padrão</button>
  </div>
  <p style="font-size:12px;margin-top:10px;color:#aaa;">Percentuais em relação à fonte do cartão. O tamanho é gravado como estilo inline no HTML: o resultado é idêntico no Anki e no PDF, independente do CSS do deck.</p>
</div>

<div class="btn-group">
  <button class="btn-primary"   id="btn-run"    onclick="processar()">▶ Formatar, Mesclar e Copiar</button>
  <button class="btn-secondary"                 onclick="limpar()">🗑 Limpar Tudo</button>
  <button class="btn-tertiary"                  onclick="copiar()">📋 Copiar Saída</button>
  <button class="btn-green"     id="btn-export" onclick="exportar()">📥 Exportar para Anki (.txt)</button>
  <button class="btn-teal" id="btn-pdf" onclick="exportarPdf(false)">📄 Exportar PDF</button>
  <button class="btn-green" id="btn-ambos" onclick="exportarPdf(true)">📦 Baixar Anki + PDF</button>
</div>


<div class="indent-panel" style="margin-top:14px;">
  <div class="indent-title">📄 Configurações do PDF</div>
  <div style="display:flex;gap:16px;align-items:center;flex-wrap:wrap;">
    <label>Layout:
      <select id="pdf-layout"
        style="padding:7px;background:#151525;color:#ddd;border:1px solid #555;">
        <option value="three" selected>Três colunas para impressão</option>
        <option value="combined">Duas colunas econômicas</option>
        <option value="continuous">Texto corrido — uma coluna</option>
        <option value="split">Frente e verso em sequência</option>
      </select>
    </label>
    <label><input id="pdf-comentarios" type="checkbox" checked> Incluir comentários abertos</label>
    <label>Fonte: <input id="pdf-fonte" type="number" min="8" max="20" value="9"
       style="width:55px;padding:6px;background:#151525;color:#ddd;border:1px solid #555;"> px</label>
  </div>
  <label style="display:block;margin-top:10px;">Título do PDF:
    <input id="pdf-titulo" value="Texto legal comentado"
      style="width:100%;margin-top:5px;padding:8px;background:#151525;color:#ddd;border:1px solid #555;">
  </label>
  <details style="margin-top:10px;"><summary style="cursor:pointer;">CSS do Anki (opcional)</summary>
    <textarea id="pdf-css" style="height:80px;margin-top:8px;" placeholder="Cole o estilo do Anki, se quiser personalizar o PDF."></textarea>
  </details>
  <p style="font-size:12px;margin:10px 0 0;color:#aaa;">PDF A4 com numeração de páginas. Usa o texto, os comentários e os recuos atuais. Na primeira exportação, aguarde a instalação do renderizador.</p>
</div>

<div class="section-label">📄 Resultado:</div>
<textarea id="output-texto" readonly placeholder="O resultado aparecerá aqui..."></textarea>

<hr class="section-divider">

<div class="comentario-panel">
  <div class="indent-title">💬 Mesclar Comentários da IA</div>

  <div class="formato-hint">
    Formato esperado (um por linha):<br>
    Art. 6º|Comentário geral do Art. 6º...<br>
    Art. 6º, inciso I|Comentário específico do inciso I...<br>
    Art. 6º, inciso XXIII, alínea a|Comentário específico da alínea a...<br>
    Art. 10, § 1º|Comentário específico do § 1º...<br>
    Art. 10, § 1º, inciso II|Comentário específico do inciso II do § 1º...<br>
    SINTESE|Síntese final do bloco.
  </div>

  <div class="section-label teal" style="margin-bottom:7px">📝 Cole os comentários gerados pela IA:</div>
  <textarea id="input-comentarios"
    placeholder="Art. X|comentário geral&#10;Art. X, inciso II|comentário do inciso&#10;Art. X, § 1º|comentário do parágrafo&#10;Art. X, § 1º, inciso III|comentário do inciso do parágrafo&#10;Art. X, inciso II, alínea a|comentário da alínea"></textarea>

  <div class="btn-group" style="margin-top:10px;margin-bottom:0">
    <button class="btn-teal" id="btn-merge" onclick="mesclar()">💬 Mesclar Comentários no HTML</button>
    <button class="btn-secondary" onclick="limparComentarios()">🗑 Limpar Comentários</button>
  </div>
</div>


<hr class="section-divider">

<!-- ═══ BLOCO 3: ATUALIZAR ARQUIVO EXPORTADO DO ANKI ═══ -->
<div class="comentario-panel" style="border-color:#3a2a5a;background:#0d0d1f;">
  <div class="indent-title" style="color:#a78bfa;">📥 Atualizar Arquivo Exportado do Anki</div>

  <div class="formato-hint" style="color:#c4b5fd;border-color:#3a2a5a;background:#0a0a18;">
    Use quando já exportou os cartões do Anki (File &gt; Export) e quer adicionar<br>
    comentários novos sem perder os GUIDs nem os comentários anteriores.<br><br>
    1. Cole abaixo o conteúdo do arquivo .txt exportado (com #separator:tab etc.)<br>
    2. Use o campo de comentários acima com os novos comentários<br>
    3. Clique em "Atualizar e Baixar" — o arquivo pronto será baixado automaticamente
  </div>

  <div class="section-label" style="color:#a78bfa;margin-bottom:7px">📄 Conteúdo do arquivo exportado do Anki (.txt):</div>
  <textarea id="input-anki-export" style="height:140px;border-color:#3a2a5a;"
    placeholder="#separator:tab&#10;#html:true&#10;#guid column:1&#10;jJ0kmav6AA&#9;&quot;&lt;span...&gt;&lt;b&gt;Art. 1.&lt;/b&gt;...&quot;&#9;ASSUNTO&#9;&quot;verso...&quot;"></textarea>

  <div class="btn-group" style="margin-top:10px;margin-bottom:0">
    <button id="btn-atualizar" onclick="atualizarAnki()"
      style="background:#7c3aed;color:#fff;padding:10px 22px;border:none;border-radius:6px;font-weight:700;font-size:14px;cursor:pointer;display:flex;align-items:center;gap:8px;">
      🔄 Atualizar e Baixar
    </button>
    <button class="btn-teal" id="btn-pdf-anki" onclick="exportarPdf(false, true)">📄 PDF deste arquivo Anki</button>
    <button onclick="document.getElementById('input-anki-export').value=''"
      class="btn-secondary">🗑 Limpar</button>
  </div>
</div>

<div class="status-bar">
  <span id="msg">Pronto — cole o texto e clique em Formatar</span>
  <span id="stats"></span>
</div>

<!-- ═══ VISUALIZADOR DE CARTÕES ═══ -->
<div id="visualizador-wrapper" style="display:none;margin-top:18px;">
  <div style="background:var(--bg-panel);border:1px solid #3a2a5a;border-radius:8px;padding:14px 18px;margin-bottom:12px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px;">
    <span style="color:#a78bfa;font-size:13px;font-weight:700;">🔍 Visualizador de Cartões</span>
    <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;">
      <span style="color:var(--fg-label);font-size:12px;">Filtrar:</span>
      <input id="viz-filtro" type="text" placeholder="artigo ou assunto..."
        oninput="vizFiltrar()"
        style="background:var(--bg-textarea);color:var(--fg-text);border:1px solid #3a2a5a;
               border-radius:5px;padding:5px 10px;font-size:12px;width:180px;">
      <span id="viz-contador" style="color:var(--accent-gold);font-size:12px;font-weight:700;"></span>
      <button onclick="document.getElementById('visualizador-wrapper').style.display='none'"
        style="background:#3a2a5a;color:#a78bfa;border:none;border-radius:5px;padding:5px 12px;
               font-size:12px;cursor:pointer;">✕ Fechar</button>
    </div>
  </div>
  <div id="viz-lista" style="display:flex;flex-direction:column;gap:10px;max-height:700px;overflow-y:auto;padding-right:4px;"></div>
</div>

<script>
  const $ = id => document.getElementById(id);

  function updateVal(id, val) { $(id).innerText = val; }

  function setStatus(msg, color) {
    $('msg').innerText = msg;
    $('msg').style.color = color || 'var(--fg-label)';
  }

  function setStats(txt) { $('stats').innerText = txt; }

  // ── Painel de tipografia: tamanhos de fonte ──
  const _FONTES_PADRAO = {
    bloco: 94, juris: 80, questao: 80, corpo: 100, ident: 80, meta: 66,
    fontes: 72, gabarito: 80, marcas: 65, incidencia: 76, esquema: 86,
    tabela: 88
  };

  function coletarFontes() {
    const out = {};
    for (const chave in _FONTES_PADRAO) {
      const el = $('sl-f-' + chave);
      if (el) out[chave] = parseFloat(el.value);
    }
    return out;
  }

  function restaurarFontes() {
    for (const chave in _FONTES_PADRAO) {
      const el = $('sl-f-' + chave);
      if (!el) continue;
      el.value = _FONTES_PADRAO[chave];
      updateVal('val-f-' + chave, el.value + '%');
    }
    setStatus('↩️  Tamanhos restaurados. Clique em Formatar para aplicar.', 'var(--accent-gold)');
  }

  async function processar() {
    const btn = $('btn-run');
    btn.innerHTML = '⏳ Processando...';
    btn.disabled = true;

    const texto   = $('input-texto').value;
    const formato = document.querySelector('input[name="fmt"]:checked').value;
    const espaco  = parseInt($('sl-espaco').value);
    const par     = parseInt($('sl-par').value);
    const inc     = parseInt($('sl-inc').value);
    const ali     = parseInt($('sl-ali').value);
    const chars   = parseInt($('sl-chars').value);
    const assuntoTipo = document.querySelector('input[name="assunto_tipo"]:checked').value;
    const entrelinha = parseFloat($('sl-entrelinha').value);
    const entrelinhaComentario = parseFloat($('sl-entrelinha-comentario').value);
    const comentarios = $('input-comentarios').value;

    if (!texto.trim()) {
      setStatus('⚠️  Cole o texto legal antes de formatar!', 'var(--accent-red)');
      btn.innerHTML = '▶ Formatar, Mesclar e Copiar';
      btn.disabled = false;
      return;
    }

    try {
      const result = await google.colab.kernel.invokeFunction(
        '_processar_callback', [texto, formato, espaco, par, inc, ali, comentarios,
          chars, assuntoTipo, entrelinha, entrelinhaComentario, coletarFontes()], {}
      );
      const data = result.data['application/json'];
      $('output-texto').value = data.resultado;
      if (!data.erro) vizPopularCartoes(data.cartoes);
      setStats(data.stats);
      if (!data.erro) {
        setStatus('✅  Processado com sucesso!', 'var(--accent-green)');
        _copiarTexto(data.resultado, true);
      } else {
        setStatus(data.stats, 'var(--accent-red)');
      }
    } catch (e) {
      setStatus('❌  Erro de comunicação com o Python.', 'var(--accent-red)');
      console.error(e);
    }

    btn.innerHTML = '▶ Formatar, Mesclar e Copiar';
    btn.disabled = false;
  }

  async function mesclar() {
    const btn = $('btn-merge');
    btn.innerHTML = '⏳ Mesclando...';
    btn.disabled = true;

    const html        = $('output-texto').value;
    const comentarios = $('input-comentarios').value;

    if (!html.trim()) {
      setStatus('⚠️  Formate o texto primeiro (clique em "Formatar").', 'var(--accent-red)');
      btn.innerHTML = '💬 Mesclar Comentários no HTML';
      btn.disabled = false;
      return;
    }
    if (!comentarios.trim()) {
      setStatus('⚠️  Cole os comentários da IA antes de mesclar.', 'var(--accent-red)');
      btn.innerHTML = '💬 Mesclar Comentários no HTML';
      btn.disabled = false;
      return;
    }

    try {
      const result = await google.colab.kernel.invokeFunction(
        '_mesclar_callback', [html, comentarios,
          parseFloat($('sl-entrelinha-comentario').value), _vizCartoes,
          coletarFontes()], {}
      );
      const data = result.data['application/json'];
      if (!data.erro) {
        $('output-texto').value = data.resultado;
        if (data.cartoes && data.cartoes.length) {
          vizPopularCartoes(data.cartoes);
        } else {
          vizPopularHtml(data.resultado);
        }
        setStats(data.stats);
        setStatus('✅  Comentários mesclados! HTML atualizado na saída.', 'var(--accent-green)');
        _copiarTexto(data.resultado, true);
      } else {
        setStatus(data.stats, 'var(--accent-red)');
      }
    } catch (e) {
      setStatus('❌  Erro ao mesclar.', 'var(--accent-red)');
      console.error(e);
    }

    btn.innerHTML = '💬 Mesclar Comentários no HTML';
    btn.disabled = false;
  }

  function limpar() {
    $('input-texto').value      = '';
    $('output-texto').value     = '';
    $('input-comentarios').value = '';
    setStats('');
    setStatus('🗑  Campos limpos — pronto para novo texto.');
  }

  function limparComentarios() {
    $('input-comentarios').value = '';
    setStatus('🗑  Comentários limpos.');
  }

  function copiar() {
    const txt = $('output-texto').value;
    if (!txt) {
      setStatus('⚠️  Nada para copiar — formate um texto primeiro.', 'var(--accent-red)');
      return;
    }
    _copiarTexto(txt, false);
  }

async function _copiarTexto(txt, isAuto) {
  let copiado = false;

  try {
    await navigator.clipboard.writeText(txt);
    copiado = true;

  } catch (_) {
    const elementoAnterior = document.activeElement;
    const scrollXAnterior = window.scrollX;
    const scrollYAnterior = window.scrollY;

    const campoTemporario = document.createElement('textarea');

    campoTemporario.value = txt;
    campoTemporario.readOnly = true;

    campoTemporario.style.cssText = [
      'position:fixed',
      'top:0',
      'left:0',
      'width:1px',
      'height:1px',
      'padding:0',
      'border:0',
      'opacity:0',
      'pointer-events:none',
      'font-size:16px'
    ].join(';');

    document.body.appendChild(campoTemporario);

    try {
      campoTemporario.focus({ preventScroll: true });
      campoTemporario.select();

      copiado = document.execCommand('copy');

    } catch (erro) {
      console.error('Falha ao copiar:', erro);

    } finally {
      campoTemporario.remove();

      if (
        elementoAnterior &&
        elementoAnterior.isConnected &&
        typeof elementoAnterior.focus === 'function'
      ) {
        elementoAnterior.focus({ preventScroll: true });
      }

      if (
        window.scrollX !== scrollXAnterior ||
        window.scrollY !== scrollYAnterior
      ) {
        window.scrollTo({
          left: scrollXAnterior,
          top: scrollYAnterior,
          behavior: 'instant'
        });
      }
    }
  }

  if (!copiado) {
    setStatus(
      '⚠️ Não foi possível copiar automaticamente. Copie pelo campo Resultado.',
      'var(--accent-red)'
    );
    return;
  }

  if (!isAuto) {
    setStatus(
      '📋 Saída copiada para a área de transferência!',
      'var(--accent-green)'
    );
  }
}

  async function exportar() {
    const btn = $('btn-export');
    btn.innerHTML = '⏳ Gerando cartões...';
    btn.disabled = true;

    const texto = $('input-texto').value;
    if (!texto.trim()) {
      setStatus('⚠️  Cole o texto antes de exportar!', 'var(--accent-red)');
      btn.innerHTML = '📥 Exportar para Anki (.txt)';
      btn.disabled = false;
      return;
    }

    const espaco = parseInt($('sl-espaco').value);
    const par    = parseInt($('sl-par').value);
    const inc    = parseInt($('sl-inc').value);
    const ali    = parseInt($('sl-ali').value);
    const chars  = parseInt($('sl-chars').value);
    const comentarios = $('input-comentarios').value;
    const assunto_tipo = document.querySelector('input[name="assunto_tipo"]:checked').value;

    try {
      const result = await google.colab.kernel.invokeFunction(
        '_exportar_callback', [texto, comentarios, espaco, par, inc, ali, chars, assunto_tipo,
          parseFloat($('sl-entrelinha').value), parseFloat($('sl-entrelinha-comentario').value),
          coletarFontes()], {}
      );
      const data = result.data['application/json'];
      if (data.erro) {
        setStatus(data.stats, 'var(--accent-red)');
      } else {
        $('output-texto').value = data.conteudo;
        vizPopularCartoes(data.cartoes);
        setStats(data.stats);
        setStatus('✅  Arquivo gerado! Baixando...', 'var(--accent-green)');
        const blob = new Blob([data.conteudo], {type: 'text/plain;charset=utf-8'});
        const url  = URL.createObjectURL(blob);
        const a    = document.createElement('a');
        a.href     = url;
        a.download = 'importar_anki.txt';
        a.click();
        URL.revokeObjectURL(url);
      }
    } catch(e) {
      setStatus('❌  Erro ao exportar.', 'var(--accent-red)');
      console.error(e);
    }

    btn.innerHTML = '📥 Exportar para Anki (.txt)';
    btn.disabled = false;
  }


  function baixarArquivo(blob, nome) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = nome; document.body.appendChild(a);
    a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url), 60000);
  }

  async function exportarPdf(baixarAnki = false, usarArquivoAnki = false) {
    const botoes = ['btn-pdf', 'btn-ambos', 'btn-pdf-anki'].map($);
    const btn = $(usarArquivoAnki ? 'btn-pdf-anki' : baixarAnki ? 'btn-ambos' : 'btn-pdf');
    const rotulo = btn.innerHTML;
    const texto = $('input-texto').value;
    const arquivoAnki = usarArquivoAnki ? $('input-anki-export').value : '';
    if (usarArquivoAnki ? !arquivoAnki.trim() : !texto.trim()) {
      setStatus(usarArquivoAnki ? '⚠️ Cole o arquivo do Anki no campo abaixo.' : '⚠️ Cole o texto legal antes de exportar.', 'var(--accent-red)');
      return;
    }
    botoes.forEach(b => b.disabled = true);
    btn.innerHTML = '⏳ Gerando PDF...';
    setStatus('⏳ Preparando PDF. Na primeira vez, a instalação pode levar alguns minutos.');
    try {
      const args = [texto, $('input-comentarios').value,
        parseInt($('sl-espaco').value), parseInt($('sl-par').value),
        parseInt($('sl-inc').value), parseInt($('sl-ali').value),
        parseInt($('sl-chars').value),
        document.querySelector('input[name="assunto_tipo"]:checked').value,
        $('pdf-layout').value, $('pdf-titulo').value, $('pdf-comentarios').checked,
        parseInt($('pdf-fonte').value) || 9, $('pdf-css').value, arquivoAnki,
        parseFloat($('sl-entrelinha').value), parseFloat($('sl-entrelinha-comentario').value),
        coletarFontes()];
      const result = await google.colab.kernel.invokeFunction('_exportar_pdf_callback', args, {});
      const data = result.data['application/json'];
      if (data.erro) { setStatus(data.stats, 'var(--accent-red)'); return; }
      const bin = atob(data.pdf_base64);
      const bytes = Uint8Array.from(bin, c => c.charCodeAt(0));
      baixarArquivo(new Blob([bytes], {type:'application/pdf'}), data.nome_pdf);
      if (baixarAnki && data.conteudo_anki) {
        baixarArquivo(new Blob([data.conteudo_anki], {type:'text/plain;charset=utf-8'}), 'importar_anki.txt');
        $('output-texto').value = data.conteudo_anki;
      }
      setStats(data.stats);
      setStatus(baixarAnki ? '✅ Anki e PDF gerados. Se o navegador pedir, permita os downloads múltiplos.' : '✅ PDF gerado. Download iniciado.', 'var(--accent-green)');
    } catch (e) {
      setStatus('❌ Erro na exportação do PDF: ' + e.message, 'var(--accent-red)');
      console.error(e);
    } finally {
      btn.innerHTML = rotulo; botoes.forEach(b => b.disabled = false);
    }
  }

  // ── Dados do visualizador (preenchidos após atualização) ──
  let _vizCartoes = [];

  function vizPopularCartoes(cartoes) {
    _vizCartoes = (cartoes || []).map(c => ({guid: '', ...c}));
    $('viz-filtro').value = '';
    vizRenderizar(_vizCartoes);
    $('visualizador-wrapper').style.display = 'block';
  }

  function vizPopular(conteudoTxt) {
  const linhas = conteudoTxt
    .split('\n')
    .filter(l => l.trim() && !l.startsWith('#'));

  _vizCartoes = [];

  for (const linha of linhas) {
    const cols = _parseTsvLinha(linha);

    if (cols.length < 2) continue;

    const guid = (cols[0] || '').trim();
    const frente = _desescapar(cols[1] || '');
    const assunto = (cols[2] || '').trim();
    const verso = _desescapar(cols[3] || '');

    _vizCartoes.push({
      guid,
      frente,
      assunto,
      verso
    });
  }

  vizRenderizar(_vizCartoes);

  document.getElementById(
    'visualizador-wrapper'
  ).style.display = 'block';

  // Atualiza o visualizador sem rolar até ele.
}

  function _parseTsvLinha(linha) {
    // Lida com células entre aspas duplas com "" como escape interno
    const cols = [];
    let i = 0, n = linha.length;
    while (i < n) {
      if (linha[i] === '"') {
        // Campo entre aspas
        i++; // pula a aspa de abertura
        let campo = '';
        while (i < n) {
          if (linha[i] === '"') {
            if (i + 1 < n && linha[i + 1] === '"') {
              campo += '"'; i += 2; // "" → "
            } else {
              i++; break; // fecha aspas
            }
          } else {
            campo += linha[i++];
          }
        }
        cols.push(campo);
        if (i < n && linha[i] === '\t') i++; // pula o tab separador
      } else {
        // Campo sem aspas
        let j = linha.indexOf('\t', i);
        if (j === -1) j = n;
        cols.push(linha.slice(i, j));
        i = j + 1;
      }
    }
    return cols;
  }

  function _desescapar(html) {
    // Remove aspas externas se presentes e desescapa "" → "
    // (já feito pelo parser, mas garante)
    return html;
  }

  function _resumirArtigos(html) {
    // Extrai lista de artigos presentes no HTML para o cabeçalho
    const matches = [...html.matchAll(/<b>(?:★+&nbsp;|★+\s*)?Art\.\s*([\d\w\-º°\.]+)/g)];
    if (!matches.length) return '';
    const nums = [...new Set(matches.map(m => 'Art. ' + m[1].replace(/[º°\.]+$/, '')))];
    return nums.slice(0, 4).join(', ') + (nums.length > 4 ? '...' : '');
  }

function vizPopularHtml(htmlStr) {
  const blocos = htmlStr.split(
    /(?=<span[^>]*>(?:★+&nbsp;|★+\s*)?<b>Art\.)/
  );

  _vizCartoes = blocos
    .filter(b => b.trim())
    .map(b => ({
      guid: '',
      frente: b,
      assunto: '',
      verso: ''
    }));

  vizRenderizar(_vizCartoes);

  document.getElementById(
    'visualizador-wrapper'
  ).style.display = 'block';

  // Atualiza o visualizador sem rolar até ele.
}

  function vizRenderizar(cartoes) {
    const lista = document.getElementById('viz-lista');
    const contador = document.getElementById('viz-contador');
    contador.textContent = cartoes.length + ' cartão(ões)';

    if (!cartoes.length) {
      lista.innerHTML = '<div style="color:#4a4a6a;padding:20px;text-align:center;">Nenhum cartão encontrado.</div>';
      return;
    }

    lista.innerHTML = cartoes.map((c, idx) => {
      const artigos = _resumirArtigos(c.frente + c.verso);
      const versoHtml = c.verso.trim()
        ? `<div class="viz-lado-label">VERSO</div>${c.verso}`
        : `<div class="viz-lado-label">VERSO</div><span class="viz-vazio">(vazio)</span>`;

      return `
        <div class="viz-card" data-idx="${idx}">
          <div class="viz-card-header">
            <span class="viz-card-guid">${c.guid || '—'}</span>
            <span style="color:#6a6a9a;font-size:11px;">${artigos}</span>
            <span class="viz-card-assunto">${c.assunto || '—'}</span>
          </div>
          <div class="viz-card-body">
            <div class="viz-lado">
              <div class="viz-lado-label">FRENTE</div>
              ${c.frente || '<span class="viz-vazio">(vazio)</span>'}
            </div>
            <div class="viz-lado">
              ${versoHtml}
            </div>
          </div>
        </div>`;
    }).join('');
  }

  function vizFiltrar() {
    const termo = document.getElementById('viz-filtro').value.toLowerCase().trim();
    if (!termo) {
      vizRenderizar(_vizCartoes);
      return;
    }
    const filtrados = _vizCartoes.filter(c =>
      c.frente.toLowerCase().includes(termo) ||
      c.verso.toLowerCase().includes(termo)  ||
      c.assunto.toLowerCase().includes(termo)||
      c.guid.toLowerCase().includes(termo)
    );
    vizRenderizar(filtrados);
  }

  async function atualizarAnki() {
    const btn = $('btn-atualizar');
    btn.innerHTML = '⏳ Atualizando...';
    btn.disabled = true;

    const conteudoAnki = $('input-anki-export').value;
    const comentarios  = $('input-comentarios').value;

    if (!conteudoAnki.trim()) {
      setStatus('⚠️  Cole o arquivo exportado do Anki no campo abaixo.', 'var(--accent-red)');
      btn.innerHTML = '🔄 Atualizar e Baixar';
      btn.disabled = false;
      return;
    }
    if (!comentarios.trim()) {
      setStatus('⚠️  Cole os novos comentários no campo "Mesclar Comentários da IA".', 'var(--accent-red)');
      btn.innerHTML = '🔄 Atualizar e Baixar';
      btn.disabled = false;
      return;
    }

    try {
      const result = await google.colab.kernel.invokeFunction(
        '_atualizar_callback', [conteudoAnki, comentarios, coletarFontes()], {}
      );
      const data = result.data['application/json'];
      setStats(data.stats);
      if (!data.erro) {
        setStatus('✅  Arquivo atualizado! Baixando...', 'var(--accent-green)');
        $('output-texto').value = data.conteudo;

        // ── Dispara download ──
        const blob = new Blob([data.conteudo], {type: 'text/plain;charset=utf-8'});
        const url  = URL.createObjectURL(blob);
        const a    = document.createElement('a');
        $('input-anki-export').value = data.conteudo;
        a.href = url; a.download = 'anki_atualizado.txt'; a.click();
        URL.revokeObjectURL(url);

        // ── Popula o visualizador ──
        vizPopular(data.conteudo);
        setStatus('✅  Atualizado, baixado e visualizado abaixo!', 'var(--accent-green)');
      } else {
        setStatus(data.stats, 'var(--accent-red)');
      }
    } catch(e) {
      setStatus('❌  Erro ao atualizar.', 'var(--accent-red)');
      console.error(e);
    }

    btn.innerHTML = '🔄 Atualizar e Baixar';
    btn.disabled = false;
  }

</script>
</body>
</html>
"""

# ============================================================
# EXIBIR INTERFACE
# ============================================================

if IN_COLAB:
    display(HTML(_HTML_UI))
else:
    print("Execute este script em um notebook do Google Colab para ver a interface visual.")
    print("Fora do Colab, use o arquivo Formatador_Lei_Anki_GUI.py (versão desktop).")
