//go:build integration

package integration

import (
	"context"
	"errors"
	"testing"
	"time"

	labv1 "example.com/wiki/p3-controller/api/v1alpha1"
	labcontroller "example.com/wiki/p3-controller/internal/controller"
	appsv1 "k8s.io/api/apps/v1"
	corev1 "k8s.io/api/core/v1"
	apierrors "k8s.io/apimachinery/pkg/api/errors"
	"k8s.io/apimachinery/pkg/api/meta"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/apis/meta/v1/unstructured"
	"k8s.io/apimachinery/pkg/watch"
	ctrl "sigs.k8s.io/controller-runtime"
	"sigs.k8s.io/controller-runtime/pkg/client"
)

func isolatedAPI(t *testing.T) (context.Context, client.Client, string) {
	t.Helper()
	ctx := context.Background()
	c, err := client.New(cfg, client.Options{Scheme: scheme})
	must(t, err)
	ns := &corev1.Namespace{ObjectMeta: metav1.ObjectMeta{GenerateName: "p3-observe-"}}
	must(t, c.Create(ctx, ns))
	t.Cleanup(func() {
		for _, obj := range []client.Object{&labv1.AppService{}, &appsv1.Deployment{}, &corev1.Service{}} {
			if err := c.DeleteAllOf(ctx, obj, client.InNamespace(ns.Name)); err != nil {
				t.Error(err)
			}
		}
		if err := c.Delete(ctx, ns); err != nil && !apierrors.IsNotFound(err) {
			t.Error(err)
		}
	})
	return ctx, c, ns.Name
}

func TestEnvtestAPIObservations(t *testing.T) {
	sub(t, "UnknownFieldPruning", func(t *testing.T) {
		ctx, c, ns := isolatedAPI(t)
		u := &unstructured.Unstructured{Object: map[string]any{"apiVersion": labv1.GroupVersion.String(), "kind": "AppService", "metadata": map[string]any{"name": "pruning", "namespace": ns}, "spec": map[string]any{"image": "operand:test", "repilcas": int64(3)}, "status": map[string]any{"observedGeneration": int64(99)}}}
		must(t, c.Create(ctx, u))
		must(t, c.Get(ctx, client.ObjectKeyFromObject(u), u))
		if _, found, err := unstructured.NestedFieldNoCopy(u.Object, "spec", "repilcas"); err != nil || found {
			t.Fatal("unknown field was not pruned")
		}
		n, found, err := unstructured.NestedInt64(u.Object, "spec", "replicas")
		if err != nil || !found || n != 1 {
			t.Fatal("pruned typo did not leave the documented default")
		}
		if _, found, _ := unstructured.NestedFieldNoCopy(u.Object, "status", "observedGeneration"); found {
			t.Fatal("create wrote the status subresource")
		}
	})
	sub(t, "ListWatchAndUIDRecreation", func(t *testing.T) {
		ctx, c, ns := isolatedAPI(t)
		wc, err := client.NewWithWatch(cfg, client.Options{Scheme: scheme})
		must(t, err)
		list := &labv1.AppServiceList{}
		must(t, wc.List(ctx, list, client.InNamespace(ns)))
		if list.ResourceVersion == "" || len(list.Items) != 0 {
			t.Fatal("initial list lacks a server snapshot boundary")
		}
		watchStartRV := list.ResourceVersion
		watchCtx, cancel := context.WithTimeout(ctx, 8*time.Second)
		defer cancel()
		w, err := wc.Watch(watchCtx, &labv1.AppServiceList{}, client.InNamespace(ns), &client.ListOptions{Raw: &metav1.ListOptions{ResourceVersion: watchStartRV}})
		must(t, err)
		defer w.Stop()
		a := &labv1.AppService{ObjectMeta: metav1.ObjectMeta{Name: "observed", Namespace: ns}, Spec: labv1.AppServiceSpec{Image: "operand:test"}}
		must(t, c.Create(ctx, a))
		await := func(want watch.EventType, generation int64) {
			t.Helper()
			for {
				select {
				case ev, ok := <-w.ResultChan():
					if !ok {
						t.Fatal("watch closed before the controlled event")
					}
					if ev.Type == watch.Error {
						t.Fatalf("watch error: %v", ev.Object)
					}
					item, ok := ev.Object.(*labv1.AppService)
					if ok && ev.Type == want && item.UID == a.UID && item.Generation == generation {
						return
					}
				case <-watchCtx.Done():
					t.Fatal("controlled watch event missing")
				}
			}
		}
		await(watch.Added, 1)
		oldUID, oldRV := a.UID, a.ResourceVersion
		two := int32(2)
		a.Spec.Replicas = &two
		must(t, c.Update(ctx, a))
		await(watch.Modified, 2)
		if a.ResourceVersion == oldRV || a.UID != oldUID {
			t.Fatal("spec update did not preserve UID and change resourceVersion")
		}
		w.Stop()
		// A fresh list recovers current state after a deliberately stopped watch.
		must(t, wc.List(ctx, list, client.InNamespace(ns)))
		if len(list.Items) != 1 || list.Items[0].Generation != 2 || *list.Items[0].Spec.Replicas != 2 {
			t.Fatal("relist did not recover current state")
		}
		must(t, c.Delete(ctx, a))
		fresh := &labv1.AppService{ObjectMeta: metav1.ObjectMeta{Name: a.Name, Namespace: ns}, Spec: labv1.AppServiceSpec{Image: "operand:test"}}
		must(t, c.Create(ctx, fresh))
		if fresh.UID == oldUID || fresh.Generation != 1 {
			t.Fatal("same-name recreation reused object identity")
		}
		record("api_observation", "pass", map[string]any{"case": "ListWatchAndUIDRecreation", "watch_started_from_list_rv": watchStartRV, "old_uid": oldUID, "new_uid": fresh.UID, "relist_generation": list.Items[0].Generation, "boundary": "controlled events; no compaction or arbitrary gap delivery guarantee"})
	})
	sub(t, "OwnedSelectorRefused", func(t *testing.T) {
		ctx, c, ns := isolatedAPI(t)
		a := &labv1.AppService{ObjectMeta: metav1.ObjectMeta{Name: "selector", Namespace: ns}, Spec: labv1.AppServiceSpec{Image: "operand:test"}}
		must(t, c.Create(ctx, a))
		controller := true
		d := &appsv1.Deployment{ObjectMeta: metav1.ObjectMeta{Name: a.Name, Namespace: ns, OwnerReferences: []metav1.OwnerReference{{APIVersion: labv1.GroupVersion.String(), Kind: "AppService", Name: a.Name, UID: a.UID, Controller: &controller}}}, Spec: appsv1.DeploymentSpec{Selector: &metav1.LabelSelector{MatchLabels: map[string]string{"immutable": "other"}}, Template: corev1.PodTemplateSpec{ObjectMeta: metav1.ObjectMeta{Labels: map[string]string{"immutable": "other"}}, Spec: corev1.PodSpec{Containers: []corev1.Container{{Name: "operand", Image: "operand:test"}}}}}}
		must(t, c.Create(ctx, d))
		rv, uid := d.ResourceVersion, d.UID
		r := &labcontroller.Reconciler{Client: c, Reader: c}
		res, err := r.Reconcile(ctx, ctrl.Request{NamespacedName: client.ObjectKeyFromObject(a)})
		must(t, err)
		must(t, c.Get(ctx, client.ObjectKeyFromObject(a), d))
		must(t, c.Get(ctx, client.ObjectKeyFromObject(a), a))
		co := meta.FindStatusCondition(a.Status.Conditions, "Ready")
		if res.RequeueAfter != 10*time.Second || d.UID != uid || d.ResourceVersion != rv || co == nil || co.Reason != "InvalidChild" || co.Status != metav1.ConditionFalse {
			t.Fatal("owned incompatible selector was replaced, changed, or hidden")
		}
	})
	sub(t, "PartialServiceFailureRecovers", func(t *testing.T) {
		ctx, c, ns := isolatedAPI(t)
		a := &labv1.AppService{ObjectMeta: metav1.ObjectMeta{Name: "partial", Namespace: ns}, Spec: labv1.AppServiceSpec{Image: "operand:test"}}
		must(t, c.Create(ctx, a))
		fault := &serviceCreateFailure{Client: c}
		r := &labcontroller.Reconciler{Client: fault, Reader: c}
		req := ctrl.Request{NamespacedName: client.ObjectKeyFromObject(a)}
		_, err := r.Reconcile(ctx, req)
		if !errors.Is(err, errServiceUnavailable) {
			t.Fatalf("partial failure hidden: %v", err)
		}
		d := &appsv1.Deployment{}
		must(t, c.Get(ctx, req.NamespacedName, d))
		uid, rv := d.UID, d.ResourceVersion
		must(t, c.Get(ctx, req.NamespacedName, a))
		co := meta.FindStatusCondition(a.Status.Conditions, "Ready")
		if co == nil || co.Reason != "ReconcileError" || co.Status != metav1.ConditionFalse {
			t.Fatal("partial failure reported Ready")
		}
		_, err = r.Reconcile(ctx, req)
		must(t, err)
		must(t, c.Get(ctx, req.NamespacedName, d))
		s := &corev1.Service{}
		must(t, c.Get(ctx, req.NamespacedName, s))
		if fault.calls != 2 || d.UID != uid || d.ResourceVersion != rv || !metav1.IsControlledBy(s, a) {
			t.Fatal("partial recovery replaced or rewrote Deployment")
		}
	})
	sub(t, "StatusUIDAndGenerationRaces", func(t *testing.T) {
		for _, mode := range []string{"generation", "uid"} {
			ctx, c, ns := isolatedAPI(t)
			a := &labv1.AppService{ObjectMeta: metav1.ObjectMeta{Name: "status-race", Namespace: ns}, Spec: labv1.AppServiceSpec{Image: "operand:test"}}
			must(t, c.Create(ctx, a))
			racer := &identityRaceClient{Client: c, mode: mode}
			r := &labcontroller.Reconciler{Client: racer, Reader: c}
			_, err := r.Reconcile(ctx, ctrl.Request{NamespacedName: client.ObjectKeyFromObject(a)})
			must(t, err)
			must(t, c.Get(ctx, client.ObjectKeyFromObject(a), a))
			if racer.calls != 1 || racer.conflicts != 1 || a.Status.ObservedGeneration != 0 || len(a.Status.Conditions) != 0 {
				t.Fatalf("stale %s observation persisted: calls=%d conflicts=%d status=%+v", mode, racer.calls, racer.conflicts, a.Status)
			}
			record("status_identity_race", "pass", map[string]any{"mode": mode, "api_conflicts": racer.conflicts, "status_patch_attempts": racer.calls, "status_written": false})
		}
	})
}

var errServiceUnavailable = errors.New("test-only transient Service create failure before API call")

type serviceCreateFailure struct {
	client.Client
	calls int
}

func (c *serviceCreateFailure) Create(ctx context.Context, obj client.Object, opts ...client.CreateOption) error {
	if _, ok := obj.(*corev1.Service); ok {
		c.calls++
		if c.calls == 1 {
			return errServiceUnavailable
		}
	}
	return c.Client.Create(ctx, obj, opts...)
}

type identityRaceClient struct {
	client.Client
	mode             string
	calls, conflicts int
}
type identityRaceWriter struct {
	client.SubResourceWriter
	parent *identityRaceClient
}

func (c *identityRaceClient) Status() client.SubResourceWriter {
	return &identityRaceWriter{SubResourceWriter: c.Client.Status(), parent: c}
}
func (w *identityRaceWriter) Patch(ctx context.Context, obj client.Object, patch client.Patch, opts ...client.SubResourcePatchOption) error {
	w.parent.calls++
	if w.parent.calls == 1 {
		fresh := &labv1.AppService{}
		if err := w.parent.Client.Get(ctx, client.ObjectKeyFromObject(obj), fresh); err != nil {
			return err
		}
		if w.parent.mode == "generation" {
			fresh.Spec.Image = "operand:changed"
			if err := w.parent.Client.Update(ctx, fresh); err != nil {
				return err
			}
		} else {
			if err := w.parent.Client.Delete(ctx, fresh); err != nil {
				return err
			}
			replacement := &labv1.AppService{ObjectMeta: metav1.ObjectMeta{Name: fresh.Name, Namespace: fresh.Namespace}, Spec: fresh.Spec}
			if err := w.parent.Client.Create(ctx, replacement); err != nil {
				return err
			}
		}
	}
	err := w.SubResourceWriter.Patch(ctx, obj, patch, opts...)
	if apierrors.IsConflict(err) {
		w.parent.conflicts++
	}
	return err
}
