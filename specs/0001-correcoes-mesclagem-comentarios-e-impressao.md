# 0001 — Correções de mesclagem de comentários e compactação para impressão

**Status:** Concluída
**Responsável:** Codex
**Criada em:** 2026-10-25

## Objetivo

Corrigir o formatador de lei para que os comentários gerados pela IA apareçam em todos os caminhos de saída (Anki, visualizador, PDF), sejam legíveis na impressão em impressora laser A4 e sigam a mesma diagramação da letra da lei.

## Escopo

### Incluído

- [x] Comentários mesclados também no modo "Texto Limpo", que antes os descartava silenciosamente.
- [x] `atualizar_arquivo_anki` passa a reconhecer blocos tipados (`TIPO|ALVO|SUBTITULO|RELEVANCIA`), não só o formato antigo `Art. X|texto`.
- [x] Checkbox "Incluir comentários abertos" do PDF marcado por padrão; sem ele o script removia todo `<details>` e o PDF saía sem nenhum comentário.
- [x] Parser do arquivo exportado do Anki detecta a coluna `#guid`; sem isso todas as colunas ficavam deslocadas e nada era encontrado.
- [x] Títulos dos blocos tipados ("Questão", "Jurisprudência", ...) removidos do `<summary>`, que só ocupavam espaço.
- [x] Incidência do dispositivo (`(PGESP-2002) (MPSP-2013)`) extraída do fim do texto e posicionada **acima** do dispositivo.
- [x] Conteúdo dos blocos justificado como a letra da lei (`text-align: justify` + `text-align-last: left`).
- [x] Hifenização por software via `pyphen`, porque o Chromium não aplica hifenização automática e a justificação em coluna estreita abria buracos entre as palavras.
- [x] Layout compacto para A4: margens de 6mm, fonte 9px, entrelinha 1.0, espaçamentos e paddings reduzidos.
- [x] Marcações de banca reduzidas (`.74em` no texto, `.76em` na incidência, `.72em` nas fontes dos blocos).

### Não incluído

- Reescrever o `PROMPT_IA.md` ou mudar o contrato do material gerado pela IA.
- Suporte a layout do PDF em duas colunas como padrão (continua disponível no seletor).
- Modularizar o `Formatador_Lei_Anki_Colab.py` em módulos menores.

## Critérios de aceite

- [x] `_processar_callback` insere todos os 7 tipos de bloco (`questao`, `comentario`, `tabela`, `esquema`, `jurisprudencia`, `doutrina`, `nota`) mais a síntese.
- [x] Modo "Texto Limpo" mantém os comentários, sem marcadores de título.
- [x] Botão "Mesclar Comentários no HTML" insere os blocos no HTML já formatado.
- [x] PDF mantém os blocos quando "Incluir comentários abertos" está marcado.
- [x] `atualizar_arquivo_anki` insere blocos tipados em arquivo exportado do Anki, com e sem coluna `#guid`.
- [x] Nenhum bloco exibe título "Questão", "Jurisprudência" ou similar.
- [x] Incidência aparece na linha imediatamente anterior ao dispositivo, em corpo menor.
- [x] Blocos justificados com última linha à esquerda.
- [x] Cada parêntese de banca continua legível e não é engolido pelo texto do artigo.
- [x] Nenhuma linha do dispositivo perde a própria incidence ao longo do documento (bug do `#INC:` tratado como cabeçalho de seção).
- [x] Densidade impressa medida: 52% mais caracteres por página que a configuração anterior.

## Plano técnico

Todas as mudanças vivem em `Formatador_Lei_Anki_Colab.py`.

**Parser de incidência** — `_separar_incidencia` extrai a sequência de grupos entre parênteses no fim da linha, valida cada parte contra `_RE_ITEM_BANCA` e devolve `(texto, incidencia)`. `formatar_texto_legal` emite uma linha `#INC:` antes do dispositivo. `_parse_secoes_artigos` reconhece `#INC:` e a prepende ao artigo seguinte, em vez de tratá-la como cabeçalho de seção.

**Regex de banca** — `_RE_ITEM_BANCA` passou a aceitar múltiplos anos (`MPSP-2005/2008/2013` antes não casava).

**Render do PDF** — `gerar_html_pdf` aplica `_hifenizar_html` sobre o texto visível, ignorando as tags. A hifenização usa `pyphen` com no máximo um ponto de divisão a cada três posições possíveis e mínimo de três caracteres por pedaço.

**Densidade** — margens de página Playwright reduzidas de 10mm/14mm para 6mm/7mm; defaults dos controles do painel e das assinaturas Python ajustados; CSS de títulos, cabeçalhos, caixas de bloco, tabelas e esquemas compactado.

**Decisões relevantes**

- `pyphen` não vem instalado no Colab. O formatador tenta `pip install` na primeira execução; se falhar, o PDF é gerado sem hifenização.
- A hifenização é feita por software em vez de CSS porque o Chromium headless não aplica `hyphens: auto` mesmo com `lang="pt-BR"` e o dicionário `pt_BR` instalado no sistema.
- A coluna `#guid` é detectada pelo header, e não assumida. Arquivos exportados com e sem a coluna são suportados.

## Validação

### Automatizada

- [x] `make test` — resultado: 29 testes aprovados
- [x] `make audit` — resultado: complexidade dentro do baseline, 0 ciclos de dependência
- [x] `make gate` — resultado: exit code 0
- [x] Regressão manual dos 5 caminhos (Formatar/Mesclar, Texto Limpo, botão Mesclar, PDF, formato legado) — resultado: passa
- [x] PDF real renderizado com Chromium e medido com `pdfplumber` — 52% mais caracteres por página

### Manual

- [ ] Substituir a célula do Colab pelo arquivo atualizado e confirmar a impressão na L3150 — resultado: pendente

## Resultado da entrega

As cinco regressões de comentário passaram, a incidência passou a anteceder o dispositivo em todos os artigos do documento, e a densidade impressa mediu 12.057 caracteres por página contra 7.935 na configuração anterior.

Três bugs de parser foram encontrados no caminho e corrigidos: a coluna `#guid` deslocando campos, o regex de banca recusando anos múltiplos, e o `#INC:` sendo tratado como cabeçalho de seção (que quebrava o artigo e perdia todas as incidências depois da primeira).

O `Formatador_Lei_Anki_Colab.py` permanece monolítico; a suíte de testes e as auditorias criadas na spec 0002 são o passo seguinte para permitir a modularização com segurança.
