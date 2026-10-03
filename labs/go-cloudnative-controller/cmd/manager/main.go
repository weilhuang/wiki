package main

import (
	"flag"
	"os"
	"time"

	labv1 "example.com/wiki/p0-controller/api/v1alpha1"
	labcontroller "example.com/wiki/p0-controller/internal/controller"
	"k8s.io/apimachinery/pkg/runtime"
	clientgoscheme "k8s.io/client-go/kubernetes/scheme"
	ctrl "sigs.k8s.io/controller-runtime"
	"sigs.k8s.io/controller-runtime/pkg/cache"
	"sigs.k8s.io/controller-runtime/pkg/healthz"
	"sigs.k8s.io/controller-runtime/pkg/log/zap"
	metricsserver "sigs.k8s.io/controller-runtime/pkg/metrics/server"
)

func main() {
	namespace := flag.String("namespace", "", "Required single namespace watched by the manager")
	flag.Parse()
	if *namespace == "" {
		os.Stderr.WriteString("--namespace is required\n")
		os.Exit(2)
	}
	ctrl.SetLogger(zap.New(zap.UseDevMode(false)))
	scheme := runtime.NewScheme()
	must(clientgoscheme.AddToScheme(scheme))
	must(labv1.AddToScheme(scheme))
	cfg := ctrl.GetConfigOrDie()
	cfg.Timeout = 8 * time.Second
	mgr, err := ctrl.NewManager(cfg, ctrl.Options{Scheme: scheme,
		Cache:   cache.Options{DefaultNamespaces: map[string]cache.Config{*namespace: {}}},
		Metrics: metricsserver.Options{BindAddress: "0"}, HealthProbeBindAddress: ":8081", LeaderElection: false})
	must(err)
	must((&labcontroller.Reconciler{Client: mgr.GetClient(), Reader: mgr.GetAPIReader()}).SetupWithManager(mgr))
	must(mgr.AddHealthzCheck("healthz", healthz.Ping))
	must(mgr.AddReadyzCheck("readyz", healthz.Ping))
	must(mgr.Start(ctrl.SetupSignalHandler()))
}
func must(err error) {
	if err != nil {
		ctrl.Log.Error(err, "manager failed")
		os.Exit(1)
	}
}
