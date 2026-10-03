// SPDX-License-Identifier: MIT
// Original teaching code, not an OpenJDK excerpt.
public final class Publication {
    static final class Box {
        int value;
        volatile boolean ready;
    }
    public static void publish(Box box) {
        box.value = 42;
        box.ready = true;
    }
    public static int readOnce(Box box) {
        if (box.ready) {
            return box.value;
        }
        return -1;
    }
}
