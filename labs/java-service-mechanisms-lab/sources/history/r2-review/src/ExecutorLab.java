// SPDX-License-Identifier: MIT
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;

public final class ExecutorLab {
    static final ChildFailures children = new ChildFailures();
    static void require(boolean b, String message) {
        if (!b) throw new AssertionError(message);
    }
    static void await(CountDownLatch latch) {
        try { require(latch.await(3, TimeUnit.SECONDS), "latch deadline"); }
        catch (InterruptedException e) { Thread.currentThread().interrupt(); throw new AssertionError(e); }
    }
    static void finish(ThreadPoolExecutor p) throws Exception {
        p.shutdownNow();
        require(p.awaitTermination(3, TimeUnit.SECONDS), "pool did not terminate");
    }
    static ThreadPoolExecutor pool(int core, int max, BlockingQueue<Runnable> q) {
        return new ThreadPoolExecutor(core, max, 1, TimeUnit.SECONDS, q, children::worker, new ThreadPoolExecutor.AbortPolicy()) {
            @Override protected void afterExecute(Runnable task, Throwable error) {
                if (error != null) children.record(error);
                else if (task instanceof Future<?> future && future.isDone() && !future.isCancelled()) {
                    try { future.get(); }
                    catch (ExecutionException e) { children.record(e.getCause()); }
                    catch (InterruptedException e) { Thread.currentThread().interrupt(); children.record(e); }
                }
            }
        };
    }
    static void admission(boolean wrongMaxFirst) throws Exception {
        ThreadPoolExecutor p = pool(1, 2, new ArrayBlockingQueue<>(1));
        CountDownLatch aStarted = new CountDownLatch(1), cStarted = new CountDownLatch(1);
        CountDownLatch release = new CountDownLatch(1);
        List<String> done = Collections.synchronizedList(new ArrayList<>());
        try {
            p.execute(() -> { aStarted.countDown(); await(release); done.add("A"); });
            await(aStarted);
            Runnable b = () -> done.add("B");
            p.execute(b);
            require(p.getPoolSize() == 1 && p.getQueue().contains(b), "B should queue before max expansion");
            if (wrongMaxFirst) require(p.getPoolSize() == 2, "MAX_FIRST_CLAIM expected=2 actual=" + p.getPoolSize());
            p.execute(() -> { cStarted.countDown(); await(release); done.add("C"); });
            await(cStarted);
            require(p.getPoolSize() == 2 && p.getQueue().size() == 1, "A/C running B queued");
            AtomicBoolean dRan = new AtomicBoolean();
            try { p.execute(() -> dRan.set(true)); throw new AssertionError("D accepted"); }
            catch (RejectedExecutionException expected) { }
            require(!dRan.get(), "rejected D ran");
            p.shutdown();
            require(!p.isTerminated(), "shutdown is not join");
            try { p.execute(() -> done.add("E")); throw new AssertionError("E accepted after shutdown"); }
            catch (RejectedExecutionException expected) { }
            release.countDown();
            require(p.awaitTermination(3, TimeUnit.SECONDS), "orderly termination");
            require(done.size() == 3 && new HashSet<>(done).equals(Set.of("A", "B", "C")), "accepted work exactly once: " + done);
            System.out.println("admission A=worker B=queue C=worker D=rejected; shutdown drained A/B/C exactly once");
        } finally { release.countDown(); finish(p); }
    }
    static void exceptions() throws Exception {
        List<String> hooks = Collections.synchronizedList(new ArrayList<>());
        CountDownLatch uncaught = new CountDownLatch(1), after = new CountDownLatch(2);
        AtomicReference<Throwable> uncaughtFailure = new AtomicReference<>();
        AtomicInteger expectedUncaught = new AtomicInteger();
        ThreadFactory factory = r -> {
            Thread t = new Thread(r, "exception-worker");
            t.setUncaughtExceptionHandler((thread, error) -> {
                if (error instanceof IllegalArgumentException && "execute-boom".equals(error.getMessage()) && expectedUncaught.incrementAndGet() == 1) {
                    uncaughtFailure.set(error);
                } else children.record(error);
                uncaught.countDown();
            });
            return children.track(t);
        };
        ThreadPoolExecutor p = new ThreadPoolExecutor(1, 1, 1, TimeUnit.SECONDS, new ArrayBlockingQueue<>(2), factory) {
            @Override protected void afterExecute(Runnable r, Throwable t) {
                hooks.add(t == null ? "null" : t.getClass().getSimpleName() + ":" + t.getMessage());
                after.countDown();
            }
        };
        try {
            p.execute(() -> { throw new IllegalArgumentException("execute-boom"); });
            await(uncaught);
            require(uncaughtFailure.get() instanceof IllegalArgumentException && "execute-boom".equals(uncaughtFailure.get().getMessage()), "wrong uncaught failure");
            Future<?> f = p.submit(() -> { throw new IllegalStateException("submit-boom"); });
            try { f.get(3, TimeUnit.SECONDS); throw new AssertionError("submit exception lost"); }
            catch (ExecutionException e) {
                if (!(e.getCause() instanceof IllegalStateException && "submit-boom".equals(e.getCause().getMessage())))
                    throw new AssertionError("wrong Future cause", e.getCause());
            }
            await(after);
            require(hooks.equals(List.of("IllegalArgumentException:execute-boom", "null")), "afterExecute: " + hooks);
            require(expectedUncaught.get() == 1, "expected uncaught exception count");
            System.out.println("execute exception=uncaught+hook; submit exception=Future.get cause; submit hook Throwable=null");
        } finally { finish(p); }
    }
    static void shutdownNowOwnership(boolean wrongFutureDone) throws Exception {
        ThreadPoolExecutor p = pool(1, 1, new ArrayBlockingQueue<>(1));
        CountDownLatch started = new CountDownLatch(1), release = new CountDownLatch(1), interrupted = new CountDownLatch(1);
        AtomicBoolean queuedRan = new AtomicBoolean();
        try {
            p.execute(() -> { started.countDown(); try { release.await(); } catch (InterruptedException e) { interrupted.countDown(); Thread.currentThread().interrupt(); } });
            await(started);
            Future<?> queued = p.submit(() -> queuedRan.set(true));
            List<Runnable> returned = p.shutdownNow();
            await(interrupted);
            require(returned.size() == 1 && returned.get(0) == queued, "returned wrapper identity");
            require(!queuedRan.get() && !queued.isDone(), "drained Future must still be pending here");
            if (wrongFutureDone) require(queued.isDone(), "DRAIN_CANCEL_CLAIM Future remained NEW");
            require(queued.cancel(false) && queued.isCancelled(), "owner cancellation");
            require(p.awaitTermination(3, TimeUnit.SECONDS), "shutdownNow termination");
            System.out.println("shutdownNow interrupted running task; returned exact queued FutureTask; owner cancelled pending Future");
        } finally { release.countDown(); finish(p); }
    }
    static final class PausingQueue extends ArrayBlockingQueue<Runnable> {
        final CountDownLatch offered = new CountDownLatch(1), resume = new CountDownLatch(1);
        PausingQueue() { super(1); }
        @Override public boolean offer(Runnable task) {
            boolean ok = super.offer(task);
            offered.countDown();
            await(resume);
            return ok;
        }
    }
    static void shutdownOfferRace() throws Exception {
        PausingQueue q = new PausingQueue();
        ThreadPoolExecutor p = pool(0, 1, q);
        AtomicBoolean ran = new AtomicBoolean();
        AtomicReference<Throwable> result = new AtomicReference<>();
        Thread submitter = children.thread(() -> {
            try { p.execute(() -> ran.set(true)); }
            catch (Throwable t) { result.set(t); }
        }, "race-submitter");
        try {
            submitter.start(); await(q.offered);
            p.shutdown(); q.resume.countDown();
            submitter.join(3000);
            require(!submitter.isAlive(), "submitter did not return");
            require(result.get() instanceof RejectedExecutionException && !ran.get() && q.isEmpty(), "recheck did not remove+reject: " + result.get());
            require(p.awaitTermination(3, TimeUnit.SECONDS), "race pool termination");
            System.out.println("offer/shutdown race: offered then shutdown then recheck removed+rejected; task never ran");
        } finally { q.resume.countDown(); finish(p); submitter.join(3000); }
    }
    public static void main(String[] args) throws Exception {
        try {
            if (args.length == 1 && args[0].equals("wrong-max-first")) { admission(true); return; }
            if (args.length == 1 && args[0].equals("wrong-drain-cancels")) { shutdownNowOwnership(true); return; }
            admission(false); exceptions(); shutdownNowOwnership(false); shutdownOfferRace();
        } finally {
            children.joinAll();
            System.out.println("EXECUTOR_CLEANUP ordinary workers joined; scenario pools terminated");
            children.throwIfAny();
        }
        System.out.println("EXECUTOR_OK");
    }
}
