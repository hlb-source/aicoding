package main

import (
	"flag"
	"fmt"
	"log"
	"net/http"
	"os"

	"pod-resource-injector/internal/webhook"
)

func main() {
	var (
		port    int
		tlsCert string
		tlsKey  string
	)

	flag.IntVar(&port, "port", 8443, "The port on which to serve the webhook")
	flag.StringVar(&tlsCert, "tls-cert", "/etc/tls/tls.crt", "Path to the TLS certificate file")
	flag.StringVar(&tlsKey, "tls-key", "/etc/tls/tls.key", "Path to the TLS private key file")
	flag.Parse()

	// Create webhook server
	server := &http.Server{
		Addr: fmt.Sprintf(":%d", port),
	}

	// Register health check endpoints
	http.HandleFunc("/healthz", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		fmt.Fprintf(w, "ok")
	})

	http.HandleFunc("/readyz", func(w http.ResponseWriter, r *http.Request) {
		// Check if TLS files exist as a basic readiness check
		if _, err := os.Stat(tlsCert); os.IsNotExist(err) {
			w.WriteHeader(http.StatusServiceUnavailable)
			fmt.Fprintf(w, "TLS certificate not found")
			return
		}
		if _, err := os.Stat(tlsKey); os.IsNotExist(err) {
			w.WriteHeader(http.StatusServiceUnavailable)
			fmt.Fprintf(w, "TLS key not found")
			return
		}
		w.WriteHeader(http.StatusOK)
		fmt.Fprintf(w, "ok")
	})

	// Register webhook handler
	http.HandleFunc("/mutate-pods", webhook.HandleMutatePods)

	// Check if TLS certificate and key files exist
	if _, err := os.Stat(tlsCert); os.IsNotExist(err) {
		log.Fatalf("TLS certificate file not found: %s", tlsCert)
	}

	if _, err := os.Stat(tlsKey); os.IsNotExist(err) {
		log.Fatalf("TLS private key file not found: %s", tlsKey)
	}

	log.Printf("Starting webhook server on port %d", port)
	log.Printf("Health check endpoint: /healthz")
	log.Printf("Readiness check endpoint: /readyz")
	log.Printf("Webhook endpoint: /mutate-pods")
	
	if err := server.ListenAndServeTLS(tlsCert, tlsKey); err != nil {
		log.Fatalf("Failed to start webhook server: %v", err)
	}
}