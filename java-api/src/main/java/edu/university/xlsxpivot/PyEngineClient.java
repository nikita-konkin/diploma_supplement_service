package edu.university.xlsxpivot;

import java.io.IOException;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Client of the Python pivot engine.
 */
public final class PyEngineClient implements PivotEngine {

    private static final int TIMEOUT_MS = 300000;

    private final FormPost post;

    /**
     * Ctor.
     *
     * @param baseUrl Base URL of the Python engine (e.g., "http://localhost:8000")
     */
    public PyEngineClient(final String baseUrl) {
        this.post = new FormPost(baseUrl + "/pivot", "Python pivot service", TIMEOUT_MS);
    }

    @Override
    public byte[] processPivot(
        final Upload scores,
        final Upload disciplines,
        final Upload curriculum
    ) throws IOException {
        final Map<String, Upload> files = new LinkedHashMap<>();
        files.put("scores_xlsx", scores);
        files.put("disciplines_xlsx", disciplines);
        if (curriculum != null) {
            files.put("curriculum_xlsx", curriculum);
        }
        return this.post.send(files, Collections.emptyMap());
    }
}
