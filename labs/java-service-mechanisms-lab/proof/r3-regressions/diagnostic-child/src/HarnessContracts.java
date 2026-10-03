// SPDX-License-Identifier: MIT
import java.io.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;

/** Deterministic checks of cleanup ownership and failure identity, not stress repetitions. */
public final class HarnessContracts {
    static void require(boolean ok, String message) { if (!ok) throw new AssertionError(message); }
    static final class ObservedPool extends ThreadPoolExecutor {
        final AtomicInteger forceCalls = new AtomicInteger();
        ObservedPool(ChildFailures children) { super(1, 1, 1, TimeUnit.SECONDS, new ArrayBlockingQueue<>(1), children::worker); }
        @Override public List<Runnable> shutdownNow() { forceCalls.incrementAndGet(); return super.shutdownNow(); }
    }
    static String trace(Throwable failure) {
        StringWriter out = new StringWriter(); failure.printStackTrace(new PrintWriter(out)); return out.toString();
    }
    static void failureIdentity() {
        ChildFailures duplicates = new ChildFailures();
        IllegalStateException same = new IllegalStateException("SAME_CHILD");
        duplicates.record(same); duplicates.record(same);
        Throwable only = duplicates.mergeInto(null);
        require(only.getCause() == same && only.getSuppressed().length == 0, "IDENTITY_DEDUP failed");
        require(!trace(only).contains("CIRCULAR REFERENCE"), "IDENTITY_DEDUP circular cause");
        ChildFailures distinct = new ChildFailures();
        IllegalArgumentException other = new IllegalArgumentException("OTHER_CHILD");
        distinct.record(same); distinct.record(other);
        AssertionError primary = new AssertionError("PRIMARY_CLAIM");
        Throwable merged = distinct.mergeInto(primary);
        require(merged == primary && merged.getSuppressed().length == 2, "PRIMARY_AND_DISTINCT failed");
        require(merged.getSuppressed()[0].getCause() == same && merged.getSuppressed()[1].getCause() == other, "distinct cause identity lost");
        require(!trace(merged).contains("CIRCULAR REFERENCE"), "distinct exceptions became circular");
        ChildFailures already = new ChildFailures(); already.record(same);
        AssertionError existing = new AssertionError("MAIN_WITH_CAUSE", same);
        require(already.mergeInto(existing) == existing && existing.getSuppressed().length == 0, "existing cause duplicated");
        System.out.println("FAILURE_IDENTITY same Throwable once; distinct children retained; primary preserved");
    }
    static void cleanup(boolean forceTimeout) throws Exception {
        ChildFailures children = new ChildFailures();
        ObservedPool pool = new ObservedPool(children);
        CountDownLatch started = new CountDownLatch(1), release = new CountDownLatch(1);
        AtomicBoolean finished = new AtomicBoolean(), interrupted = new AtomicBoolean();
        pool.execute(() -> {
            started.countDown();
            try { release.await(); }
            catch (InterruptedException expectedOnlyOnForce) { interrupted.set(true); Thread.currentThread().interrupt(); }
            finished.set(true);
        });
        AssertionError primary = new AssertionError("CLEANUP_PRIMARY");
        Throwable caught = null;
        try (PoolCleanup cleanup = new PoolCleanup(pool, forceTimeout ? null : release)) {
            require(started.await(2, TimeUnit.SECONDS), "worker startup deadline");
            throw primary;
        } catch (Throwable failure) { caught = failure; }
        children.joinAll();
        caught = children.mergeInto(caught);
        require(caught == primary, "cleanup replaced primary");
        require(finished.get() && pool.isTerminated(), "cleanup incomplete");
        if (forceTimeout) {
            require(pool.forceCalls.get() == 1 && interrupted.get(), "forced cleanup missing");
            require(primary.getSuppressed().length == 1 && primary.getSuppressed()[0].getMessage().startsWith("POOL_ORDERLY_CLEANUP_TIMEOUT"), "forced timeout was not reported");
            System.out.println("FORCED_CLEANUP bounded timeout recorded as suppressed; worker ended");
        } else {
            require(pool.forceCalls.get() == 0 && !interrupted.get(), "COOPERATIVE_CLEANUP used shutdownNow");
            require(primary.getSuppressed().length == 0, "cooperative cleanup invented error");
            System.out.println("COOPERATIVE_CLEANUP release then shutdown then await; no shutdownNow or interrupt");
        }
    }
    public static void main(String[] args) throws Exception {
        failureIdentity(); cleanup(false); cleanup(true);
        System.out.println("HARNESS_CONTRACTS_OK");
    }
}
