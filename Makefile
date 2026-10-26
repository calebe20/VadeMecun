# Makefile do Formatador de Lei
#
# Alvos principais:
#   make test    — suíte de testes unitários
#   make audit   — auditorias de complexidade e dependências
#   make gate    — auditorias + testes (portão único antes de entregar)
#   make spec    — lista as specs e mostra as pendentes
#
# Requer Python 3.8+ e pytest. Para preparar o ambiente:
#   make setup

PYTHON ?= python3
VENV   ?= .venv
PY     := $(VENV)/bin/python
PIP    := $(VENV)/bin/pip

ALVO      := Formatador_Lei_Anki_Colab.py
PYTEST    := $(PY) -m pytest tests/ -q
AUDIT_CX  := $(PY) scripts/complexity_audit.py
AUDIT_DEP := $(PY) scripts/dependency_audit.py

.PHONY: help setup test audit gate spec check clean

help:
	@echo "Formatador de Lei — alvos disponiveis:"
	@echo "  make setup   cria o venv e instala o pytest"
	@echo "  make test    roda a suíte de testes"
	@echo "  make audit   roda as auditorias (complexidade + dependencias)"
	@echo "  make gate    auditorias + testes (use antes de entregar)"
	@echo "  make spec    mostra o estado das especificações"
	@echo "  make clean   remove caches e o venv"

setup:
	$(PYTHON) -m venv $(VENV)
	$(PIP) install -q --upgrade pip
	$(PIP) install -q pytest
	@echo "ambiente pronto"

test:
	@$(PYTEST)

audit:
	@$(AUDIT_CX)
	@echo
	@$(AUDIT_DEP)

gate: audit test
	@echo
	@echo "GATE OK — auditorias e testes passaram"

spec:
	@echo "Especificacoes em specs/:"
	@for f in specs/[0-9]*.md; do \
		[ -e "$$f" ] || continue; \
		estado=$$(grep -m1 '^\*\*Status:\*\*' "$$f" | sed 's/.*Status:\*\* //'); \
		printf '  %-58s %s\n' "$$f" "$$estado"; \
	done

check:
	@$(PYTHON) -c "import ast,sys; ast.parse(open('$(ALVO)',encoding='utf-8').read()); print('sintaxe ok')"

clean:
	@rm -rf .pytest_cache __pycache__ tests/__pycache__ .ruff_cache
	@find . -name '__pycache__' -not -path './.venv/*' -exec rm -rf {} + 2>/dev/null || true
	@echo "limpo"
