"""Carrega os stubs gerados a partir de proto/loja.proto.

O protoc gera `loja_pb2_grpc.py` com `import loja_pb2`, por isso a pasta gerada entra no sys.path.
"""
import os
import sys

PASTA = os.environ.get("PROTO_GEN", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "gen"))
if PASTA not in sys.path:
    sys.path.insert(0, PASTA)

import loja_pb2 as pb  # noqa: E402
import loja_pb2_grpc as rpc  # noqa: E402

__all__ = ["pb", "rpc"]
