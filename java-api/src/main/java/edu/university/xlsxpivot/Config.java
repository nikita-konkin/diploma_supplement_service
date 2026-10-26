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

    public static int apiPort() {
        return getInt("API_PORT", 8080);
    }

    public static String pivotEngineBase() {
        return get(
            "PYTHON_ENGINE_URL",
            get("PIVOT_ENGINE_BASE_URL", "http://python-engine:8000")
        );
    }

    public static String xmlApiBase() {
        return get(
            "XML_API_BASE_URL",
            get("PYTHON_XML_ENGINE_URL", "http://python-xml-engine:8001")
        );
    }

    public static String xmlGeneratePath() {
        return get("XML_GENERATE_PATH", "/generate-xml");
    }

    /**
     * Largest accepted upload request, bytes (MAX_UPLOAD_MB, 20 by default).
     */
    public static long maxUploadBytes() {
        return getInt("MAX_UPLOAD_MB", 20) * 1048576L;
    }
}
