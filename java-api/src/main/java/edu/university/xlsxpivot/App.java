package edu.university.xlsxpivot;

import java.io.File;
import org.takes.facets.fork.FkRegex;
import org.takes.facets.fork.TkFork;
import org.takes.http.Exit;
import org.takes.http.FtBasic;
import org.takes.tk.TkClasspath;
import org.takes.tk.TkFiles;
import org.takes.tk.TkWithType;

/**
 * Main application entry point.
 * Serves both the front-end HTML and API endpoints.
 */
public final class App {

    /**
     * Application entry point.
     *
     * @param args Command line arguments
     * @throws Exception If server fails to start
     */
    public static void main(final String... args) throws Exception {
        new FtBasic(
            new TkFork(
                // Front-end: Serve HTML upload page at root using a small Take
                new FkRegex("^/$", new TkIndex()),
                // Front-end: Serve HTML about pivot page at /about-pivot using a small Take
                new FkRegex("^/about-pivot", new TkPivotDescription()),
                // Static CSS files (root level)
                new FkRegex("^/styles\\.css$", new TkStyles()),
                // Static JavaScript files (root level)
                new FkRegex("^/script\\.js$", new TkScript()),
                // Static CSS files (in css directory)
                new FkRegex("/imgs/.+", new TkImgs()),
                new FkRegex(
                    "/css/.+",
                    new TkWithType(new TkClasspath(), "text/css; charset=UTF-8")
                ),
                new FkRegex(
                    "/js/.+",
                    new TkWithType(new TkClasspath(), "application/javascript; charset=UTF-8")
                ),
                // Static Font files (from file system)
                new FkRegex(
                    "/fonts/.+",
                    new TkWithType(
                        new TkFiles(new File("./resources/public")),
                        "font/otf"
                    )
                ),
                // API: Process XLSX files
                new FkRegex("/pivot", new TkPivot()),
                // XML generation proxy (forwards to python xml-engine)
                new FkRegex("/generate-xml", new TkGenerateXml()),
                // Runtime config for frontend
                new FkRegex("/config", new TkConfig()),
                // Health check endpoint
                new FkRegex("/health", new TkHealth())
            ),
            Config.apiPort()
        )
            .start(Exit.NEVER);
    }
}
