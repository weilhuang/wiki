// SPDX-License-Identifier: MIT
import java.util.concurrent.*;

/** Release cooperative work, then wait orderly; forced cleanup is itself a failure. */
public final class PoolCleanup implements AutoCloseable {
    private final ThreadPoolExecutor pool;
    private final CountDownLatch release;
    public PoolCleanup(ThreadPoolExecutor pool, CountDownLatch release) {
        this.pool = pool; this.release = release;
    }
    @Override public void close() throws Exception {
        if (release != null) release.countDown();
        pool.shutdown();
        try {
            if (pool.awaitTermination(3, TimeUnit.SECONDS)) return;
            int returned = pool.shutdownNow().size();
            boolean ended = pool.awaitTermination(3, TimeUnit.SECONDS);
            throw new AssertionError("POOL_ORDERLY_CLEANUP_TIMEOUT forcedStop=true ended=" + ended + " returned=" + returned);
        } catch (InterruptedException primary) {
            pool.shutdownNow();
            try {
                if (!pool.awaitTermination(3, TimeUnit.SECONDS)) primary.addSuppressed(new AssertionError("pool alive after interrupted cleanup"));
            } catch (InterruptedException cleanup) { primary.addSuppressed(cleanup); }
            Thread.currentThread().interrupt();
            throw primary;
        }
    }
}
