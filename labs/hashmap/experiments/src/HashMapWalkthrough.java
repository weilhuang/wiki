import java.util.HashMap;
import java.util.Map;

public class HashMapWalkthrough {
    // 人为控制散列值；两个分量都参与 record 的 equals。
    record Key(String id, int rawHash) {
        @Override public int hashCode() { return rawHash; }
    }

    public static void main(String[] args) {
        Map<Key, String> map = new HashMap<>(4);
        Key a = new Key("A", 1);
        System.out.println("put A -> " + map.put(a, "a1"));
        System.out.println("put A' -> " + map.put(new Key("A", 1), "a2"));
        System.out.println("size after update -> " + map.size());
        map.put(new Key("B", 5), "b1");
        map.put(new Key("C", 9), "c1");
        map.put(new Key("D", 13), "d1");
        System.out.println("size after inserts -> " + map.size());
        for (Key key : new Key[]{a, new Key("B", 5), new Key("C", 9), new Key("D", 13)}) {
            System.out.println(key.id() + " -> " + map.get(key));
        }
    }
}
