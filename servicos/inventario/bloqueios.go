package main

import (
	"sort"
	"sync"
)

// Bloqueios guarda um sync.Mutex por produto (Modulo 1: primitivas do SO contra race conditions).
//
// Duas compras do mesmo produto esperam uma pela outra; compras de produtos diferentes correm em
// paralelo. O mapa e protegido por um mutex proprio, porque goroutines diferentes podem pedir o
// mutex de um produto novo ao mesmo tempo.
type Bloqueios struct {
	mu         sync.Mutex
	porProduto map[string]*sync.Mutex
}

func NovosBloqueios() *Bloqueios {
	return &Bloqueios{porProduto: make(map[string]*sync.Mutex)}
}

func (b *Bloqueios) de(produto string) *sync.Mutex {
	b.mu.Lock()
	defer b.mu.Unlock()
	m, ok := b.porProduto[produto]
	if !ok {
		m = &sync.Mutex{}
		b.porProduto[produto] = m
	}
	return m
}

// BloquearVarios bloqueia os produtos sempre pela mesma ordem (alfabetica). Sem esta ordem,
// duas encomendas {A,B} e {B,A} podiam ficar cada uma a espera da outra (deadlock).
// Devolve a funcao que liberta os bloqueios pela ordem inversa.
func (b *Bloqueios) BloquearVarios(produtos []string) func() {
	unicos := make(map[string]bool)
	for _, p := range produtos {
		unicos[p] = true
	}
	ordem := make([]string, 0, len(unicos))
	for p := range unicos {
		ordem = append(ordem, p)
	}
	sort.Strings(ordem)

	obtidos := make([]*sync.Mutex, 0, len(ordem))
	for _, p := range ordem {
		m := b.de(p)
		m.Lock()
		obtidos = append(obtidos, m)
	}
	return func() {
		for i := len(obtidos) - 1; i >= 0; i-- {
			obtidos[i].Unlock()
		}
	}
}
