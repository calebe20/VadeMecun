#!/usr/bin/env python3
"""Interface local do organizador. Execute: .venv/bin/python app.py"""
import argparse
import base64
import copy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib
import json
from pathlib import Path
import secrets
import tempfile
import threading
from urllib.parse import urlparse
import webbrowser

import vademecum

ROOT = Path(__file__).resolve().parent
TOKEN = secrets.token_urlsafe(32)
SESSIONS = {}
LOCK = threading.Lock()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def send_bytes(self, value, mime, status=200):
        self.send_response(status)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(value)))
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(value)

    def send_json(self, value, status=200):
        self.send_bytes(json.dumps(value, ensure_ascii=False).encode(), 'application/json; charset=utf-8', status)

    def do_GET(self):
        if urlparse(self.path).path != '/':
            self.send_json({'error': 'Não encontrado'}, 404)
            return
        page = (ROOT / 'interface.html').read_text(encoding='utf-8').replace('__TOKEN__', TOKEN)
        self.send_bytes(page.encode(), 'text/html; charset=utf-8')

    def do_POST(self):
        if self.headers.get('X-App-Token') != TOKEN:
            self.send_json({'error': 'Sessão inválida. Reabra a interface.'}, 403)
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if length < 1 or length > 30 * 1024 * 1024:
                raise ValueError('Escolha um DOCX de até 20 MB.')
            importlib.reload(vademecum)
            request = json.loads(self.rfile.read(length))
            if self.path == '/api/extract':
                name = Path(request['name']).name
                if not name.lower().endswith('.docx'):
                    raise ValueError('Esta versão aceita arquivos .docx.')
                binary = base64.b64decode(request['file'], validate=True)
                with tempfile.TemporaryDirectory() as folder:
                    source = Path(folder) / name
                    source.write_bytes(binary)
                    data = vademecum.Extractor(source).extract()
                sid = secrets.token_urlsafe(24)
                with LOCK:
                    if len(SESSIONS) >= 10:
                        SESSIONS.pop(next(iter(SESSIONS)))
                    SESSIONS[sid] = data
                self.send_json({'session': sid, 'blocks': data['blocks'], 'warnings': data['warnings'],
                                'paragraphs': data['body_paragraphs'], 'notes': len(data['notes'])})
            elif self.path == '/api/export':
                with LOCK:
                    data = copy.deepcopy(SESSIONS.get(request['session']))
                if data is None:
                    raise ValueError('Importe o arquivo novamente; a sessão não está mais disponível.')
                options = request['options']
                paper, columns, size = options['paper'], int(options['columns']), float(options['size'])
                if paper not in ('A4', 'A5') or columns not in (1, 2, 3) or not 7 <= size <= 18:
                    raise ValueError('Configuração de impressão inválida.')
                box_styles = options.get('boxStyles', {})
                validated_styles = {}
                for kind in ('questao', 'comentario', 'jurisprudencia', 'misto'):
                    if kind == 'misto' and kind not in box_styles:
                        continue
                    style = box_styles.get(kind, {})
                    mode = style.get('mode')
                    border_style = style.get('borderStyle')
                    try:
                        width = float(style.get('borderWidth'))
                    except (TypeError, ValueError):
                        raise ValueError('Informe a espessura da borda de cada caixa.')
                    background, border_color = style.get('background'), style.get('borderColor')
                    valid_color = lambda color: isinstance(color, str) and len(color) == 7 and color[0] == '#' and all(c in '0123456789abcdefABCDEF' for c in color[1:])
                    if mode not in ('fill', 'outline', 'plain') or border_style not in ('solid', 'dashed', 'dotted', 'double') or not .5 <= width <= 3 or not valid_color(background) or not valid_color(border_color):
                        raise ValueError('Confira o preenchimento, a cor e a borda de cada tipo de caixa.')
                    validated_styles[kind] = {'mode': mode, 'background': background,
                                              'border_color': border_color, 'border_width': width,
                                              'border_style': border_style}
                for block in data['blocks']:
                    kind = request.get('categories', {}).get(block['id'], block['kind'])
                    if kind not in ('legislacao', 'artigo', 'capitulo', 'titulo_capitulo', 'divisao', 'titulo_divisao', 'informacao', 'questao', 'comentario', 'jurisprudencia'):
                        raise ValueError('Categoria inválida.')
                    block['kind'] = kind
                document = vademecum.render_html(data, paper, columns, size, bool(options['colors']), validated_styles,
                                                 hide_amendments=bool(options.get('hideAmendments', False)),
                                                 hide_revoked=bool(options.get('hideRevoked', False)))
                kind = request['format']
                if kind == 'html':
                    self.send_bytes(document.encode(), 'text/html; charset=utf-8')
                elif kind == 'txt':
                    self.send_bytes('\n\n'.join(b['text'] for b in data['blocks']).encode(), 'text/plain; charset=utf-8')
                elif kind == 'json':
                    self.send_json(data)
                elif kind == 'pdf':
                    from weasyprint import HTML
                    binary = HTML(string=document).write_pdf()
                    verification = vademecum.verify_pdf(data, binary)
                    if verification['paragraphs_not_matched_in_pdf']:
                        raise ValueError('A conferência detectou texto não localizado no PDF. Exporte HTML/JSON para revisar: '
                                         + ', '.join(verification['paragraphs_not_matched_in_pdf']))
                    self.send_bytes(binary, 'application/pdf')
                else:
                    raise ValueError('Formato inválido.')
            else:
                self.send_json({'error': 'Não encontrado'}, 404)
        except Exception as exc:
            self.send_json({'error': str(exc)}, 400)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    address = f'http://127.0.0.1:{args.port}'
    print(f'Organizador disponível em {address}\nCtrl+C para encerrar.', flush=True)
    if not args.no_browser:
        webbrowser.open(address)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
