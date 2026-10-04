package controller

import (
	"context"
	"errors"
	"testing"
	"time"

	labv1 "example.com/wiki/p3-controller/api/v1alpha1"
	appsv1 "k8s.io/api/apps/v1"
	corev1 "k8s.io/api/core/v1"
	"k8s.io/apimachinery/pkg/api/meta"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/client-go/util/workqueue"
	ctrl "sigs.k8s.io/controller-runtime"
	"sigs.k8s.io/controller-runtime/pkg/client"
)

func TestStatusDoesNotStampRecreatedUID(t *testing.T) {
	a, c, r := fixture(t)
	old := a.DeepCopy()
	if err := c.Delete(context.Background(), a); err != nil {
		t.Fatal(err)
	}
	fresh := &labv1.AppService{ObjectMeta: metav1.ObjectMeta{Name: a.Name, Namespace: a.Namespace, UID: "replacement-uid", Generation: 1}, Spec: a.Spec}
	if err := c.Create(context.Background(), fresh); err != nil {
		t.Fatal(err)
	}
	if err := r.writeStatus(context.Background(), old, readiness(old, nil)); err != nil {
		t.Fatal(err)
	}
	if err := c.Get(context.Background(), client.ObjectKeyFromObject(fresh), fresh); err != nil {
		t.Fatal(err)
	}
	if fresh.Status.ObservedGeneration != 0 || len(fresh.Status.Conditions) != 0 {
		semanticAssert(t, "STALE_UID_STAMPED", fresh.Status, labv1.AppServiceStatus{})
	}
}

func TestReconcileRefusesOwnedIncompatibleSelector(t *testing.T) {
	a, c, r := fixture(t)
	d := &appsv1.Deployment{ObjectMeta: metav1.ObjectMeta{Name: a.Name, Namespace: a.Namespace, OwnerReferences: owner(a)}, Spec: appsv1.DeploymentSpec{Selector: &metav1.LabelSelector{MatchLabels: map[string]string{"other": "selector"}}}}
	if err := c.Create(context.Background(), d); err != nil {
		t.Fatal(err)
	}
	rv := d.ResourceVersion
	res, err := r.Reconcile(context.Background(), ctrl.Request{NamespacedName: client.ObjectKeyFromObject(a)})
	if err != nil || res.RequeueAfter != 10*time.Second {
		t.Fatalf("unexpected policy: %+v %v", res, err)
	}
	if err := c.Get(context.Background(), client.ObjectKeyFromObject(a), d); err != nil {
		t.Fatal(err)
	}
	if d.ResourceVersion != rv || d.Spec.Selector.MatchLabels["other"] != "selector" {
		t.Fatal("IMMUTABLE_SELECTOR_CHANGED: refused child was mutated")
	}
	if err := c.Get(context.Background(), client.ObjectKeyFromObject(a), a); err != nil {
		t.Fatal(err)
	}
	cond := meta.FindStatusCondition(a.Status.Conditions, "Ready")
	if cond == nil || cond.Reason != "InvalidChild" || cond.Status != metav1.ConditionFalse {
		t.Fatal("IMMUTABLE_SELECTOR_UNREPORTED: expected InvalidChild")
	}
}

type oneServiceFailure struct {
	client.Client
	attempts int
}

var errInjectedService = errors.New("test-only transient Service create failure")

func (c *oneServiceFailure) Create(ctx context.Context, obj client.Object, opts ...client.CreateOption) error {
	if _, ok := obj.(*corev1.Service); ok {
		c.attempts++
		if c.attempts == 1 {
			return errInjectedService
		}
	}
	return c.Client.Create(ctx, obj, opts...)
}
func TestPartialServiceFailureRecovers(t *testing.T) {
	a, c, r := fixture(t)
	failing := &oneServiceFailure{Client: c}
	r.Client = failing
	req := ctrl.Request{NamespacedName: client.ObjectKeyFromObject(a)}
	_, err := r.Reconcile(context.Background(), req)
	if !errors.Is(err, errInjectedService) {
		t.Fatalf("TRANSIENT_ERROR_HIDDEN: %v", err)
	}
	d := &appsv1.Deployment{}
	if err := c.Get(context.Background(), req.NamespacedName, d); err != nil {
		t.Fatal(err)
	}
	rv := d.ResourceVersion
	if err := c.Get(context.Background(), req.NamespacedName, a); err != nil {
		t.Fatal(err)
	}
	cond := meta.FindStatusCondition(a.Status.Conditions, "Ready")
	if cond == nil || cond.Reason != "ReconcileError" || cond.Status != metav1.ConditionFalse {
		t.Fatal("PARTIAL_FAILURE_READY: missing failure condition")
	}
	if _, err := r.Reconcile(context.Background(), req); err != nil {
		t.Fatal(err)
	}
	if err := c.Get(context.Background(), req.NamespacedName, d); err != nil {
		t.Fatal(err)
	}
	s := &corev1.Service{}
	if err := c.Get(context.Background(), req.NamespacedName, s); err != nil {
		t.Fatal(err)
	}
	if failing.attempts != 2 || d.ResourceVersion != rv || !metav1.IsControlledBy(s, a) {
		t.Fatal("PARTIAL_FAILURE_NOT_RECOVERED: duplicate deployment write or missing Service")
	}
}

// This selects client-go's ordinary queue deliberately. The manager uses the
// controller-runtime v0.25.2 default priorityqueue; this is not its implementation.
func TestClientGoQueueKeyCoalescing(t *testing.T) {
	q := workqueue.NewTyped[string]()
	defer q.ShutDown()
	q.Add("lesson/sample")
	q.Add("lesson/sample")
	if q.Len() != 1 {
		t.Fatal("duplicate key was not coalesced before Get")
	}
	key, shutdown := q.Get()
	if shutdown || key != "lesson/sample" || q.Len() != 0 {
		t.Fatal("unexpected first Get")
	}
	q.Add(key)
	q.Add(key)
	if q.Len() != 0 {
		t.Fatal("processing key was handed to a second worker")
	}
	q.Done(key)
	if q.Len() != 1 {
		t.Fatal("dirty processing key lost its later turn")
	}
	again, shutdown := q.Get()
	if shutdown || again != key {
		t.Fatal("dirty key was not returned")
	}
	q.Done(again)
	if q.Len() != 0 {
		t.Fatal("duplicate events created extra work")
	}
	q.ShutDown()
	if _, stopped := q.Get(); !stopped {
		t.Fatal("shutdown did not unblock empty Get")
	}
}

func TestExplicitExponentialLimiter(t *testing.T) {
	r := workqueue.NewTypedItemExponentialFailureRateLimiter[string](200*time.Millisecond, 10*time.Second)
	expected := []time.Duration{200 * time.Millisecond, 400 * time.Millisecond, 800 * time.Millisecond, 1600 * time.Millisecond, 3200 * time.Millisecond, 6400 * time.Millisecond, 10 * time.Second, 10 * time.Second}
	for _, want := range expected {
		if got := r.When("a"); got != want {
			t.Fatalf("backoff=%v want=%v", got, want)
		}
	}
	if got := r.When("b"); got != 200*time.Millisecond {
		t.Fatal("per-key failure count leaked to another key")
	}
	r.Forget("a")
	if r.NumRequeues("a") != 0 || r.When("a") != 200*time.Millisecond {
		t.Fatal("Forget did not reset per-key history")
	}
}
