"""Regras do pagamento simulado. Nao ha banco real nem credenciais externas."""
import os
import random

CARTAO_RECUSADO = "4000000000000002"   # cartao de teste que e sempre recusado


def luhn_valido(numero: str) -> bool:
    if not numero.isdigit() or not 12 <= len(numero) <= 19:
        return False
    soma = 0
    for i, c in enumerate(reversed(numero)):
        d = int(c)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        soma += d
    return soma % 10 == 0


class RegrasPagamento:
    def __init__(self, limite_centavos: int = None, falha_pct: float = None, semente: int = None):
        self.limite = limite_centavos if limite_centavos is not None else int(os.environ.get("LIMITE_CENTAVOS", "5000000"))
        self.falha_pct = falha_pct if falha_pct is not None else float(os.environ.get("FALHA_PAGAMENTO_PCT", "0"))
        self.aleatorio = random.Random(semente)

    def avaliar(self, valor_centavos: int, cartao: str):
        """Devolve (aprovado, motivo)."""
        if not luhn_valido(cartao):
            return False, "cartao invalido"
        if cartao == CARTAO_RECUSADO:
            return False, "cartao recusado pelo emissor"
        if valor_centavos > self.limite:
            return False, "valor acima do limite do cartao"
        if self.falha_pct and self.aleatorio.random() * 100 < self.falha_pct:
            return False, "recusa aleatoria simulada"
        return True, ""
