package edu.university.xlsxpivot;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.takes.Request;
import org.takes.Response;
import org.takes.Take;
import org.takes.rs.RsWithBody;
import org.takes.rs.RsWithType;

/**
 * Take that handles XLSX pivot processing requests.
 * Accepts multipart form data with two workbooks and returns a processed report.
 */
public final class TkPivot implements Take {

    private static final Logger LOG = LoggerFactory.getLogger(TkPivot.class);

    private final PivotEngine client;

    private final long limit;

    public TkPivot() {
        this(new PyEngineClient(Config.pivotEngineBase()));
    }

    public TkPivot(final PivotEngine client) {
        this(client, Config.maxUploadBytes());
    }

    TkPivot(final PivotEngine client, final long limit) {
        this.client = client;
        this.limit = limit;
    }

    @Override
    public Response act(final Request req) {
        LOG.info("Received pivot request");
        try {
            final UploadForm form = new UploadForm(req, this.limit);
            final byte[] result = this.client.processPivot(
                form.file("scores_xlsx", "ведомость с оценками"),
                form.file("disciplines_xlsx", "список дисциплин учебного плана")
            );
            LOG.info("Pivot request completed with {} response bytes", result.length);
            return new RsWithType(
                new RsWithBody(result),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            );
        } catch (final RejectedRequest err) {
            LOG.warn("Rejected pivot request: {}", err.getMessage());
            return ApiResponse.error(err.status(), err.getMessage());
        } catch (final DownstreamServiceException err) {
            LOG.error(
                "Pivot service failed with HTTP {}: {}",
                err.status(),
                err.getMessage(),
                err
            );
            return ApiResponse.error(err.status(), err.getMessage());
        } catch (final Exception err) {
            LOG.error("Pivot request failed", err);
            return ApiResponse.error(500, "Не удалось построить сводную таблицу: " + err.getMessage());
        }
    }
}
