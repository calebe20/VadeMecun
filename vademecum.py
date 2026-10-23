#!/usr/bin/env python3
"""Extração auditável de DOCX e composição de um caderno para impressão."""
import argparse
from collections import Counter
import hashlib
import html
import json
from pathlib import Path
import re
from xml.etree import ElementTree as ET
from zipfile import ZipFile

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
NS = {'w': W}
DIVISION_RE = re.compile(
    r'^(CAP[ÍI]TULO|T[ÍI]TULO|LIVRO|SE[ÇC][ÃA]O|SUBSE[ÇC][ÃA]O|PARTE)\s+'
    r'([IVXLCDM]+|\d+[º°ªo]?|[ÚU]NIC[OA]|GERAL|ESPECIAL|PRELIMINAR|'
    r'PRIMEIR[OA]|SEGUND[OA]|TERCEIR[OA]|QUART[OA]|QUINT[OA]|SEXT[OA]|S[ÉE]TIM[OA]|OITAV[OA]|NON[OA]|D[ÉE]CIM[OA])'
    r'(?:\s*[-–—:]\s*(.+))?$', re.I)


def val(node, name='val', default=''):
    return node.get(f'{{{W}}}{name}', default) if node is not None else default


def text_of(node):
    parts = []
    for el in node.iter():
        tag = el.tag.rsplit('}', 1)[-1]
        if tag == 't':
            parts.append(el.text or '')
        elif tag == 'tab':
            parts.append('\t')
        elif tag in ('br', 'cr'):
            parts.append('\n')
    return ''.join(parts)


def category(text, editorial):
    if not editorial:
        return 'legislacao'
    if text.lstrip().startswith('Última atualização'):
        return 'informacao'
    # Rótulos visuais conservadores: a classificação nunca exclui texto.
    if text.lstrip().startswith('(') and re.search(r'\d{4}', text[:90]):
        return 'questao'
    if re.search(r'#(?:STF|STJ)\b|\b(?:STF|STJ)\.|Súmula', text, re.I):
        return 'jurisprudencia'
    return 'comentario'


AMENDMENT_START = re.compile(
    r'\(\s*(?:Inclu[ií]d[oa]s?|Acrescid[oa]s?|Acrescentad[oa]s?|Inserid[oa]s?|'
    r'Alterad[oa]s?|Renumerad[oa]s?|Revogad[oa]s?|Reda[çc][ãa]o\b[^()]*?dada|'
    r'Vide|Regulament[oa](?:d[oa])?|Vig[êe]ncia|Produ[çc][ãa]o\s+de\s+efeitos|'
    r'(?:Artigo|Par[áa]grafo|Inciso|Al[ií]nea|Item)\s+'
    r'(?:inclu[ií]d[oa]|acrescentad[oa]|alterad[oa]|revogad[oa]))\b', re.I)
NORM_REFERENCE = re.compile(r'\b(?:Lei|Leis|Decreto(?:-Lei)?|Medida\s+Provis[óo]ria|Emenda\s+Constitucional|LC|MP)\b', re.I)


def clean_amendment_runs(runs):
    """Retira notas de alteração balanceadas, preservando os runs e o texto útil."""
    text = ''.join(run['text'] for run in runs)
    removals = []
    previous_end = 0
    for match in AMENDMENT_START.finditer(text):
        if match.start() < previous_end:
            continue
        depth = 0
        end = None
        for index in range(match.start(), len(text)):
            if text[index] == '(':
                depth += 1
            elif text[index] == ')':
                depth -= 1
                if depth == 0:
                    end = index + 1
                    break
        # Não exclua marcações de situação como (VETADO) ou (Revogado),
        # nem uma anotação sem fechamento ou sem referência a outra norma.
        if end is None or not NORM_REFERENCE.search(text[match.start():end]):
            continue
        start = match.start()
        left = start
        while left and text[left - 1] in ' \t\u00a0':
            left -= 1
        if left and end < len(text) and text[end] in '.:;' and text[left - 1] == text[end]:
            end += 1
        if end == len(text) or text[end].isspace() or text[end] in '.,;:!?':
            start = left
        replacement = ' ' if start and end < len(text) and text[start - 1].isalnum() and text[end].isalnum() else ''
        status = re.match(r'\(\s*(Revogad[oa]s?)\b', text[match.start():end], re.I)
        if status:
            # A referência à lei pode sair; a situação do dispositivo deve ficar.
            replacement = (' ' if start and not text[start - 1].isspace() else '') + '(' + status[1] + ')'
            if end < len(text) and text[end].isalnum():
                replacement += ' '
        removals.append((start, end, replacement))
        previous_end = end
    if not removals:
        return runs, 0

    mask = bytearray(len(text))
    insertions = {}
    for start, end, replacement in removals:
        mask[start:end] = b'\x01' * (end - start)
        if replacement:
            insertions[start] = replacement
    cleaned = []
    position = 0
    for run in runs:
        pieces = []
        for char in run['text']:
            if position in insertions:
                pieces.append(insertions[position])
            if not mask[position]:
                pieces.append(char)
            position += 1
        value = ''.join(pieces)
        if value or run.get('notes'):
            cleaned.append({**run, 'text': value})
    return cleaned, len(removals)


class Extractor:
    def __init__(self, source):
        self.source = source
        self.blocks = []
        self.warnings = []
        self.notes = []
        self.article = None

    def paragraph(self, node, editorial=False, part='word/document.xml'):
        text = text_of(node)
        block = {'id': f'p{len(self.blocks) + 1}', 'text': text,
                 'kind': category(text, editorial), 'part': part,
                 'article': self.article, 'runs': []}
        match = re.match(r'^\s*Art(?:igo)?\.?\s*(\d+(?:\.\d+)*|[úu]nico)(?:\s*[º°ªo]|\.[º°ªo])?(?:[-–]([A-Za-z0-9]+))?(?:\s*[º°ªo])?', text, re.I)
        if match and not editorial and part == 'word/document.xml':
            self.article = match[1] + ('-' + match[2] if match[2] else '')
            block['kind'] = 'artigo'
            block['article'] = self.article
        division_text = ''.join(r['text'] for r in clean_amendment_runs([{'text': text}])[0]).strip()
        division = DIVISION_RE.fullmatch(division_text) if not editorial else None
        if division:
            block['kind'] = 'capitulo' if division[1].casefold() in ('capítulo', 'capitulo') else 'divisao'
            block['division_subtitle_expected'] = not division[3] and division[2].casefold() not in ('geral', 'especial', 'preliminar')
        elif not editorial and re.fullmatch(r'DISPOSI[ÇC][ÕO]ES\s+(?:GERAIS|PRELIMINARES|FINAIS|TRANSIT[ÓO]RIAS|FINAIS E TRANSIT[ÓO]RIAS)', text.strip(), re.I):
            block['kind'] = 'divisao'
            block['standalone_division_title'] = True
        for run in node.findall('.//w:r', NS):
            props = run.find('w:rPr', NS)
            item = {'text': text_of(run)}
            if props is not None:
                for prop in ('b', 'i', 'strike', 'caps'):
                    e = props.find('w:' + prop, NS)
                    item[prop] = e is not None and val(e, default='1') not in ('0', 'false', 'off')
                item['underline'] = val(props.find('w:u', NS)) not in ('', 'none', '0')
                item['color'] = val(props.find('w:color', NS))
                item['highlight'] = val(props.find('w:highlight', NS))
                item['vertical'] = val(props.find('w:vertAlign', NS))
            refs = run.findall('w:footnoteReference', NS)
            item['notes'] = [val(e, 'id') for e in refs]
            block['runs'].append(item)
        self.blocks.append(block)
        return {'type': 'paragraph', 'id': block['id']}

    def children(self, parent, editorial=False, part='word/document.xml'):
        result = []
        for node in parent:
            tag = node.tag.rsplit('}', 1)[-1]
            if tag == 'p':
                result.append(self.paragraph(node, editorial, part))
            elif tag == 'tbl':
                rows = []
                for row in node.findall('w:tr', NS):
                    cells = []
                    for cell in row.findall('w:tc', NS):
                        span = val(cell.find('w:tcPr/w:gridSpan', NS), default='1')
                        cells.append({'span': int(span), 'children': self.children(cell, True, part)})
                    rows.append(cells)
                result.append({'type': 'table', 'rows': rows})
            elif tag == 'sdt':
                content = node.find('w:sdtContent', NS)
                if content is not None:
                    result.extend(self.children(content, editorial, part))
        return result

    def extract(self):
        with ZipFile(self.source) as archive:
            root = ET.fromstring(archive.read('word/document.xml'))
            if root.findall('.//w:drawing', NS) or root.findall('.//w:pict', NS):
                self.warnings.append('O arquivo contém imagens: este extrator não as reproduz.')
            if root.findall('.//w:numPr', NS):
                self.warnings.append('Há listas automáticas; conferir numeração gerada pelo Word.')
            if root.findall('.//w:del', NS) or root.findall('.//w:ins', NS):
                self.warnings.append('Há controle de alterações: revisar a extração manualmente.')
            tree = self.children(root.find('w:body', NS))
            # Conferência independente: todos os parágrafos do corpo, inclusive tabelas.
            original = [text_of(p) for p in root.findall('.//w:body//w:p', NS)]
            extracted = [b['text'] for b in self.blocks]
            if original != extracted:
                raise ValueError('A sequência extraída difere dos parágrafos do DOCX. Revisar estrutura.')
            body_count = len(self.blocks)
            for part, tag in [('word/footnotes.xml', 'footnote'), ('word/endnotes.xml', 'endnote')]:
                if part not in archive.namelist():
                    continue
                notes = ET.fromstring(archive.read(part))
                for note in notes.findall('w:' + tag, NS):
                    if int(val(note, 'id')) <= 0:
                        continue
                    self.notes.append({'number': val(note, 'id'), 'type': tag,
                                       'children': self.children(note, True, part)})
            if 'word/comments.xml' in archive.namelist():
                self.warnings.append('Há comentários de revisão do Word, não incorporados ao texto. Conferir no original.')
        # O nome de uma divisão pode vir em outro parágrafo, com linhas vazias entre eles.
        body_blocks = [b for b in self.blocks[:body_count] if b['text'].strip()]
        for prev, current in zip(body_blocks, body_blocks[1:]):
            if (prev.get('division_subtitle_expected') and (current['kind'] == 'legislacao' or current.get('standalone_division_title'))
                    and not re.match(r'^(?:Art\.|§|Parágrafo\b|[IVXLCDM]+\s*[-–]|[a-z]\))', current['text'], re.I)):
                current['kind'] = 'titulo_capitulo' if prev['kind'] == 'capitulo' else 'titulo_divisao'
        return {'source': self.source.name,
                'sha256': hashlib.sha256(self.source.read_bytes()).hexdigest(),
                'body_paragraphs': body_count, 'verified_paragraph_sequence': True,
                'warnings': self.warnings, 'blocks': self.blocks,
                'tree': tree, 'notes': self.notes}


REVOKED_REST = re.compile(
    r'[\s\-–—.:;]*\(\s*revogad[oa]s?(?:\s+pel[oa]\s+[^)]*)?\)?'
    r'[\s.,;:"”\']*(?:\(NR\))?[\s.,;:"”\']*', re.I)
REVOKED_LABEL = re.compile(r'\s*\d+\s*[º°ªoO]?\)')
DIVISION_LEVEL = {'parte': 0, 'livro': 1, 'título': 2, 'titulo': 2, 'capítulo': 3, 'capitulo': 3,
                  'seção': 4, 'secao': 4, 'subseção': 5, 'subsecao': 5}


def is_revoked_text(text):
    """Dispositivo cujo único conteúdo é a marcação (Revogado), com ou sem nota de alteração."""
    cleaned = ''.join(r['text'] for r in clean_amendment_runs([{'text': text}])[0]).strip()
    prefix = DEVICE_PREFIX.match(cleaned) or REVOKED_LABEL.match(cleaned)
    rest = cleaned[prefix.end():] if prefix else cleaned
    return bool(REVOKED_REST.fullmatch(rest))


def revoked_block_ids(blocks):
    """IDs dos dispositivos revogados e dos títulos que ficariam sem conteúdo."""
    legal = ('artigo', 'legislacao', 'capitulo', 'titulo_capitulo', 'divisao', 'titulo_divisao')
    body = [b for b in blocks if b['part'] == 'word/document.xml' and b['text'].strip()]
    removed = {b['id'] for b in body if b['kind'] in ('artigo', 'legislacao') and is_revoked_text(b['text'])}
    revoked_count = len(removed)

    def level(block):
        text = ''.join(r['text'] for r in clean_amendment_runs([{'text': block['text']}])[0]).strip()
        match = DIVISION_RE.match(text)
        return DIVISION_LEVEL.get(match[1].casefold(), 3) if match else 3

    for index in range(len(body) - 1, -1, -1):
        block = body[index]
        if block['kind'] not in ('capitulo', 'divisao') or block['id'] in removed:
            continue
        mine, has_content = level(block), False
        for follower in body[index + 1:]:
            if follower['id'] in removed or follower['kind'] in ('titulo_capitulo', 'titulo_divisao'):
                continue
            if follower['kind'] in ('capitulo', 'divisao'):
                if level(follower) <= mine:
                    break
                continue
            has_content = True
            break
        if not has_content:
            removed.add(block['id'])
            nxt = body[index + 1] if index + 1 < len(body) else None
            if nxt and nxt['kind'] in ('titulo_capitulo', 'titulo_divisao'):
                removed.add(nxt['id'])
    return removed, revoked_count


def run_html(run, colors, plain=False, text=None, citation_class='', add_notes=True):
    raw_text = run['text'] if text is None else text
    value = html.escape(raw_text).replace('\n', '<br>').replace('\t', ' ')
    for flag, tag in [('i', 'em'), ('strike', 's'), ('underline', 'u')]:
        if plain:
            continue
        if run.get(flag):
            value = f'<{tag}>{value}</{tag}>'
    if run.get('vertical') in ('superscript', 'subscript'):
        tag = 'sup' if run['vertical'] == 'superscript' else 'sub'
        value = f'<{tag}>{value}</{tag}>'
    styles = []
    color = run.get('color', '')
    # Branco era usado sobre fundos do Word. No papel branco, convertemos em preto.
    if not plain and colors and re.fullmatch(r'[0-9a-fA-F]{6}', color) and color.upper() != 'FFFFFF':
        styles.append(f'color:#{color}')
    if not plain and colors and run.get('highlight') == 'yellow':
        styles.append('background:#fff4a3')
    if styles:
        value = f'<span style="{";".join(styles)}">{value}</span>'
    if citation_class == 'device-label':
        value = f'<strong class="device-label">{value}</strong>'
    elif citation_class:
        value = f'<span class="{citation_class}">{value}</span>'
    if add_notes:
        for note in run.get('notes', []):
            value += f'<sup><a href="#nota-{note}">[{note}]</a></sup>'
    return value


DEVICE_PREFIX = re.compile(
    r'^\s*('
    r'(?:Art(?:igo)?|ART(?:IGO)?)\.?\s*(?:[úuÚU]nico\.?|\d+(?:\.\d+)*(?:\s*[º°ªoO]|\.[º°ªoO])?(?:[-–][A-Za-z0-9]+)*(?:\s*[º°ªoO])?\.?)'
    r'|(?:Par[áa]grafo\s+[úu]nico|PAR[ÁA]GRAFO\s+[ÚU]NICO)\.?'
    r'|§§?\s*(?:[úuÚU]nico\.?|\d+(?:\.\d+)*(?:\s*[º°ªoO]|\.[º°ªoO])?(?:[-–][A-Za-z0-9]+)*(?:\s*[º°ªoO])?(?:\s*(?:e|a)\s*\d+(?:\s*[º°ªoO]|\.[º°ªoO])?)?\.?)'
    r'|(?:[IVXLCDM]+|Il)(?:[-–][A-Za-z0-9]+)*(?=\s*[-–—.)])'
    r'|[a-zA-Z](?:[-–.][a-zA-Z0-9]+)?\)(?=\s|$)'
    r'|\d+(?:[-–][A-Za-z0-9]+)*[.)](?=\s)|\d+(?:[-–][A-Za-z0-9]+)*(?=\s*[-–—])'
    r'|(?:Pena|PENA)\s*:'
    r')'
)


def paragraph_runs_html(runs, colors, plain=False, citation_class='exam-context', normalize_basis=False):
    """Renderiza runs preservando ênfases, com citações detectadas no texto unido."""
    joined = ''.join(run['text'] for run in runs)
    code = re.compile(r'\b[A-Z][A-Z0-9]*(?:[-/][A-Z0-9ºª°.]+)*-\d{4}(?:/\d{4})*\b', re.I)
    regions = []
    if plain:
        prefix = DEVICE_PREFIX.match(joined)
        if prefix:
            regions.append((*prefix.span(1), 'device-label'))
    if citation_class:
        # O identificador completo pode conter a banca depois do ano e estar
        # dividido em runs: (MPMS-2024-FAPEC). Inclua também os parênteses.
        parentheses = [(m.start(), m.end() + (1 if joined[m.end():m.end() + 1] == ':' else 0))
                       for m in re.finditer(r'\([^()\n]*\)', joined) if code.search(m.group())]
        regions.extend((start, end, citation_class) for start, end in parentheses)
        for match in code.finditer(joined):
            if not any(start <= match.start() and match.end() <= end for start, end in parentheses):
                regions.append((*match.span(), citation_class))
    if normalize_basis:
        basis = re.search(r'\bBL\s*:', joined)
        if basis:
            regions.append((basis.start(), len(joined), 'legal-basis'))

    rendered = []
    position = 0
    for run in runs:
        source = run['text']
        stop = position + len(source)
        cuts = {0, len(source)}
        for start, end, _ in regions:
            if position < start < stop:
                cuts.add(start - position)
            if position < end < stop:
                cuts.add(end - position)
        ordered = sorted(cuts)
        if len(ordered) == 1:  # An empty run may still carry a footnote marker.
            ordered.append(0)
        for index, (left, right) in enumerate(zip(ordered, ordered[1:])):
            chunk_start, chunk_end = position + left, position + right
            marked_class = next((cls for start, end, cls in reversed(regions)
                                 if chunk_start < end and chunk_end > start), '')
            normalized = plain or marked_class in ('exam-context', 'legal-basis')
            rendered.append(run_html(run, colors, normalized, source[left:right], marked_class,
                                     add_notes=index == len(ordered) - 2))
        position = stop
    return re.sub(r'</strong><strong class="device-label">', '', ''.join(rendered))


def render_html(data, paper, columns, font_size, colors, box_styles=None, hide_amendments=False, hide_revoked=False):
    if columns not in (1, 2, 3):
        raise ValueError('Escolha uma, duas ou três colunas.')
    title = next((b['text'] for b in data['blocks'] if b['text'].strip()), data['source'])
    safe_title = html.escape(title)
    short_title = title[:75].replace('"', '').replace('\\', '').replace('\n', ' ')
    lookup = {b['id']: b for b in data['blocks']}
    data['rendered_text_by_id'] = {}
    data['rendered_amendment_removals'] = 0
    data['render_settings'] = {'hide_amendments': bool(hide_amendments), 'hide_revoked': bool(hide_revoked)}
    skipped, data['rendered_revoked_removals'] = revoked_block_ids(data['blocks']) if hide_revoked else (set(), 0)
    kinds = ('questao', 'comentario', 'jurisprudencia')
    defaults = {
        'questao': {'mode': 'fill', 'background': '#fff2c9', 'border_color': '#c9a84a', 'border_width': 1, 'border_style': 'solid'},
        'comentario': {'mode': 'outline', 'background': '#e8eef2', 'border_color': '#90a5b1', 'border_width': 1, 'border_style': 'solid'},
        'jurisprudencia': {'mode': 'outline', 'background': '#e7efe8', 'border_color': '#8ca28e', 'border_width': 1, 'border_style': 'double'},
        'misto': {'mode': 'outline', 'background': '#eef6f6', 'border_color': '#8a9c9f', 'border_width': 1, 'border_style': 'solid'},
    }
    box_styles = {**defaults, **(box_styles or {})}
    for kind in defaults:
        style = box_styles.get(kind, {})
        if style.get('mode') not in ('fill', 'outline', 'plain'):
            raise ValueError(f'Modo de caixa inválido: {kind}')
        for key in ('background', 'border_color'):
            if not re.fullmatch(r'#[0-9a-fA-F]{6}', style.get(key, '')):
                raise ValueError(f'Cor de caixa inválida: {kind}')
        if style.get('border_style') not in ('solid', 'dashed', 'dotted', 'double'):
            raise ValueError(f'Estilo de borda inválido: {kind}')
        if not isinstance(style.get('border_width'), (int, float)) or not 0.5 <= float(style['border_width']) <= 3:
            raise ValueError(f'Espessura de borda inválida: {kind}')

    def omit_original_orientation(table):
        # Mantém as datas de atualização, omitindo a caixa de orientações do DOCX.
        for row in table['rows']:
            for cell in row:
                children = cell['children']
                for index, child in enumerate(children):
                    if child['type'] == 'paragraph' and 'observações quanto à compreensão do material' in lookup[child['id']]['text'].casefold():
                        del children[index:]
                        return
                    if child['type'] == 'table':
                        omit_original_orientation(child)

    def question_table_paragraphs(node):
        if node.get('type') != 'table' or len(node['rows']) != 1 or len(node['rows'][0]) != 1:
            return None
        children = [c for c in node['rows'][0][0]['children']
                    if c['type'] != 'paragraph' or lookup[c['id']]['text'].strip()]
        if not children or any(c['type'] != 'paragraph' or lookup[c['id']]['kind'] != 'questao' for c in children):
            return None
        return children

    def contained_kinds(children):
        found = set()
        for child in children:
            if child['type'] == 'paragraph':
                block = lookup[child['id']]
                if block['text'].strip() and block['kind'] in kinds:
                    found.add(block['kind'])
            else:
                for row in child['rows']:
                    for cell in row:
                        found.update(contained_kinds(cell['children']))
        return found

    def editorial_box(kind, children):
        return f'<div class="editorial-group {kind}-group">' + nodes_html(children, in_source_box=True, highlight_questions=kind != 'questao') + '</div>'

    def nodes_html(nodes, in_source_box=False, highlight_questions=False):
        parts = []
        index = 0
        while index < len(nodes):
            node = nodes[index]
            if node['type'] == 'paragraph' and not lookup[node['id']]['text'].strip():
                index += 1
                continue
            if in_source_box and highlight_questions and node['type'] == 'paragraph' and lookup[node['id']]['kind'] == 'questao':
                grouped = []
                end = index
                while end < len(nodes):
                    child = nodes[end]
                    if child['type'] != 'paragraph':
                        break
                    block = lookup[child['id']]
                    if block['text'].strip() and block['kind'] != 'questao':
                        break
                    grouped.append(child)
                    end += 1
                parts.append('<div class="question-highlight">' + nodes_html(grouped, in_source_box=True) + '</div>')
                index = end
                continue
            question_nodes = question_table_paragraphs(node) if not in_source_box else None
            if question_nodes is not None:
                grouped = list(question_nodes)
                end = index + 1
                while end < len(nodes):
                    next_questions = question_table_paragraphs(nodes[end])
                    if next_questions is None:
                        break
                    grouped.extend(next_questions)
                    end += 1
                parts.append(editorial_box('questao', grouped))
                index = end
                continue
            if node['type'] == 'paragraph':
                block = lookup[node['id']]
                if not block['text'].strip() or block['id'] in skipped:
                    index += 1
                    continue
                kind = block['kind']
                tag = 'h2' if kind in ('capitulo', 'divisao') else 'h3' if kind in ('titulo_capitulo', 'titulo_divisao') else 'p'
                if block['id'] == 'p1' and kind not in ('capitulo', 'divisao', 'titulo_capitulo', 'titulo_divisao'):
                    tag = 'h1'
                # Normaliza o texto legal: ignora negrito e caixa alta herdados do DOCX.
                plain = kind in ('artigo', 'legislacao')
                citation_class = 'exam-citation' if plain else 'exam-context'
                runs = block['runs']
                if hide_amendments and kind in ('artigo', 'legislacao', 'capitulo', 'titulo_capitulo', 'divisao', 'titulo_divisao'):
                    runs, count = clean_amendment_runs(runs)
                    data['rendered_amendment_removals'] += count
                printed_text = ''.join(r['text'] for r in runs)
                if not printed_text.strip():
                    index += 1
                    continue
                data['rendered_text_by_id'][block['id']] = printed_text
                value = paragraph_runs_html(runs, colors, plain=plain,
                                            citation_class=citation_class,
                                            normalize_basis=kind in kinds)
                parts.append(f'<{tag} id="{block["id"]}" class="{kind}">{value}</{tag}>')
            else:
                omit_original_orientation(node)
                rows = node['rows']
                # A célula original determina a caixa, mesmo com tipos misturados.
                # Tabelas internas mantêm sua estrutura dentro dessa caixa externa.
                if not in_source_box and all(len(row) == 1 for row in rows):
                    for row in rows:
                        children = row[0]['children']
                        found = contained_kinds(children)
                        if found:
                            box_kind = next(iter(found)) if len(found) == 1 else 'misto'
                            parts.append(editorial_box(box_kind, children))
                        else:
                            parts.append(nodes_html(children))
                else:
                    parts.append('<table><tbody>')
                    for row in rows:
                        parts.append('<tr>' + ''.join(f'<td colspan="{c["span"]}">{nodes_html(c["children"], in_source_box=True, highlight_questions=highlight_questions or not in_source_box)}</td>' for c in row) + '</tr>')
                    parts.append('</tbody></table>')
            index += 1
        return ''.join(parts)

    # Abertura original e orientações ficam em uma coluna; a lei segue em colunas.
    split = next((i for i, node in enumerate(data['tree'])
                  if node['type'] == 'paragraph' and lookup[node['id']]['text'].startswith('LEI ')), 0)
    opening = nodes_html(data['tree'][:split])
    body = nodes_html(data['tree'][split:])
    toc = []
    blocks = data['blocks']
    for i, block in enumerate(blocks):
        if block['kind'] in ('capitulo', 'divisao') and block['id'] not in skipped:
            following = next((b for b in blocks[i + 1:] if b['text'].strip()), None)
            title = data['rendered_text_by_id'].get(following['id'], following['text']) if following and following['kind'] in ('titulo_capitulo', 'titulo_divisao') else ''
            label = data['rendered_text_by_id'].get(block['id'], block['text']) + (' — ' + title if title else '')
            toc.append(f'<li><a href="#{block["id"]}">{html.escape(label)}</a></li>')
    notes = ''.join(f'<div id="nota-{n["number"]}"><p>Nota {n["number"]}</p>{nodes_html(n["children"])}</div>' for n in data['notes'])
    box_rules = []
    for kind in defaults:
        style = box_styles[kind]
        fill = style['background'] if style['mode'] == 'fill' else 'transparent'
        edge = f"{style['border_width']}pt {style['border_style']} {style['border_color']}" if style['mode'] == 'outline' else 'none'
        selector = f'.editorial-group.{kind}-group' + (', .question-highlight' if kind == 'questao' else '')
        box_rules.append(f'{selector} {{ background:{fill}; border:{edge}; }}')
    box_rules = '\n'.join(box_rules)
    css = f'''
    @page {{ size: {paper}; margin: 15mm 14mm 16mm;
      @top-left {{ content: "{html.escape(short_title)}"; font: 8pt "Roboto", sans-serif; color: #444; }}
      @bottom-right {{ content: counter(page) " / " counter(pages); font: 8pt "Roboto", sans-serif; }} }}
    @page:first {{ @top-left {{ content: none; }} }}
    * {{ box-sizing: border-box; -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
    body {{ margin: 0; color: #111; font: {font_size}pt/1.22 "Roboto", "DejaVu Sans", sans-serif; }}
    h1, h2, h3 {{ color: #000; font-family: "Roboto", "DejaVu Sans", sans-serif; font-weight: 400; break-after: avoid; text-align: left; }}
    h1 {{ font-size: 19pt; line-height: 1.2; margin: 0 0 4mm; }}
    h2 {{ font-size: 12pt; margin: 3.5mm 0 1mm; }}
    h3 {{ font-size: 10pt; margin: 0 0 2mm; }}
    .capitulo, .titulo_capitulo, .divisao, .titulo_divisao {{ text-align: center; }}
    p {{ margin: 0 0 0.7mm; orphans: 3; widows: 3; overflow-wrap: anywhere; }}
    a {{ color: inherit; text-decoration: none; }}
    .device-label, .device-label * {{ font-weight: 700 !important; }}
    .exam-citation, .exam-citation *, .legal-basis, .legal-basis * {{ color: #555 !important; font-size: 5.5pt !important; line-height: 1.05 !important; font-weight: 400 !important; text-decoration: none !important; text-transform: none !important; background: transparent !important; }}
    .exam-context, .exam-context * {{ color: inherit !important; font-size: inherit !important; font-weight: inherit !important; font-style: inherit !important; text-decoration: none !important; text-transform: none !important; background: transparent !important; }}
    .jurisprudencia, .jurisprudencia * {{ font-style: italic !important; font-weight: 400 !important; }}
    .artigo {{ margin-top: 1.4mm; }}
    .editorial {{ margin: 1.2mm 0 1.5mm; }}
    .editorial-group {{ font-size: .94em; padding: 1mm 2.2mm; margin: 1.2mm 0 1.5mm; border-radius: 1mm; break-inside: auto; }}
    .editorial-group p {{ font-size: inherit; background: transparent; border: none; padding: 0; margin: 0.7mm 0; break-inside: avoid; }}
    .question-highlight {{ padding: 0.8mm 1.8mm; margin: 0.8mm 0; border-radius: 1mm; break-inside: auto; }}
    {box_rules}
    .editorial .legislacao, .editorial .artigo, .editorial .capitulo, .editorial .titulo_capitulo, .editorial .informacao {{ background: transparent; padding-left: 0; border: none; }}
    table {{ width: 100%; border-collapse: collapse; font-size: .92em; margin: 2mm 0; }}
    td {{ border: .4pt solid #aaa; padding: 1.5mm; vertical-align: top; }}
    td p {{ margin-bottom: 1mm; }}
    .opening {{ font-size: 9.5pt; }}
    nav {{ break-after: auto; }}
    nav h2 {{ margin-top: 5mm; }}
    nav ul {{ list-style: none; padding: 0; margin: 2mm 0; }}
    nav li {{ margin: 0 0 1.7mm; font: 9pt/1.35 "Roboto", "DejaVu Sans", sans-serif; }}
    .columns {{ column-count: {columns}; column-gap: {5 if columns == 3 else 7}mm; column-fill: balance; column-rule: .3pt solid #bbb; }}
    .notes {{ margin-top: 4mm; }}
    .toolbar {{ font: 14px/1.5 "Roboto", sans-serif; padding: 16px; background: #eee; margin-bottom: 24px; }}
    button {{ font: inherit; padding: 6px 12px; cursor: pointer; }}
    @media screen {{ body {{ max-width: 1100px; margin: 24px auto; padding: 24px; }} nav {{ margin-bottom: 30px; }} }}
    @media print {{ .toolbar {{ display: none; }} }}
    '''
    return f'''<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
    <title>{safe_title}</title>
    <style>{css}</style></head><body>
    <div class="toolbar"><button onclick="window.print()">Imprimir / Salvar PDF</button>
    <span>Documento completo · {paper} · {columns} coluna(s) · {font_size} pt.
    Para a paginação conferida, use o PDF gerado junto deste arquivo.</span></div>
    <div class="opening">{opening}</div>
    <nav aria-label="Sumário"><h2>Sumário</h2><ul>{''.join(toc)}</ul></nav>
    <main class="columns">{body}<section class="notes"><h2>Notas do material original</h2>{notes}</section></main>
    </body></html>'''


def verify_pdf(data, pdf_bytes):
    """Confere que o PDF contém o texto extraído, além da paginação visual."""
    from io import BytesIO
    from pypdf import PdfReader
    pdf = PdfReader(BytesIO(pdf_bytes))
    title = next((b['text'] for b in data['blocks'] if b['text'].strip()), data['source'])
    short_title = title[:75].replace('"', '').replace('\\', '').replace('\n', ' ').strip()
    total = len(pdf.pages)
    pages_text = []
    for index, page in enumerate(pdf.pages, 1):
        raw = (page.extract_text() or '').strip()
        raw = re.sub(r'(?:' + re.escape(short_title) + r'\s*)?' + rf'{index}\s*/\s*{total}\s*$', '', raw)
        pages_text.append(raw)
    normalize = lambda s: re.sub(r'[\u00ad\u200b-\u200f\u2060\ufeff]', '', re.sub(r'\s+|\[\d+\]', '', s)).casefold()
    printed = normalize(''.join(pages_text))
    expected = data.get('rendered_text_by_id', {b['id']: b['text'] for b in data['blocks']})
    missing = [block_id for block_id, text in expected.items() if text.strip() and normalize(text) not in printed]
    return {'pdf_pages': total, 'paragraphs_not_matched_in_pdf': missing}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--output', type=Path, default=Path('output'))
    parser.add_argument('--paper', choices=['A4', 'A5'], default='A4')
    parser.add_argument('--columns', type=int, choices=[1, 2, 3], default=2)
    parser.add_argument('--font-size', type=float, default=9.5)
    parser.add_argument('--colors', action='store_true', help='Preservar cores diretas e marcações amarelas')
    parser.add_argument('--html-only', action='store_true', help='Extrair sem depender do WeasyPrint')
    parser.add_argument('--hide-amendments', action='store_true', help='Retirar notas de alteração legislativa do HTML e PDF')
    parser.add_argument('--hide-revoked', action='store_true', help='Excluir dispositivos revogados (e títulos vazios) do HTML e PDF')
    args = parser.parse_args()
    if not 7 <= args.font_size <= 18:
        parser.error('--font-size deve ficar entre 7 e 18 pontos')
    data = Extractor(args.source).extract()
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / 'conteudo.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    (args.output / 'texto-integral.txt').write_text('\n\n'.join(b['text'] for b in data['blocks']), encoding='utf-8')
    document = render_html(data, args.paper, args.columns, args.font_size, args.colors,
                           hide_amendments=args.hide_amendments, hide_revoked=args.hide_revoked)
    target = args.output / 'vade-mecum.html'
    target.write_text(document, encoding='utf-8')
    report = {'source': data['source'], 'sha256': data['sha256'],
              'paragraphs_body': data['body_paragraphs'], 'paragraphs_total': len(data['blocks']),
              'paragraph_sequence_matches_source': data['verified_paragraph_sequence'],
              'categories': dict(Counter(b['kind'] for b in data['blocks'])),
              'notes': len(data['notes']), 'warnings': data['warnings'],
              'hidden_amendment_notes': data['rendered_amendment_removals']}
    if not args.html_only:
        from weasyprint import HTML
        pdf_dir = args.output / 'pdf'
        pdf_dir.mkdir(exist_ok=True)
        pdf_path = pdf_dir / 'vade-mecum.pdf'
        HTML(filename=str(target)).write_pdf(pdf_path)
        report.update(verify_pdf(data, pdf_path.read_bytes()))
    (args.output / 'verificacao.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report.get('paragraphs_not_matched_in_pdf'):
        raise SystemExit('Conferir parágrafos não localizados em output/verificacao.json antes de imprimir.')


if __name__ == '__main__':
    main()
