package edu.university.xlsxpivot;

/**
 * Simple config helper to read environment variables with defaults.
 */
public final class Config {
    private Config() { }

    public static String get(final String name, final String def) {
        final String v = System.getenv(name);
        return (v == null || v.isEmpty()) ? def : v;
    }

    public static int getInt(final String name, final int def) {
        final String v = System.getenv(name);
        if (v == null || v.isEmpty()) return def;
        try {
            return Integer.parseInt(v);
        } catch (final Exception e) {
            return def;
        }
    }

    public static String apiBase() {
        return get("PIVOT_ENGINE_BASE_URL", "xn----etb9agicel");
        // return "xn----etb9agicel.xn--p1ai";
    }

    public static int apiPort() {
        return getInt("API_PORT", 8080);
    }

    public static String xmlApiBase() {
        return get("XML_API_BASE_URL", "xn----etb9agicel.xn--p1ai");
    }

    public static String xmlGeneratePath() {
        return get("XML_GENERATE_PATH", "/generate-xml");
    }

    public static String pivotEngineBase() {
        return get("PIVOT_ENGINE_BASE_URL", "xn----etb9agicel");
        // return "xn----etb9agicel.xn--p1ai";
    }

    public static String apiPivotPath() {
        return get("PIVOT_API_PATH", "/pivot");
    }
}
