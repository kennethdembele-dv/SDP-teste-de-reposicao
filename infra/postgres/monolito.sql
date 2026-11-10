-- Base de dados unica do monolito (comparacao do Modulo 2).
CREATE DATABASE monolito;
\connect monolito
CREATE TABLE produtos (
    id              TEXT PRIMARY KEY,
    nome            TEXT NOT NULL,
    preco_centavos  BIGINT NOT NULL,
    stock           INTEGER NOT NULL CHECK (stock >= 0)
);
CREATE TABLE encomendas (
    id              TEXT PRIMARY KEY,
    total_centavos  BIGINT NOT NULL,
    criada_em       TIMESTAMPTZ NOT NULL DEFAULT now()
);
INSERT INTO produtos VALUES
    ('P001', 'Telemovel Android 128 GB', 1250000, 1000000),
    ('P002', 'Auscultadores sem fios',    185000, 1000000),
    ('P003', 'Portatil 14 polegadas',    4200000, 1000000),
    ('P004', 'Carregador rapido USB-C',    65000, 1000000),
    ('P005', 'Relogio inteligente',       390000, 1000000);
