import java.util.ConcurrentModificationException;
import java.util.HashMap;
import java.util.Iterator;
import java.util.Map;
import java.util.Objects;

/** 本文的可见断言。默认只使用 API；实现观察需显式 --impl。没有反射或 --add-opens。 */
public class HashMapLab {
    record Key(String id, int rawHash) {
        @Override public int hashCode() { return rawHash; }
    }

    static final class MutableKey {
        int id;
        MutableKey(int id) { this.id = id; }
        @Override public int hashCode() { return id; }
        @Override public boolean equals(Object other) {
            return other instanceof MutableKey key && id == key.id;
        }
    }

    // 故意违约：equals 只看 id，hashCode 却可因 salt 而不同。
    static final class BrokenKey {
        final int id;
        final int salt;
        BrokenKey(int id, int salt) { this.id = id; this.salt = salt; }
        @Override public int hashCode() { return salt; }
        @Override public boolean equals(Object other) {
            return other instanceof BrokenKey key && id == key.id;
        }
    }

    static void check(boolean condition, String message) {
        if (!condition) throw new AssertionError("ASSERTION_FAILED: " + message);
    }
    static void equal(Object expected, Object actual, String message) {
        check(Objects.equals(expected, actual), message + " expected=" + expected + " actual=" + actual);
    }
    static int spread(int raw) { return raw ^ (raw >>> 16); }
    static int bucket(int spread, int capacity) { return spread & (capacity - 1); }

    static void identityAndCollision() {
        Map<Key, String> map = new HashMap<>(4);
        equal(null, map.put(new Key("A", 1), "a1"), "new key returns null");
        equal("a1", map.put(new Key("A", 1), "a2"), "equal key returns old value");
        equal(1, map.size(), "equal key must not add mapping");
        equal(null, map.put(new Key("X", 1), "x1"), "same hash different key adds mapping");
        equal(2, map.size(), "collision must not replace unequal key");
        equal("a2", map.get(new Key("A", 1)), "A survives collision");
        equal("x1", map.get(new Key("X", 1)), "X survives collision");
        System.out.println("API identity: equal key replaces; collision keeps both; size=2");
    }

    static void mainTraceAndBitModel() {
        Map<Key, String> map = new HashMap<>(4);
        Key[] keys = {new Key("A", 1), new Key("B", 5), new Key("C", 9), new Key("D", 13)};
        for (Key key : keys) map.put(key, key.id());
        equal(4, map.size(), "four mappings");
        for (Key key : keys) equal(key.id(), map.get(new Key(key.id(), key.rawHash())), "mapping retained");
        int[] expected8 = {1, 5, 1, 5};
        for (int i = 0; i < keys.length; i++) {
            int h = spread(keys[i].rawHash());
            equal(1, bucket(h, 4), "all four share old bucket in source-derived model");
            equal(expected8[i], bucket(h, 8), "new index follows extra bit");
        }
        equal(0x00010000, spread(0x00010001), "high bits fold down");
        equal(0, bucket(spread(0x00010001), 16), "spread changes low-bit index");
        equal(0, bucket(spread(-1), 16), "negative raw hash also gives valid index");
        System.out.println("API trace: A/B/C/D retained; model index4=1/1/1/1 index8=1/5/1/5");
    }

    static void brokenContract() {
        BrokenKey a = new BrokenKey(7, 1), b = new BrokenKey(7, 2);
        check(a.equals(b), "counterexample keys compare equal");
        check(a.hashCode() != b.hashCode(), "counterexample violates hash contract");
        Map<BrokenKey, String> map = new HashMap<>();
        map.put(a, "saved");
        equal(null, map.get(b), "fixed implementation misses equal key with different hash");
        System.out.println("COUNTEREXAMPLE broken contract: equals=true; different hashes; get(equal key)=null");
    }

    static void mutableKey() {
        Map<MutableKey, String> map = new HashMap<>();
        MutableKey key = new MutableKey(1);
        map.put(key, "saved");
        equal("saved", map.get(key), "before mutation");
        key.id = 2;
        equal(null, map.get(key), "same reference is searched using changed hash");
        equal(1, map.size(), "mapping still exists");
        equal("saved", map.entrySet().iterator().next().getValue(), "entry still holds value");
        key.id = 1; // 仅为了显示本例路径；这不是给真实系统的修复策略。
        equal("saved", map.get(key), "restoring id recovers this specific example");
        map.remove(key);
        key.id = 2;
        map.put(key, "saved");
        equal("saved", map.get(new MutableKey(2)), "remove before changing identity, then reinsert");
        System.out.println("COUNTEREXAMPLE mutable key: before=saved changed=null size=1 restored=saved");
    }

    static void nullAndUpdate() {
        Map<String, String> map = new HashMap<>();
        map.put("present", null);
        equal(null, map.get("present"), "null value");
        equal(null, map.get("absent"), "missing key");
        check(map.containsKey("present") && !map.containsKey("absent"), "containsKey distinguishes");
        map.put(null, "null-key");
        equal("null-key", map.get(null), "null key");
        equal("built", map.computeIfAbsent("present", k -> "built"), "null is computed");
        equal(null, map.computeIfAbsent("still-absent", k -> null), "null result not inserted");
        check(!map.containsKey("still-absent"), "null callback result leaves key absent");
        System.out.println("API null: containsKey distinguishes missing; computeIfAbsent fills null value");
    }

    static void iteration() {
        Map<Integer, String> map = new HashMap<>();
        map.put(1, "one");
        map.put(2, "two");
        Iterator<Map.Entry<Integer, String>> iterator = map.entrySet().iterator();
        map.put(3, "three");
        boolean threw = false;
        try { iterator.next(); }
        catch (ConcurrentModificationException expected) { threw = true; }
        check(threw, "fixed same-thread structural mutation is detected at next");
        Iterator<Map.Entry<Integer, String>> safe = map.entrySet().iterator();
        while (safe.hasNext()) {
            Map.Entry<Integer, String> entry = safe.next();
            if (entry.getKey() == 2) safe.remove();
            else entry.setValue(entry.getValue().toUpperCase());
        }
        equal(2, map.size(), "iterator remove");
        equal("ONE", map.get(1), "entry setValue");
        check(!map.containsKey(2), "removed target");
        equal("THREE", map.get(3), "other entry updated");
        System.out.println("API iteration: same-thread misuse throws; iterator.remove and entry.setValue work");
    }

    static void presizing() {
        Map<Integer, Integer> map = HashMap.newHashMap(13);
        for (int i = 0; i < 13; i++) map.put(i, i * i);
        equal(13, map.size(), "expected mapping count factory");
        for (int i = 0; i < 13; i++) equal(i * i, map.get(i), "factory retains data");
        System.out.println("API sizing: newHashMap(13) stores 13 mappings; internal capacity not measured");
    }

    // 接口返回的是 Map.Entry；具体类名只是本次 OpenJDK 的实现观察，不是 API 保证。
    static String entryKind(Map<Key, Integer> map, Key key) {
        return map.entrySet().stream().filter(e -> e.getKey().equals(key)).findFirst().orElseThrow()
                .getClass().getName();
    }
    static void kind(String expectedSuffix, Map<Key, Integer> map, Key key) {
        equal("java.util.HashMap$" + expectedSuffix, entryKind(map, key), "entry implementation");
    }
    static Key collision(int i) { return new Key("K" + i, 0); }

    static void implPutThreshold() {
        Map<Key, Integer> map = new HashMap<>(64);
        for (int i = 1; i <= 8; i++) equal(null, map.put(collision(i), i), "new collision key has no old value");
        equal(8, map.size(), "eight mappings before update");
        for (int i = 1; i <= 8; i++) equal(i, map.get(collision(i)), "pre-tree mapping value");
        kind("Node", map, collision(1));
        equal(1, map.put(collision(1), 100), "update existing collision key");
        kind("Node", map, collision(1));
        equal(8, map.size(), "update does not count as insertion");
        equal(null, map.put(collision(9), 9), "ninth key has no old value");
        equal(9, map.size(), "ninth distinct key adds one mapping");
        for (int i = 1; i <= 9; i++) kind("TreeNode", map, collision(i));
        for (int i = 2; i <= 9; i++) equal(i, map.get(collision(i)), "tree lookup");
        equal(100, map.get(collision(1)), "updated value retained");
        System.out.println("IMPL put capacity-request=64: after 8=Node; update=Node; after 9=TreeNode");
    }

    static void implDefaultGrowth() {
        Map<Key, Integer> map = new HashMap<>();
        for (int i = 1; i <= 11; i++) {
            equal(null, map.put(collision(i), i), "default growth adds new key");
            equal(i, map.size(), "default growth mapping count");
            if (i == 8 || i == 9 || i == 10) kind("Node", map, collision(1));
        }
        for (int i = 1; i <= 11; i++) {
            kind("TreeNode", map, collision(i));
            equal(i, map.get(collision(i)), "default growth retains mappings");
        }
        System.out.println("IMPL default put: after 8/9/10=Node; after 11=TreeNode; capacities inferred from source only");
    }

    static void implComputeThreshold() {
        Map<Key, Integer> map = new HashMap<>(64);
        for (int i = 1; i <= 7; i++) equal(null, map.put(collision(i), i), "compute fixture adds distinct key");
        equal(7, map.size(), "compute fixture has seven mappings");
        for (int i = 1; i <= 7; i++) {
            kind("Node", map, collision(i));
            equal(i, map.get(collision(i)), "compute fixture preserves prior value");
        }
        Integer result = map.computeIfAbsent(collision(8), k -> 8);
        equal(8, result, "computeIfAbsent returns independently expected eighth value");
        equal(8, map.size(), "computeIfAbsent adds exactly one mapping");
        for (int i = 1; i <= 8; i++) {
            kind("TreeNode", map, collision(i));
            equal(i, map.get(collision(i)), "compute treeification preserves every expected value");
        }
        System.out.println("IMPL computeIfAbsent capacity-request=64: 7 existing -> insert 8 -> TreeNode");
    }

    static void implTreeSplit() {
        Map<Key, Integer> map = new HashMap<>(64);
        for (int i = 1; i <= 6; i++) equal(null, map.put(new Key("L" + i, 0), i), "low fixture new key");
        for (int i = 1; i <= 7; i++) equal(null, map.put(new Key("H" + i, 64), i), "high fixture new key");
        equal(13, map.size(), "tree split starts with thirteen mappings");
        for (int i = 1; i <= 6; i++) {
            Key key = new Key("L" + i, 0);
            kind("TreeNode", map, key); equal(i, map.get(key), "low mapping before split");
        }
        for (int i = 1; i <= 7; i++) {
            Key key = new Key("H" + i, 64);
            kind("TreeNode", map, key); equal(i, map.get(key), "high mapping before split");
        }
        for (int i = 1; i <= 36; i++) equal(null, map.put(new Key("F" + i, i), i), "filler is a new key");
        equal(49, map.size(), "49 mappings exceed 64*0.75 in source-derived model");
        for (int i = 1; i <= 6; i++) {
            Key key = new Key("L" + i, 0);
            kind("Node", map, key); equal(i, map.get(key), "low split mapping");
        }
        for (int i = 1; i <= 7; i++) {
            Key key = new Key("H" + i, 64);
            kind("TreeNode", map, key); equal(i, map.get(key), "high split mapping");
        }
        for (int i = 1; i <= 36; i++) {
            Key key = new Key("F" + i, i);
            kind("Node", map, key); equal(i, map.get(key), "filler mapping");
        }
        System.out.println("IMPL resize split: before=TreeNode; low 6=Node; high 7=TreeNode; size=49");
    }

    static void negative(String name) {
        switch (name) {
            case "equal-adds" -> {
                Map<Key, String> map = new HashMap<>();
                map.put(new Key("A", 1), "a1"); map.put(new Key("A", 1), "a2");
                equal(2, map.size(), "wrong hypothesis equal-adds");
            }
            case "collision-overwrites" -> {
                Map<Key, String> map = new HashMap<>();
                map.put(new Key("A", 1), "a"); map.put(new Key("X", 1), "x");
                equal(1, map.size(), "wrong hypothesis collision-overwrites");
            }
            case "mutable-stays-readable" -> {
                Map<MutableKey, String> map = new HashMap<>();
                MutableKey key = new MutableKey(1); map.put(key, "saved"); key.id = 2;
                equal("saved", map.get(key), "wrong hypothesis mutable-stays-readable");
            }
            case "eighth-put-tree" -> {
                Map<Key, Integer> map = new HashMap<>(64);
                for (int i = 1; i <= 8; i++) map.put(collision(i), i);
                check(entryKind(map, collision(1)).endsWith("$TreeNode"), "wrong hypothesis eighth-put-tree");
            }
            case "resize-keeps-every-index" ->
                equal(bucket(spread(5), 4), bucket(spread(5), 8), "wrong hypothesis resize-keeps-every-index");
            default -> throw new IllegalArgumentException("Unknown negative test: " + name);
        }
        throw new IllegalStateException("Negative hypothesis unexpectedly survived: " + name);
    }

    public static void main(String[] args) {
        if (Runtime.version().feature() != 21) throw new IllegalStateException("Requires JDK 21");
        if (args.length == 0 || args[0].equals("--api")) {
            identityAndCollision(); mainTraceAndBitModel(); brokenContract(); mutableKey();
            nullAndUpdate(); iteration(); presizing(); System.out.println("PASS api scenarios=7");
        } else if (args[0].equals("--impl")) {
            implPutThreshold(); implDefaultGrowth(); implComputeThreshold(); implTreeSplit();
            System.out.println("PASS implementation observations=4 (not an API guarantee)");
        } else if (args[0].equals("--negative") && args.length == 2) negative(args[1]);
        else throw new IllegalArgumentException("Usage: --api | --impl | --negative NAME");
    }
}
