# Organizador de vade-mécum

Programa local em Python para extrair um DOCX, revisar a organização dos seus parágrafos e gerar uma edição para impressão. Preserva o texto da legislação e os complementos do material fornecido: questões, comentários, julgados e notas. O arquivo original nunca é alterado. Nenhum documento é importado automaticamente ao abrir o programa.

## Iniciar

No Linux, dentro desta pasta:

```bash
bash iniciar.sh
```

A interface abre no navegador em **http://127.0.0.1:8765**. Ela roda neste computador, sem conta e sem enviar o material para serviços externos. Para encerrar, pressione `Ctrl+C` no terminal. A primeira instalação das bibliotecas precisa de internet.

Se preferir iniciar manualmente:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python app.py
```

Requer Python 3.10 ou superior, fontes e bibliotecas nativas do WeasyPrint. No Ubuntu, caso faltem dependências do sistema: `sudo apt install python3-venv libpango-1.0-0 libpangoft2-1.0-0 fonts-dejavu-core`. Consulte também a [instalação oficial do WeasyPrint](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#installation).

## Uso

1. Selecione um arquivo `.docx` e clique em **Importar para revisão**.
2. Confira os parágrafos. A busca ajuda a localizar um artigo ou tribunal. Ajuste os rótulos de legislação, questão, comentário ou jurisprudência, se necessário.
3. Escolha papel A4/A5, uma/duas/três colunas, tamanho da fonte e a apresentação de cada caixa. Questões, comentários e jurisprudência podem ter fundo, só borda (com cor, tipo e espessura próprios) ou nenhum dos dois. Questões consecutivas são agrupadas numa caixa. Todo o conteúdo impresso sai sem negrito, inclusive comentários e rótulos de dispositivos; as divisões continuam centralizadas. Referências de banca ligadas diretamente aos dispositivos são reduzidas, incluindo edições como `ENAC/1º-2025`; quando aparecem em questões, comentários ou jurisprudência, acompanham a formatação do item. A base legal iniciada por `BL:` fica menor e discreta como as referências após dispositivos. A jurisprudência sai em itálico. As instruções de apresentação do início do material são omitidas; as datas de atualização são mantidas.
4. Clique em **Baixar PDF**, **Baixar HTML**, **Texto integral** ou **Estrutura JSON**.

Os parágrafos de legislação, questões, comentários e jurisprudência ficam na sequência original, inclusive os que estão dentro de tabelas aninhadas. A classificação visual não reordena conteúdo. Notas de rodapé são reunidas ao final e recebem links no texto. O PDF contém cabeçalho e numeração de páginas. Os capítulos reconhecidos entram no sumário com links. Confira a prévia de impressão antes de imprimir.

Cada caixa original do DOCX mantém todo o conteúdo em uma caixa externa, mesmo quando mistura comentários, jurisprudência, questões e tabelas internas. O controle **Caixas mistas do documento** define o fundo ou a borda desses blocos. A jurisprudência mantém o itálico, e as questões internas recebem o destaque configurado para questões, sem dividir a caixa externa. Tabelas existentes dentro da caixa são mantidas. Nas questões, a identificação completa entre parênteses segue o estilo do texto, e a base legal `BL:` recebe fonte menor e cinza, sem o negrito herdado do Word.

Livros, partes, títulos, capítulos, seções, subseções e seus subtítulos ficam centralizados. O programa reconhece numeração romana, números e divisões como “Seção Única” ou “Parte Geral”.

A opção **Retirar notas de alteração da impressão** oculta indicações de inclusão, redação, acréscimo, alteração e renumeração vinculadas a outra norma. Exemplo: `(Incluído pela Lei nº 13.465, de 2017)`. A remoção respeita parênteses aninhados e notas divididas entre trechos do Word. Ela se aplica ao texto legal no HTML e PDF; comentários, questões, jurisprudência, o DOCX, o texto integral e o JSON original continuam preservados. Parênteses explicativos, referências de concursos e marcações como `(VETADO)` ou `(Revogado)` são mantidos; `(Revogado pela Lei…)` fica apenas `(Revogado)`. Desmarque a opção para imprimir as notas normalmente.

Os rótulos revisados ficam na memória até encerrar o programa ou importar novamente; baixe o JSON para guardá-los. Esta versão não reimporta JSON e não oferece edição do texto. Faça mudanças de redação no DOCX original ou trabalhe sobre o texto/HTML exportado.

## Linha de comando

A interface usa o mesmo extrator que pode ser executado diretamente:

```bash
.venv/bin/python vademecum.py "seu-material.docx" --paper A4 --columns 2 --font-size 9.5 --output output/meu-material
```

Opções: `--paper A4|A5`, `--columns 1|2|3`, `--font-size 7..18`, `--colors`, `--hide-amendments` e `--html-only`. A extração para HTML/TXT/JSON usa apenas a biblioteca padrão do Python; o PDF precisa das dependências de `requirements.txt`.

Saídas: `vade-mecum.html`, `texto-integral.txt`, `conteudo.json`, `pdf/vade-mecum.pdf` e `verificacao.json`. Use uma pasta de saída por material: uma nova execução sobrescreve os arquivos dessa pasta.

## Integridade e limites

- O extrator compara a sequência de todos os parágrafos do corpo com o XML original, incluindo tabelas. Se houver divergência, a operação falha.
- O JSON registra o hash SHA-256 do arquivo de origem, texto, trechos de formatação, categoria, artigo associado e estrutura de tabelas.
- Antes de disponibilizar o PDF, o programa procura o texto de todos os parágrafos no texto extraído do PDF. Essa conferência complementa a revisão visual; não prova a exatidão jurídica nem a equivalência visual com o Word.
- Os rótulos são heurísticos e revisáveis. Menções a STF/STJ e referências de concursos ajudam a classificar os complementos. Cores herdadas de estilos/temas não são reproduzidas integralmente.
- Esta primeira versão foi projetada a partir da inspeção estrutural do DOCX de Parcelamento do Solo Urbano desta pasta. Outros DOCX podem exigir adaptação. Imagens, listas numeradas automaticamente, controle de alterações e comentários de revisão do Word geram avisos e exigem conferência no original. Cabeçalhos, rodapés, campos automáticos e URLs dos hyperlinks do Word não são reproduzidos.
- Comentários editoriais escritos no corpo ou nas tabelas são preservados. Eles são diferentes dos comentários de revisão do Word.
- O conteúdo e as datas do material não são atualizados por consulta a legislação ou jurisprudência externa.
- O material enviado pelo usuário não foi convertido durante o desenvolvimento. Os testes usam documentos fictícios.

## Pesquisa e decisões

Repositórios e documentação examinados:

- [Mammoth](https://github.com/mwilliamson/python-mammoth): converte DOCX para HTML sem tentar copiar toda a apresentação do Word. Bom candidato para uma importação mais geral.
- [docx2python](https://github.com/ShayHill/docx2python): extrai texto, tabelas, notas, imagens e outras partes do documento. Útil para ampliar os formatos de entrada.
- [python-docx](https://github.com/python-openxml/python-docx): lê e modifica documentos Word. Útil se uma futura versão também precisar exportar DOCX.
- [WeasyPrint](https://github.com/Kozea/WeasyPrint) e sua [documentação de paginação](https://doc.courtbouillon.org/weasyprint/stable/api_reference.html): compõem PDF a partir de HTML e CSS, com recursos de impressão.

Nesta versão, o extrator lê diretamente o XML do DOCX usando `zipfile` e `ElementTree` para permitir uma conferência explícita da sequência dos parágrafos. A apresentação é gerada separadamente e o WeasyPrint produz o PDF. Não há OCR nem uso de IA para reescrever ou resumir o material.

## Testes

```bash
.venv/bin/python -m unittest discover -s tests -v
```

Os testes cobrem tabelas aninhadas, nota de rodapé, associação a artigo, classificação, escape de HTML, exportação PDF em três layouts e importação/exportação pela interface local. Nenhum teste lê o documento do usuário.
