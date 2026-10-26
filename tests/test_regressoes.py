"""
Regressao dos bugs corrigidos na spec 0001.

Cada teste deste arquivo falharia sem a correcao correspondente.
A regra de negocio esta no comentario do teste, nao no codigo.
"""

import pytest


# ------------------------------------------------------------------
# Incidencia do dispositivo (bug: incidencia ficava no fim do artigo)
# ------------------------------------------------------------------

def test_incidencia_vai_para_linha_propria(fmt):
    """A incidencia e extraida do fim do texto do dispositivo."""
    linha = 'Art. 3o Texto do artigo. (PGESP-2002) (MPSP-2013)'
    corpo, incidencia = fmt._separar_incidencia(linha)

    assert corpo == 'Art. 3o Texto do artigo.'
    assert incidencia == 'PGESP-2002; MPSP-2013'


def test_incidencia_aceita_anos_multiplos(fmt):
    """Bug: o regex de banca recusava 'MPSP-2005/2008/2013'."""
    _, incidencia = fmt._separar_incidencia(
        'Art. 3o Texto. (MPSP-2005/2008/2013)'
    )
    assert incidencia == 'MPSP-2005/2008/2013'


def test_incidencia_aceita_banca_com_estado_e_organo(fmt):
    """Bancas como 'Cartorios/TJMG-2018' sao validas."""
    _, incidencia = fmt._separar_incidencia(
        'Art. 3o Texto. (Cartorios/TJMG-2018) (PGM-Goiania/GO-2015)'
    )
    assert incidencia == 'Cartorios/TJMG-2018; PGM-Goiania/GO-2015'


def test_incidencia_ignora_parenteses_que_nao_sao_banca(fmt):
    """Nota do planalto nao pode ser confundida com incidencia."""
    linha = 'Art. 3o Texto. (Incluido pela Lei 13.709/2018)'
    corpo, incidencia = fmt._separar_incidencia(linha)

    assert incidencia == ''
    assert corpo == linha


def test_incidencia_antecede_o_dispositivo_no_html(fmt):
    """A incidencia precisa vir ANTES do dispositivo no HTML."""
    lei = 'Art. 3o Texto do artigo. (PGESP-2002)'
    html, _ = fmt.formatar_para_anki(fmt.formatar_texto_legal(lei))

    pos_incidencia = html.find('incidencia-dispositivo')
    pos_artigo = html.find('Art. 3º')

    assert pos_incidencia != -1, 'incidencia nao foi renderizada'
    assert pos_artigo != -1, 'dispositivo nao foi renderizado'
    assert pos_incidencia < pos_artigo


def test_incidencia_aparece_em_todos_os_artigos(fmt):
    """Bug: '#INC:' era tratado como cabecalho e quebrava o artigo.

    Com o bug, so a primeira incidencia do documento sobrevivia.
    """
    lei = (
        'Art. 1o Texto. (MPRR-2008)\n'
        'Art. 2o Texto. (MPCE-2011)\n'
        'Art. 3o Texto. (TJPI-2012)'
    )
    cartoes = fmt.gerar_importacao_anki(
        lei, '', 1500, 2, 2, 8, 8, 'capitulo', _retornar_cartoes=True
    )
    total = sum(
        c['frente'].count('incidencia-dispositivo') + c['verso'].count('incidencia-dispositivo')
        for c in cartoes
    )

    assert total == 3, 'esperava 3 incidencias, obteve %d' % total


def test_incidencia_nao_vaza_para_o_corpo_do_artigo(fmt):
    """O parentese da banca nao pode sobrar no texto do dispositivo."""
    lei = 'Art. 3o Texto do artigo. (PGESP-2002)'
    html, _ = fmt.formatar_para_anki(fmt.formatar_texto_legal(lei))

    linha_artigo = html[html.find('data-dispositivo="artigo"'):]
    linha_artigo = linha_artigo[:linha_artigo.find('</span>')]

    assert '(PGESP-2002)' not in linha_artigo


# ------------------------------------------------------------------
# Blocos tipados (bug: modo texto e atualizar_arquivo_anki perdiam tudo)
# ------------------------------------------------------------------

BLOCOS_TIPADOS = """QUESTAO|Art. 2º, § 1º|Questao|96
ENUNCIADO: Julgue o item.
RESPOSTA: Certo

COMENTARIO|Art. 3º|Dica|88
Texto da dica.
"""

TIPOS = ('questao', 'comentario', 'tabela', 'esquema',
         'jurisprudencia', 'doutrina', 'nota')


LEI_COMPLETA = (
    'Art. 1º. Disposicao geral.\n'
    'Art. 2º. O parcelamento somente pode ocorrer:\n'
    '§ 1º O loteamento subdivide.\n'
    '§ 2º O desmembramento divide.\n'
    'Art. 2º-A. Disposicao acrescida:\n'
    'a) Primeira alinea.\n'
    'Art. 3º. Outra disposicao.\n'
    'Parágrafo único. Regra do parágrafo único.'
)


def _blocos_completo():
    return """QUESTAO|Art. 2º, § 1º|Questao|96
ENUNCIADO: Julgue o item.
RESPOSTA: Certo

COMENTARIO|Art. 2º, § 1º e 2º|Dica|88
Texto da dica.

TABELA|Art. 2º, § 1º e 2º|Tabela|85
| A | B |
|---|---|
| 1 | 2 |

ESQUEMA|Art. 3º|Fluxo|70
A
|
v
B

JURISPRUDENCIA|Art. 2º-A|Julgado|74
TRIBUNAL: STF
EMENTA: Ementa.

DOUTRINA|Art. 1º|Tese|65
AUTOR: Autor
OBRA: Obra
TESE: Tese.

NOTA|Art. 3º, parágrafo único|Aviso|40
Texto da nota.

SINTESE|
Sintese geral.
"""


def test_todos_os_tipos_de_bloco_sao_gerados(fmt):
    """Os sete tipos de bloco devem chegar ao HTML."""
    html, _ = fmt.formatar_para_anki(
        fmt.formatar_texto_legal(LEI_COMPLETA)
    )
    html = fmt.mesclar_comentarios(html, _blocos_completo())

    for tipo in TIPOS:
        assert 'data-bloco="%s"' % tipo in html, 'faltou o tipo %s' % tipo


def test_modo_texto_limpo_nao_descarta_comentarios(fmt):
    """Bug: o modo 'texto' retornava o texto sem os comentarios."""
    lei = 'Art. 2º. O parcelamento somente pode ocorrer:\n§ 1º O loteamento subdivide.'
    out = fmt._processar_callback(
        lei, 'texto', 2, 2, 8, 8, BLOCOS_TIPADOS, 1500, 'capitulo', 1.0, 1.0
    )
    resultado = out.data['resultado']

    assert 'Julgue o item.' in resultado
    assert 'Texto da dica.' in resultado


def test_modo_texto_limpo_nao_mostra_titulo_de_bloco(fmt):
    """O modo texto nao deve rotular 'Questao' ou 'Comentario'."""
    lei = 'Art. 2º. O parcelamento somente pode ocorrer:\n§ 1º O loteamento subdivide.'
    out = fmt._processar_callback(
        lei, 'texto', 2, 2, 8, 8, BLOCOS_TIPADOS, 1500, 'capitulo', 1.0, 1.0
    )
    resultado = out.data['resultado']

    assert '>>>' not in resultado
    assert 'Questão -' not in resultado
    assert 'Comentário -' not in resultado


def test_modo_anki_insere_blocos(fmt):
    """O caminho principal deve mesclar todos os blocos."""
    out = fmt._processar_callback(
        LEI_COMPLETA, 'anki', 2, 2, 8, 8, _blocos_completo(), 1500, 'capitulo', 1.0, 1.0
    )
    resultado = out.data['resultado']

    for tipo in TIPOS:
        assert 'data-bloco="%s"' % tipo in resultado


def test_botao_mesclar_insere_no_html_existente(fmt):
    """O botao 'Mesclar' opera sobre o HTML ja formatado."""
    lei = 'Art. 2º. O parcelamento somente pode ocorrer:\n§ 1º O loteamento subdivide.'
    primeiro = fmt._processar_callback(
        lei, 'anki', 2, 2, 8, 8, '', 1500, 'capitulo', 1.0, 1.0
    )
    assert '<details' not in primeiro.data['resultado']

    segundo = fmt._mesclar_callback(
        primeiro.data['resultado'], _blocos_completo(), 1.0, []
    )
    assert '<details' in segundo.data['resultado']


def test_formato_antigo_continua_funcionando(fmt):
    """O formato 'Art. X|texto' nao pode ter quebrado."""
    html = '<span data-dispositivo="artigo"><b>Art. 2º</b> Texto.</span>'
    resultado = fmt.mesclar_comentarios(html, 'Art. 2º|comentario antigo')

    assert '<details' in resultado
    assert 'comentario antigo' in resultado


# ------------------------------------------------------------------
# Titulos dos blocos (bug: titulos ocupavam espaco sem utilidade)
# ------------------------------------------------------------------

def test_blocos_nao_exibem_titulo(fmt):
    """O summary do bloco tipado deve estar vazio."""
    html, _ = fmt.formatar_para_anki(fmt.formatar_texto_legal(LEI_COMPLETA))
    html = fmt.mesclar_comentarios(html, _blocos_completo())

    assert '<summary></summary>' in html
    assert '>Questão<' not in html
    assert '>Jurisprudência<' not in html


def test_bloco_preserva_o_tipo_no_data_bloco(fmt):
    """Sem titulo, o tipo continua marcado para o CSS colorir a caixa."""
    html, _ = fmt.formatar_para_anki(fmt.formatar_texto_legal(LEI_COMPLETA))
    html = fmt.mesclar_comentarios(html, _blocos_completo())

    assert 'data-bloco="jurisprudencia"' in html


# ------------------------------------------------------------------
# Justificacao e hifenizacao
# ------------------------------------------------------------------

def test_css_justifica_os_blocos(fmt):
    """O CSS do PDF precisa justificar o conteudo dos blocos."""
    css = fmt._PDF_CSS

    assert 'text-align: justify !important' in css
    assert 'text-align-last: left !important' in css


def test_blocos_justificados_por_padrao(fmt):
    """A regra de justificacao alcança o corpo do bloco tipado."""
    css = fmt._PDF_CSS
    assert 'details.comentario[data-bloco] .bloco-corpo' in css
    assert 'details.comentario[data-bloco] .bloco-linha' in css


def test_hifenizacao_quebra_palavra_longa(fmt):
    """Palavras longas recebem ponto de divisao."""
    if fmt._HIFENIZADOR is None:
        pytest.skip('pyphen nao instalado')

    resultado = fmt._hifenizar_palavra('desaproveitamento')

    assert '&shy;' in resultado
    assert resultado.replace('&shy;', '') == 'desaproveitamento'


def test_hifenizacao_respeita_o_texto_das_tags(fmt):
    """As tags do HTML nao podem ser alteradas pela hifenizacao."""
    if fmt._HIFENIZADOR is None:
        pytest.skip('pyphen nao instalado')

    html = '<span class="x">desaproveitamento</span>'
    resultado = fmt._hifenizar_html(html)

    assert resultado.startswith('<span class="x">')
    assert resultado.endswith('</span>')
    assert '&shy;' in resultado


def test_hifenizacao_nao_quebra_palavra_curta(fmt):
    """Palavras curtas nao recebem ponto de divisao."""
    if fmt._HIFENIZADOR is None:
        pytest.skip('pyphen nao instalado')

    assert fmt._hifenizar_palavra('lei') == 'lei'


# ------------------------------------------------------------------
# Parser do arquivo exportado do Anki (bug: coluna #guid deslocava tudo)
# ------------------------------------------------------------------

TSV_SEM_GUID = (
    '#separator:tab\n'
    '#html:true\n'
    '#columns:Front\tBack\tTags\n'
    '"<b>Art. 1º.</b> Disposicao geral."\t""\t"GERAL"\t""\n'
    '"<b>Art. 3º.</b> Outra disposicao."\t""\t"GERAL"\t""\n'
)

TSV_COM_GUID = (
    '#separator:tab\n'
    '#html:true\n'
    '#guid column:1\n'
    '#columns:Front\tBack\tTags\n'
    '"abc123"\t"<b>Art. 1º.</b> Disposicao geral."\t""\t"GERAL"\t""\n'
    '"def456"\t"<b>Art. 3º.</b> Outra disposicao."\t""\t"GERAL"\t""\n'
)


BLOCOS_PARA_TSV = """QUESTAO|Art. 1º|Questao|96
ENUNCIADO: Julgue o item.
RESPOSTA: Certo

COMENTARIO|Art. 3º|Dica|88
Texto da dica.
"""


@pytest.mark.parametrize('conteudo', [TSV_SEM_GUID, TSV_COM_GUID])
def test_atualizar_arquivo_anki_insere_blocos(fmt, conteudo):
    """Bug: os campos ficavam deslocados e nada era encontrado."""
    novo, relatorio = fmt.atualizar_arquivo_anki(conteudo, BLOCOS_PARA_TSV)

    assert 'data-bloco' in novo
    assert 'Não encontrados' not in relatorio


def test_atualizar_arquivo_anki_preserva_o_guid(fmt):
    """Com '#guid column:1', o guid original e preservado."""
    novo, _ = fmt.atualizar_arquivo_anki(TSV_COM_GUID, BLOCOS_PARA_TSV)

    assert 'abc123' in novo
    assert 'def456' in novo


def test_atualizar_arquivo_anki_nao_adiciona_guid_inexistente(fmt):
    """Sem '#guid column:1', o guid nao pode ser inventado."""
    novo, _ = fmt.atualizar_arquivo_anki(TSV_SEM_GUID, BLOCOS_PARA_TSV)

    cabecalho = novo.split('\n')
    assert '#guid' not in cabecalho[0]


# ------------------------------------------------------------------
# PDF: checkbox e margens
# ------------------------------------------------------------------

def test_pdf_comentarios_marcado_por_padrao(fmt):
    """Bug: sem o checkbox, o PDF removia todo <details>."""
    html = fmt._HTML_UI
    assert 'id="pdf-comentarios" type="checkbox" checked' in html


def test_margem_da_pagina_reduzida(fmt):
    """A margem da pagina precisa estar em 6mm."""
    assert "'top': '6mm'" in fmt._PDF_RENDERER
    assert "'left': '6mm'" in fmt._PDF_RENDERER
    assert "'right': '6mm'" in fmt._PDF_RENDERER


def test_pdf_mantem_os_blocos_quando_incluidos(fmt):
    """Com 'incluir_comentarios', os blocos ficam no HTML do PDF."""
    cartoes = fmt.gerar_importacao_anki(
        LEI_COMPLETA, BLOCOS_TIPADOS, 1500, 2, 2, 8, 8, 'capitulo', _retornar_cartoes=True
    )
    html = fmt.gerar_html_pdf(
        cartoes, 'three', 'T', True, 9, '', 2, 2, 8, 8, 1.0, 1.0, 'capitulo'
    )

    assert '<details' in html
    assert 'data-bloco' in html


def test_css_da_incidencia_presente_no_pdf(fmt):
    """A classe da incidencia precisa existir no CSS do PDF."""
    assert '.incidencia-dispositivo {' in fmt._PDF_CSS


# ------------------------------------------------------------------
# Caixas dos blocos (sem barra lateral, jurisprudencia com borda)
# ------------------------------------------------------------------

def test_blocos_nao_tem_barra_lateral(fmt):
    """A barra vertical foi removida: sobra so o fundo."""
    assert 'border-left' not in fmt._PDF_CSS


def test_jurisprudencia_tem_borda_completa(fmt):
    """A jurisprudencia fica dentro de uma caixa com borda."""
    css = fmt._PDF_CSS
    inicio = css.find('details.comentario[data-bloco="jurisprudencia"]')
    assert inicio != -1, 'a regra da jurisprudencia sumiu'

    trecho = css[inicio:inicio + 400]
    assert 'border:' in trecho, 'a jurisprudencia precisa de borda'
    assert 'background:' in trecho


def test_outros_blocos_mantem_so_o_fundo(fmt):
    """Os demais blocos ficam com fundo, sem borda."""
    css = fmt._PDF_CSS

    for tipo in ('questao', 'doutrina', 'tabela', 'esquema', 'nota'):
        inicio = css.find('details.comentario[data-bloco="%s"]' % tipo)
        assert inicio != -1, 'faltou a regra do tipo %s' % tipo

        regra = css[inicio:inicio + 200]
        regra = regra[:regra.find('}')]
        assert 'border' not in regra, (
            'o tipo %s nao deveria ter borda: %s' % (tipo, regra.strip())
        )


# ------------------------------------------------------------------
# Contrato geral
# ------------------------------------------------------------------

def test_simbolos_esperados_existem(fmt, simbolos_esperados):
    """A suite depende destes simbolos; a ausencia quebra o contrato."""
    faltando = [s for s in simbolos_esperados if not hasattr(fmt, s)]
    assert not faltando, 'faltando: %s' % ', '.join(faltando)


# ------------------------------------------------------------------
# Separador entre itens (bug: linha acima da primeira questao da caixa,
# inclusive quando a caixa tinha uma questao so)
# ------------------------------------------------------------------

def _html_do_pdf(fmt, blocos=BLOCOS_TIPADOS, lei=LEI_COMPLETA):
    cartoes = fmt.gerar_importacao_anki(
        lei, blocos, 1500, 2, 2, 8, 8, 'capitulo', _retornar_cartoes=True
    )
    return fmt.gerar_html_pdf(
        cartoes, 'three', 'T', True, 9, '', 2, 2, 8, 8, 1.0, 1.0, 'capitulo'
    )


def test_separador_so_entre_itens(fmt):
    """A linha de separacao vale apenas para um item que tem anterior."""
    html = _html_do_pdf(fmt)

    assert '.estilo-lei > span.pdf-inicio-artigo:not(:first-child)' in html
    assert '.estilo-lei > span.pdf-inicio-artigo {' not in html, (
        'voltou a regra que desenha a linha em qualquer artigo, '
        'inclusive no primeiro item da caixa'
    )


def test_primeiro_item_da_caixa_nao_recebe_separador(fmt):
    """O primeiro item de cada caixa e marcado para ficar sem linha."""
    html = _html_do_pdf(fmt)

    # A marcacao e por CAIXA, nao por secao: cada .estilo-lei do PDF
    # (uma por cartao no layout sequencial) tem o proprio primeiro item.
    assert ".estilo-lei, .pdf-flow" in html
    assert 'pdf-sem-separador' in html
    assert 'body .pdf-sem-separador' in html
    assert 'border-top: 0 !important' in html.split('body .pdf-sem-separador')[1][:200]


def test_separador_fica_acima_da_incidencia(fmt):
    """A linha separa acima da banca, nao entre a banca e o artigo."""
    html = _html_do_pdf(fmt)

    assert "anterior.classList.contains('incidencia-dispositivo')" in html


def test_caixa_com_uma_questao_nao_tem_linha(fmt):
    """Com um item so nao ha o que separar: nenhuma linha no topo."""
    html = _html_do_pdf(
        fmt,
        blocos='QUESTAO|Art. 1º|Questao|96\nENUNCIADO: Julgue o item.\nRESPOSTA: Certo\n',
    )

    # O unico item da caixa e o bloco da questao: ele nao pode ser
    # marcado como inicio de artigo, que e quem desenha a linha.
    assert 'pdf-sem-separador' in html
    assert 'body .pdf-flow > :first-child' in html
    assert 'body details.comentario[data-bloco] > .bloco-corpo > :first-child' in html


def test_questoes_consecutivas_ficam_separadas(fmt):
    """Duas questoes no mesmo bloco continuam separadas por uma linha."""
    html = _html_do_pdf(fmt)

    assert ('.bloco-linha + .bloco-linha' in html), (
        'a linha que separa duas questoes do mesmo bloco sumiu'
    )


# ------------------------------------------------------------------
# Espacamento das caixas (bug: vao dentro da caixa somado ao de fora)
# ------------------------------------------------------------------

def test_ultimo_item_nao_empurra_a_borda_da_caixa(fmt):
    """O ultimo item da caixa nao reserva margem antes do padding."""
    css = fmt._PDF_CSS

    assert '.estilo-lei > :last-child {' in css
    trecho = css.split('.estilo-lei > :last-child {')[1][:120]
    assert 'margin-bottom: 0 !important' in trecho


def test_bloco_no_fim_da_caixa_sem_margem(fmt):
    """O bloco que fecha a caixa tambem nao deixa vao morto."""
    css = fmt._PDF_CSS

    assert 'details.comentario:last-child {' in css
    trecho = css.split('details.comentario:last-child {')[1][:120]
    assert 'margin-bottom: 0 !important' in trecho


def test_padding_vertical_das_caixas_compacto(fmt):
    """O padding vertical da caixa nao pode voltar a 10px."""
    css = fmt._PDF_CSS

    assert 'padding: 10px 12px' not in css
    assert css.count('padding: 5px 12px 2px') >= 4
