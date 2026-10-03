// SPDX-License-Identifier: MIT
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;

public final class JmmLab {
    static volatile int counter;
    static final ChildFailures children = new ChildFailures();
    static void require(boolean b, String message) {
        if (!b) throw new AssertionError(message);
    }
    static void join(Thread t) throws Exception {
        t.join(3000);
        require(!t.isAlive(), "worker did not end: " + t.getName());
    }
    static void publication() throws Exception {
        Publication.Box box = new Publication.Box();
        AtomicInteger seen = new AtomicInteger(-1);
        Thread reader = children.thread(() -> {
            long end = System.nanoTime() + TimeUnit.SECONDS.toNanos(2);
            int value;
            do { value = Publication.readOnce(box); }
            while (value == -1 && System.nanoTime() < end);
            seen.set(value);
        }, "publication-reader");
        reader.start();
        Publication.publish(box);
        join(reader);
        require(seen.get() == 42, "PUBLICATION_VALUE expected 42 got " + seen.get());
        System.out.println("publication observed=42; guarantee comes from JLS, not this run");
    }
    static int splitIncrement() throws Exception {
        counter = 0;
        CyclicBarrier bothRead = new CyclicBarrier(2);
        AtomicReference<Throwable> failure = new AtomicReference<>();
        Runnable task = () -> {
            try {
                int previous = counter;
                bothRead.await(2, TimeUnit.SECONDS);
                counter = previous + 1;
            } catch (Throwable e) { failure.compareAndSet(null, e); }
        };
        Thread a = children.thread(task, "split-a");
        Thread b = children.thread(task, "split-b");
        a.start(); b.start(); join(a); join(b);
        if (failure.get() != null) throw new AssertionError("barrier failure", failure.get());
        return counter;
    }
    static void atomicIncrement() throws Exception {
        AtomicInteger total = new AtomicInteger();
        Thread a = children.thread(() -> { total.incrementAndGet(); throw new IllegalStateException("REVIEWER_CHILD_ATOMIC_FAILURE"); }, "atomic-a");
        Thread b = children.thread(total::incrementAndGet, "atomic-b");
        a.start(); b.start(); join(a); join(b);
        require(total.get() == 2, "ATOMIC_TOTAL");
        System.out.println("atomic increment result=2");
    }
    public static void main(String[] args) throws Exception {
        Throwable primary = null;
        boolean negative = args.length == 1 && args[0].equals("wrong-volatile-is-atomic");
        try {
            if (negative) {
                int result = splitIncrement();
                require(result == 2, "VOLATILE_COMPOUND_CLAIM expected=2 actual=" + result);
            } else {
                publication();
                require(splitIncrement() == 1, "controlled lost update missing");
                System.out.println("volatile split read-modify-write result=1; both readers saw 0");
                atomicIncrement();
            }
        } catch (Throwable failure) { primary = failure; }
        primary = children.finish(primary, "JMM_CLEANUP all workers joined");
        ChildFailures.rethrow(primary);
        if (!negative) System.out.println("JMM_OK");
    }
}
