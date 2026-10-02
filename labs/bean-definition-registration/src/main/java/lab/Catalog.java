package lab;

public final class Catalog {
    public static int constructions;
    public static int initializations;
    public static int destructions;
    private String label;

    public Catalog() { constructions++; }
    public void setLabel(String label) { this.label = label; }
    public String label() { return label; }
    public void init() { initializations++; }
    public void close() { destructions++; }

    public static void resetCounters() {
        constructions = 0;
        initializations = 0;
        destructions = 0;
    }
}
