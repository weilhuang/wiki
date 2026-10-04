//go:build integration

package integration

import (
	"context"
	"errors"
	"sync"
	"testing"
	"time"

	labv1 "example.com/wiki/p3-controller/api/v1alpha1"
	labcontroller "example.com/wiki/p3-controller/internal/controller"
	appsv1 "k8s.io/api/apps/v1"
	corev1 "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	kcache "k8s.io/client-go/tools/cache"
	"k8s.io/client-go/util/workqueue"
	ctrl "sigs.k8s.io/controller-runtime"
	"sigs.k8s.io/controller-runtime/pkg/cache"
	"sigs.k8s.io/controller-runtime/pkg/client"
	crconfig "sigs.k8s.io/controller-runtime/pkg/config"
	crcontroller "sigs.k8s.io/controller-runtime/pkg/controller"
	metricsserver "sigs.k8s.io/controller-runtime/pkg/metrics/server"
	"sigs.k8s.io/controller-runtime/pkg/reconcile"
)

func TestEnvtestCacheAndQueue(t *testing.T) {
	sub(t, "InformerCacheSyncAndCancellation", func(t *testing.T) {
		ctx, c, ns := isolatedAPI(t)
		a := &labv1.AppService{ObjectMeta: metav1.ObjectMeta{Name: "cached", Namespace: ns}, Spec: labv1.AppServiceSpec{Image: "operand:initial"}}
		must(t, c.Create(ctx, a))
		ca, err := cache.New(cfg, cache.Options{Scheme: scheme, DefaultNamespaces: map[string]cache.Config{ns: {}}})
		must(t, err)
		informer, err := ca.GetInformer(ctx, &labv1.AppService{}, cache.BlockUntilSynced(false))
		must(t, err)
		events := make(chan *labv1.AppService, 32)
		send := func(obj any) {
			if item, ok := obj.(*labv1.AppService); ok {
				select {
				case events <- item.DeepCopy():
				default:
				}
			}
		}
		registration, err := informer.AddEventHandler(kcache.ResourceEventHandlerFuncs{AddFunc: send, UpdateFunc: func(_, next any) { send(next) }})
		must(t, err)
		runCtx, cancel := context.WithCancel(ctx)
		ended := make(chan error, 1)
		go func() { ended <- ca.Start(runCtx) }()
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
					t.Error(err)
				}
			case <-time.After(5 * time.Second):
				t.Error("informer cancellation did not return")
			}
		}
		t.Cleanup(stop)
		syncCtx, done := context.WithTimeout(runCtx, 8*time.Second)
		defer done()
		if !ca.WaitForCacheSync(syncCtx) {
			t.Fatal("registered AppService informer failed to synchronize")
		}
		eventually(t, func() (bool, error) { return registration.HasSynced(), nil })
		read := &labv1.AppService{}
		must(t, ca.Get(ctx, client.ObjectKeyFromObject(a), read))
		if read.UID != a.UID || read.Spec.Image != "operand:initial" {
			t.Fatal("initial list not available behind sync barrier")
		}
		read.Spec.Image = "local-copy-only"
		must(t, ca.Get(ctx, client.ObjectKeyFromObject(a), read))
		if read.Spec.Image != "operand:initial" {
			t.Fatal("cache read leaked mutable reference")
		}
		a.Spec.Image = "operand:updated"
		must(t, c.Update(ctx, a))
		deadline := time.NewTimer(8 * time.Second)
		defer deadline.Stop()
		observed := false
		for !observed {
			select {
			case item := <-events:
				observed = item.UID == a.UID && item.ResourceVersion == a.ResourceVersion && item.Spec.Image == "operand:updated"
			case <-deadline.C:
				t.Fatal("API update did not reach informer handler")
			}
		}
		eventually(t, func() (bool, error) {
			err := ca.Get(ctx, client.ObjectKeyFromObject(a), read)
			return err == nil && read.ResourceVersion == a.ResourceVersion, err
		})
		must(t, informer.RemoveEventHandler(registration))
		stop()
		record("informer_observation", "pass", map[string]any{"namespace": ns, "initial_sync": true, "api_update_rv": a.ResourceVersion, "handler_observed": true, "cancel_returned": true, "cache_reads_are_latest": false})
	})
	sub(t, "ManagerTransientErrorRetry", func(t *testing.T) {
		ctx, c, ns := isolatedAPI(t)
		a := &labv1.AppService{ObjectMeta: metav1.ObjectMeta{Name: "retry", Namespace: ns}, Spec: labv1.AppServiceSpec{Image: "operand:test"}}
		must(t, c.Create(ctx, a))
		skip := true
		mgr, err := ctrl.NewManager(cfg, ctrl.Options{Scheme: scheme, Controller: crconfig.Controller{SkipNameValidation: &skip}, Cache: cache.Options{DefaultNamespaces: map[string]cache.Config{ns: {}}}, Metrics: metricsserver.Options{BindAddress: "0"}, HealthProbeBindAddress: "0", LeaderElection: false})
		must(t, err)
		reader := &failFirstReader{Reader: mgr.GetAPIReader(), key: client.ObjectKeyFromObject(a)}
		limiter := &observedLimiter{TypedRateLimiter: workqueue.NewTypedItemExponentialFailureRateLimiter[reconcile.Request](200*time.Millisecond, 10*time.Second), calls: make(chan limiterCall, 8)}
		r := &labcontroller.Reconciler{Client: mgr.GetClient(), Reader: reader}
		// NewQueue and UsePriorityQueue deliberately remain nil: exercise the pinned
		// controller-runtime default priorityqueue. Only fault/limiter observation is test-owned.
		must(t, ctrl.NewControllerManagedBy(mgr).Named("retry-observation").For(&labv1.AppService{}).Owns(&appsv1.Deployment{}).Owns(&corev1.Service{}).
			WithOptions(crcontroller.Options{MaxConcurrentReconciles: 1, RateLimiter: limiter}).Complete(r))
		for _, obj := range []client.Object{&labv1.AppService{}, &appsv1.Deployment{}, &corev1.Service{}} {
			_, err := mgr.GetCache().GetInformer(ctx, obj, cache.BlockUntilSynced(false))
			must(t, err)
		}
		runCtx, cancel := context.WithCancel(ctx)
		ended := make(chan error, 1)
		go func() { ended <- mgr.Start(runCtx) }()
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
					t.Error(err)
					record("manager_stop", "fail", err.Error())
				} else {
					record("manager_stop", "pass", nil)
				}
			case <-time.After(5 * time.Second):
				t.Error("retry manager failed to stop")
				record("manager_stop", "fail", "timeout")
			}
		}
		t.Cleanup(stop)
		syncCtx, done := context.WithTimeout(runCtx, 8*time.Second)
		defer done()
		if !mgr.GetCache().WaitForCacheSync(syncCtx) {
			t.Fatal("retry manager cache failed to sync")
		}
		record("manager_start", "pass", ns)
		record("manager_cache_sync", "pass", ns)
		var observed limiterCall
		select {
		case observed = <-limiter.calls:
		case <-time.After(8 * time.Second):
			t.Fatal("injected reader error never reached real manager rate limiter")
		}
		if observed.key.NamespacedName != client.ObjectKeyFromObject(a) || observed.delay != 200*time.Millisecond {
			t.Fatalf("unexpected per-key retry observation: %+v", observed)
		}
		eventually(t, func() (bool, error) {
			s := &corev1.Service{}
			err := c.Get(ctx, client.ObjectKeyFromObject(a), s)
			return err == nil && metav1.IsControlledBy(s, a), err
		})
		reader.mu.Lock()
		calls := append([]time.Time(nil), reader.calls...)
		reader.mu.Unlock()
		if len(calls) < 2 || calls[1].Sub(calls[0]) < 180*time.Millisecond {
			t.Fatal("retry occurred before the explicitly configured first backoff")
		}
		stop()
		record("manager_retry_observation", "pass", map[string]any{"key": ns + "/retry", "injected_read_failures": 1, "limiter_delay_ns": observed.delay.Nanoseconds(), "first_to_second_read_ns": calls[1].Sub(calls[0]).Nanoseconds(), "reader_calls": len(calls), "queue_selection": "v0.25.2 default priorityqueue, NewQueue nil", "boundary": "test-only failure before API read; manager/cache/queue and subsequent API writes are real"})
	})
}

type limiterCall struct {
	key   reconcile.Request
	delay time.Duration
}
type observedLimiter struct {
	workqueue.TypedRateLimiter[reconcile.Request]
	calls chan limiterCall
}

func (l *observedLimiter) When(key reconcile.Request) time.Duration {
	delay := l.TypedRateLimiter.When(key)
	select {
	case l.calls <- limiterCall{key, delay}:
	default:
	}
	return delay
}

type failFirstReader struct {
	client.Reader
	key   client.ObjectKey
	mu    sync.Mutex
	calls []time.Time
}

func (r *failFirstReader) Get(ctx context.Context, key client.ObjectKey, obj client.Object, opts ...client.GetOption) error {
	if _, ok := obj.(*labv1.AppService); ok && key == r.key {
		r.mu.Lock()
		r.calls = append(r.calls, time.Now())
		first := len(r.calls) == 1
		r.mu.Unlock()
		if first {
			return errors.New("test-only transient reader failure; no API write occurred")
		}
	}
	return r.Reader.Get(ctx, key, obj, opts...)
}
