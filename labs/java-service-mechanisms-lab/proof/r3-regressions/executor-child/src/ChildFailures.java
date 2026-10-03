// SPDX-License-Identifier: MIT
import java.util.*;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.concurrent.atomic.AtomicInteger;

/** Original teaching harness: ended workers may have failed; primary failure wins. */
public final class ChildFailures {
    record Failure(String thread, Throwable cause) { }
    private final List<Failure> failures = new ArrayList<>();
    private final Set<Throwable> recorded = Collections.newSetFromMap(new IdentityHashMap<>());
    private final List<Thread> threads = new CopyOnWriteArrayList<>();
    private final AtomicInteger next = new AtomicInteger();
    public synchronized void record(Throwable cause) {
        if (recorded.add(cause)) failures.add(new Failure(Thread.currentThread().getName(), cause));
    }
    public Thread thread(Runnable task, String name) {
        return track(new Thread(() -> {
            try { task.run(); }
            catch (Throwable cause) { record(cause); }
        }, name));
    }
    public Thread track(Thread thread) { threads.add(thread); return thread; }
    public Thread worker(Runnable task) { return thread(task, "ordinary-worker-" + next.incrementAndGet()); }
    public void joinAll() throws InterruptedException {
        for (Thread thread : threads) {
            thread.join(3000);
            if (thread.isAlive()) throw new AssertionError("child did not terminate: " + thread.getName());
        }
    }
    static boolean contains(Throwable graph, Throwable target) {
        if (graph == null) return false;
        Set<Throwable> seen = Collections.newSetFromMap(new IdentityHashMap<>());
        ArrayDeque<Throwable> todo = new ArrayDeque<>(); todo.add(graph);
        while (!todo.isEmpty()) {
            Throwable next = todo.remove();
            if (next == target) return true;
            if (!seen.add(next)) continue;
            if (next.getCause() != null) todo.add(next.getCause());
            Collections.addAll(todo, next.getSuppressed());
        }
        return false;
    }
    public static Throwable append(Throwable primary, Throwable extra) {
        if (primary == null) return extra;
        if (extra != null && !contains(primary, extra) && !contains(extra, primary)) primary.addSuppressed(extra);
        return primary;
    }
    public synchronized Throwable mergeInto(Throwable primary) {
        for (Failure failure : failures) {
            if (contains(primary, failure.cause())) continue;
            AssertionError child = new AssertionError("UNEXPECTED_CHILD_FAILURE thread=" + failure.thread(), failure.cause());
            primary = append(primary, child);
        }
        failures.clear();
        return primary;
    }
    public Throwable finish(Throwable primary, String cleanupMarker) {
        try { joinAll(); System.out.println(cleanupMarker); }
        catch (Throwable cleanup) { primary = append(primary, cleanup); }
        return mergeInto(primary);
    }
    public static void rethrow(Throwable failure) throws Exception {
        if (failure instanceof Error error) throw error;
        if (failure instanceof Exception exception) throw exception;
        if (failure != null) throw new AssertionError(failure);
    }
}
