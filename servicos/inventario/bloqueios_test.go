package main

import (
	"sync"
	"testing"
	"time"
)

// Simula o padrao ler-verificar-escrever do stock com muitas goroutines.
// Com o mutex, nunca se vende mais do que o stock. Correr com: go test -race ./...
func TestMutexImpedeVendaAcimaDoStock(t *testing.T) {
	b := NovosBloqueios()
	stock := 50
	vendidas := 0
	var wg sync.WaitGroup
	for i := 0; i < 500; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			libertar := b.BloquearVarios([]string{"P001"})
			defer libertar()
			lido := stock
			time.Sleep(10 * time.Microsecond) // alarga a janela onde a corrida aconteceria
			if lido >= 1 {
				stock = lido - 1
				vendidas++
			}
		}()
	}
	wg.Wait()
	if vendidas != 50 || stock != 0 {
		t.Fatalf("esperado 50 vendidas e stock 0; obtido %d vendidas e stock %d", vendidas, stock)
	}
}

// Duas encomendas com os mesmos produtos em ordem inversa nao podem bloquear-se mutuamente.
func TestOrdemFixaEvitaDeadlock(t *testing.T) {
	b := NovosBloqueios()
	terminou := make(chan bool)
	go func() {
		var wg sync.WaitGroup
		for i := 0; i < 200; i++ {
			wg.Add(2)
			go func() { defer wg.Done(); l := b.BloquearVarios([]string{"A", "B"}); l() }()
			go func() { defer wg.Done(); l := b.BloquearVarios([]string{"B", "A"}); l() }()
		}
		wg.Wait()
		terminou <- true
	}()
	select {
	case <-terminou:
	case <-time.After(5 * time.Second):
		t.Fatal("deadlock: as goroutines nao terminaram")
	}
}

func TestProdutosRepetidosSoBloqueiamUmaVez(t *testing.T) {
	b := NovosBloqueios()
	feito := make(chan bool)
	go func() {
		l := b.BloquearVarios([]string{"A", "A", "B"})
		l()
		feito <- true
	}()
	select {
	case <-feito:
	case <-time.After(time.Second):
		t.Fatal("o mesmo produto repetido bloqueou a propria goroutine")
	}
}
