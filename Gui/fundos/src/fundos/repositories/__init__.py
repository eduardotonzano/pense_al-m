"""Repositorios minimos do modulo de Fundos.

Cada repositorio recebe uma conexao aberta por fundos.database.Database.
Quem chama controla a transacao (Database.transaction()); as gravacoes
compostas usam SAVEPOINT. Nao ha leitura de arquivo da CVM aqui.
"""


class IdentityConflictError(ValueError):
    """Conflito de identificador: bloqueia em vez de unir ou trocar."""
