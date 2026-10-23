import base64
from html.parser import HTMLParser
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from zipfile import ZipFile

import app
from vademecum import Extractor, clean_amendment_runs, paragraph_runs_html, render_html, verify_pdf


DOCUMENT = '''<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>
<w:p><w:r><w:t>Material fictício de teste</w:t></w:r></w:p>
<w:p><w:r><w:t>LEI DE EXEMPLO</w:t></w:r></w:p>
<w:p><w:r><w:t>CAPÍTULO I</w:t></w:r></w:p>
<w:p><w:r><w:t>Disposições de teste</w:t></w:r></w:p>
<w:p><w:r><w:rPr><w:b/></w:rPr><w:t>Art. 2º-A. Texto &amp; preservação.</w:t></w:r><w:r><w:footnoteReference w:id="1"/></w:r></w:p>
<w:tbl><w:tr><w:tc>
<w:p><w:r><w:t>(EXEMPLO-2025): Questão fictícia.</w:t></w:r></w:p>
<w:tbl><w:tr><w:tc><w:p><w:r><w:t>#STJ: Julgado fictício.</w:t></w:r></w:p></w:tc>
<w:tc><w:p><w:r><w:t>Comentário &lt;script&gt; preservado como texto.</w:t></w:r></w:p></w:tc></w:tr></w:tbl>
</w:tc></w:tr></w:tbl>
<w:p><w:r><w:rPr><w:caps/></w:rPr><w:t>Art. 3º. Fim do exemplo.</w:t></w:r></w:p>
</w:body></w:document>'''
NOTES = '''<w:footnotes xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:footnote w:id="1"><w:p><w:r><w:t>Nota fictícia mantida integralmente.</w:t></w:r></w:p></w:footnote></w:footnotes>'''


class BoxInspector(HTMLParser):
    def __init__(self, document):
        super().__init__()
        self.stack = []
        self.groups = []
        self.highlights = []
        self.feed(document)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'div':
            classes = set(attrs.get('class', '').split())
            box = None
            if 'editorial-group' in classes or 'question-highlight' in classes:
                box = {'classes': classes, 'paragraphs': [], 'tables': 0}
                (self.groups if 'editorial-group' in classes else self.highlights).append(box)
            self.stack.append(box)
        elif tag == 'p' and 'id' in attrs:
            for box in self.stack:
                if box is not None:
                    box['paragraphs'].append(attrs['id'])
        elif tag == 'table':
            for box in self.stack:
                if box is not None:
                    box['tables'] += 1

    def handle_endtag(self, tag):
        if tag == 'div':
            self.stack.pop()


class ExtractionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.source = Path(self.temp.name) / 'exemplo.docx'
        with ZipFile(self.source, 'w') as z:
            z.writestr('word/document.xml', DOCUMENT)
            z.writestr('word/footnotes.xml', NOTES)
        self.data = Extractor(self.source).extract()

    def tearDown(self):
        self.temp.cleanup()

    def test_nested_tables_notes_order_and_categories(self):
        blocks = self.data['blocks']
        self.assertEqual(self.data['body_paragraphs'], 9)
        self.assertEqual(len(blocks), 10)
        self.assertEqual(blocks[4]['article'], '2-A')
        self.assertEqual(blocks[5]['kind'], 'questao')
        self.assertEqual(blocks[6]['kind'], 'jurisprudencia')
        self.assertEqual(blocks[7]['article'], '2-A')
        self.assertEqual(blocks[8]['article'], '3')
        self.assertEqual(blocks[9]['part'], 'word/footnotes.xml')
        self.assertTrue(self.data['verified_paragraph_sequence'])

    def test_html_normalizes_legal_text_and_escapes_source(self):
        page = render_html(self.data, 'A5', 1, 11, False)
        self.assertNotIn('<strong>Art. 2º-A.', page)
        self.assertIn('<strong class="device-label">Art. 2º-A.</strong> Texto &amp; preservação.', page)
        self.assertIn('<strong class="device-label">Art. 3º.</strong> Fim do exemplo.', page)
        self.assertIn('&lt;script&gt;', page)
        self.assertIn('href="#nota-1"', page)
        self.assertIn('column-count: 1', page)
        self.assertNotIn('Lei 6.766', page)

    def test_device_labels_bold_in_legal_text(self):
        for prefix, rest in [('Art. 2º-A.', ' Texto.'), ('Art. 18-B.', ' Texto.'),
                             ('Parágrafo único.', ' Texto.'), ('§ 1º -', ' Texto.'),
                             ('§ 4º.', ' Texto.'), ('III-A -', ' Texto.'), ('a)', ' Texto.')]:
            runs = [{'text': prefix + rest, 'b': False}]
            result = paragraph_runs_html(runs, False, plain=True, citation_class='exam-citation')
            expected_label = prefix.rstrip(' -')
            self.assertEqual(result, f'<strong class="device-label">{expected_label}</strong>{prefix[len(expected_label):]}{rest}')

    def test_pdf_text_complete_for_all_layouts(self):
        from weasyprint import HTML
        for paper, columns in [('A4', 2), ('A4', 1), ('A5', 1), ('A4', 3), ('A5', 3)]:
            with self.subTest(paper=paper, columns=columns):
                pdf = HTML(string=render_html(self.data, paper, columns, 9.5, False)).write_pdf()
                self.assertEqual(verify_pdf(self.data, pdf)['paragraphs_not_matched_in_pdf'], [])

    def test_interface_import_and_export(self):
        server = app.ThreadingHTTPServer(('127.0.0.1', 0), app.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        address = 'http://127.0.0.1:' + str(server.server_port)
        def post(path, body, token=app.TOKEN):
            req = Request(address + path, data=json.dumps(body).encode(),
                          headers={'Content-Type': 'application/json', 'X-App-Token': token})
            return urlopen(req)
        try:
            self.assertIn(b'Organizador de vade', urlopen(address).read())
            with self.assertRaises(HTTPError) as error:
                post('/api/extract', {}, token='invalid')
            self.assertEqual(error.exception.code, 403)
            imported = json.load(post('/api/extract', {'name': 'exemplo.docx',
                                 'file': base64.b64encode(self.source.read_bytes()).decode()}))
            self.assertEqual(imported['paragraphs'], 9)
            options = {'paper': 'A4', 'columns': 3, 'size': 9.5, 'colors': False}
            options['boxStyles'] = {kind: {'mode': 'fill' if kind == 'questao' else 'outline',
                                           'background': '#fff2c9', 'borderColor': '#555555',
                                           'borderWidth': 1, 'borderStyle': 'solid'}
                                    for kind in ('questao', 'comentario', 'jurisprudencia')}
            request = {'session': imported['session'], 'format': 'json', 'options': options,
                       'categories': {'p6': 'comentario'}}
            exported = json.load(post('/api/export', request))
            self.assertEqual(exported['blocks'][5]['kind'], 'comentario')
            self.assertEqual(exported['blocks'][5]['text'], self.data['blocks'][5]['text'])
            request['format'] = 'pdf'
            self.assertTrue(post('/api/export', request).read().startswith(b'%PDF'))
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_question_identifier_and_basis_do_not_inherit_source_bold(self):
        runs = [{'text': '(MPMS-', 'b': True}, {'text': '2024-FAPEC):', 'b': True},
                {'text': ' Corpo da questão. '}, {'text': 'BL', 'b': True},
                {'text': ': art. 32-A, II, LPU.', 'b': True, 'i': True}]
        result = paragraph_runs_html(runs, False, normalize_basis=True)
        self.assertNotIn('<strong>', result)
        self.assertNotIn('<em>', result)
        self.assertIn('class="exam-context">2024-FAPEC):</span>', result)
        self.assertIn('class="legal-basis">: art. 32-A, II, LPU.</span>', result)
        self.assertNotIn('class="exam-citation"', result)

    def test_one_comment_box_preserves_all_paragraphs_and_separate_source_boxes(self):
        comment_xml = '''<w:tbl><w:tr><w:tc>
        <w:p><w:r><w:t>#Atenção: comentário inicial.</w:t></w:r></w:p>
        <w:p/>
        <w:p><w:r><w:t>Quando ocorrerá a devolução?</w:t></w:r></w:p>
        <w:p><w:r><w:t>I - Loteamentos em andamento.</w:t></w:r></w:p>
        <w:p><w:r><w:t>II - Loteamentos concluídos.</w:t></w:r></w:p>
        <w:p><w:r><w:t>Regra final do mesmo comentário.</w:t></w:r></w:p>
        </w:tc></w:tr></w:tbl>'''
        xml = DOCUMENT.replace('</w:body>', comment_xml + '</w:body>')
        with ZipFile(self.source, 'w') as z:
            z.writestr('word/document.xml', xml)
        data = Extractor(self.source).extract()
        result = render_html(data, 'A4', 2, 9.5, False)
        self.assertEqual(result.count('class="editorial-group comentario-group"'), 1)
        # The comparison table stays inside its original mixed box.
        group = result.split('class="editorial-group comentario-group">')[-1].split('</div>')[0]
        self.assertEqual(group.count('<p '), 5)
        self.assertIn('Regra final do mesmo comentário.', group)

    def test_mixed_source_box_preserves_types_and_nested_tables_together(self):
        result = render_html(self.data, 'A4', 2, 9.5, False)
        layout = BoxInspector(result)
        self.assertEqual(len(layout.groups), 1)
        self.assertIn('misto-group', layout.groups[0]['classes'])
        self.assertEqual(layout.groups[0]['paragraphs'], ['p6', 'p7', 'p8'])
        self.assertEqual(layout.groups[0]['tables'], 1)
        self.assertEqual(layout.highlights[0]['paragraphs'], ['p6'])

    def test_enac_ordinals_match_other_competition_references_across_runs(self):
        for edition in ['1º', '2ª', '1.º', '1o']:
            runs = [{'text': '(ENAC/'}, {'text': edition, 'b': True}, {'text': '-2025)'}]
            result = paragraph_runs_html(runs, False, plain=True, citation_class='exam-citation')
            self.assertEqual(result.count('class="exam-citation"'), 3)
            self.assertNotIn('<strong', result)

    def test_source_bold_is_removed_in_comments_and_other_content(self):
        runs = [{'text': '#Comentários sobre o julgado: ', 'b': True},
                {'text': 'Texto com ênfase de origem.', 'b': True, 'i': True}]
        result = paragraph_runs_html(runs, False)
        self.assertNotIn('<strong', result)
        self.assertIn('<em>Texto com ênfase de origem.</em>', result)

    def test_nested_questions_follow_question_color_option_without_losing_outer_box(self):
        styles = {'questao': {'mode': 'fill', 'background': '#ffee99', 'border_color': '#555555',
                               'border_width': 1, 'border_style': 'solid'}}
        page = render_html(self.data, 'A4', 3, 9.5, False, styles)
        self.assertIn('.editorial-group.questao-group, .question-highlight { background:#ffee99; border:none; }', page)
        self.assertIn('column-count: 3', page)
        self.assertIn('print-color-adjust: exact', page)
        self.assertEqual(len(BoxInspector(page).groups), 1)

    def test_mixed_box_style_can_be_configured_separately(self):
        styles = {'misto': {'mode': 'fill', 'background': '#ddeeff', 'border_color': '#123456',
                             'border_width': 1, 'border_style': 'dashed'}}
        result = render_html(self.data, 'A4', 2, 9.5, False, styles)
        self.assertIn('.editorial-group.misto-group { background:#ddeeff; border:none; }', result)

    def test_revoked_provisions_and_empty_headings_are_excluded_on_request(self):
        from html import escape
        texts = ['LEI X', 'Seção V', 'Do regime fiduciário', '(Revogado pela Lei nº 1, de 2022)',
                 'Art. 9º (Revogado pela Lei nº 1, de 2022)', 'Art. 10. (Revogado pela Lei nº 1, de 2022)',
                 'I - (Revogado pela Lei nº 1, de 2022)', 'Parágrafo único. (Revogado)',
                 'Seção VI', 'Das garantias', 'Art. 17. Texto vigente.', '§ 1º (Revogado).',
                 '§ 2º (VETADO).', 'II - (revogado);', 'Art. 18. Ficam revogados os dispositivos.']
        xml = '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
        xml += ''.join('<w:p><w:r><w:t>' + escape(t) + '</w:t></w:r></w:p>' for t in texts)
        xml += '</w:body></w:document>'
        with ZipFile(self.source, 'w') as z:
            z.writestr('word/document.xml', xml)
        data = Extractor(self.source).extract()
        kept = render_html(data, 'A4', 2, 9.5, False)
        self.assertIn('Art. 9º', kept)
        self.assertIn('Do regime fiduciário', kept)
        page = render_html(data, 'A4', 2, 9.5, False, hide_revoked=True)
        for gone in ('Art. 9º', 'Art. 10.', 'Seção V<', 'Do regime fiduciário', 'Parágrafo único', '§ 1º', 'II -'):
            self.assertNotIn(gone, page)
        for stays in ('Seção VI', 'Das garantias', 'Art. 17.', '(VETADO)', 'Ficam revogados'):
            self.assertIn(stays, page)
        self.assertEqual(data['rendered_revoked_removals'], 7)
        self.assertIn('Art. 9º', data['blocks'][4]['text'])
        from weasyprint import HTML
        self.assertEqual(verify_pdf(data, HTML(string=page).write_pdf())['paragraphs_not_matched_in_pdf'], [])

    def test_blank_paragraphs_complete_without_loop(self):
        xml = DOCUMENT.replace('</w:body>', '<w:p/><w:p><w:r><w:t> </w:t></w:r></w:p></w:body>')
        with ZipFile(self.source, 'w') as z:
            z.writestr('word/document.xml', xml)
        result = render_html(Extractor(self.source).extract(), 'A4', 2, 9.5, False)
        self.assertIn('Fim do exemplo.', result)

    def test_legal_divisions_and_their_subtitles_are_centered(self):
        from html import escape
        texts = ['LIVRO PRIMEIRO', 'Das pessoas', 'TÍTULO I', '', 'Das regras gerais',
                 'CAPÍTULO II', 'Disposições preliminares', 'Seção Única', 'Das regras especiais',
                 'Subseção I', 'Do procedimento', 'Art. 1º. Texto fictício.',
                 'PARTE ESPECIAL', 'Art. 2º. Outro dispositivo.']
        xml = '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
        xml += ''.join('<w:p><w:r><w:t>'+escape(t)+'</w:t></w:r></w:p>' for t in texts)
        xml += '</w:body></w:document>'
        with ZipFile(self.source, 'w') as z:
            z.writestr('word/document.xml', xml)
        data = Extractor(self.source).extract()
        kinds = [b['kind'] for b in data['blocks']]
        self.assertEqual(kinds, ['divisao', 'titulo_divisao', 'divisao', 'legislacao', 'titulo_divisao',
                                 'capitulo', 'titulo_capitulo', 'divisao', 'titulo_divisao',
                                 'divisao', 'titulo_divisao', 'artigo', 'divisao', 'artigo'])
        result = render_html(data, 'A4', 2, 9.5, False)
        self.assertIn('.capitulo, .titulo_capitulo, .divisao, .titulo_divisao { text-align: center; }', result)
        self.assertIn('<h2 id="p1" class="divisao">LIVRO PRIMEIRO</h2>', result)
        self.assertIn('<h3 id="p7" class="titulo_capitulo">Disposições preliminares</h3>', result)

    def test_amendment_notes_balance_parentheses_and_cross_formatting_runs(self):
        runs = [{'text': '§ 1º. Prazo de 90 (noventa) dias. (Reda', 'b': True},
                {'text': 'ção dada pela Lei nº 1, com efeitos após 90 (noventa) dias)'},
                {'text': '. (BANCA-2025) Texto seguinte.', 'i': True}]
        original = json.dumps(runs)
        cleaned, count = clean_amendment_runs(runs)
        self.assertEqual(count, 1)
        self.assertEqual(''.join(r['text'] for r in cleaned),
                         '§ 1º. Prazo de 90 (noventa) dias. (BANCA-2025) Texto seguinte.')
        self.assertTrue(cleaned[0]['b'])
        self.assertTrue(cleaned[-1]['i'])
        self.assertEqual(json.dumps(runs), original)

    def test_cleaning_preserves_statuses_explanations_and_unclosed_notes(self):
        text = 'Art. 1º. (VETADO) (Revogado) (trinta por cento) (BANCA-2025) (Incluído pela Lei nº 1'
        cleaned, count = clean_amendment_runs([{'text': text}])
        self.assertEqual(count, 0)
        self.assertEqual(cleaned[0]['text'], text)
        text = 'Texto(Incluído pela Lei nº 1)continuação (Renumerado pela Lei nº 2).'
        cleaned, count = clean_amendment_runs([{'text': text}])
        self.assertEqual(count, 2)
        self.assertEqual(''.join(r['text'] for r in cleaned), 'Texto continuação.')
        cleaned, count = clean_amendment_runs([{'text': 'Art. 9º. (Revogado pela Lei nº 1, de 2024)'}])
        self.assertEqual(count, 1)
        self.assertEqual(''.join(r['text'] for r in cleaned), 'Art. 9º. (Revogado)')

    def test_print_cleaning_is_optional_preserves_source_and_pdf_verification(self):
        annotation = ' (Incluído pela Lei nº 13.465, de 2017)'
        xml = DOCUMENT.replace('Texto &amp; preservação.', 'Texto &amp; preservação.' + annotation)
        xml = xml.replace('Questão fictícia.', 'Questão fictícia.' + annotation)
        with ZipFile(self.source, 'w') as z:
            z.writestr('word/document.xml', xml)
        data = Extractor(self.source).extract()
        render_html(data, 'A4', 2, 9.5, False)
        self.assertIn(annotation, data['rendered_text_by_id']['p5'])
        page = render_html(data, 'A4', 2, 9.5, False, hide_amendments=True)
        self.assertNotIn(annotation, data['rendered_text_by_id']['p5'])
        self.assertIn(annotation, data['rendered_text_by_id']['p6'])
        self.assertIn(annotation, data['blocks'][4]['text'])
        self.assertEqual(data['rendered_amendment_removals'], 1)
        from weasyprint import HTML
        pdf = HTML(string=page).write_pdf()
        self.assertEqual(verify_pdf(data, pdf)['paragraphs_not_matched_in_pdf'], [])

    def test_heading_note_is_removed_from_heading_and_table_of_contents(self):
        annotation = ' (Incluído pela Lei nº 13.465, de 2017)'
        xml = DOCUMENT.replace('CAPÍTULO I', 'CAPÍTULO I' + annotation)
        with ZipFile(self.source, 'w') as z:
            z.writestr('word/document.xml', xml)
        data = Extractor(self.source).extract()
        self.assertEqual(data['blocks'][2]['kind'], 'capitulo')
        page = render_html(data, 'A4', 2, 9.5, False, hide_amendments=True)
        self.assertNotIn(annotation, page)


if __name__ == '__main__':
    unittest.main()
