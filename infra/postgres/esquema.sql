-- Corre no master, uma vez. As replicas recebem tudo por replicacao fisica.

CREATE DATABASE inventario;
CREATE DATABASE encomendas;
CREATE DATABASE pagamentos;

\connect inventario
CREATE TABLE produtos (
    id              TEXT PRIMARY KEY,
    nome            TEXT NOT NULL,
    preco_centavos  BIGINT NOT NULL CHECK (preco_centavos > 0),
    stock           INTEGER NOT NULL CHECK (stock >= 0),
    imagem          TEXT,
    atualizado_em   TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- Reserva feita pelo passo 1 da saga. A chave inclui o saga_id: repetir nao reserva duas vezes.
CREATE TABLE reservas (
    saga_id         TEXT NOT NULL,
    produto_id      TEXT NOT NULL REFERENCES produtos (id),
    quantidade      INTEGER NOT NULL CHECK (quantidade > 0),
    preco_centavos  BIGINT NOT NULL,
    estado          TEXT NOT NULL CHECK (estado IN ('RESERVADA', 'COMPENSADA')),
    criada_em       TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (saga_id, produto_id)
);
INSERT INTO produtos (id, nome, preco_centavos, stock) VALUES
    ('P001', 'Telemovel Android 128 GB', 1250000, 50),
    ('P002', 'Auscultadores sem fios',    185000, 120),
    ('P003', 'Portatil 14 polegadas',    4200000, 15),
    ('P004', 'Carregador rapido USB-C',    65000, 300),
    ('P005', 'Relogio inteligente',       390000, 40);

\connect encomendas
CREATE TABLE sagas (
    id              TEXT PRIMARY KEY,
    cliente         TEXT NOT NULL,
    chave           TEXT NOT NULL,
    itens           JSONB NOT NULL,
    estado          TEXT NOT NULL,
    total_centavos  BIGINT NOT NULL DEFAULT 0,
    motivo          TEXT NOT NULL DEFAULT '',
    cartao          TEXT NOT NULL,
    criada_em       TIMESTAMPTZ NOT NULL DEFAULT now(),
    actualizada_em  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (cliente, chave)
);
CREATE TABLE saga_passos (
    id       BIGSERIAL PRIMARY KEY,
    saga_id  TEXT NOT NULL REFERENCES sagas (id),
    detalhe  TEXT NOT NULL,
    em       TIMESTAMPTZ NOT NULL DEFAULT now()
);

\connect pagamentos
CREATE TABLE pagamentos (
    saga_id         TEXT PRIMARY KEY,
    cliente         TEXT NOT NULL,
    valor_centavos  BIGINT NOT NULL,
    aprovado        BOOLEAN NOT NULL,
    motivo          TEXT NOT NULL DEFAULT '',
    referencia      TEXT NOT NULL DEFAULT '',
    criado_em       TIMESTAMPTZ NOT NULL DEFAULT now()
);
