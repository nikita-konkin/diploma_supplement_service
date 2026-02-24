package edu.university.xlsxpivot;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import org.takes.Request;
import org.takes.Response;
import org.takes.Take;
import org.takes.rq.RqHref;
import org.takes.rs.RsWithBody;
import org.takes.rs.RsWithStatus;
import org.takes.rs.RsWithType;

public final class TkImgs implements Take {
    @Override
    public Response act(final Request req) throws Exception {
        final String path = new RqHref.Base(req).href().path();
        // path is e.g. /imgs/favicon-32x32.png
        final InputStream in = this.getClass().getResourceAsStream(
            "/public" + path
        );
        if (in == null) {
            return new RsWithStatus(new RsWithBody("Image not found"), 404);
        }
        final ByteArrayOutputStream buf = new ByteArrayOutputStream();
        final byte[] tmp = new byte[8192];
        int read;
        while ((read = in.read(tmp)) != -1) {
            buf.write(tmp, 0, read);
        }
        in.close();
        return new RsWithType(
            new RsWithBody(buf.toByteArray()),
            "image/png"
        );
    }
}