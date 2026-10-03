package controller

import (
	"context"
	"errors"
	"fmt"
	"time"

	labv1 "example.com/wiki/p0-controller/api/v1alpha1"
	appsv1 "k8s.io/api/apps/v1"
	corev1 "k8s.io/api/core/v1"
	"k8s.io/apimachinery/pkg/api/equality"
	apierrors "k8s.io/apimachinery/pkg/api/errors"
	"k8s.io/apimachinery/pkg/api/meta"
	"k8s.io/apimachinery/pkg/api/resource"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/util/intstr"
	"k8s.io/apimachinery/pkg/util/wait"
	"k8s.io/client-go/util/retry"
	"k8s.io/client-go/util/workqueue"
	ctrl "sigs.k8s.io/controller-runtime"
	"sigs.k8s.io/controller-runtime/pkg/client"
	crcontroller "sigs.k8s.io/controller-runtime/pkg/controller"
	"sigs.k8s.io/controller-runtime/pkg/reconcile"
)

const OwnerLabel = "lab.wiki.example/owner-uid"

var ErrForeignChild = errors.New("same-name child is not controlled by this AppService UID")
var ErrImmutableSelector = errors.New("owned Deployment has incompatible immutable selector")

// Reader is the uncached manager APIReader: retry reads must not reuse a stale informer object.
// Watches still drive requests through the real manager/cache/queue.
type Reconciler struct {
	Client client.Client
	Reader client.Reader
}

func (r *Reconciler) SetupWithManager(mgr ctrl.Manager) error {
	return ctrl.NewControllerManagedBy(mgr).Named("appservice").
		For(&labv1.AppService{}).Owns(&appsv1.Deployment{}).Owns(&corev1.Service{}).
		WithOptions(crcontroller.Options{MaxConcurrentReconciles: 1,
			RateLimiter: workqueue.NewTypedItemExponentialFailureRateLimiter[reconcile.Request](200*time.Millisecond, 10*time.Second)}).
		Complete(r)
}
func (r *Reconciler) Reconcile(ctx context.Context, req ctrl.Request) (ctrl.Result, error) {
	ctx, cancel := context.WithTimeout(ctx, 10*time.Second)
	defer cancel()
	a := &labv1.AppService{}
	if err := r.Reader.Get(ctx, req.NamespacedName, a); err != nil {
		return ctrl.Result{}, client.IgnoreNotFound(err)
	}
	if !a.DeletionTimestamp.IsZero() {
		return ctrl.Result{}, nil
	}
	dep, err := r.ensureDeployment(ctx, a)
	if err == nil {
		err = r.ensureService(ctx, a)
	}
	cond := readiness(a, dep)
	if err != nil {
		cond.Status = metav1.ConditionFalse
		cond.Reason = "ReconcileError"
		cond.Message = "Child reconciliation has not succeeded"
		if errors.Is(err, ErrForeignChild) {
			cond.Reason = "OwnershipConflict"
			cond.Message = ErrForeignChild.Error()
		}
		if errors.Is(err, ErrImmutableSelector) {
			cond.Reason = "InvalidChild"
			cond.Message = ErrImmutableSelector.Error()
		}
	}
	if statusErr := r.writeStatus(ctx, a, cond); statusErr != nil {
		return ctrl.Result{}, errors.Join(err, statusErr)
	}
	if errors.Is(err, ErrForeignChild) || errors.Is(err, ErrImmutableSelector) {
		return ctrl.Result{RequeueAfter: 10 * time.Second}, nil
	}
	return ctrl.Result{}, err
}
func replicas(a *labv1.AppService) int32 {
	if a.Spec.Replicas == nil {
		return 1
	}
	return *a.Spec.Replicas
}
func ptr[T any](v T) *T { return &v }
func labels(a *labv1.AppService) map[string]string {
	return map[string]string{OwnerLabel: string(a.UID)}
}
func owner(a *labv1.AppService) []metav1.OwnerReference {
	// Background owner GC suffices; false avoids needing permission to modify an owner's finalizers.
	return []metav1.OwnerReference{{APIVersion: labv1.GroupVersion.String(), Kind: "AppService", Name: a.Name, UID: a.UID, Controller: ptr(true), BlockOwnerDeletion: ptr(false)}}
}
func desiredContainer(a *labv1.AppService) corev1.Container {
	return corev1.Container{Name: "operand", Image: a.Spec.Image, ImagePullPolicy: corev1.PullNever,
		Ports:                  []corev1.ContainerPort{{Name: "http", ContainerPort: 8080, Protocol: corev1.ProtocolTCP}},
		Resources:              corev1.ResourceRequirements{Requests: corev1.ResourceList{corev1.ResourceCPU: resource.MustParse("20m"), corev1.ResourceMemory: resource.MustParse("16Mi")}, Limits: corev1.ResourceList{corev1.ResourceCPU: resource.MustParse("100m"), corev1.ResourceMemory: resource.MustParse("32Mi")}},
		SecurityContext:        &corev1.SecurityContext{AllowPrivilegeEscalation: ptr(false), ReadOnlyRootFilesystem: ptr(true), Capabilities: &corev1.Capabilities{Drop: []corev1.Capability{"ALL"}}},
		ReadinessProbe:         &corev1.Probe{ProbeHandler: corev1.ProbeHandler{HTTPGet: &corev1.HTTPGetAction{Path: "/readyz", Port: intstr.FromInt32(8080), Scheme: corev1.URISchemeHTTP}}, TimeoutSeconds: 1, PeriodSeconds: 2, SuccessThreshold: 1, FailureThreshold: 3},
		TerminationMessagePath: "/dev/termination-log", TerminationMessagePolicy: corev1.TerminationMessageReadFile,
	}
}
func mutateDeployment(a *labv1.AppService, d *appsv1.Deployment) error {
	selector := &metav1.LabelSelector{MatchLabels: labels(a)}
	if d.Spec.Selector != nil && !equality.Semantic.DeepEqual(d.Spec.Selector, selector) {
		return ErrImmutableSelector
	}
	d.Spec.Selector = selector
	d.Spec.Replicas = ptr(replicas(a))
	d.Spec.Template.Labels = labels(a)
	// Only this explicitly listed workload contract is managed. Preserve API/admission defaults
	// on other Pod/Deployment fields so defaults cannot create an update loop.
	d.Spec.Template.Spec.AutomountServiceAccountToken = ptr(false)
	d.Spec.Template.Spec.SecurityContext = &corev1.PodSecurityContext{RunAsNonRoot: ptr(true), RunAsUser: ptr(int64(65532)), SeccompProfile: &corev1.SeccompProfile{Type: corev1.SeccompProfileTypeRuntimeDefault}}
	d.Spec.Template.Spec.Containers = []corev1.Container{desiredContainer(a)}
	return nil
}
func mutateService(a *labv1.AppService, s *corev1.Service) {
	s.Spec.Type = corev1.ServiceTypeClusterIP
	s.Spec.Selector = labels(a)
	s.Spec.Ports = []corev1.ServicePort{{Name: "http", Port: 8080, TargetPort: intstr.FromInt32(8080), Protocol: corev1.ProtocolTCP}}
	// ClusterIP, ClusterIPs, IPFamilies, IPFamilyPolicy and API-assigned/default fields remain intact.
}
func (r *Reconciler) ensureDeployment(ctx context.Context, a *labv1.AppService) (*appsv1.Deployment, error) {
	d := &appsv1.Deployment{}
	err := r.Reader.Get(ctx, client.ObjectKeyFromObject(a), d)
	if apierrors.IsNotFound(err) {
		d = &appsv1.Deployment{ObjectMeta: metav1.ObjectMeta{Name: a.Name, Namespace: a.Namespace, OwnerReferences: owner(a)}}
		if err := mutateDeployment(a, d); err != nil {
			return nil, err
		}
		return d, r.Client.Create(ctx, d)
	}
	if err != nil {
		return nil, err
	}
	if !metav1.IsControlledBy(d, a) {
		return nil, fmt.Errorf("Deployment %s: %w", d.Name, ErrForeignChild)
	}
	before := d.DeepCopy()
	if err := mutateDeployment(a, d); err != nil {
		return d, err
	}
	if !equality.Semantic.DeepEqual(before.Spec, d.Spec) {
		if err := r.Client.Patch(ctx, d, client.MergeFromWithOptions(before, client.MergeFromWithOptimisticLock{})); err != nil {
			return d, err
		}
		// Never promote stale status from the old generation immediately after a spec write.
		d.Status = appsv1.DeploymentStatus{}
	}
	return d, nil
}
func (r *Reconciler) ensureService(ctx context.Context, a *labv1.AppService) error {
	s := &corev1.Service{}
	err := r.Reader.Get(ctx, client.ObjectKeyFromObject(a), s)
	if apierrors.IsNotFound(err) {
		s = &corev1.Service{ObjectMeta: metav1.ObjectMeta{Name: a.Name, Namespace: a.Namespace, OwnerReferences: owner(a)}}
		mutateService(a, s)
		return r.Client.Create(ctx, s)
	}
	if err != nil {
		return err
	}
	if !metav1.IsControlledBy(s, a) {
		return fmt.Errorf("Service %s: %w", s.Name, ErrForeignChild)
	}
	before := s.DeepCopy()
	mutateService(a, s)
	if equality.Semantic.DeepEqual(before.Spec, s.Spec) {
		return nil
	}
	return r.Client.Patch(ctx, s, client.MergeFromWithOptions(before, client.MergeFromWithOptimisticLock{}))
}
func readiness(a *labv1.AppService, d *appsv1.Deployment) metav1.Condition {
	c := metav1.Condition{Type: "Ready", Status: metav1.ConditionFalse, Reason: "Progressing", Message: "Waiting for current Deployment rollout", ObservedGeneration: a.Generation}
	n := replicas(a)
	if d == nil || !d.DeletionTimestamp.IsZero() || d.Generation == 0 || d.Status.ObservedGeneration < d.Generation || d.Spec.Replicas == nil || *d.Spec.Replicas != n || d.Status.UpdatedReplicas != n || d.Status.Replicas != n || d.Status.ReadyReplicas != n || d.Status.AvailableReplicas != n || d.Status.UnavailableReplicas != 0 {
		return c
	}
	for _, dc := range d.Status.Conditions {
		if dc.Type == appsv1.DeploymentAvailable && dc.Status == corev1.ConditionTrue {
			c.Status = metav1.ConditionTrue
			c.Reason = "DeploymentAvailable"
			c.Message = "Current Deployment reports all desired replicas updated, ready and available"
		}
	}
	return c
}
func (r *Reconciler) writeStatus(ctx context.Context, observed *labv1.AppService, cond metav1.Condition) error {
	return retry.RetryOnConflict(wait.Backoff{Steps: 3, Duration: 20 * time.Millisecond, Factor: 2, Jitter: .1}, func() error {
		current := &labv1.AppService{}
		if err := r.Reader.Get(ctx, client.ObjectKeyFromObject(observed), current); err != nil {
			return client.IgnoreNotFound(err)
		}
		if current.UID != observed.UID || current.Generation != observed.Generation || !current.DeletionTimestamp.IsZero() {
			return nil
		}
		before := current.DeepCopy()
		current.Status.ObservedGeneration = observed.Generation
		meta.SetStatusCondition(&current.Status.Conditions, cond)
		if equality.Semantic.DeepEqual(before.Status, current.Status) {
			return nil
		}
		return r.Client.Status().Patch(ctx, current, client.MergeFromWithOptions(before, client.MergeFromWithOptimisticLock{}))
	})
}
