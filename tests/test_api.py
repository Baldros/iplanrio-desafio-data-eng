"""
Testes da API REST de Terceirizados.

Utiliza mocking do DatabaseManager para evitar dependência de banco real,
permitindo execução dos testes sem infraestrutura S3/MinIO.
"""

import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

# Mock do database antes de importar a app
mock_conn = MagicMock()
mock_db_manager = MagicMock()
mock_db_manager.get_connection.return_value = mock_conn

with patch.dict("sys.modules", {}):
    pass

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))

# Patch do db_manager antes de importar as rotas
with patch("database.db_manager", mock_db_manager):
    from main import app

client = TestClient(app)


# =====================================================================
# Fixtures
# =====================================================================

SAMPLE_ROW_LIST = (1, "MEC", "12345678000100", "12345678901")
SAMPLE_COLUMNS_LIST = ["id_terceirizado", "orgao_superior_sigla", "cnpj", "cpf"]

SAMPLE_ROW_FULL = (
    1, "MEC", "12345678000100", "12345678901",
    "João da Silva", "Auxiliar Administrativo", "Ensino Médio",
    40, 1500.00, 3000.00, "Empresa XYZ Ltda", "CT-001",
    "MEC", "Ministério da Educação", "26401", "26241",
    "153004", "Universidade Federal X", "UFX", "Secretaria Admin.",
    1, "Janeiro", 2024, "2024-01-01"
)
SAMPLE_COLUMNS_FULL = [
    "id_terceirizado", "orgao_superior_sigla", "cnpj", "cpf",
    "terceirizado_nome", "categoria_profissional_nome", "escolaridade_nome",
    "jornada_quantidade", "salario_mensal_valor", "custo_mensal_valor",
    "empresa_razao_social_nome", "contrato_numero",
    "orgao_sigla", "orgao_nome", "orgao_codigo_siafi", "orgao_codigo_siape",
    "unidade_gestora_codigo", "unidade_gestora_nome", "unidade_gestora_sigla",
    "unidade_prestacao_nome", "mes_carga_numero", "mes_carga_nome",
    "ano_carga", "mes_referencia_data"
]


# =====================================================================
# Testes - Health Check
# =====================================================================

class TestHealthCheck:
    def test_root_returns_online(self):
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "online"
        assert "docs" in data


# =====================================================================
# Testes - Listagem /terceirizados
# =====================================================================

class TestListTerceirizados:
    @patch("routes.db_manager")
    def test_list_returns_paginated_response(self, mock_db):
        conn = MagicMock()
        mock_db.get_connection.return_value = conn
        conn.execute.return_value.fetchone.return_value = (1,)
        conn.execute.return_value.fetchall.return_value = [SAMPLE_ROW_LIST]
        conn.description = [(c,) for c in SAMPLE_COLUMNS_LIST]

        response = client.get("/terceirizados/?page=1&page_size=10")
        assert response.status_code == 200

        data = response.json()
        assert "total_count" in data
        assert "page" in data
        assert "page_size" in data
        assert "items" in data
        assert isinstance(data["items"], list)

    @patch("routes.db_manager")
    def test_list_respects_pagination_params(self, mock_db):
        conn = MagicMock()
        mock_db.get_connection.return_value = conn
        conn.execute.return_value.fetchone.return_value = (100,)
        conn.execute.return_value.fetchall.return_value = [SAMPLE_ROW_LIST]
        conn.description = [(c,) for c in SAMPLE_COLUMNS_LIST]

        response = client.get("/terceirizados/?page=2&page_size=5")
        assert response.status_code == 200

        data = response.json()
        assert data["page"] == 2
        assert data["page_size"] == 5

    def test_list_rejects_invalid_page(self):
        response = client.get("/terceirizados/?page=0")
        assert response.status_code == 422

    def test_list_rejects_oversized_page(self):
        response = client.get("/terceirizados/?page_size=200")
        assert response.status_code == 422


# =====================================================================
# Testes - Detalhes /terceirizados/{id}
# =====================================================================

class TestGetTerceirizado:
    @patch("routes.db_manager")
    def test_get_existing_terceirizado(self, mock_db):
        conn = MagicMock()
        mock_db.get_connection.return_value = conn
        conn.execute.return_value.fetchone.return_value = SAMPLE_ROW_FULL
        conn.description = [(c,) for c in SAMPLE_COLUMNS_FULL]

        response = client.get("/terceirizados/1")
        assert response.status_code == 200

        data = response.json()
        assert data["id_terceirizado"] == 1
        assert data["cpf"] == "12345678901"
        assert data["terceirizado_nome"] == "João da Silva"
        assert data["orgao_codigo_siafi"] == "26401"

    @patch("routes.db_manager")
    def test_get_nonexistent_terceirizado_returns_404(self, mock_db):
        conn = MagicMock()
        mock_db.get_connection.return_value = conn
        conn.execute.return_value.fetchone.return_value = None

        response = client.get("/terceirizados/999999")
        assert response.status_code == 404
        assert "não encontrado" in response.json()["detail"].lower()

    @patch("routes.db_manager")
    def test_get_returns_all_gold_fields(self, mock_db):
        """Verifica que o endpoint retorna todos os campos da camada ouro."""
        conn = MagicMock()
        mock_db.get_connection.return_value = conn
        conn.execute.return_value.fetchone.return_value = SAMPLE_ROW_FULL
        conn.description = [(c,) for c in SAMPLE_COLUMNS_FULL]

        response = client.get("/terceirizados/1")
        data = response.json()

        expected_fields = {
            "id_terceirizado", "orgao_superior_sigla", "cnpj", "cpf",
            "terceirizado_nome", "categoria_profissional_nome", "escolaridade_nome",
            "jornada_quantidade", "salario_mensal_valor", "custo_mensal_valor",
            "empresa_razao_social_nome", "contrato_numero",
            "orgao_sigla", "orgao_nome", "orgao_codigo_siafi", "orgao_codigo_siape",
            "unidade_gestora_codigo", "unidade_gestora_nome", "unidade_gestora_sigla",
            "unidade_prestacao_nome", "mes_carga_numero", "mes_carga_nome",
            "ano_carga", "mes_referencia_data"
        }
        assert expected_fields.issubset(set(data.keys())), (
            f"Campos faltantes: {expected_fields - set(data.keys())}"
        )
