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
            "{\"PIVOT_ENGINE_BASE_URL\":\"%s\",\"XML_API_BASE_URL\":\"%s\",\"XML_GENERATE_PATH\":\"%s\",\"PIVOT_API_PATH\":\"%s\"}",
            Config.pivotEngineBase(), Config.xmlApiBase(), Config.xmlGeneratePath(), Config.apiPivotPath()
        );
        return new RsWithType(new RsWithBody(json), "application/json");
    }
}
