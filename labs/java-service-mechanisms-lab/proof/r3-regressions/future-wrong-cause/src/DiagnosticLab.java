// SPDX-License-Identifier: MIT
import java.io.*;
import java.lang.management.*;
import java.util.*;
import java.util.concurrent.*;

public final class DiagnosticLab {
    static final ChildFailures children = new ChildFailures();
    static final Object monitor = new Object();
    static final CountDownLatch held = new CountDownLatch(1), release = new CountDownLatch(1);
    static volatile boolean running = true;
    static volatile long checksum;
    static volatile byte[][] retained;
    static void awaitRelease() {
        try { release.await(); } catch (InterruptedException e) { Thread.currentThread().interrupt(); }
    }
    static void busy() {
        long value = 1;
        while (running) value = value * 1664525L + 1013904223L;
        checksum = value;
    }
    static void allocate() {
        byte[][] ring = new byte[16][];
        for (int i = 0; i < 2048; i++) {
            byte[] block = new byte[128 * 1024];
            block[0] = (byte) i;
            ring[i % ring.length] = block;
        }
        retained = ring;
        System.out.println("ALLOCATED payloadBytes=268435456 retainedSlots=16");
    }
    static void snapshot(ThreadMXBean bean) {
        for (ThreadInfo info : bean.dumpAllThreads(true, true)) {
            if (!info.getThreadName().startsWith("lab-")) continue;
            System.out.println("SNAPSHOT name=" + info.getThreadName() + " state=" + info.getThreadState() + " lock=" + info.getLockName() + " owner=" + info.getLockOwnerName());
            for (StackTraceElement frame : info.getStackTrace()) System.out.println("    at " + frame);
            for (MonitorInfo lock : info.getLockedMonitors()) System.out.println("    locked monitor " + lock + " at " + lock.getLockedStackFrame());
            for (LockInfo lock : info.getLockedSynchronizers()) System.out.println("    locked synchronizer " + lock);
        }
        System.out.println("SNAPSHOT_END");
    }
    static void awaitState(Thread t, Thread.State wanted) {
        long end = System.nanoTime() + TimeUnit.SECONDS.toNanos(2);
        while (t.getState() != wanted && System.nanoTime() < end) Thread.onSpinWait();
        if (t.getState() != wanted) throw new AssertionError(t.getName() + " did not enter " + wanted);
    }
    public static void main(String[] args) throws Exception {
        Thread busy = children.thread(DiagnosticLab::busy, "lab-cpu-busy");
        Thread holder = children.thread(() -> { synchronized (monitor) { held.countDown(); awaitRelease(); } }, "lab-monitor-holder");
        Thread blocked = children.thread(() -> { synchronized (monitor) { checksum ^= 17; } }, "lab-monitor-blocked");
        Thread parked = children.thread(DiagnosticLab::awaitRelease, "lab-latch-waiter");
        Thread watchdog = children.thread(() -> {
            try {
                if (!release.await(12, TimeUnit.SECONDS)) {
                    System.err.println("WATCHDOG deadline"); running = false; release.countDown(); System.exit(90);
                }
            } catch (InterruptedException e) { Thread.currentThread().interrupt(); }
        }, "lab-watchdog");
        watchdog.setDaemon(true);
        Throwable primary = null;
        try {
        watchdog.start();
        holder.start();
        if (!held.await(2, TimeUnit.SECONDS)) throw new AssertionError("monitor not acquired");
        blocked.start(); parked.start(); busy.start();
        awaitState(blocked, Thread.State.BLOCKED); awaitState(parked, Thread.State.WAITING);
        ThreadMXBean bean = ManagementFactory.getThreadMXBean();
        if (!bean.isThreadCpuTimeSupported()) throw new AssertionError("CPU time unsupported");
        if (!bean.isThreadCpuTimeEnabled()) bean.setThreadCpuTimeEnabled(true);
        List<Thread> threads = List.of(busy, holder, blocked, parked);
        long[] before = threads.stream().mapToLong(t -> bean.getThreadCpuTime(t.threadId())).toArray();
        System.out.println("READY cpu=RUNNABLE blocked=BLOCKED latch=WAITING");
        try (BufferedReader in = new BufferedReader(new InputStreamReader(System.in))) {
            String command;
            while ((command = in.readLine()) != null) {
                if (command.equals("allocate")) { allocate(); }
                else if (command.equals("snapshot")) { snapshot(bean); }
                else if (command.equals("sample")) {
                    for (int i = 0; i < threads.size(); i++) {
                        Thread t = threads.get(i);
                        long delta = bean.getThreadCpuTime(t.threadId()) - before[i];
                        System.out.println("CPU " + t.getName() + " state=" + t.getState() + " deltaNs=" + delta);
                    }
                    System.out.println("SAMPLED");
                } else if (command.equals("stop")) { break; }
                else throw new AssertionError("unknown command " + command);
            }
        }
        } catch (Throwable failure) { primary = failure; }
        running = false; release.countDown();
        primary = children.finish(primary, "CLEANUP all four workers joined; watchdog joined");
        ChildFailures.rethrow(primary);
        System.out.println("DIAGNOSTIC_OK");
    }
}
