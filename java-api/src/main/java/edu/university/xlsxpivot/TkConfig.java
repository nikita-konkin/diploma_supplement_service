package edu.university.xlsxpivot;

import org.takes.Request;
import org.takes.Response;
import org.takes.Take;
import org.takes.rs.RsWithBody;
import org.takes.rs.RsWithType;

/**
 * Returns runtime config values useful to the front-end.
 */
public final class TkConfig implements Take {
    @Override
    public Response act(final Request req) throws Exception {
        final String json = String.format(
            "{\"API_BASE_URL\":\"%s\",\"XML_API_BASE_URL\":\"%s\",\"XML_GENERATE_PATH\":\"%s\",\"API_PIVOT_PATH\":\"%s\"}",
            Config.apiBase(), Config.xmlApiBase(), Config.xmlGeneratePath(), Config.apiPivotPath(), Config.pivotEngineBase()
        );
        return new RsWithType(new RsWithBody(json), "application/json");
    }
}
