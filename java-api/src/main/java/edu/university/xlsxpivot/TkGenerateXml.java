package edu.university.xlsxpivot;

import java.util.LinkedHashMap;
import java.util.Map;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.takes.Request;
import org.takes.Response;
import org.takes.Take;
import org.takes.rs.RsWithBody;
import org.takes.rs.RsWithType;

/**
 * Take that handles XML diploma generation requests.
 * Proxies requests to Python XML generation service.
 */
public final class TkGenerateXml implements Take {

    private static final Logger LOG = LoggerFactory.getLogger(TkGenerateXml.class);

    private static final int TIMEOUT_MS = 120000;

    private final XmlEngine engine;

    private final long limit;

    public TkGenerateXml() {
        this(
            new FormPost(
                Config.xmlApiBase() + Config.xmlGeneratePath(),
                "Python XML service",
                TIMEOUT_MS
            )::send
        );
    }

    TkGenerateXml(final XmlEngine engine) {
        this(engine, Config.maxUploadBytes());
    }

    TkGenerateXml(final XmlEngine engine, final long limit) {
        this.engine = engine;
        this.limit = limit;
    }

    @Override
    public Response act(final Request req) {
        LOG.info("Received XML generation request");
        try {
            final UploadForm form = new UploadForm(req, this.limit);
            final Map<String, Upload> files = new LinkedHashMap<>();
            files.put("pivot_table", form.file("pivot_table", "сводная таблица"));
            files.put("student_info", form.file("student_info", "сведения о студентах"));
            final byte[] result = this.engine.generate(files, form.params());
            LOG.info("XML generation completed with {} response bytes", result.length);
            return new RsWithType(new RsWithBody(result), "application/xml");
        } catch (final RejectedRequest err) {
            LOG.warn("Rejected XML request: {}", err.getMessage());
            return ApiResponse.error(err.status(), err.getMessage());
        } catch (final DownstreamServiceException err) {
            LOG.error(
                "XML service failed with HTTP {}: {}",
                err.status(),
                err.getMessage(),
                err
            );
            return ApiResponse.error(err.status(), err.getMessage());
        } catch (final Exception err) {
            LOG.error("XML generation request failed", err);
            return ApiResponse.error(500, "Не удалось сформировать XML: " + err.getMessage());
        }
    }
}
