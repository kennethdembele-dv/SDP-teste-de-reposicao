"""Formato comum dos logs: hora, servico, thread e mensagem."""
import logging
import sys


def registo(servico: str) -> logging.Logger:
    log = logging.getLogger(servico)
    if not log.handlers:
        h = logging.StreamHandler(sys.stdout)
        h.setFormatter(logging.Formatter("%(asctime)s [%(name)s] [%(threadName)s] %(message)s"))
        log.addHandler(h)
        log.setLevel(logging.INFO)
        log.propagate = False
    return log
