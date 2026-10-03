//go:build integration

package integration

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	labv1 "example.com/wiki/p0-controller/api/v1alpha1"
	labcontroller "example.com/wiki/p0-controller/internal/controller"
	appsv1 "k8s.io/api/apps/v1"
	corev1 "k8s.io/api/core/v1"
	apierrors "k8s.io/apimachinery/pkg/api/errors"
	"k8s.io/apimachinery/pkg/api/meta"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/runtime"
	"k8s.io/client-go/discovery"
	clientgoscheme "k8s.io/client-go/kubernetes/scheme"
	"k8s.io/client-go/rest"
	ctrl "sigs.k8s.io/controller-runtime"
	"sigs.k8s.io/controller-runtime/pkg/cache"
	"sigs.k8s.io/controller-runtime/pkg/client"
	crconfig "sigs.k8s.io/controller-runtime/pkg/config"
	"sigs.k8s.io/controller-runtime/pkg/envtest"
	metricsserver "sigs.k8s.io/controller-runtime/pkg/metrics/server"
)

var cfg *rest.Config
var scheme = runtime.NewScheme()
var report = map[string]any{"schema_version": 1, "status": "fail", "layer": "envtest-real-manager", "readiness_inputs": "simulated Deployment status only; no workload or GC controllers"}
var cases []map[string]any
var lifecycle []map[string]any
var required = []string{"APIValidationAndDefaults", "StatusSubresourceAndConflict", "WatchConvergenceAndNoop", "CurrentGenerationSimulatedStatus", "ForeignOwnershipRefused", "ManagerRestartConverges"}

func record(event, status string, details any) {
	lifecycle = append(lifecycle, map[string]any{"event": event, "status": status, "at": time.Now().UTC().Format(time.RFC3339Nano), "details": details})
}
func TestMain(m *testing.M) { os.Exit(runMain(m)) }
func runMain(m *testing.M) (code int) {
	code = 1
	output := os.Getenv("P0_ENVTEST_REPORT")
	source := os.Getenv("P0_SOURCE_ID")
	report["source_id"] = source
	report["required_cases"] = required
	for _, id := range required {
		cases = append(cases, map[string]any{"id": id, "status": "not_run", "details": "case did not run"})
	}
	// Report output is an explicit private new file, never an inferred repository path.
	if output == "" || source == "" || os.Getenv("P0_ENVTEST") != "1" {
		fmt.Fprintln(os.Stderr, "P0_ENVTEST=1, P0_SOURCE_ID and P0_ENVTEST_REPORT are required")
		return 1
	}
	output, err := filepath.Abs(output)
	if err != nil {
		return 1
	}
	parent, err := filepath.EvalSymlinks(filepath.Dir(output))
	if err != nil || parent != filepath.Dir(output) {
		fmt.Fprintln(os.Stderr, "report parent missing or symlinked")
		return 1
	}
	if _, err := os.Lstat(output); !os.IsNotExist(err) {
		fmt.Fprintln(os.Stderr, "report output already exists or cannot be inspected")
		return 1
	}
	defer func() {
		report["cases"] = cases
		report["lifecycle"] = lifecycle
		report["exit_code"] = code
		if code == 0 {
			report["status"] = "pass"
		}
		data, err := json.MarshalIndent(report, "", "  ")
		if err == nil {
			var f *os.File
			f, err = os.OpenFile(output, os.O_WRONLY|os.O_CREATE|os.O_EXCL, 0600)
			if err == nil {
				_, err = f.Write(append(data, '\n'))
				if closeErr := f.Close(); err == nil {
					err = closeErr
				}
			}
		}
		if err != nil {
			fmt.Fprintln(os.Stderr, "cannot write envtest report:", err)
			code = 1
		}
	}()
	if err := clientgoscheme.AddToScheme(scheme); err != nil {
		record("scheme", "fail", err.Error())
		return 1
	}
	if err := labv1.AddToScheme(scheme); err != nil {
		record("scheme", "fail", err.Error())
		return 1
	}
	assets := os.Getenv("KUBEBUILDER_ASSETS")
	if !filepath.IsAbs(assets) {
		record("assets", "fail", "explicit absolute KUBEBUILDER_ASSETS required")
		return 1
	}
	for _, name := range []string{"kube-apiserver", "etcd", "kubectl"} {
		st, err := os.Stat(filepath.Join(assets, name))
		if err != nil || st.IsDir() || st.Mode()&0111 == 0 {
			record("assets", "fail", "missing executable: "+name)
			return 1
		}
	}
	useExisting := false
	env := &envtest.Environment{CRDDirectoryPaths: []string{filepath.Join("..", "..", "config", "crd")}, ErrorIfCRDPathMissing: true, BinaryAssetsDirectory: assets, UseExistingCluster: &useExisting, ControlPlaneStartTimeout: 20 * time.Second, ControlPlaneStopTimeout: 10 * time.Second}
	record("control_plane_start", "attempt", nil)
	cfg, err = env.Start()
	// Start can partially allocate processes. Stop is attempted after every Start attempt.
	defer func() {
		if err := env.Stop(); err != nil {
			record("control_plane_stop", "fail", err.Error())
			code = 1
		} else {
			record("control_plane_stop", "pass", nil)
		}
	}()
	if err != nil {
		record("control_plane_start", "fail", err.Error())
		return 1
	}
	record("control_plane_start", "pass", nil)
	cfg.Timeout = 5 * time.Second
	dc, err := discovery.NewDiscoveryClientForConfig(cfg)
	if err != nil {
		record("server_version", "fail", err.Error())
		return 1
	}
	version, err := dc.ServerVersion()
	if err != nil {
		record("server_version", "fail", err.Error())
		return 1
	}
	report["server_version"] = version.GitVersion
	if version.GitVersion != "v1.37.0" {
		record("server_version", "fail", "unexpected server version")
		return 1
	}
	record("server_version", "pass", version.GitVersion)
	code = m.Run()
	for _, c := range cases {
		if c["status"] != "pass" {
			code = 1
		}
	}
	return code
}
func must(t *testing.T, err error) {
	t.Helper()
	if err != nil {
		t.Fatal(err)
	}
}
func eventually(t *testing.T, fn func() (bool, error)) {
	t.Helper()
	deadline := time.Now().Add(8 * time.Second)
	var last error
	for time.Now().Before(deadline) {
		ok, err := fn()
		if err == nil && ok {
			return
		}
		last = err
		time.Sleep(50 * time.Millisecond)
	}
	t.Fatalf("condition not reached in 8s; last error: %v", last)
}
func startManager(t *testing.T, namespace string) func() {
	t.Helper()
	skipSequentialNameValidation := true
	// controller-runtime keeps a process-global name registry even after a manager stops.
	// Only this sequential in-process restart fixture bypasses that metric-name check.
	mgr, err := ctrl.NewManager(cfg, ctrl.Options{Scheme: scheme, Controller: crconfig.Controller{SkipNameValidation: &skipSequentialNameValidation}, Cache: cache.Options{DefaultNamespaces: map[string]cache.Config{namespace: {}}}, Metrics: metricsserver.Options{BindAddress: "0"}, HealthProbeBindAddress: "0", LeaderElection: false})
	must(t, err)
	must(t, (&labcontroller.Reconciler{Client: mgr.GetClient(), Reader: mgr.GetAPIReader()}).SetupWithManager(mgr))
	// Register all watched GVKs before starting; an empty cache is not a meaningful synchronization barrier.
	for _, obj := range []client.Object{&labv1.AppService{}, &appsv1.Deployment{}, &corev1.Service{}} {
		_, err := mgr.GetCache().GetInformer(context.Background(), obj, cache.BlockUntilSynced(false))
		must(t, err)
	}
	ctx, cancel := context.WithCancel(context.Background())
	ended := make(chan error, 1)
	go func() { ended <- mgr.Start(ctx) }()
	record("manager_start", "attempt", map[string]string{"namespace": namespace})
	stopped := false
	stop := func() {
		if stopped {
			return
		}
		stopped = true
		cancel()
		select {
		case err := <-ended:
			if err != nil {
				record("manager_stop", "fail", err.Error())
				t.Errorf("manager stop: %v", err)
			} else {
				record("manager_stop", "pass", nil)
			}
		case <-time.After(5 * time.Second):
			record("manager_stop", "fail", "5s timeout")
			t.Error("manager stop timed out")
		}
	}
	t.Cleanup(stop)
	syncCtx, done := context.WithTimeout(ctx, 10*time.Second)
	defer done()
	if !mgr.GetCache().WaitForCacheSync(syncCtx) {
		record("manager_cache_sync", "fail", nil)
		t.Fatal("cache did not synchronize")
	}
	record("manager_start", "pass", nil)
	record("manager_cache_sync", "pass", nil)
	return stop
}
func sub(t *testing.T, id string, fn func(*testing.T)) {
	t.Helper()
	skipped := false
	ok := t.Run(id, func(st *testing.T) { defer func() { skipped = st.Skipped() }(); fn(st) })
	if skipped {
		ok = false
	}
	for _, c := range cases {
		if c["id"] == id {
			if ok {
				c["status"] = "pass"
				c["details"] = "assertions completed"
			} else {
				c["status"] = "fail"
				c["details"] = "see exact go test JSON failure"
			}
			return
		}
	}
	t.Fatalf("unregistered case %s", id)
}

// Inject a real API resource-version race, not a fabricated Conflict error.
type racingStatusClient struct {
	client.Client
	attempts, conflicts int
}
type racingStatusWriter struct {
	client.SubResourceWriter
	parent *racingStatusClient
}

func (c *racingStatusClient) Status() client.SubResourceWriter {
	return &racingStatusWriter{SubResourceWriter: c.Client.Status(), parent: c}
}
func (w *racingStatusWriter) Patch(ctx context.Context, obj client.Object, patch client.Patch, opts ...client.SubResourcePatchOption) error {
	w.parent.attempts++
	if w.parent.attempts == 1 {
		fresh := &labv1.AppService{}
		if err := w.parent.Client.Get(ctx, client.ObjectKeyFromObject(obj), fresh); err != nil {
			return err
		}
		fresh.Annotations = map[string]string{"test.lab.wiki.example/race": "advance-resource-version"}
		if err := w.parent.Client.Update(ctx, fresh); err != nil {
			return err
		}
	}
	err := w.SubResourceWriter.Patch(ctx, obj, patch, opts...)
	if apierrors.IsConflict(err) {
		w.parent.conflicts++
	}
	return err
}
func TestEnvtestManagerLifecycle(t *testing.T) {
	ctx := context.Background()
	c, err := client.New(cfg, client.Options{Scheme: scheme})
	must(t, err)
	ns := &corev1.Namespace{ObjectMeta: metav1.ObjectMeta{GenerateName: "p0-envtest-"}}
	must(t, c.Create(ctx, ns))
	record("namespace_created", "pass", ns.Name)
	// Cleanup explicitly: envtest has no namespace controller or owner garbage collector.
	t.Cleanup(func() {
		for _, o := range []client.Object{&labv1.AppService{}, &appsv1.Deployment{}, &corev1.Service{}} {
			if err := c.DeleteAllOf(ctx, o, client.InNamespace(ns.Name)); err != nil {
				record("resources_delete", "fail", err.Error())
				t.Error(err)
			}
		}
		if err := c.Delete(ctx, ns); err != nil && !apierrors.IsNotFound(err) {
			record("namespace_delete_request", "fail", err.Error())
			t.Error(err)
		} else {
			record("namespace_delete_request", "pass", "deletion requested; no claim of namespace controller/GC")
		}
	})
	var app *labv1.AppService
	key := client.ObjectKey{Namespace: ns.Name, Name: "sample"}
	sub(t, "APIValidationAndDefaults", func(t *testing.T) {
		for _, n := range []int32{0, 4} {
			bad := &labv1.AppService{ObjectMeta: metav1.ObjectMeta{Name: fmt.Sprintf("invalid-%d", n), Namespace: ns.Name}, Spec: labv1.AppServiceSpec{Image: "operand:test", Replicas: &n}}
			if err := c.Create(ctx, bad); !apierrors.IsInvalid(err) {
				t.Fatalf("expected server Invalid for replicas %d, got %v", n, err)
			}
		}
		for _, name := range []string{"has.dot", strings.Repeat("a", 64)} {
			invalid := &labv1.AppService{ObjectMeta: metav1.ObjectMeta{Name: name, Namespace: ns.Name}, Spec: labv1.AppServiceSpec{Image: "operand:test"}}
			if err := c.Create(ctx, invalid); !apierrors.IsInvalid(err) {
				t.Fatalf("expected CEL Invalid for Service-incompatible name %q, got %v", name, err)
			}
		}
		bad := &labv1.AppService{ObjectMeta: metav1.ObjectMeta{Name: "invalid-image", Namespace: ns.Name}, Spec: labv1.AppServiceSpec{Image: ""}}
		if err := c.Create(ctx, bad); !apierrors.IsInvalid(err) {
			t.Fatalf("expected server Invalid for empty image, got %v", err)
		}
		app = &labv1.AppService{ObjectMeta: metav1.ObjectMeta{Name: key.Name, Namespace: ns.Name}, Spec: labv1.AppServiceSpec{Image: "operand:test"}, Status: labv1.AppServiceStatus{ObservedGeneration: 999}}
		must(t, c.Create(ctx, app))
		must(t, c.Get(ctx, key, app))
		if app.Spec.Replicas == nil || *app.Spec.Replicas != 1 || app.Generation != 1 || app.Status.ObservedGeneration != 0 {
			t.Fatalf("schema/default/status create contract failed: %+v", app)
		}
	})
	if app == nil {
		t.Fatal("valid fixture unavailable")
	}
	sub(t, "StatusSubresourceAndConflict", func(t *testing.T) {
		one, two := app.DeepCopy(), app.DeepCopy()
		one.Labels = map[string]string{"version": "one"}
		must(t, c.Update(ctx, one))
		two.Labels = map[string]string{"version": "two"}
		if err := c.Update(ctx, two); !apierrors.IsConflict(err) {
			t.Fatalf("expected real stale resourceVersion conflict, got %v", err)
		}
		must(t, c.Get(ctx, key, app))
		generation := app.Generation
		app.Status.ObservedGeneration = 88
		must(t, c.Update(ctx, app))
		must(t, c.Get(ctx, key, app))
		if app.Status.ObservedGeneration != 0 {
			t.Fatal("main endpoint accepted status")
		}
		app.Status.ObservedGeneration = 1
		must(t, c.Status().Update(ctx, app))
		must(t, c.Get(ctx, key, app))
		if app.Generation != generation || app.Status.ObservedGeneration != 1 {
			t.Fatal("status subresource changed spec generation or lost status")
		}
		raced := &labv1.AppService{ObjectMeta: metav1.ObjectMeta{Name: "conflict-retry", Namespace: ns.Name}, Spec: labv1.AppServiceSpec{Image: "operand:test"}}
		must(t, c.Create(ctx, raced))
		racer := &racingStatusClient{Client: c}
		r := &labcontroller.Reconciler{Client: racer, Reader: c}
		_, err := r.Reconcile(ctx, ctrl.Request{NamespacedName: client.ObjectKeyFromObject(raced)})
		must(t, err)
		if racer.attempts != 2 || racer.conflicts != 1 {
			t.Fatalf("real API conflict recovery: attempts=%d conflicts=%d", racer.attempts, racer.conflicts)
		}
		must(t, c.Get(ctx, client.ObjectKeyFromObject(raced), raced))
		if co := meta.FindStatusCondition(raced.Status.Conditions, "Ready"); co == nil || co.Status != metav1.ConditionFalse || co.ObservedGeneration != raced.Generation {
			t.Fatal("real conflict retry did not persist current status")
		}
	})
	stop := startManager(t, ns.Name)
	sub(t, "WatchConvergenceAndNoop", func(t *testing.T) {
		d := &appsv1.Deployment{}
		s := &corev1.Service{}
		eventually(t, func() (bool, error) {
			if err := c.Get(ctx, key, d); err != nil {
				return false, err
			}
			if err := c.Get(ctx, key, s); err != nil {
				return false, err
			}
			must(t, c.Get(ctx, key, app))
			cond := meta.FindStatusCondition(app.Status.Conditions, "Ready")
			return cond != nil && cond.Status == metav1.ConditionFalse && metav1.IsControlledBy(d, app) && metav1.IsControlledBy(s, app) && s.Spec.ClusterIP != "", nil
		})
		ip := s.Spec.ClusterIP
		drv, srv := d.ResourceVersion, s.ResourceVersion
		cond := meta.FindStatusCondition(app.Status.Conditions, "Ready")
		transition := cond.LastTransitionTime
		r := &labcontroller.Reconciler{Client: c, Reader: c}
		for range 3 {
			_, err := r.Reconcile(ctx, ctrl.Request{NamespacedName: key})
			must(t, err)
		}
		must(t, c.Get(ctx, key, d))
		must(t, c.Get(ctx, key, s))
		must(t, c.Get(ctx, key, app))
		if d.ResourceVersion != drv || s.ResourceVersion != srv || !meta.FindStatusCondition(app.Status.Conditions, "Ready").LastTransitionTime.Equal(&transition) {
			t.Fatal("no-op reconciliation wrote child specs or changed transition time")
		}
		s.Spec.Selector = map[string]string{"drift": "yes"}
		must(t, c.Update(ctx, s))
		eventually(t, func() (bool, error) {
			err := c.Get(ctx, key, s)
			return err == nil && s.Spec.Selector[labcontroller.OwnerLabel] == string(app.UID) && s.Spec.ClusterIP == ip, err
		})
		oldUID := s.UID
		must(t, c.Delete(ctx, s))
		eventually(t, func() (bool, error) {
			err := c.Get(ctx, key, s)
			return err == nil && s.UID != oldUID && metav1.IsControlledBy(s, app), err
		})
	})
	sub(t, "CurrentGenerationSimulatedStatus", func(t *testing.T) {
		// These status writes are deliberately synthetic. envtest runs no Deployment controller or Pods.
		d := &appsv1.Deployment{}
		must(t, c.Get(ctx, key, d))
		d.Status = appsv1.DeploymentStatus{ObservedGeneration: d.Generation - 1, Replicas: 1, UpdatedReplicas: 1, ReadyReplicas: 1, AvailableReplicas: 1, Conditions: []appsv1.DeploymentCondition{{Type: appsv1.DeploymentAvailable, Status: corev1.ConditionTrue}}}
		must(t, c.Status().Update(ctx, d))
		r := &labcontroller.Reconciler{Client: c, Reader: c}
		_, err := r.Reconcile(ctx, ctrl.Request{NamespacedName: key})
		must(t, err)
		must(t, c.Get(ctx, key, app))
		if meta.IsStatusConditionTrue(app.Status.Conditions, "Ready") {
			t.Fatal("stale Deployment status accepted")
		}
		must(t, c.Get(ctx, key, d))
		d.Status.ObservedGeneration = d.Generation
		must(t, c.Status().Update(ctx, d))
		eventually(t, func() (bool, error) {
			err := c.Get(ctx, key, app)
			co := meta.FindStatusCondition(app.Status.Conditions, "Ready")
			return err == nil && co != nil && co.Status == metav1.ConditionTrue && co.ObservedGeneration == app.Generation, err
		})
		// Image change creates a new desired Deployment generation; previous readiness cannot authorize it.
		must(t, c.Get(ctx, key, app))
		app.Spec.Image = "operand:changed"
		must(t, c.Update(ctx, app))
		eventually(t, func() (bool, error) {
			err := c.Get(ctx, key, app)
			co := meta.FindStatusCondition(app.Status.Conditions, "Ready")
			return err == nil && co != nil && co.Status == metav1.ConditionFalse && co.ObservedGeneration == app.Generation && app.Status.ObservedGeneration == app.Generation, err
		})
	})
	sub(t, "ForeignOwnershipRefused", func(t *testing.T) {
		for _, kind := range []string{"deployment", "service"} {
			k := client.ObjectKey{Namespace: ns.Name, Name: "foreign-" + kind}
			var child client.Object
			if kind == "deployment" {
				child = &appsv1.Deployment{ObjectMeta: metav1.ObjectMeta{Name: k.Name, Namespace: k.Namespace}, Spec: appsv1.DeploymentSpec{Selector: &metav1.LabelSelector{MatchLabels: map[string]string{"foreign": "yes"}}, Template: corev1.PodTemplateSpec{ObjectMeta: metav1.ObjectMeta{Labels: map[string]string{"foreign": "yes"}}, Spec: corev1.PodSpec{Containers: []corev1.Container{{Name: "foreign", Image: "foreign:fixed"}}}}}}
			} else {
				child = &corev1.Service{ObjectMeta: metav1.ObjectMeta{Name: k.Name, Namespace: k.Namespace}, Spec: corev1.ServiceSpec{Ports: []corev1.ServicePort{{Port: 9090}}}}
			}
			must(t, c.Create(ctx, child))
			rv := child.GetResourceVersion()
			a := &labv1.AppService{ObjectMeta: metav1.ObjectMeta{Name: k.Name, Namespace: k.Namespace}, Spec: labv1.AppServiceSpec{Image: "operand:test"}}
			must(t, c.Create(ctx, a))
			eventually(t, func() (bool, error) {
				err := c.Get(ctx, k, a)
				co := meta.FindStatusCondition(a.Status.Conditions, "Ready")
				return err == nil && co != nil && co.Status == metav1.ConditionFalse && co.Reason == "OwnershipConflict", err
			})
			must(t, c.Get(ctx, k, child))
			if child.GetResourceVersion() != rv || len(child.GetOwnerReferences()) != 0 {
				t.Fatal("foreign child changed")
			}
		}
	})
	sub(t, "ManagerRestartConverges", func(t *testing.T) {
		stop()
		d := &appsv1.Deployment{}
		must(t, c.Get(ctx, key, d))
		d.Spec.Template.Spec.Containers[0].Image = "drift:while-stopped"
		must(t, c.Update(ctx, d))
		stop = startManager(t, ns.Name)
		eventually(t, func() (bool, error) {
			err := c.Get(ctx, key, d)
			return err == nil && d.Spec.Template.Spec.Containers[0].Image == "operand:changed", err
		})
		stop()
	})
}
