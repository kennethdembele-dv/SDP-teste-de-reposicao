"""Identidade por HTTPS com mTLS (uvicorn real) e API Gateway REST -> gRPC."""
import os
import ssl
import threading
import time
import unittest
import urllib.error
import urllib.request

import apoio
from comum import seguranca
from comum.token_servico import TokenServico

identidade = apoio.carregar("identidade", "main", "identidade_main")


class TesteIdentidade(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import uvicorn
        identidade.SERVICOS["svc-encomendas"] = "segredo-de-teste"
        d = apoio.CERTS
        cfg = uvicorn.Config(identidade.app, host="127.0.0.1", port=18443, log_level="warning",
                             ssl_certfile=os.path.join(d, "identidade.pem"), ssl_keyfile=os.path.join(d, "identidade-chave.pem"),
                             ssl_ca_certs=os.path.join(d, "ca.pem"), ssl_cert_reqs=ssl.CERT_REQUIRED)
        cls.servidor = uvicorn.Server(cfg)
        threading.Thread(target=cls.servidor.run, daemon=True).start()
        for _ in range(100):
            if cls.servidor.started:
                break
            time.sleep(0.05)
        cls.url = "https://localhost:18443"

    @classmethod
    def tearDownClass(cls):
        cls.servidor.should_exit = True

    def pedir(self, caminho, corpo, contexto):
        r = urllib.request.Request(self.url + caminho, data=corpo, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(r, context=contexto, timeout=5) as x:
            import json
            return json.loads(x.read())

    def test_login_emite_jwt_valido(self):
        t = self.pedir("/token", b'{"username":"cliente1","password":"Cliente#2026"}', seguranca.contexto_ssl_cliente("gateway"))
        claims = seguranca.VerificadorJwt().verificar(t["access_token"])
        self.assertEqual((claims["sub"], claims["papel"]), ("cliente1", "cliente"))

    def test_senha_errada_e_recusada(self):
        with self.assertRaises(urllib.error.HTTPError) as e:
            self.pedir("/token", b'{"username":"cliente1","password":"errada"}', seguranca.contexto_ssl_cliente("gateway"))
        self.assertEqual(e.exception.code, 401)

    def test_token_de_servico(self):
        t = TokenServico("encomendas", self.url, "segredo-de-teste").obter()
        self.assertEqual(seguranca.VerificadorJwt().verificar(t)["papel"], "servico")

    def test_sem_certificado_de_cliente_a_ligacao_falha(self):
        sem_cert = ssl.create_default_context(cafile=os.path.join(apoio.CERTS, "ca.pem"))
        with self.assertRaises(OSError):
            self.pedir("/token", b'{"username":"cliente1","password":"Cliente#2026"}', sem_cert)


class TesteGateway(unittest.TestCase):
    def test_openapi_documenta_a_api_publica(self):
        gateway = apoio.carregar("gateway", "main", "gateway_main")
        esquema = gateway.app.openapi()
        caminhos = set(esquema["paths"])
        for c in ("/api/v1/auth/token", "/api/v1/produtos", "/api/v1/encomendas", "/api/v1/produtos/{produto_id}/imagem",
                  "/api/v1/relatorios/faturacao"):
            self.assertIn(c, caminhos)
        self.assertIn("HTTPBearer", esquema["components"]["securitySchemes"])

    def test_pedido_sem_token_devolve_401(self):
        from fastapi.testclient import TestClient
        gateway = apoio.carregar("gateway", "main", "gateway_main2")
        r = TestClient(gateway.app).get("/api/v1/produtos")
        self.assertEqual(r.status_code, 401)

    def test_interface_grafica_e_servida(self):
        from fastapi.testclient import TestClient
        gateway = apoio.carregar("gateway", "main", "gateway_main4")
        cliente = TestClient(gateway.app)
        raiz = cliente.get("/", follow_redirects=False)
        self.assertEqual((raiz.status_code, raiz.headers["location"]), (307, "/app/"))
        pagina = cliente.get("/app/")
        self.assertEqual(pagina.status_code, 200)
        self.assertIn("Distributed-Buy", pagina.text)
        for f in ("/app/app.js", "/app/app.css"):
            self.assertEqual(cliente.get(f).status_code, 200)

    def test_cliente_nao_pode_carregar_imagens(self):
        from fastapi.testclient import TestClient
        gateway = apoio.carregar("gateway", "main", "gateway_main3")
        r = TestClient(gateway.app).post("/api/v1/produtos/P001/imagem", files={"ficheiro": ("a.png", b"x", "image/png")},
                                         headers={"Authorization": "Bearer " + apoio.token()})
        self.assertEqual(r.status_code, 403)


if __name__ == "__main__":
    unittest.main(verbosity=2)
