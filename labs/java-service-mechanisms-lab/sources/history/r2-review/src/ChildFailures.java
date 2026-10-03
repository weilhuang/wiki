// SPDX-License-Identifier: MIT
import java.util.List;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.concurrent.ConcurrentLinkedQueue;
import java.util.concurrent.atomic.AtomicInteger;

/** Original teaching harness: successful join does not imply successful work. */
public final class ChildFailures {
    record Failure(String thread, Throwable cause) { }
    private final ConcurrentLinkedQueue<Failure> failures = new ConcurrentLinkedQueue<>();
    private final List<Thread> threads = new CopyOnWriteArrayList<>();
    private final AtomicInteger next = new AtomicInteger();
    public void record(Throwable cause) {
        failures.add(new Failure(Thread.currentThread().getName(), cause));
    }
    public Thread thread(Runnable task, String name) {
        Thread thread = new Thread(() -> {
            try { task.run(); }
            catch (Throwable cause) { record(cause); }
        }, name);
        return track(thread);
    }
    public Thread track(Thread thread) {
        threads.add(thread);
        return thread;
    }
    public Thread worker(Runnable task) {
        return thread(task, "ordinary-worker-" + next.incrementAndGet());
    }
    public void joinAll() throws InterruptedException {
        for (Thread thread : threads) {
            thread.join(3000);
            if (thread.isAlive()) throw new AssertionError("child did not terminate: " + thread.getName());
        }
    }
    public void throwIfAny() {
        Failure first = failures.poll();
        if (first == null) return;
        AssertionError error = new AssertionError("UNEXPECTED_CHILD_FAILURE thread=" + first.thread(), first.cause());
        for (Failure extra; (extra = failures.poll()) != null;) error.addSuppressed(extra.cause());
        throw error;
    }
}
