package controller

import (
	"context"
	"errors"
	"reflect"
	"testing"

	labv1 "example.com/wiki/p0-controller/api/v1alpha1"
	appsv1 "k8s.io/api/apps/v1"
	corev1 "k8s.io/api/core/v1"
	apierrors "k8s.io/apimachinery/pkg/api/errors"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/runtime"
	"k8s.io/apimachinery/pkg/runtime/schema"
	"k8s.io/apimachinery/pkg/types"
	clientgoscheme "k8s.io/client-go/kubernetes/scheme"
	ctrl "sigs.k8s.io/controller-runtime"
	"sigs.k8s.io/controller-runtime/pkg/client"
	"sigs.k8s.io/controller-runtime/pkg/client/fake"
)

func fixture(t *testing.T) (*labv1.AppService, client.Client, *Reconciler) {
	t.Helper()
	s := runtime.NewScheme()
	if err := clientgoscheme.AddToScheme(s); err != nil {
		t.Fatal(err)
	}
	if err := labv1.AddToScheme(s); err != nil {
		t.Fatal(err)
	}
	a := &labv1.AppService{ObjectMeta: metav1.ObjectMeta{Name: "sample", Namespace: "test", UID: types.UID("owner-123"), Generation: 1}, Spec: labv1.AppServiceSpec{Image: "operand:test", Replicas: ptr(int32(1))}}
	c := fake.NewClientBuilder().WithScheme(s).WithStatusSubresource(&labv1.AppService{}, &appsv1.Deployment{}).WithObjects(a).Build()
	return a, c, &Reconciler{Client: c, Reader: c}
}
func TestReadinessRequiresCurrentRollout(t *testing.T) {
	a, _, _ := fixture(t)
	base := appsv1.Deployment{ObjectMeta: metav1.ObjectMeta{Generation: 2}, Spec: appsv1.DeploymentSpec{Replicas: ptr(int32(1))}, Status: appsv1.DeploymentStatus{ObservedGeneration: 2, Replicas: 1, UpdatedReplicas: 1, ReadyReplicas: 1, AvailableReplicas: 1, Conditions: []appsv1.DeploymentCondition{{Type: appsv1.DeploymentAvailable, Status: corev1.ConditionTrue}}}}
	tests := []struct {
		name   string
		change func(*appsv1.Deployment)
		ready  bool
	}{
		{"current", func(d *appsv1.Deployment) {}, true},
		{"stale-observation", func(d *appsv1.Deployment) { d.Status.ObservedGeneration = 1 }, false},
		{"not-ready", func(d *appsv1.Deployment) { d.Status.ReadyReplicas = 0 }, false},
		{"old-replicas", func(d *appsv1.Deployment) { d.Status.Replicas = 2 }, false},
		{"not-updated", func(d *appsv1.Deployment) { d.Status.UpdatedReplicas = 0 }, false},
		{"unavailable", func(d *appsv1.Deployment) { d.Status.AvailableReplicas = 0 }, false},
		{"missing-condition", func(d *appsv1.Deployment) { d.Status.Conditions = nil }, false},
		{"wrong-spec", func(d *appsv1.Deployment) { d.Spec.Replicas = ptr(int32(2)) }, false},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			d := base.DeepCopy()
			tt.change(d)
			c := readiness(a, d)
			if (c.Status == metav1.ConditionTrue) != tt.ready || c.ObservedGeneration != a.Generation {
				t.Fatalf("unexpected condition: %+v", c)
			}
		})
	}
}
func TestServiceMutationPreservesAllocatedFields(t *testing.T) {
	a, _, _ := fixture(t)
	s := &corev1.Service{Spec: corev1.ServiceSpec{ClusterIP: "10.96.0.8", ClusterIPs: []string{"10.96.0.8"}, IPFamilies: []corev1.IPFamily{corev1.IPv4Protocol}, IPFamilyPolicy: ptr(corev1.IPFamilyPolicySingleStack), HealthCheckNodePort: 0}}
	before := s.DeepCopy()
	mutateService(a, s)
	if s.Spec.ClusterIP != before.Spec.ClusterIP || !reflect.DeepEqual(s.Spec.ClusterIPs, before.Spec.ClusterIPs) || !reflect.DeepEqual(s.Spec.IPFamilies, before.Spec.IPFamilies) || *s.Spec.IPFamilyPolicy != *before.Spec.IPFamilyPolicy {
		t.Fatal("allocated fields changed")
	}
	if s.Spec.Selector[OwnerLabel] != string(a.UID) || s.Spec.Ports[0].Port != 8080 {
		t.Fatal("desired fields missing")
	}
}
func TestReconcileRefusesForeignChildren(t *testing.T) {
	for _, kind := range []string{"Deployment", "Service"} {
		for _, ownership := range []string{"unowned", "foreign"} {
			t.Run(kind+"/"+ownership, func(t *testing.T) {
				a, c, r := fixture(t)
				ctx := context.Background()
				var object client.Object
				m := metav1.ObjectMeta{Name: a.Name, Namespace: a.Namespace}
				if ownership == "foreign" {
					m.OwnerReferences = []metav1.OwnerReference{{APIVersion: labv1.GroupVersion.String(), Kind: "AppService", Name: "other", UID: "other-uid", Controller: ptr(true)}}
				}
				if kind == "Deployment" {
					object = &appsv1.Deployment{ObjectMeta: m}
				} else {
					object = &corev1.Service{ObjectMeta: m}
				}
				if err := c.Create(ctx, object); err != nil {
					t.Fatal(err)
				}
				rv := object.GetResourceVersion()
				res, err := r.Reconcile(ctx, ctrl.Request{NamespacedName: client.ObjectKeyFromObject(a)})
				if err != nil || res.RequeueAfter <= 0 {
					t.Fatalf("expected bounded ownership retry: %v %+v", err, res)
				}
				if err := c.Get(ctx, client.ObjectKeyFromObject(a), object); err != nil {
					t.Fatal(err)
				}
				if object.GetResourceVersion() != rv {
					t.Fatal("foreign child changed")
				}
				if err := c.Get(ctx, client.ObjectKeyFromObject(a), a); err != nil {
					t.Fatal(err)
				}
				if len(a.Status.Conditions) != 1 || a.Status.Conditions[0].Reason != "OwnershipConflict" || a.Status.Conditions[0].Status != metav1.ConditionFalse {
					t.Fatalf("wrong status %+v", a.Status)
				}
			})
		}
	}
}
func TestReconcileStableAndRepairsDrift(t *testing.T) {
	a, c, r := fixture(t)
	ctx := context.Background()
	req := ctrl.Request{NamespacedName: client.ObjectKeyFromObject(a)}
	run := func() {
		t.Helper()
		if _, err := r.Reconcile(ctx, req); err != nil {
			t.Fatal(err)
		}
	}
	run()
	d := &appsv1.Deployment{}
	s := &corev1.Service{}
	read := func() {
		t.Helper()
		if err := c.Get(ctx, req.NamespacedName, d); err != nil {
			t.Fatal(err)
		}
		if err := c.Get(ctx, req.NamespacedName, s); err != nil {
			t.Fatal(err)
		}
		if err := c.Get(ctx, req.NamespacedName, a); err != nil {
			t.Fatal(err)
		}
	}
	read()
	drv, srv, arv := d.ResourceVersion, s.ResourceVersion, a.ResourceVersion
	transition := a.Status.Conditions[0].LastTransitionTime
	for range 4 {
		run()
	}
	read()
	if d.ResourceVersion != drv || s.ResourceVersion != srv || a.ResourceVersion != arv || !a.Status.Conditions[0].LastTransitionTime.Equal(&transition) {
		t.Fatal("stable reconcile wrote resources/status")
	}
	d.Spec.Template.Spec.Containers[0].Image = "wrong:image"
	if err := c.Update(ctx, d); err != nil {
		t.Fatal(err)
	}
	s.Spec.Selector = map[string]string{"drift": "yes"}
	if err := c.Update(ctx, s); err != nil {
		t.Fatal(err)
	}
	run()
	read()
	if d.Spec.Template.Spec.Containers[0].Image != a.Spec.Image || s.Spec.Selector[OwnerLabel] != string(a.UID) {
		t.Fatal("drift not repaired")
	}
	if err := c.Delete(ctx, s); err != nil {
		t.Fatal(err)
	}
	run()
	read()
	if !metav1.IsControlledBy(d, a) || !metav1.IsControlledBy(s, a) {
		t.Fatal("owner reference missing")
	}
}

type conflictClient struct {
	client.Client
	remaining, patches int
}
type conflictStatus struct {
	client.SubResourceWriter
	parent *conflictClient
}

func (c *conflictClient) Status() client.SubResourceWriter {
	return &conflictStatus{SubResourceWriter: c.Client.Status(), parent: c}
}
func (s *conflictStatus) Patch(ctx context.Context, o client.Object, p client.Patch, opts ...client.SubResourcePatchOption) error {
	s.parent.patches++
	if s.parent.remaining > 0 {
		s.parent.remaining--
		return apierrors.NewConflict(schema.GroupResource{Group: labv1.GroupVersion.Group, Resource: "appservices"}, o.GetName(), errors.New("injected conflict"))
	}
	return s.SubResourceWriter.Patch(ctx, o, p, opts...)
}
func TestStatusConflictRetryBounded(t *testing.T) {
	for _, n := range []int{1, 10} {
		t.Run(map[int]string{1: "recovers", 10: "exhausts"}[n], func(t *testing.T) {
			a, c, r := fixture(t)
			cc := &conflictClient{Client: c, remaining: n}
			r.Client = cc
			err := r.writeStatus(context.Background(), a, readiness(a, nil))
			if n == 1 {
				if err != nil || cc.patches != 2 {
					t.Fatalf("retry failed: %d %v", cc.patches, err)
				}
			} else if !apierrors.IsConflict(err) || cc.patches != 3 {
				t.Fatalf("retry exceeded bound or hid failure: %d %v", cc.patches, err)
			}
		})
	}
}
func TestStatusDoesNotStampNewGeneration(t *testing.T) {
	a, c, r := fixture(t)
	old := a.DeepCopy()
	a.Generation = 2
	if err := c.Update(context.Background(), a); err != nil {
		t.Fatal(err)
	}
	if err := r.writeStatus(context.Background(), old, readiness(old, nil)); err != nil {
		t.Fatal(err)
	}
	if err := c.Get(context.Background(), client.ObjectKeyFromObject(a), a); err != nil {
		t.Fatal(err)
	}
	if a.Status.ObservedGeneration != 0 || len(a.Status.Conditions) != 0 {
		t.Fatal("stale result stamped a new generation")
	}
}
