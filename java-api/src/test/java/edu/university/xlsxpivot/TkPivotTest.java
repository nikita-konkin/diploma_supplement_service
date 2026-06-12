package edu.university.xlsxpivot;

import java.io.ByteArrayOutputStream;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import org.junit.Test;
import org.takes.Request;
import org.takes.rq.RqFake;
import org.takes.rs.RsPrint;

import static org.hamcrest.CoreMatchers.allOf;
import static org.hamcrest.CoreMatchers.containsString;
import static org.junit.Assert.assertThat;

public final class TkPivotTest {

    @Test
    public void cannotHidePivotServiceFailure() throws Exception {
        final PivotEngine engine = (scores, disciplines) -> {
            throw new DownstreamServiceException(422, "Scores sheet is malformed");
        };
        assertThat(
            "Pivot endpoint hid the Python validation failure",
            new RsPrint(new TkPivot(engine).act(TkPivotTest.request())).print(),
            allOf(
                containsString("HTTP/1.1 422"),
                containsString("\"error\":\"Scores sheet is malformed\"")
            )
        );
    }

    private static Request request() throws Exception {
        final String boundary = "angry-pivot-boundary";
        final ByteArrayOutputStream body = new ByteArrayOutputStream();
        TkPivotTest.file(body, boundary, "scores_xlsx");
        TkPivotTest.file(body, boundary, "disciplines_xlsx");
        body.write(("--" + boundary + "--\r\n").getBytes(StandardCharsets.UTF_8));
        return new RqFake(
            Arrays.asList(
                "POST /pivot HTTP/1.1",
                "Content-Type: multipart/form-data; boundary=" + boundary,
                "Content-Length: " + body.size()
            ),
            body.toByteArray()
        );
    }

    private static void file(
        final ByteArrayOutputStream body,
        final String boundary,
        final String name
    ) throws Exception {
        body.write((
            "--" + boundary + "\r\n"
                + "Content-Disposition: form-data; name=\"" + name
                + "\"; filename=\"file.xlsx\"\r\n"
                + "Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet\r\n\r\n"
                + "PK-test-content\r\n"
        ).getBytes(StandardCharsets.UTF_8));
    }
}
